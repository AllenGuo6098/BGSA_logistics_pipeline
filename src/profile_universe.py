"""Profile the Phase 1 universe: what signals do we already have, pre-enrichment?

Run:  python src/profile_universe.py

The point of this module is to show what the registry data alone can tell us
before any headcount enrichment happens -- i.e. how much free triage we get.
"""
import csv
import sys
from collections import Counter

import config


def main():
    with open(config.UNIVERSE_CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("no universe found; run build_universe.py first")
        return 1

    n = len(rows)
    by_sources = Counter(int(r["n_sources"]) for r in rows)
    permits = sorted(int(r["cbp_permit_count"]) for r in rows
                     if int(r["cbp_permit_count"]) > 0)
    states = Counter(r["state"] for r in rows if r["state"])

    print(f"Universe: {n:,} distinct US companies\n")

    print("Licences held (a proxy for how built-out the operator is)")
    for k in sorted(by_sources):
        share = by_sources[k] / n * 100
        print(f"  in {k} registr{'y' if k==1 else 'ies'}: {by_sources[k]:>6,}  ({share:4.1f}%)")

    print("\nCBP port permits (only for the 2.4k customs brokers)")
    if permits:
        print(f"  max            : {max(permits)}")
        print(f"  median         : {permits[len(permits)//2]}")
        print(f"  >= 5 permits   : {sum(1 for x in permits if x >= 5):,}")
        print(f"  >= 10 permits  : {sum(1 for x in permits if x >= 10):,}")

    print("\nTop states")
    for st, cnt in states.most_common(8):
        print(f"  {st:<4}: {cnt:,}")

    print("\nMost built-out operators (all 3 licences, most port permits)")
    tri = [r for r in rows if int(r["n_sources"]) == 3]
    tri.sort(key=lambda r: -int(r["cbp_permit_count"]))
    for r in tri[:10]:
        print(f"  {r['company_name'][:44]:<46} permits={r['cbp_permit_count']:>3}"
              f"  {r['city'][:18]}, {r['state']}")
    print(f"\n  ({len(tri):,} companies hold all three licences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
