"""Researched profile of the top-ranked customs brokers and freight forwarders.

Companies come from screen_forwarders.py, which ranks the 283 independent
tri-licence firms by inferred tenure. Everything below was then checked by
hand against company sites, trade press and PE announcements.

THREE FILTERS, EACH DOING A DIFFERENT JOB
    tenure     ranks the universe toward the established-independent profile
    headcount  sizes it, via ~$190K net revenue per employee (Transport Topics
               Top 100, n=45), so $5-30M EBITDA is roughly 88-528 employees
    ownership  qualifies it: family, independent, or sponsor-held

None of the three is sufficient alone. The top-ranked firm by tenure turned
out to be PE-owned, and the second-oldest firm in the whole set has 11 people.

    HEADCOUNT IS THE WEAK LINK. Figures come from third-party aggregators
    which disagree materially: Shapiro is quoted at 100, 156 and 214 by
    different sources, and Deringer's revenue is given as $147M, $188M and
    $750M. Treated as an order-of-magnitude band, never as a number. Anything
    close to a band edge needs a primary check before it is acted on.
"""

# rank, company, founded, headcount_low, headcount_high, ownership, evidence
PROFILED = [
    (1, "Horizon Air Freight", 1970, 61, 61, "SPONSOR",
     "Portfolio company of GHK Capital Partners, a Greenwich CT middle-market PE firm"),
    (5, "Samuel Shapiro & Co.", 1915, 100, 214, "FAMILY",
     "Third generation; Margie Shapiro leads, granddaughter of the 1915 founder"),
    (6, "John F. Kilroy Co.", 1932, None, None, "UNKNOWN",
     "Founded 1932 Rosedale NY; ownership not publicly disclosed"),
    (7, "C.H. Powell Company", 1919, 200, 200, "FAMILY",
     "Fourth generation; 18 US offices; co-founder and equity partner in the "
     "Tandem Global network, which is a network stake rather than a sale"),
    (9, "Hoyt Shepston & Sciaroni", 1850, 11, 11, "INDEPENDENT",
     "Trading since 1850, never closed except during the 1906 earthquake"),
    (12, "Western Overseas Corp.", 1948, 148, 200, "INDEPENDENT",
     "Founded San Pedro 1948; describes itself as independent; branch network at every major US gateway"),
    (14, "Rogers & Brown", 1968, 63, 100, "FAMILY",
     "Don Brown Sr. Chairman, Don 'Bo' Brown Jr. VP Sales -- second generation active"),
    (17, "Charles M. Schayer & Co.", 1946, 50, 50, "FAMILY",
     "Charles M. Schayer Jr. is principal; second generation"),
    (21, "Page & Jones", 1892, 56, 56, "INDEPENDENT",
     "Founded 1892; bought by three employees in the 1950s; privately held since; 12 offices"),
    (23, "R.L. Swearer Company", 1915, 22, 22, "INDEPENDENT",
     "Founded 1915; Chas Watson Jr. President"),
    (27, "A.N. Deringer", 1919, 500, 500, "PRIVATE",
     "The reference company. Founded 1919 St. Albans VT; privately held"),
    (28, "Carmichael International Service", 1961, 180, 183, "INDEPENDENT",
     "States it is full-service, independent and privately owned; led by Asim Faiz"),
]

# $5-30M EBITDA at 30% of net revenue and ~$190K net revenue per employee
NET_REV_PER_EMPLOYEE = 190_000
BAND_MIN_HEADCOUNT = round(16.7e6 / NET_REV_PER_EMPLOYEE)   # ~88
BAND_MAX_HEADCOUNT = round(100e6 / NET_REV_PER_EMPLOYEE)    # ~526


def implied_net_revenue(headcount):
    return headcount * NET_REV_PER_EMPLOYEE


def implied_ebitda(headcount):
    return implied_net_revenue(headcount) * 0.30


def in_band(row):
    _, _, _, lo, hi, _, _ = row
    if lo is None:
        return None
    return hi >= BAND_MIN_HEADCOUNT and lo <= BAND_MAX_HEADCOUNT


if __name__ == "__main__":
    print(f"Band on headcount: {BAND_MIN_HEADCOUNT} to {BAND_MAX_HEADCOUNT} employees")
    print(f"(that is $5-30M EBITDA at 30% of net revenue "
          f"and ${NET_REV_PER_EMPLOYEE:,}/head)\n")

    print(f"{'#':>3}  {'company':<34}{'est.':<7}{'headcount':<12}"
          f"{'implied EBITDA':<17}{'ownership'}")
    print("-" * 96)
    for row in PROFILED:
        rank, name, founded, lo, hi, own, _ = row
        hc = "n/a" if lo is None else (f"{lo}" if lo == hi else f"{lo}-{hi}")
        if lo is None:
            eb = "unknown"
        elif lo == hi:
            eb = f"~${implied_ebitda(lo)/1e6:.1f}M"
        else:
            eb = f"${implied_ebitda(lo)/1e6:.1f}-{implied_ebitda(hi)/1e6:.1f}M"
        band = in_band(row)
        mark = " <-- in band" if band else ("" if band is None else "  (outside)")
        print(f"{rank:>3}  {name:<34}{founded:<7}{hc:<12}{eb:<17}{own}{mark}")

    hits = [r for r in PROFILED if in_band(r) and r[5] in ("FAMILY", "INDEPENDENT", "PRIVATE")]
    print(f"\nIn band and not sponsor-held: {len(hits)}")
    for rank, name, founded, lo, hi, own, _ in hits:
        print(f"   #{rank:<3} {name:<34} founded {founded}, {own.lower()}")
