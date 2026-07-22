"""Size the candidates off filed participant counts instead of aggregator data.

This replaces the weakest input in the last pass. Headcount previously came
from third-party aggregators that disagreed by 2x on the same company; here it
comes from each firm's own Form 5500, filed annually with the Department of
Labor.

The cascade is unchanged from sizing.py, so the two passes are comparable:
    net revenue per head   $190K
    EBITDA                 30% of net revenue
    => EBITDA per head     $57K
    => the $5-30M target band   88 to 526 people

Two things to keep straight when reading the output:

  1. Participant counts sit BELOW headcount. Employees in a waiting period, part
     timers, and anyone who declines the plan are all excluded. So every EBITDA
     figure here is a FLOOR, not a midpoint. Where a firm files both a 401(k)
     and a health plan I show the range between them, because health plans
     usually capture more of the workforce.

  2. $190K of net revenue per head is a sector average applied to specific
     companies. A customs brokerage doing high-volume entry filing carries more
     people per dollar than a forwarder arranging large freight moves, so the
     brokers in this list are more likely to be overstated than understated.

Run:  python src/size_from_filings.py
"""
import sizing

NET_REV_PER_HEAD_USD = 190_000
BAND_LOW_EBITDA_MM = 5
BAND_HIGH_EBITDA_MM = 30

# From src/headcount.py against DOL Form 5500 / 5500-SF, filing years 2022-2024.
# (firm, founded, 2024 low headcount, 2024 high headcount, source, note)
FILED = [
    ("A.N. Deringer", 1919, 530, 532, "401(k) 530 active / health plan 532 active",
     "control, not a candidate"),
    ("C.H. Powell", 1919, 156, 203, "401(k) 156 active, 203 total",
     "active count fell 174 -> 161 -> 156 across 2022-24"),
    ("Samuel Shapiro & Co", 1915, 136, 185, "profit sharing 136 active, 185 total; "
     "welfare plan 103 active", "aggregators said 100 / 156 / 214"),
    ("Rogers & Brown", 1868, 125, 155, "401(k) 125 active, 155 total",
     "flat across all three years"),
    ("Horizon Air Freight", None, 66, 70, "5500-SF 66 active, 70 total",
     "GHK Capital portfolio company; below the band on size as well"),
    ("Hoyt Shepston", 1850, 18, 20, "5500-SF 18 active, 20 total",
     "I estimated ~11 last time from a headcount page"),
]

# Firms that file nothing findable. Absence is not a size measurement.
NO_FILING = [
    ("Carmichael International Service", 1961, "Los Angeles CA"),
    ("Western Overseas", 1948, "Cypress CA"),
]


def band_people():
    """The $5-30M EBITDA band expressed in people."""
    per_head_ebitda = NET_REV_PER_HEAD_USD * sizing.EBITDA_PCT_OF_NET_REV
    return (BAND_LOW_EBITDA_MM * 1e6 / per_head_ebitda,
            BAND_HIGH_EBITDA_MM * 1e6 / per_head_ebitda)


def implied(heads):
    net_rev = heads * NET_REV_PER_HEAD_USD
    return net_rev / 1e6, sizing.ebitda(net_rev) / 1e6


def verdict(lo_eb, hi_eb):
    if hi_eb < BAND_LOW_EBITDA_MM:
        return "BELOW band"
    if lo_eb > BAND_HIGH_EBITDA_MM:
        return "ABOVE band"
    if lo_eb < BAND_LOW_EBITDA_MM <= hi_eb:
        return "straddles floor"
    return "IN band"


if __name__ == "__main__":
    lo_p, hi_p = band_people()
    print("SIZING FROM FILED PARTICIPANT COUNTS (DOL Form 5500, 2024 filings)")
    print("=" * 104)
    print(f"cascade: ${NET_REV_PER_HEAD_USD:,}/head net revenue, "
          f"EBITDA {sizing.EBITDA_PCT_OF_NET_REV:.0%} of net revenue")
    print(f"Target ${BAND_LOW_EBITDA_MM}-{BAND_HIGH_EBITDA_MM}M band "
          f"= {lo_p:.0f} to {hi_p:.0f} people\n")
    print(f"{'firm':<26}{'est':>4}{'people':>11}{'net rev $M':>14}"
          f"{'EBITDA $M':>14}  verdict")
    print("-" * 104)
    for name, founded, lo, hi, src, note in FILED:
        lo_nr, lo_eb = implied(lo)
        hi_nr, hi_eb = implied(hi)
        v = verdict(lo_eb, hi_eb)
        yr = str(founded) if founded else "-"
        print(f"{name:<26}{yr:>5}{lo:>5}-{hi:<5}{lo_nr:>7.1f}-{hi_nr:<6.1f}"
              f"{lo_eb:>7.1f}-{hi_eb:<6.1f}  {v}")
        print(f"      filed: {src}")
        if note:
            print(f"      note:  {note}")
    print()
    for name, founded, where in NO_FILING:
        print(f"{name:<26}{founded:>5}  {where:<18}no Form 5500 found - size still unknown")

    print("\n" + "=" * 104)
    d_lo, d_hi = implied(530)[1], implied(532)[1]
    print(f"Control check: Deringer's filings imply ${d_lo:.1f}-{d_hi:.1f}M EBITDA.")
    print("The tenure-plus-headcount pass last week put it at about $28M from a")
    print("different route entirely. Two independent methods landing in the same")
    print("place is the main reason I trust the band edges now.")
