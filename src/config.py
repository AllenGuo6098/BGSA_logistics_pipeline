"""Shared paths + source definitions for the sourcing pipeline.

Deliberately stdlib-only: the whole pipeline runs on a clean Python 3
install with no pip step, so it can be handed to someone else and just run.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

for _d in (RAW, PROCESSED, OUTPUTS):
    _d.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Sources. All three are free, public, and asset-light by definition: a
# customs broker, an ocean freight forwarder and an NVOCC are all licensed
# intermediaries, none of them own trucks. That is the point -- the universe
# comes out asset-light without having to filter for it.
# ---------------------------------------------------------------------------

# CBP publishes the permitted-broker list as a static CSV, refreshed quarterly.
# NOTE: the filename carries its release date, so this URL moves each quarter.
# fetch_sources.py falls back to the cached copy if the URL 404s.
CBP_BROKERS_URL = (
    "https://www.cbp.gov/sites/default/files/2025-04/"
    "TA-015%20Broker%20Permit_Contact%20List%20Final%2003.2025.csv"
)
CBP_BROKERS_RAW = RAW / "cbp_permitted_brokers.csv"
CBP_HEADER_ROW = 0  # header is the first line

# FMC's OTI list is an ASP.NET WebForms app; the CSV button is a postback,
# not a link, so fetch_sources.py replays the form (see that module).
FMC_PAGES = {
    "ocean_freight_forwarder": {
        "url": "https://www2.fmc.gov/oti/FF.aspx",
        "raw": RAW / "fmc_ocean_freight_forwarders.csv",
        "header_row": 2,  # two banner lines above the real header
    },
    "nvocc": {
        "url": "https://www2.fmc.gov/oti/NVOCC.aspx",
        "raw": RAW / "fmc_nvocc.csv",
        "header_row": 3,  # extra regulatory note line above the header
    },
}

# ---------------------------------------------------------------------------
# Truck brokerage / freight management.
#
# A property broker arranges freight but owns no equipment, so it clears the
# asset-light bar the same way a customs broker or NVOCC does. The catch is
# where the data lives:
#
#   - FMCSA's Licensing & Insurance data, which carries the actual BROKER
#     authority flag, is published on data.transportation.gov as dataset
#     jeyh-5nsj -- but that entry is assetType "href", i.e. a link out to the
#     query-only web app at li-public.fmcsa.dot.gov. There is no bulk file
#     behind it, which is why the SODA endpoint 403s.
#   - The Company Census File (az4n-8mr2) IS a real tabular dataset with a
#     working SODA API: 4.47M rows, and it carries power_units, truck_units
#     and total_drivers.
#
# So: census gives asset intensity but not authority type; L&I gives authority
# type but not in bulk. The workable move is to screen the census file for
# registered entities that own no equipment (power_units = 0, drivers = 0),
# which is a proxy for broker authority, then confirm authority per-record.
# Flagged as an assumption to check rather than settled.
# ---------------------------------------------------------------------------
FMCSA_CENSUS_DATASET = "az4n-8mr2"
FMCSA_SODA_URL = f"https://data.transportation.gov/resource/{FMCSA_CENSUS_DATASET}.json"
FMCSA_RAW = RAW / "fmcsa_asset_light.csv"
FMCSA_PAGE_SIZE = 50_000  # SODA caps a single page; build_universe pages through

# CBSA publishes Canada's licensed customs brokers as an HTML table (~600
# entries) carrying company name, website AND email -- better contactability
# than any of the US registries, which mostly give phone only.
CBSA_BROKERS_URL = "https://www.cbsa-asfc.gc.ca/services/cb-cd/cb-cd-eng.html"
CBSA_BROKERS_RAW = RAW / "cbsa_licensed_brokers.csv"

# Mexico: CAAAREM publishes an agentes aduanales directory but the site failed
# TLS verification on fetch, so it is NOT wired up yet. Open item.
MEXICO_SOURCE_STATUS = "unresolved - CAAAREM cert failure, needs a look"

# ---------------------------------------------------------------------------
# Scope. North American (US / Canada / Mexico) rather than US-only. Note this barely moves the ocean-side numbers -- FMC's forwarder
# list is 3,269/3,272 US by construction, and the NVOCC list adds only 111
# Canadian and 5 Mexican entities. The real N.A. expansion is CBSA + FMCSA.
# ---------------------------------------------------------------------------
NORTH_AMERICA_ONLY = True
NA_COUNTRY_VALUES = {
    "UNITED STATES", "UNTED STATES", "USA", "US", "",   # sic: FMC has typos
    "CANADA", "CA",
    "MEXICO", "MX",
}
US_COUNTRY_VALUES = {"UNITED STATES", "UNTED STATES", "USA", "US", ""}

# Sizing assumptions live in sizing.py (the 25% / 30% cascade, calibrated
# against EXPD's actual SEC filings).

UNIVERSE_CSV = PROCESSED / "universe_pilot.csv"
SUMMARY_TXT = OUTPUTS / "phase1_summary.txt"
