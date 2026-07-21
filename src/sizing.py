"""Revenue -> net revenue -> EBITDA cascade for freight forwarders.

Industry rule of thumb:
    net revenue  = 25% of gross revenue
    EBITDA       = 30% of net revenue
    => EBITDA    = 7.5% of gross revenue

I wanted to know how conservative that is before screening on it, so I pulled
Expeditors' (EXPD) actual reported figures from SEC XBRL rather than a data
vendor. Everything in EXPD_ACTUALS below is straight off the 10-K tags:

    gross revenue  us-gaap:Revenues / RevenueFromContractWithCustomer...
    net revenue    gross - us-gaap:DirectOperatingCosts
                   ("directly related cost of transportation and other expenses")
    EBITDA         us-gaap:OperatingIncomeLoss
                   + us-gaap:DepreciationDepletionAndAmortization

Source: https://data.sec.gov/api/xbrl/companyfacts/CIK0000746515.json
"""

# (fiscal_year, gross_rev_usd_mm, net_rev_usd_mm, ebitda_usd_mm)
EXPD_ACTUALS = [
    (2020,  9_584,  2_928,   997),
    (2021, 16_524,  4_465, 1_961),
    (2022, 17_071,  4_494, 1_882),
    (2023,  9_300,  3_246, 1_008),
    (2024, 10_601,  3_414, 1_102),
    (2025, 11_069,  3_667, 1_109),
]

# Defaults everything screens on.
NET_REV_PCT_OF_GROSS = 0.25
EBITDA_PCT_OF_NET_REV = 0.30


def net_revenue(gross_revenue, ratio=NET_REV_PCT_OF_GROSS):
    """Gross (billed) revenue -> net revenue / gross margin."""
    return gross_revenue * ratio


def ebitda(net_rev, ratio=EBITDA_PCT_OF_NET_REV):
    """Net revenue -> EBITDA. 'Profit' means EBITDA here."""
    return net_rev * ratio


def ebitda_from_gross(gross_revenue,
                      nr_ratio=NET_REV_PCT_OF_GROSS,
                      ebitda_ratio=EBITDA_PCT_OF_NET_REV):
    """Full cascade. Default 25% x 30% = 7.5% of gross."""
    return ebitda(net_revenue(gross_revenue, nr_ratio), ebitda_ratio)


def gross_revenue_for_ebitda(target_ebitda,
                             nr_ratio=NET_REV_PCT_OF_GROSS,
                             ebitda_ratio=EBITDA_PCT_OF_NET_REV):
    """Inverse: what does a target hit as a billed-revenue screen?

    This is the one that matters operationally -- registries and data
    vendors report gross revenue, so an EBITDA threshold has to be
    translated back into gross before it can filter anything.
    """
    return target_ebitda / (nr_ratio * ebitda_ratio)


def calibration():
    """The rule-of-thumb ratios vs EXPD actuals, year by year."""
    rows = []
    for fy, gross, net, eb in EXPD_ACTUALS:
        rows.append({
            "fy": fy,
            "gross_mm": gross,
            "net_mm": net,
            "net_pct_of_gross": net / gross,
            "ebitda_mm": eb,
            "ebitda_pct_of_net": eb / net,
            "ebitda_pct_of_gross": eb / gross,
        })
    return rows


def _mean(xs):
    return sum(xs) / len(xs)


if __name__ == "__main__":
    rows = calibration()
    print("EXPD actuals (SEC XBRL) vs the rule of thumb")
    print("-" * 68)
    print(f"{'FY':<6}{'gross':>9}{'net rev':>9}{'NR/GR':>8}{'EBITDA':>9}{'EB/NR':>8}{'EB/GR':>8}")
    for r in rows:
        print(f"{r['fy']:<6}{r['gross_mm']:>8,}M{r['net_mm']:>8,}M"
              f"{r['net_pct_of_gross']:>8.1%}{r['ebitda_mm']:>8,}M"
              f"{r['ebitda_pct_of_net']:>8.1%}{r['ebitda_pct_of_gross']:>8.1%}")

    recent = rows[-3:]
    print("-" * 68)
    print(f"Rule:  NR/GR {NET_REV_PCT_OF_GROSS:.0%}   EB/NR {EBITDA_PCT_OF_NET_REV:.0%}"
          f"   EB/GR {NET_REV_PCT_OF_GROSS * EBITDA_PCT_OF_NET_REV:.1%}")
    print(f"EXPD 6yr mean:  NR/GR {_mean([r['net_pct_of_gross'] for r in rows]):.1%}"
          f"   EB/NR {_mean([r['ebitda_pct_of_net'] for r in rows]):.1%}"
          f"   EB/GR {_mean([r['ebitda_pct_of_gross'] for r in rows]):.1%}")
    print(f"EXPD 23-25 mean: NR/GR {_mean([r['net_pct_of_gross'] for r in recent]):.1%}"
          f"   EB/NR {_mean([r['ebitda_pct_of_net'] for r in recent]):.1%}"
          f"   EB/GR {_mean([r['ebitda_pct_of_gross'] for r in recent]):.1%}")
    print()
    print("Read: the 30% EBITDA-on-net-revenue lands almost exactly on EXPD's")
    print("last three years (31.0 / 32.3 / 30.3). The 25% net-on-gross is ~5-8pts")
    print("below EXPD in a normal year, but right on top of 2021-22 -- when the")
    print("rate spike inflated gross revenue without moving net revenue much.")
    print("So the cascade is conservative in normal markets, which is what you")
    print("want in a screen. Caveat I can't resolve from public data: EXPD is")
    print("the best operator at global scale. A regional forwarder doing $15-30M")
    print("of net revenue is unlikely to convert at 30% -- I'd treat that as a")
    print("ceiling and expect real targets to come in lower.")
    print()
    for tgt in (3, 5, 10):
        print(f"  EBITDA >= ${tgt}M  implies gross revenue >= "
              f"${gross_revenue_for_ebitda(tgt):,.0f}M "
              f"(net revenue >= ${tgt / EBITDA_PCT_OF_NET_REV:,.1f}M)")
