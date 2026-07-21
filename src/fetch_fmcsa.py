"""Pull asset-light FMCSA registrants -- the truck brokerage / freight
management leg.

The honest caveat, up front: this does NOT filter on broker authority,
because FMCSA does not publish authority type in bulk (see config.py).
What it filters on is *owning no equipment* -- an active USDOT registrant
reporting zero power units and zero drivers is arranging freight rather
than hauling it, which is the economic property we actually care about.

RESULT: the proxy does not hold up. Keeping the code and the
finding rather than deleting it, because the negative result is the useful
part -- it says where truck brokerage has to come from instead.

    8,845  active N.A. registrants with 0 power units and 0 drivers
    3,295  after requiring AUTHORIZED FOR HIRE
    3,274  after dropping passenger operations
        2  after requiring a real business entity

Why it fails:
  - 41% of the pool is classed PRIVATE PASSENGER, NON-BUSINESS -- these
    are individuals, not firms. Sample names are literally personal names.
  - business_org_desc is essentially unpopulated, so there is no reliable
    way to separate a company from a person.
  - equipment counts are self-reported on the MCS-150 and go stale. The
    single longest-tenured survivor is "JB TRUCKING CO INC" -- a trucking
    company reporting zero trucks, which tells you what the field is worth.
  - 92% of the pool registered since 2020 and 30% in 2025 alone, so it
    skews to brand-new registrations rather than established brokerages.

Where truck brokerage should come from instead (in preference order):
  1. TIA (Transportation Intermediaries Association) -- ~1,600 member
     companies whose principal business is arranging freight. Membership
     is itself a quality screen. Directory is behind a login wall, so it
     needs a member credential or a data request, not a scrape.
  2. FMCSA L&I per-record lookup at li-public.fmcsa.dot.gov -- carries the
     real BROKER authority flag. Query-only, so it works to CONFIRM a
     candidate list but cannot generate one.
  3. A paid feed (Carrier411 / RMIS / Highway / DAT) for coverage
     rather than a curated shortlist.

Run:  python src/fetch_fmcsa.py [--limit N]
"""
import csv
import gzip
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import config

FIELDS = [
    "dot_number", "legal_name", "dba_name", "status_code",
    "phy_street", "phy_city", "phy_state", "phy_zip", "phy_country",
    "phone", "email_address",
    "power_units", "truck_units", "total_drivers",
    "add_date", "mcs150_date", "mcs150_mileage", "mcs150_mileage_year",
    "carrier_operation", "classdef", "business_org_desc",
]

# Active registrant, owns no trucks, employs no drivers, North American.
#
# NOTE: power_units / total_drivers are typed TEXT in Socrata, not number, so
# these have to be string comparisons -- `power_units = 0` throws a type
# mismatch. Blank is treated as unknown and excluded rather than assumed zero;
# a registrant who never filed equipment counts is not evidence of asset-light.
WHERE = (
    "status_code = 'A' "
    "AND power_units = '0' "
    "AND total_drivers = '0' "
    "AND phy_country in ('US', 'CA', 'MX')"
)


def _get(params):
    url = config.FMCSA_SODA_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": config.USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def count():
    r = _get({"$select": "count(1)", "$where": WHERE})
    return int(r[0].get("count_1") or r[0].get("count"))


def fetch(limit=None):
    total = count()
    target = min(total, limit) if limit else total
    print(f"asset-light active N.A. registrants: {total:,}")
    print(f"fetching {target:,} in pages of {config.FMCSA_PAGE_SIZE:,}...")

    rows, offset = [], 0
    while len(rows) < target:
        page = _get({
            "$select": ",".join(FIELDS),
            "$where": WHERE,
            "$order": "dot_number",
            "$limit": min(config.FMCSA_PAGE_SIZE, target - len(rows)),
            "$offset": offset,
        })
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        print(f"   {len(rows):,}/{target:,}")

    with open(config.FMCSA_RAW, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"wrote {len(rows):,} rows -> {config.FMCSA_RAW}")
    return rows


FREE_MAIL = ("gmail.", "aol.", "hotmail.", "yahoo.", "outlook.",
             "icloud.", "msn.", "comcast.")


def profile():
    """Reproduce the tightening cascade documented in the module docstring.

    Run this after fetch() to re-check the finding against fresh data --
    if FMCSA ever populates business_org_desc, the conclusion changes.
    """
    with open(config.FMCSA_RAW, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    steps = [("active, 0 units, 0 drivers, N.A.", rows)]
    s = [r for r in rows if "AUTHORIZED FOR HIRE" in (r["classdef"] or "")]
    steps.append(("+ AUTHORIZED FOR HIRE", s))
    s = [r for r in s if "PASSENGER" not in (r["classdef"] or "")]
    steps.append(("+ not passenger ops", s))
    s = [r for r in s if (r["business_org_desc"] or "").upper()
         in ("CORPORATION", "LLC", "LIMITED LIABILITY COMPANY", "PARTNERSHIP")]
    steps.append(("+ real business entity", s))
    s = [r for r in s if r["add_date"][:4].isdigit() and int(r["add_date"][:4]) <= 2016]
    steps.append(("+ registered 10+ yrs", s))
    s = [r for r in s if r["email_address"]
         and not any(f in r["email_address"].lower() for f in FREE_MAIL)]
    steps.append(("+ corporate email", s))

    for label, rs in steps:
        print(f"   {label:<36} {len(rs):>6,}")
    print("\n   survivors:")
    for r in sorted(s, key=lambda r: r["add_date"]):
        print(f"     {r['add_date'][:4]}  {r['legal_name'][:44]:<46} {r['phy_state']}")
    return s


if __name__ == "__main__":
    if "--profile" in sys.argv:
        profile()
        sys.exit(0)
    lim = None
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    try:
        fetch(lim)
    except urllib.error.HTTPError as e:
        print(f"FMCSA fetch failed: HTTP {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
