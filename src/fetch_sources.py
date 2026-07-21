"""Download the three public registries that make up the universe.

Run:  python src/fetch_sources.py

CBP is a plain static CSV. The FMC list is harder: it is an ASP.NET WebForms
app where the CSV button is a form postback rather than a link, so we have to
GET the page, carry the __VIEWSTATE / __EVENTVALIDATION tokens and the session
cookie, then POST back as if the button had been clicked. That is done here
with the standard library so there is nothing to install.
"""
import re
import sys
import urllib.parse
import urllib.request
import http.cookiejar

import config

_HIDDEN = r'id="{}"[^>]*value="([^"]*)"'


def _opener():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", config.USER_AGENT)]
    return op


def fetch_cbp() -> bool:
    """CBP permitted customs brokers (static CSV, refreshed quarterly)."""
    dest = config.CBP_BROKERS_RAW
    try:
        op = _opener()
        with op.open(config.CBP_BROKERS_URL, timeout=120) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"[cbp ] downloaded {len(data):,} bytes -> {dest.name}")
        return True
    except Exception as e:
        # The CBP filename embeds its release date, so the URL rotates each
        # quarter. Don't fail the pipeline -- fall back to the cached copy and
        # make the staleness obvious.
        if dest.exists():
            print(f"[cbp ] WARN download failed ({e}); using cached {dest.name}")
            return True
        print(f"[cbp ] ERROR download failed and no cache present: {e}")
        return False


def fetch_fmc(kind: str) -> bool:
    """FMC OTI list (ocean freight forwarders / NVOCCs) via form postback."""
    spec = config.FMC_PAGES[kind]
    url, dest = spec["url"], spec["raw"]
    try:
        op = _opener()
        with op.open(url, timeout=120) as r:
            html = r.read().decode("utf-8", "replace")

        def hidden(field):
            m = re.search(_HIDDEN.format(field), html)
            return m.group(1) if m else ""

        form = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": hidden("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": hidden("__EVENTVALIDATION"),
            # image buttons post their click coordinates
            "ctl00$searchPlaceHolder$ibtnCSV.x": "10",
            "ctl00$searchPlaceHolder$ibtnCSV.y": "10",
        }
        if not form["__VIEWSTATE"]:
            raise RuntimeError("no __VIEWSTATE found; page layout may have changed")

        body = urllib.parse.urlencode(form).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": url},
        )
        with op.open(req, timeout=300) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"[fmc ] {kind}: downloaded {len(data):,} bytes -> {dest.name}")
        return True
    except Exception as e:
        if dest.exists():
            print(f"[fmc ] WARN {kind} failed ({e}); using cached {dest.name}")
            return True
        print(f"[fmc ] ERROR {kind} failed and no cache present: {e}")
        return False


def main() -> int:
    ok = [fetch_cbp(), fetch_fmc("ocean_freight_forwarder"), fetch_fmc("nvocc")]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
