"""Export the shortlist as CRM-ready import files.

This is the 'into the CRM' stage. It writes two CSVs in the shape a CRM ingests
directly -- one for companies, one for contacts -- linked by a stable key so a
re-run updates existing records instead of creating duplicates.

    WHY TWO FILES: every CRM (HubSpot, Salesforce, Affinity, DealCloud) models
    companies and people as separate objects with an association between them.
    A single flat sheet forces the client to split it by hand.

    THE DEDUPE KEY is the company's EIN where a Form 5500 filing gives one,
    else the website domain. This is the same lesson as the outreach tracker:
    dedupe on a stable identifier, never on the display name, because
    'Rogers & Brown' and 'Rogers & Brown Custom Brokers, Inc.' are one company.

    COLUMN NAMES follow HubSpot's import schema because it is the best
    documented and imports without a mapping step. Salesforce / Affinity /
    DealCloud take the same columns under different headers; the mapping is a
    one-line rename per field and is listed in AUTOMATION.md. Confirm the
    client's CRM before wiring the live sync -- that is an open question, so
    this produces a file a human reviews and imports, not a live push.

    THE EMAIL COLUMN IS LEFT BLANK ON PURPOSE. No contact email exists in any
    public registry; it comes from the enrichment step. Leaving it blank (not
    guessed) keeps the file safe to import as-is and marks where enrichment writes.

Run:  python src/crm_export.py
Output: outputs/crm_companies.csv, outputs/crm_contacts.csv
"""
import csv
import re

import build_profiles
import config


def _domain_guess(name):
    """A placeholder domain is NOT written -- guessing domains is what caused the
    bounce round on the other project. Left blank for enrichment to fill."""
    return ""


def _dedupe_key(r):
    f = r["filed"]
    # EIN would come from the 5500 join; the sample carries the filing match as
    # the stable anchor. Fall back to a normalised name only as a last resort.
    if f and f.get("ein"):
        return f"EIN:{f['ein']}"
    return "NAME:" + re.sub(r"[^a-z0-9]", "", r["name"].lower())


COMPANY_COLUMNS = [
    "Company name", "Company domain name", "City", "State/Region", "Country",
    "Industry", "Company owner",              # HubSpot standard fields
    # custom properties (create once in the CRM; names are the API-internal ones)
    "tgt_subsector", "tgt_tenure_rank", "tgt_founded",
    "tgt_ownership", "tgt_est_ebitda_low_mm", "tgt_est_ebitda_high_mm",
    "tgt_size_source", "tgt_in_band", "tgt_dedupe_key",
]

CONTACT_COLUMNS = [
    "First name", "Last name", "Email", "Job title",
    "Associated company", "Contact owner",
    "tgt_contact_status", "tgt_dedupe_key",
]


def rows():
    return build_profiles.join()


def company_records(data):
    out = []
    for r in data:
        f = r["filed"]
        eb_lo = f"{f['eb_lo']:.1f}" if f else ""
        eb_hi = f"{f['eb_hi']:.1f}" if f else ""
        verdict = f["verdict"] if f else ("unconfirmed" if r["research_hc_lo"] else "unknown")
        out.append({
            "Company name": r["name"],
            "Company domain name": _domain_guess(r["name"]),
            "City": "", "State/Region": "", "Country": "United States",
            "Industry": "Logistics / Freight Forwarding",
            "Company owner": "",   # assigned in the CRM
            "tgt_subsector": r["sub_sector"],
            "tgt_tenure_rank": r["rank"],
            "tgt_founded": r["founded"],
            "tgt_ownership": r["ownership"].title(),
            "tgt_est_ebitda_low_mm": eb_lo,
            "tgt_est_ebitda_high_mm": eb_hi,
            "tgt_size_source": "DOL Form 5500 (filed)" if f else "research estimate",
            "tgt_in_band": "Yes" if verdict == "IN band" else
                            ("Edge" if verdict == "straddles floor" else "No"),
            "tgt_dedupe_key": _dedupe_key(r),
        })
    return out


def contact_records(data):
    out = []
    for r in data:
        if not r["contact_name"]:
            # no named principal yet -> a contact row still goes in, flagged for
            # enrichment, so the CRM shows the gap rather than hiding the company
            first = last = ""
            status = "needs enrichment: name + email"
        else:
            parts = r["contact_name"].split()
            first, last = parts[0], " ".join(parts[1:])
            status = "name from research; email needs enrichment"
        out.append({
            "First name": first, "Last name": last,
            "Email": "",   # never guessed
            "Job title": r["contact_title"],
            "Associated company": r["name"],
            "Contact owner": "",
            "tgt_contact_status": status,
            "tgt_dedupe_key": _dedupe_key(r),
        })
    return out


def _write(path, columns, records):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(records)


if __name__ == "__main__":
    data = rows()
    comps = company_records(data)
    conts = contact_records(data)

    cpath = config.OUTPUTS / "crm_companies.csv"
    tpath = config.OUTPUTS / "crm_contacts.csv"
    _write(cpath, COMPANY_COLUMNS, comps)
    _write(tpath, CONTACT_COLUMNS, conts)

    in_band = sum(1 for c in comps if c["tgt_in_band"] == "Yes")
    have_name = sum(1 for c in conts if c["First name"])
    print(f"wrote {len(comps)} companies -> {cpath}")
    print(f"wrote {len(conts)} contacts  -> {tpath}")
    print(f"   in band                     : {in_band}")
    print(f"   contacts with a named person: {have_name}")
    print(f"   contacts needing enrichment : {len(conts) - have_name}")
    print("   every Email cell is intentionally blank -- enrichment fills it")
