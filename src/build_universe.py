"""Phase 1: turn three raw registry dumps into one deduplicated company universe.

Run:  python src/build_universe.py

Output: data/processed/universe_pilot.csv  (one row per company)
        outputs/phase1_summary.txt         (counts, for the record)

What this does, in order:
  1. parse each registry, handling its own quirks (banner rows, note rows)
  2. optionally keep US-domiciled entities only
  3. collapse duplicate rows *within* a registry
       - CBP lists one row per PORT PERMIT, so a national broker appears many
         times; the permit count is itself a useful size signal, so it is kept
  4. merge *across* registries on the normalised company name, so a firm that
     is both a customs broker and an NVOCC becomes one row carrying both
  5. write the universe + a summary
"""
import csv
import sys
from collections import defaultdict

import config
from normalize import normalize_name, clean, clean_phone


def _read_rows(path, header_row):
    """Yield dict rows from a CSV whose real header is at `header_row`."""
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if header_row >= len(rows):
        return []
    header = [clean(h) for h in rows[header_row]]
    out = []
    for r in rows[header_row + 1:]:
        if not any(c.strip() for c in r):
            continue
        out.append({header[i]: (r[i] if i < len(r) else "") for i in range(len(header))})
    return out


def load_cbp():
    """CBP permitted customs brokers. One row per port permit."""
    rows = _read_rows(config.CBP_BROKERS_RAW, config.CBP_HEADER_ROW)
    recs = []
    for r in rows:
        name = clean(r.get("Permitted Broker Name", ""))
        if not name:
            continue
        recs.append({
            "name": name,
            "norm": normalize_name(name),
            "city": clean(r.get("City", "")),
            "state": clean(r.get("State", "")),
            "country": "UNITED STATES",
            "phone": clean_phone(r.get("Work Phone Number", "")),
            "email": clean(r.get("Email Address", "")),
            "filer_code": clean(r.get("Filer Code", "")),
        })
    return recs


def load_fmc(kind):
    """FMC OTI list: ocean freight forwarders or NVOCCs."""
    spec = config.FMC_PAGES[kind]
    rows = _read_rows(spec["raw"], spec["header_row"])
    recs = []
    for r in rows:
        # the FF export uses 'Name', the NVOCC export uses 'NAME'
        name = clean(r.get("Name", "") or r.get("NAME", ""))
        if not name:
            continue
        country = clean(r.get("Country", "")).upper()
        recs.append({
            "name": name,
            "norm": normalize_name(name),
            "city": clean(r.get("City", "")),
            "state": clean(r.get("State", "")),
            "country": country,
            "phone": clean_phone(r.get("Phone", "")),
            "email": "",
            "org_no": clean(r.get("Org. No.", "")),
            "lic_no": clean(r.get("Lic. No.", "")),
            "trade_names": clean(r.get("Trade Name(s)", "")),
        })
    return recs


def _in_scope(rec):
    """North America (US/CA/MX), or US-only if flipped."""
    country = rec.get("country", "").upper()
    if config.NORTH_AMERICA_ONLY:
        return country in config.NA_COUNTRY_VALUES
    return country in config.US_COUNTRY_VALUES


def build():
    cbp = load_cbp()
    ff = load_fmc("ocean_freight_forwarder")
    nv = load_fmc("nvocc")
    raw_counts = {"cbp_permits": len(cbp), "fmc_ff": len(ff), "fmc_nvocc": len(nv)}

    ff_us = [r for r in ff if _in_scope(r)]
    nv_us = [r for r in nv if _in_scope(r)]

    companies = {}          # norm -> merged record
    cbp_permits = defaultdict(int)

    def _touch(norm):
        if norm not in companies:
            companies[norm] = {
                "company_name": "", "city": "", "state": "", "country": "",
                "phone": "", "email": "", "sources": set(),
                "fmc_org_no": "", "cbp_filer_codes": set(),
                "fmc_trade_names": "",
            }
        return companies[norm]

    def _fill(dst, src, source_tag):
        dst["sources"].add(source_tag)
        if not dst["company_name"]:
            dst["company_name"] = src["name"]
        for f in ("city", "state", "country", "phone", "email"):
            if not dst.get(f) and src.get(f):
                dst[f] = src[f]

    for r in cbp:
        if not r["norm"]:
            continue
        c = _touch(r["norm"])
        _fill(c, r, "cbp_customs_broker")
        cbp_permits[r["norm"]] += 1
        if r["filer_code"]:
            c["cbp_filer_codes"].add(r["filer_code"])

    for tag, recs in (("fmc_ocean_freight_forwarder", ff_us), ("fmc_nvocc", nv_us)):
        for r in recs:
            if not r["norm"]:
                continue
            c = _touch(r["norm"])
            _fill(c, r, tag)
            if not c["fmc_org_no"] and r.get("org_no"):
                c["fmc_org_no"] = r["org_no"]
            tn = r.get("trade_names", "")
            if tn and tn.upper() != "N/A" and not c["fmc_trade_names"]:
                c["fmc_trade_names"] = tn

    rows = []
    for norm, c in companies.items():
        srcs = sorted(c["sources"])
        rows.append({
            "company_name": c["company_name"],
            "normalized_name": norm,
            "city": c["city"],
            "state": c["state"],
            "country": c["country"] or "UNITED STATES",
            "phone": c["phone"],
            "email": c["email"],
            "sources": "|".join(srcs),
            "n_sources": len(srcs),
            "cbp_permit_count": cbp_permits.get(norm, 0),
            "cbp_filer_codes": "|".join(sorted(c["cbp_filer_codes"])),
            "fmc_org_no": c["fmc_org_no"],
            "fmc_trade_names": c["fmc_trade_names"],
        })

    rows.sort(key=lambda r: (-r["n_sources"], -r["cbp_permit_count"],
                             r["normalized_name"]))

    fields = list(rows[0].keys()) if rows else []
    with open(config.UNIVERSE_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # ---- summary -----------------------------------------------------------
    multi = sum(1 for r in rows if r["n_sources"] > 1)
    by_source = defaultdict(int)
    for r in rows:
        for s in r["sources"].split("|"):
            by_source[s] += 1
    with_email = sum(1 for r in rows if r["email"])
    with_phone = sum(1 for r in rows if r["phone"])

    lines = [
        "Sourcing pipeline - Phase 1 (universe build)",
        "",
        "RAW REGISTRY ROWS",
        f"  CBP permitted broker permits      : {raw_counts['cbp_permits']:,}",
        f"  FMC ocean freight forwarders      : {raw_counts['fmc_ff']:,}",
        f"  FMC NVOCCs                        : {raw_counts['fmc_nvocc']:,}",
        "",
        f"GEOGRAPHY FILTER: {'North America (US/CA/MX)' if config.NORTH_AMERICA_ONLY else 'US only'}",
        f"  FMC ocean freight forwarders      : {len(ff_us):,}",
        f"  FMC NVOCCs                        : {len(nv_us):,}",
        "",
        "DEDUPLICATED UNIVERSE",
        f"  Distinct companies                : {len(rows):,}",
        f"  Appearing in >1 registry          : {multi:,}",
        "",
        "  by registry (post-dedup):",
    ]
    for s in sorted(by_source):
        lines.append(f"    {s:<34}: {by_source[s]:,}")
    lines += [
        "",
        "CONTACTABILITY",
        f"  with a phone number               : {with_phone:,}",
        f"  with an email address             : {with_email:,}",
        "",
        f"Output: {config.UNIVERSE_CSV}",
    ]
    summary = "\n".join(lines)
    config.SUMMARY_TXT.write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(build())
