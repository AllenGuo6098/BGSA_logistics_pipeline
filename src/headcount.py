"""Real headcount for the forwarder candidates, from DOL Form 5500 filings.

The open problem left by the last pass was that every headcount came from
third-party aggregators and they disagreed badly -- Samuel Shapiro was quoted at
100, 156 and 214 by three different sources, and Deringer's revenue at $147M,
$188M and $750M. Sizing the band on numbers like that is guesswork, and the
band edge is exactly where the decision gets made.

Form 5500 is a different kind of number. Any employer sponsoring a 401(k) or a
welfare plan files one annually with the Department of Labor, under penalty of
perjury, and the filing states how many people are in the plan. It is a primary
document rather than a scrape.

    WHAT THE NUMBER IS: 'active participants' counts employees enrolled in the
    plan, not employees. Eligibility waiting periods, part-timers and staff who
    decline all sit outside it, so it runs BELOW true headcount -- typically by
    10-30% for a 401(k) with auto-enrolment, and by more without it. Treat it
    as a floor and a consistency check, never as an exact census.

    WHAT IT MISSES: a firm with no plan, or a plan under 100 participants filing
    the short 5500-SF, may not appear in this dataset at all. Absence is not
    evidence of a small company.

Source: https://askebsa.dol.gov/FOIA%20Files/{year}/Latest/F_5500_{year}_Latest.zip

Run:  python src/headcount.py [--year 2024]
"""
import csv
import os
import re
import sys

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")

# NAICS codes the Form 5500 'BUSINESS_CODE' field uses for this sector.
FREIGHT_NAICS = {
    "488510",   # freight transportation arrangement -- forwarders and brokers
    "488500",
    "488990",   # other support activities for transportation
    "492110",   # couriers
    "493110",   # warehousing
    "484121", "484122", "484110",  # trucking, for the asset-based check
}

# The shortlisted firms, plus the two the tenure ranking got wrong.
#
# Each carries the state it operates from. A name fragment alone is not enough:
# 'shapiro' pulls in a Chicago foreclosure law firm and a Maryland mechanical
# contractor, both far bigger than the forwarder and neither remotely relevant.
# A match must also sit in the right state or carry a freight NAICS code.
TARGETS = [
    ("Samuel Shapiro & Co (Baltimore MD, 1915)", ["samuel shapiro", "shapiro co"], "MD"),
    ("C.H. Powell (Canton MA, 1919)", ["c h powell", "ch powell"], "MA"),
    ("Carmichael International Service (Los Angeles CA, 1961)",
     ["carmichael international", "carmichael intl"], "CA"),
    ("Western Overseas (Cypress CA, 1948)", ["western overseas"], "CA"),
    ("Rogers & Brown (Charleston SC, 1868)", ["rogers brown"], "SC"),
    ("A.N. Deringer (St Albans VT, 1919) -- control", ["deringer"], "VT"),
    ("Horizon Air Freight -- GHK Capital portfolio company",
     ["horizon air freight"], "NY"),
    ("Hoyt Shepston (1850) -- ranked 2nd on tenure", ["hoyt shepston"], "CA"),
]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def rows_for_year(year):
    path = os.path.join(RAW, f"f5500_{year}.csv")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            yield row


def as_int(v):
    try:
        return int(float(str(v).strip() or 0))
    except (TypeError, ValueError):
        return 0


def sf_rows_for_year(year):
    """Form 5500-SF: the short form, filed by plans with fewer than 100
    participants. A firm that appears ONLY here has a small plan, which is a
    real signal about its size."""
    path = os.path.join(RAW, f"f5500sf_{year}.csv")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            yield row


def _match(name, state, naics, frags, want_state):
    if not any(f in name for f in frags):
        return False
    # a name hit still has to be the right company
    return state == want_state or naics in FREIGHT_NAICS


def find_targets(years=(2024, 2023, 2022)):
    """Every filing that is plausibly one of the target firms, from both the
    full Form 5500 and the short-form 5500-SF."""
    hits = {}
    for year in years:
        for row in rows_for_year(year):
            name = norm(row.get("SPONSOR_DFE_NAME"))
            if not name:
                continue
            state = row.get("SPONS_DFE_MAIL_US_STATE", "").strip().upper()
            naics = row.get("BUSINESS_CODE", "").strip()
            for label, frags, want_state in TARGETS:
                if _match(name, state, naics, frags, want_state):
                    hits.setdefault(label, []).append({
                        "form": "5500", "year": year,
                        "sponsor": row.get("SPONSOR_DFE_NAME", "").strip(),
                        "plan": row.get("PLAN_NAME", "").strip(),
                        "city": row.get("SPONS_DFE_MAIL_US_CITY", "").strip(),
                        "state": state, "naics": naics,
                        "active": as_int(row.get("TOT_ACTIVE_PARTCP_CNT")),
                        "total": as_int(row.get("TOT_PARTCP_BOY_CNT")),
                    })
                    break
        for row in sf_rows_for_year(year):
            name = norm(row.get("SF_SPONSOR_NAME"))
            if not name:
                continue
            state = row.get("SF_SPONS_US_STATE", "").strip().upper()
            naics = row.get("SF_BUSINESS_CODE", "").strip()
            for label, frags, want_state in TARGETS:
                if _match(name, state, naics, frags, want_state):
                    hits.setdefault(label, []).append({
                        "form": "5500-SF", "year": year,
                        "sponsor": row.get("SF_SPONSOR_NAME", "").strip(),
                        "plan": row.get("SF_PLAN_NAME", "").strip(),
                        "city": row.get("SF_SPONS_US_CITY", "").strip(),
                        "state": state, "naics": naics,
                        "active": as_int(row.get("SF_TOT_ACT_PARTCP_EOY_CNT"))
                                  or as_int(row.get("SF_TOT_ACT_PARTCP_BOY_CNT")),
                        "total": as_int(row.get("SF_TOT_PARTCP_BOY_CNT")),
                    })
                    break
    return hits


def sector_population(year=2024):
    """All freight-sector filings, so a candidate can be placed in a distribution
    rather than judged against a number in isolation."""
    out = []
    for row in rows_for_year(year):
        if row.get("BUSINESS_CODE", "").strip() not in FREIGHT_NAICS:
            continue
        active = as_int(row.get("TOT_ACTIVE_PARTCP_CNT"))
        if active <= 0:
            continue
        out.append((active, row.get("SPONSOR_DFE_NAME", "").strip(),
                    row.get("SPONS_DFE_MAIL_US_STATE", "").strip()))
    return out


if __name__ == "__main__":
    year = 2024
    if "--year" in sys.argv:
        year = int(sys.argv[sys.argv.index("--year") + 1])

    hits = find_targets()
    print("FORM 5500 FILINGS FOR THE CANDIDATE FIRMS")
    print("=" * 100)
    for label, _, _ in TARGETS:
        recs = hits.get(label, [])
        print(f"\n{label}")
        if not recs:
            print("   NO FILING in either the full 5500 or the 5500-SF.")
            print("   Means no plan at all, or a plan too small to file, or a "
                  "different legal entity name. Not evidence of headcount.")
            continue
        recs.sort(key=lambda r: (-r["year"], -r["active"]))
        for r in recs[:8]:
            print(f"   {r['year']} {r['form']:<8} active {r['active']:>6,}  "
                  f"total {r['total']:>6,}  naics {r['naics']:<8}"
                  f"{r['city'][:16]:<18}{r['state']:<4}{r['sponsor'][:34]}")
            print(f"         plan: {r['plan'][:80]}")

    pop = sector_population(year)
    if pop:
        pop.sort(reverse=True)
        n = len(pop)
        print(f"\n\nFREIGHT-SECTOR FILERS, {year}: {n:,} plans with an active count")
        for pct in (0.5, 0.75, 0.9, 0.95, 0.99):
            idx = int(n * (1 - pct))
            print(f"   {pct:>5.0%} percentile  {pop[idx][0]:>7,} active participants")
