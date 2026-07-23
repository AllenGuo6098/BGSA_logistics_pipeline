"""Turn the scored shortlist into one-page target profiles.

This is the 'list -> profile' stage of the workflow. It joins the two things
that were built separately:

    forwarders.PROFILED       researched context -- founding, ownership tier,
                              named principal, evidence (checked by hand)
    size_from_filings.FILED   headcount from DOL Form 5500 filings, a primary
                              source, with the implied net-revenue / EBITDA band

The join is deliberate about provenance. Where a firm has a real filing, the
headcount and size come from that and are labelled 'filed'. Where it does not,
the profile says so rather than quietly falling back to an aggregator number.

The one field this cannot fill from public data is a contact EMAIL. Named
principals come from the research (Margie Shapiro, the Browns, Asim Faiz), but
an address needs an enrichment seat (Apollo / ZoomInfo). So the contact block
carries the name and the firm, and marks the email as the point where that
step plugs in -- which is exactly the dependency to confirm with the client.

Output: outputs/target_profiles.html  (one printable page per firm)
Render to PDF with the same headless-Chrome step used for the other reports.

Run:  python src/build_profiles.py
"""
import html
import re

import forwarders
import size_from_filings as sf


# Sub-sector and named-contact supplements, pulled from the researched evidence
# already in forwarders.PROFILED so nothing new is invented here. Fields are
# (sub_sector, contact_name, contact_title). A title is only a real job title
# when a person is named; where no individual appears in the evidence, both are
# blank and the firm goes to the enrichment queue. Ownership context is NOT put
# here -- it lives on the company record's ownership/evidence row.
SUPPLEMENT = {
    "Samuel Shapiro & Co.":            ("Customs broker / forwarder", "Margie Shapiro", "President"),
    "C.H. Powell Company":             ("Customs broker / forwarder", "", ""),
    "Rogers & Brown":                  ("Customs broker / forwarder", "Don Brown Sr.", "Chairman"),
    "Carmichael International Service": ("Customs broker / forwarder", "Asim Faiz", "Principal"),
    "Western Overseas Corp.":          ("Freight forwarder", "", ""),
    "A.N. Deringer":                   ("Customs broker / forwarder", "", ""),
    "Horizon Air Freight":             ("Air freight forwarder", "", ""),
    "Hoyt Shepston & Sciaroni":        ("Customs broker / forwarder", "", ""),
    "John F. Kilroy Co.":              ("Customs broker / forwarder", "", ""),
    "Charles M. Schayer & Co.":        ("Customs broker / forwarder", "Charles M. Schayer Jr.", "Principal"),
    "Page & Jones":                    ("Customs broker / forwarder", "", ""),
    "R.L. Swearer Company":            ("Customs broker / forwarder", "Chas Watson Jr.", "President"),
}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _filed_rows():
    """(label, headcount_low, headcount_high, ebitda_low, ebitda_high, source, verdict)"""
    out = []
    for name, founded, lo, hi, src, note in sf.FILED:
        lo_nr, lo_eb = sf.implied(lo)
        hi_nr, hi_eb = sf.implied(hi)
        out.append({
            "name": name, "lo": lo, "hi": hi,
            "eb_lo": lo_eb, "eb_hi": hi_eb,
            "nr_lo": lo_nr, "nr_hi": hi_nr,
            "source": src, "verdict": sf.verdict(lo_eb, hi_eb), "note": note,
        })
    return out


def _match_filed(name, filed):
    """Filed labels ('Samuel Shapiro & Co (Baltimore MD, 1915)') and research
    names ('Samuel Shapiro & Co.') differ, so match on a shared leading token
    run rather than an exact key."""
    n = _norm(name)
    best = None
    for base, rec in filed.items():
        if not base:
            continue
        # require a solid shared prefix so 'Powell' doesn't grab the wrong firm
        k = min(len(base), len(n), 8)
        if base[:k] and n.startswith(base[:k]):
            best = rec
            break
        if base in n or n in base:
            best = rec
    return best


def join():
    """One record per researched firm, with filed size attached where it exists."""
    filed = {}
    for r in _filed_rows():
        base = _norm(re.split(r"\(|--", r["name"])[0])
        filed[base] = r

    rows = []
    for rank, name, founded, lo, hi, own, evidence in forwarders.PROFILED:
        sub, contact_name, contact_title = SUPPLEMENT.get(
            name, ("Customs broker / forwarder", "", own.title()))
        f = _match_filed(name, filed)
        rows.append({
            "rank": rank, "name": name, "founded": founded,
            "sub_sector": sub, "ownership": own, "evidence": evidence,
            "contact_name": contact_name, "contact_title": contact_title,
            "research_hc_lo": lo, "research_hc_hi": hi,
            "filed": f,
        })
    return rows


def _fmt_band(lo, hi, unit=""):
    if lo is None:
        return "unknown"
    if abs(lo - hi) < 1e-6:
        return f"{lo:g}{unit}"
    return f"{lo:g}–{hi:g}{unit}"


def profile_html(r):
    f = r["filed"]
    if f:
        size_line = (f"{f['lo']}–{f['hi']} active plan participants "
                     f"(DOL Form 5500, filed)")
        rev_line = f"${f['nr_lo']:.0f}–{f['nr_hi']:.0f}M net revenue (implied)"
        eb_line = f"${f['eb_lo']:.1f}–{f['eb_hi']:.1f}M EBITDA (implied, floor)"
        verdict = f['verdict']
        size_src = "primary — filed with the Department of Labor"
    else:
        lo, hi = r["research_hc_lo"], r["research_hc_hi"]
        size_line = (f"{_fmt_band(lo, hi)} employees (research estimate)"
                     if lo else "headcount unknown")
        rev_line = eb_line = "— no filing found, size not confirmed"
        verdict = "unconfirmed" if lo else "unknown"
        size_src = "weak — no Form 5500 on file; research aggregators only"

    contact = (f'{html.escape(r["contact_name"])} &middot; '
               f'{html.escape(r["contact_title"])}'
               if r["contact_name"]
               else '<span class="gap">named principal not yet resolved '
                    '(research); needs enrichment</span>')

    vclass = {"IN band": "in", "straddles floor": "edge"}.get(verdict, "out")

    return f"""
    <section class="profile">
      <div class="hdr">
        <h2>{html.escape(r["name"])}</h2>
        <span class="badge {vclass}">{html.escape(verdict)}</span>
      </div>
      <div class="meta">{html.escape(r["sub_sector"])} &middot;
        founded {r["founded"]} &middot; tenure rank #{r["rank"]} of 283</div>

      <table>
        <tr><th>Size</th><td>{size_line}<div class="src">{size_src}</div></td></tr>
        <tr><th>Net revenue</th><td>{rev_line}</td></tr>
        <tr><th>EBITDA</th><td>{eb_line}
          <div class="src">$190K net rev / head, 30% EBITDA on net rev;
          participant counts sit below true headcount, so this is a floor</div></td></tr>
        <tr><th>Ownership</th><td><b>{html.escape(r["ownership"].title())}</b> &mdash;
          {html.escape(r["evidence"])}</td></tr>
        <tr><th>Primary contact</th><td>{contact}
          <div class="src email">Email: <b>needs enrichment</b>
          (Apollo / ZoomInfo) &mdash; not published in any registry</div></td></tr>
      </table>
      {"<div class='note'>" + html.escape("Note: " + r["filed"]["note"]) + "</div>"
       if r["filed"] and r["filed"].get("note") else ""}
    </section>"""


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Target Profiles</title>
<style>
  @page {{ size: letter; margin: 0.7in; }}
  body {{ font: 10.5pt/1.4 Georgia, serif; color: #1a1a1a; }}
  h1 {{ font-size: 15pt; margin: 0 0 2px; }}
  .lead {{ color: #666; font-size: 9pt; margin-bottom: 4px; }}
  .profile {{ border: 1px solid #ddd; border-radius: 4px; padding: 12px 16px;
    margin-bottom: 12px; page-break-inside: avoid; }}
  .hdr {{ display: flex; justify-content: space-between; align-items: baseline; }}
  h2 {{ font-size: 12.5pt; margin: 0; }}
  .badge {{ font: 700 8pt Helvetica, sans-serif; padding: 2px 8px; border-radius: 10px;
    text-transform: uppercase; letter-spacing: .04em; }}
  .badge.in {{ background: #e3f3e8; color: #1a6b2f; }}
  .badge.edge {{ background: #fdf1dc; color: #97600a; }}
  .badge.out {{ background: #eee; color: #888; }}
  .meta {{ color: #777; font-size: 9pt; margin: 2px 0 8px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; }}
  th {{ text-align: left; width: 118px; vertical-align: top; padding: 4px 8px 4px 0;
    color: #555; font-family: Helvetica, sans-serif; font-size: 8.5pt;
    text-transform: uppercase; letter-spacing: .03em; }}
  td {{ padding: 4px 0; border-bottom: 1px solid #f0f0f0; }}
  .src {{ font-size: 8pt; color: #888; margin-top: 2px; }}
  .src.email {{ color: #a3600a; }}
  .note {{ font-size: 8.5pt; color: #666; margin-top: 6px; font-style: italic; }}
  .gap {{ color: #a3600a; }}
</style>
<h1>Target Profiles &mdash; Customs Brokers &amp; Freight Forwarders</h1>
<div class="lead">Vertical-slice sample &middot; generated {date} &middot;
every field carries its source; the contact-email gap is the enrichment step</div>
{body}
"""


if __name__ == "__main__":
    import datetime

    rows = join()
    # order: in-band first, then edges, then the rest; control (Deringer) last
    order = {"IN band": 0, "straddles floor": 1}
    def sort_key(r):
        v = r["filed"]["verdict"] if r["filed"] else "zzz"
        ctrl = 9 if "Deringer" in r["name"] else 0
        return (ctrl, order.get(v, 5), r["rank"])
    rows.sort(key=sort_key)

    body = "\n".join(profile_html(r) for r in rows)
    import config
    dest = config.OUTPUTS / "target_profiles.html"
    dest.write_text(PAGE.format(date=datetime.date.today().isoformat(), body=body),
                    encoding="utf-8")

    in_band = [r for r in rows if r["filed"] and r["filed"]["verdict"] == "IN band"]
    print(f"wrote {len(rows)} profiles -> {dest}")
    print(f"   in band, filed size confirmed : {len(in_band)}")
    for r in in_band:
        print(f"      {r['name']}  (${r['filed']['eb_lo']:.1f}-"
              f"{r['filed']['eb_hi']:.1f}M EBITDA)")
    print("   render to PDF: headless Chrome --print-to-pdf on the HTML")
