"""Ownership classification for the in-band brokerage candidates.

Every entry below was checked individually against company sites, trade press
and PE/VC announcements. `evidence` is what the classification rests on, so a
wrong call can be traced and corrected rather than argued about.

Tiers:
  FOUNDER    entrepreneur or family owned, no institutional sponsor found
  SPONSOR    PE or VC holds a stake (majority unless noted)
  CORPORATE  subsidiary or segment of a larger group; not a pure play
  ESOP       employee owned
  ASSET      asset-based operator, fails the asset-light test

Net revenue figures are Transport Topics 2026 Top 100 Freight Brokerage.
"""

FOUNDER, SPONSOR, CORPORATE, ESOP, ASSET = (
    "FOUNDER", "SPONSOR", "CORPORATE", "ESOP", "ASSET")

# company, net_rev_mm, tier, principal, evidence
CANDIDATES = [
    ("Logistics Plus", 54, FOUNDER, "Jim Berlin",
     "Founded 1996 Erie PA; described as owner and CEO; EY Entrepreneur of the Year"),
    ("Beemac Logistics", 58, FOUNDER, "Richard A. Mackin",
     "Founded 1984; no funding rounds on record; emphasises employee ownership"),
    ("Trident Transport", 40, FOUNDER, "Heath Haley, Mark Harrell",
     "Founded 2013 Chattanooga by two brothers-in-law; 6x Inc. 5000; private"),
    ("BBI Logistics", 39, FOUNDER, "Brent Bosse",
     "Founded 2017 Columbus; listed as Owner/CEO; no sponsor found"),
    ("SPI Logistics", 39, FOUNDER, "Mitch Helten",
     "Founder, Chairman and CEO; 45 years; BC Canada; agent-network model"),
    ("OpenRoad Global", 38, FOUNDER, "Mark and Liz Weisensee",
     "Founded 2004 Dallas OR; states it reinvests profits, no outside capital"),
    ("Ease Logistics", 32, FOUNDER, "Peter Coratola Jr.",
     "Founded 2014; one of the largest privately held companies in Columbus"),
    ("Best Bay Logistics", 27, FOUNDER, "Boparai family",
     "Family owned, founded 2015; NOTE sister company Best Bay Trucking is asset-based"),
    ("Fifth Wheel Freight", 24, FOUNDER, "Brian Bennett",
     "Founded 2012; founder now Chairman, CEO handed to Reese Van Heck -- succession underway"),
    ("Longship", 24, FOUNDER, "Kenny Ray Schomp",
     "Founded 2012 Lexington KY; Xavier entrepreneurship grad; grew from one trailer"),
    ("Automated Logistics Systems", 24, FOUNDER, "Parker family lineage",
     "Traces to Parker Motor Freight pre-Depression; family owned; quadrupled since 2004"),
    ("Motus Freight", 23, FOUNDER, "Lackey, Mitchell, Smith",
     "Founded 2015; three serial operators; no funding rounds on record"),
    ("Destination Transport", 23, FOUNDER, "not identified",
     "Founded 2014 Anoka MN; founders not named publicly; UNCONFIRMED"),
    ("Paul Logistics", 20, FOUNDER, "Troy Paul",
     "Founded 2003; NOTE brokerage arm of Paul Transportation, an asset-based carrier"),
    ("Genpro", 18, FOUNDER, "Robert A. Goldstein",
     "Founded 1989 Rutherford NJ; owner and president; third-generation produce family"),

    ("InXpress", 95, SPONSOR, "Hudson Hill Capital",
     "PE owned; also a franchise system, ~400 locations, not a single operating company"),
    ("Steam Logistics", 88, SPONSOR, "Dynamo Ventures, Lamp Post",
     "VC backed but only ~$4M raised; founder Jason Provonsha still CEO -- borderline"),
    ("Logistic Dynamics", 91, SPONSOR, "Tritium Partners",
     "Acquired by Tritium; founder Dennis Brown no longer CEO"),
    ("FLS Transportation", 62, SPONSOR, "Abry Partners",
     "Acquired by Abry 2016"),
    ("Capstone Logistics", 52, SPONSOR, "H.I.G. Capital",
     "H.I.G. majority since 2020, second time owning it; Jordan Co. retains minority"),
    ("BlueGrace Logistics", 40, SPONSOR, "Warburg Pincus",
     "$255M but explicitly a MINORITY stake; founder Bobby Harris still CEO -- borderline"),
    ("Loadsmart", 19, SPONSOR, "SoftBank, BlackRock",
     "$384M raised across 6 rounds, $1.3B valuation; not a control opportunity"),
    ("FreightVana", 20, SPONSOR, "venture investors",
     "Founded 2020 by Shannon Breen and John Gamero; VC backed; investor list unconfirmed"),

    ("NFI", 74, CORPORATE, "Brown family",
     "Family owned since 1932 but $3.7B group; this is the brokerage segment only"),
    ("Watco Logistics", 49, CORPORATE, "Webb family",
     "Family owned but a rail, terminal and port group; logistics is one segment"),
    ("Roar Logistics", 30, CORPORATE, "Rich Products",
     "Subsidiary of Rich Products, a family-owned food company; not a pure play"),
    ("Canada Cartage / GTI", 27, CORPORATE, "Mubadala Capital",
     "Canada Cartage owned by Mubadala, UAE sovereign fund, since 2022"),

    ("Triple T Transport", 40, ESOP, "employees",
     "100% ESOP since 2010; founders Sanfillipo and Walker 1988; already has a liquidity path"),

    ("Bay & Bay Transportation", 31, ASSET, "family owned",
     "Family owned since 1941 but describes itself as an asset-based trucking company"),
]


def by_tier(tier):
    return [c for c in CANDIDATES if c[2] == tier]


def summary():
    from collections import Counter
    counts = Counter(c[2] for c in CANDIDATES)
    return counts


if __name__ == "__main__":
    counts = summary()
    print(f"{len(CANDIDATES)} in-band brokerage candidates screened\n")
    for tier in (FOUNDER, SPONSOR, CORPORATE, ESOP, ASSET):
        rows = by_tier(tier)
        if not rows:
            continue
        print(f"{tier}  ({len(rows)})")
        for name, net, _, principal, ev in sorted(rows, key=lambda r: -r[1]):
            print(f"   ${net:>3}M net  {name:<30} {principal}")
        print()
    clean = [c for c in by_tier(FOUNDER)
             if "NOTE" not in c[4] and "UNCONFIRMED" not in c[4]]
    print(f"Clean entrepreneur-owned pure plays, no caveats: {len(clean)}")
    for name, net, _, principal, _ in sorted(clean, key=lambda r: -r[1]):
        print(f"   ${net:>3}M net  {name:<30} {principal}")
