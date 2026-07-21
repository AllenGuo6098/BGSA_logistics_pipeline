"""Transport Topics sector rankings -- a public revenue source.

The Top 100 Freight Brokerage list is the useful one: it publishes BOTH gross
and net revenue per company, which is the only place I have found that lets the
25%/30% cascade be tested against a whole sector rather than one public comp.

The airfreight list ranks by metric tons and carries no revenue, so it is
useful for identifying forwarder names but not for sizing them.

Table is plain HTML, no JS, no paywall. Parsed with html.parser to keep the
pipeline stdlib-only.

Run:  python src/fetch_ttnews.py
"""
import csv
import gzip
import re
import sys
import urllib.request
from html.parser import HTMLParser

import config

LISTS = {
    # gross + net revenue + employees. Covers forwarders and customs brokers,
    # so this is the one that answers sizing for the main target sector.
    "top100_logistics": "https://www.ttnews.com/top100/logistics/2026",
    # gross + net revenue. The only sector list I have found that prices
    # truck brokerage, which is what makes the ratio test possible.
    "freight_brokerage": "https://www.ttnews.com/logistics/freightbrokerage/2026",
    # ranked by metric tons, no revenue -- useful for names, not for sizing.
    "airfreight": "https://www.ttnews.com/logistics/airfreight/2026",
    "ocean": "https://www.ttnews.com/logistics/ocean/2026",
}


class TableParser(HTMLParser):
    """Collect every <table> as a list of rows of cell text."""

    def __init__(self):
        super().__init__()
        self.tables, self._tbl, self._row, self._cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._tbl = []
        elif tag == "tr" and self._tbl is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self._tbl is not None:
            self.tables.append(self._tbl)
            self._tbl = None
        elif tag == "tr" and self._row is not None:
            if any(c.strip() for c in self._row):
                self._tbl.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.append(text)
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": config.USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def _money(s):
    """'$1,234.5' -> 1234.5 ; '' / 'NA' -> None"""
    s = (s or "").replace("$", "").replace(",", "").strip()
    if not s or s.upper() in ("NA", "N/A", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def scrape(name):
    parser = TableParser()
    parser.feed(_get(LISTS[name]))
    # keep the widest, longest table on the page
    tables = sorted(parser.tables, key=lambda t: (len(t), max(len(r) for r in t)))
    if not tables:
        raise RuntimeError(f"no table found on the {name} page")
    return tables[-1]


def _parse(name, cols):
    """Generic: map header keywords -> our field names, keep numbered rows.

    `cols` is {our_field: (keyword, kind)} where kind is 'money' or 'text'.
    Column order differs between lists, so match on the header text rather
    than position.
    """
    rows = scrape(name)
    header = [h.lower().strip() for h in rows[0]]
    idx = {}
    for field, (kw, kind) in cols.items():
        for i, h in enumerate(header):
            if kw in h:
                idx[field] = (i, kind)
                break
    out = []
    for r in rows[1:]:
        first = r[0].strip().rstrip(".").split()[0] if r[0].strip() else ""
        if not first.isdigit():
            continue
        rec = {"rank": int(first)}
        for field, (i, kind) in idx.items():
            raw = r[i] if i < len(r) else ""
            rec[field] = _money(raw) if kind == "money" else raw.strip()
        out.append(rec)
    return out, header


def brokerage():
    """-> rank, company, gross_mm, net_mm, freight_types."""
    return _parse("freight_brokerage", {
        "company": ("company", "text"),
        "gross_mm": ("gross", "money"),
        "net_mm": ("net", "money"),
        "freight_types": ("freight", "text"),
    })


def top100_logistics():
    """-> rank, company, gross_mm, net_mm, employees. Covers forwarders."""
    return _parse("top100_logistics", {
        "company": ("company", "text"),
        "gross_mm": ("gross", "money"),
        "net_mm": ("net", "money"),
        "employees": ("employee", "money"),
    })


def _ratios(rows, label):
    both = [r for r in rows if r.get("gross_mm") and r.get("net_mm")]
    if not both:
        print(f"  {label}: no priced rows")
        return
    rs = sorted(r["net_mm"] / r["gross_mm"] for r in both)
    n = len(rs)
    print(f"  {label} (n={n}):  median {rs[n // 2]:.1%}   mean {sum(rs) / n:.1%}"
          f"   p25 {rs[n // 4]:.1%}   p75 {rs[3 * n // 4]:.1%}")


if __name__ == "__main__":
    for name, fn, fields in (
        ("ttnews_top100_logistics_2026.csv", top100_logistics,
         ["rank", "company", "gross_mm", "net_mm", "employees"]),
        ("ttnews_freight_brokerage_2026.csv", brokerage,
         ["rank", "company", "gross_mm", "net_mm", "freight_types"]),
    ):
        try:
            rows, header = fn()
        except Exception as e:
            print(f"{name}: FAILED ({e})")
            continue
        out = config.RAW / name
        with open(out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows -> {out}")
        print(f"   header seen: {header}")
        _ratios(rows, "   net/gross")
        print()
