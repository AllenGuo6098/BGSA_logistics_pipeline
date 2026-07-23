"""One command, source -> CRM-ready output. The entry point n8n calls.

Chains the stages that are built today. The source/dedupe/score stages
(build_universe, screen_forwarders) already produce the scored shortlist that
forwarders.py and size_from_filings.py draw on; this driver runs the two stages
added in the vertical slice -- profiles and CRM export -- and prints where each
artifact landed.

    Kept stdlib-only and import-driven (not shelling out) so it runs cold on a
    clean Python install, which is the whole point of handing it to someone else.

Run:  python src/run_pipeline.py
"""
import sys

import build_profiles
import crm_export
import config


def main():
    print("Logistics sourcing pipeline")
    print("=" * 60)

    # ---- profile stage -------------------------------------------------
    rows = build_profiles.join()
    order = {"IN band": 0, "straddles floor": 1}

    def sort_key(r):
        v = r["filed"]["verdict"] if r["filed"] else "zzz"
        ctrl = 9 if "Deringer" in r["name"] else 0
        return (ctrl, order.get(v, 5), r["rank"])

    rows.sort(key=sort_key)
    import datetime
    body = "\n".join(build_profiles.profile_html(r) for r in rows)
    prof = config.OUTPUTS / "target_profiles.html"
    prof.write_text(
        build_profiles.PAGE.format(date=datetime.date.today().isoformat(), body=body),
        encoding="utf-8")
    in_band = [r for r in rows if r["filed"] and r["filed"]["verdict"] == "IN band"]
    print(f"  profiles   : {len(rows)} written, {len(in_band)} in band  -> {prof.name}")

    # ---- CRM export stage ----------------------------------------------
    data = crm_export.rows()
    comps = crm_export.company_records(data)
    conts = crm_export.contact_records(data)
    cpath = config.OUTPUTS / "crm_companies.csv"
    tpath = config.OUTPUTS / "crm_contacts.csv"
    crm_export._write(cpath, crm_export.COMPANY_COLUMNS, comps)
    crm_export._write(tpath, crm_export.CONTACT_COLUMNS, conts)
    named = sum(1 for c in conts if c["First name"])
    print(f"  CRM export : {len(comps)} companies, {len(conts)} contacts "
          f"({named} named, {len(conts) - named} need enrichment)")
    print(f"               -> {cpath.name}, {tpath.name}")

    print("\nnext stages (need client input, see AUTOMATION.md):")
    print("  enrich  -> contact email     (Apollo/ZoomInfo seat)")
    print("  sync    -> live CRM upsert    (which CRM?)")
    print("  outreach-> gated mail drafts  (mail system + do-not-contact list)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
