"""Rank the customs broker / freight forwarder universe toward the Deringer profile.

The problem this solves: the registries carry no size signal at all. CBP permit
count maxes out at 2, and 299 of the 301 tri-licence firms hold exactly one
filer code. Both were tested and dropped. So ranking has to come from somewhere
else.

The signal used here is TENURE, inferred from the FMC organisation number.
Those appear to be issued sequentially, so a low number means an early
registration. Spot-checking supports it: the lowest numbers are firms like
M.E. Dey (Milwaukee, founded 1907), Cartwright International Van Lines and
Leschaco, while the highest are recently formed LLCs with generic names.
A.N. Deringer sits at 4,899 in a 374-35,639 range, the bottom 13%.

    KNOWN LIMITATION: the number tracks the REGISTRATION, not the founding.
    Laufer Group, established 1948, carries org no. 35,584 -- almost certainly
    a re-registration under a new entity. So a high number does not prove a
    firm is young, though a low number is decent evidence it is old. Treat
    this as a ranking heuristic, not a fact about any single company.

Why tenure: a firm that has held all three licences and survived since the
1970s or 80s is, by construction, an independent that made it through several
freight cycles without being rolled up. That is the profile worth calling.

Run:  python src/screen_forwarders.py [--top N]
"""
import csv
import sys

import config

# Global majors, public companies and subsidiaries of them. Registries make no
# distinction between an independent and a subsidiary, so this has to be an
# explicit list. Matched case-insensitively against the normalised name.
EXCLUDE_FRAGMENTS = [
    "FEDEX", "DHL", "KUEHNE", "EXPEDITORS", "DSV", "NIPPON EXPRESS",
    "KINTETSU", "UPS ", "UNITED PARCEL", "C H ROBINSON", "CH ROBINSON",
    "GEODIS", "SCHENKER", "PANALPINA", "AGILITY", "YUSEN", "HELLMANN",
    "CEVA", "BOLLORE", "SINOTRANS", "MAERSK", "KERRY LOGISTICS",
    "AMAZON", "MATSON", "PENSKE", "RADIANT LOGISTICS", "FORWARD AIR",
    "XPO", "RXO", "GXO", "HUB GROUP", "LANDSTAR", "ECHO GLOBAL",
    "TOTAL QUALITY LOGISTICS", "WORLDWIDE EXPRESS", "SEKO", "CRANE WORLDWIDE",
    "FLEXPORT", "OIA GLOBAL", "RHENUS", "DACHSER", "CMA CGM", "COSCO",
    "MSC ", "EVERGREEN", "HAPAG", "ONE LINE", "SF EXPRESS", "JD LOGISTICS",
    "SAMSUNG", "LG ", "PANTOS", "GLOVIS", "TOLL GLOBAL", "DB GROUP",
]


def load_universe():
    with open(config.UNIVERSE_CSV, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def is_excluded(row):
    n = row["normalized_name"].upper()
    return any(frag in n for frag in EXCLUDE_FRAGMENTS)


def screen(min_sources=3, top=None):
    rows = load_universe()
    stages = [("universe", len(rows))]

    multi = [r for r in rows if int(r["n_sources"]) >= min_sources]
    stages.append((f"holding {min_sources}+ licences", len(multi)))

    kept = [r for r in multi if not is_excluded(r)]
    stages.append(("after removing global majors", len(kept)))

    priced = [r for r in kept if r["fmc_org_no"].strip().isdigit()]
    stages.append(("with an FMC org number", len(priced)))

    for r in priced:
        r["_org"] = int(r["fmc_org_no"])
    priced.sort(key=lambda r: r["_org"])

    # percentile against the whole forwarder population, not just this subset
    all_orgs = sorted(int(r["fmc_org_no"]) for r in rows
                      if r["fmc_org_no"].strip().isdigit())
    for r in priced:
        below = sum(1 for o in all_orgs if o < r["_org"])
        r["_pct"] = below / len(all_orgs)

    return (priced[:top] if top else priced), stages


if __name__ == "__main__":
    n = None
    if "--top" in sys.argv:
        n = int(sys.argv[sys.argv.index("--top") + 1])
    ranked, stages = screen(top=n or 30)

    for label, count in stages:
        print(f"   {label:<34} {count:>6,}")
    print()
    print("Ranked by inferred tenure (lowest FMC org number = earliest registration)")
    print("-" * 92)
    print(f"{'#':<4}{'org no':>7}{'pct':>7}  {'company':<44}{'city':<18}{'st':<4}")
    print("-" * 92)
    for i, r in enumerate(ranked, 1):
        print(f"{i:<4}{r['_org']:>7}{r['_pct']:>6.0%}  "
              f"{r['company_name'][:42]:<44}{r['city'][:16]:<18}{r['state']:<4}")
