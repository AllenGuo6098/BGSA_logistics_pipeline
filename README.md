# Asset-light logistics sourcing pipeline

Builds a deduplicated universe of privately held, **asset-light** logistics and
supply-chain companies in North America from public licensing registries, then
sizes them using published sector financials.

The premise: rather than buying a commercial database and filtering it down,
start from registries where every entity is asset-light *by definition*. A
licensed customs broker, an ocean freight forwarder and an NVOCC are all
licensed intermediaries. None of them own trucks. The universe comes out
asset-light without having to filter for it, and it is not a list anyone is
selling off the shelf.

**Standard library only.** No `pip install`, no virtualenv, no API keys. Clone
it and run it.

```bash
python src/fetch_sources.py     # CBP + FMC registries
python src/fetch_ttnews.py      # Transport Topics sector financials
python src/build_universe.py    # parse -> filter -> dedupe -> merge
python src/profile_universe.py  # what signals exist pre-enrichment
python src/sizing.py            # revenue cascade, calibrated against EXPD
```

## Current output

| | |
|---|---|
| CBP permitted customs brokers | 2,407 permits |
| FMC ocean freight forwarders | 3,272 |
| FMC NVOCCs | 9,045 |
| **Distinct North American companies after dedupe** | **7,124** |
| Appearing in more than one registry | 2,744 |
| Holding all three licences | 301 |

The licence count doubles as a rough proxy for how built-out a company is: a
firm carrying all three is running a real multi-service operation rather than a
one-desk shop.

## Sources

| Source | What it gives | How it is fetched |
|---|---|---|
| CBP Permitted Broker list | ~2.4k licensed US customs brokers | Static CSV, refreshed quarterly |
| FMC OTI (Ocean Freight Forwarders) | ~3.3k licensed forwarders | CSV export behind an ASP.NET postback |
| FMC OTI (NVOCCs) | ~9.0k, 4.4k US-domiciled | Same |
| FMCSA Company Census | 4.47M registrants, equipment counts | Socrata API |
| Transport Topics Top 100 Logistics | Gross + net revenue + headcount | HTML table |
| Transport Topics Top 100 Brokerage | Gross + net revenue | HTML table |

## Two implementation details worth knowing

**The FMC CSV button is not a link.** It is an ASP.NET WebForms postback, so
you have to GET the page, carry the `__VIEWSTATE` / `__VIEWSTATEGENERATOR` /
`__EVENTVALIDATION` tokens plus the session cookie, and replay the form as an
image-button click. Handled in `fetch_sources.py`. Both fetchers fall back to a
cached copy rather than failing, because CBP embeds the release date in the
filename and it rotates every quarter.

**FMCSA types its numeric columns as text.** `power_units = 0` throws a SoQL
type mismatch; it has to be `power_units = '0'`. Blank is treated as unknown
and excluded rather than assumed zero.

## Sizing

Freight is largely pass-through, so gross revenue means very little. The model
works off net revenue:

```
net revenue = 25% of gross revenue
EBITDA      = 30% of net revenue
```

`sizing.py` checks that against Expeditors' (EXPD) actual reported figures,
pulled from SEC XBRL rather than a data vendor:

| FY | Net / gross | EBITDA / net |
|---|---|---|
| 2021 | 27.0% | 43.9% |
| 2022 | 26.3% | 41.9% |
| 2023 | 34.9% | 31.1% |
| 2024 | 32.2% | 32.3% |
| 2025 | 33.1% | 30.2% |

The 30% holds up well against the last three years. The 25% is conservative in
a normal year but lands almost exactly on 2021-22, when the rate spike inflated
gross revenue without moving net revenue much, so the ratio largely tracks where
freight rates sit.

**The ratio is sector specific.** Across the 60 Transport Topics brokerage firms
that report both figures, net revenue is 14.7% of gross at the median, roughly
half what forwarding converts. Running a forwarder ratio on a truck broker
overstates net revenue by about 70%.

## A negative result, kept deliberately

`fetch_fmcsa.py` documents an approach that **does not work**, because knowing
that is more useful than a list nobody should trust.

FMCSA publishes broker authority only through a query-one-record-at-a-time
interface, never as a bulk file. The obvious workaround is to infer it from the
census file: an active registrant reporting no trucks and no drivers is
arranging freight rather than hauling it. It collapses.

| Filter | Companies |
|---|---|
| Active, zero power units, zero drivers, North America | 8,845 |
| + classified "authorized for hire" | 3,295 |
| + not a passenger operation | 3,274 |
| + an actual business entity | **2** |

Both survivors are trucking companies with stale filings. About 41% of the
starting pool is classified private passenger and non-business, meaning
individuals rather than firms, `business_org_desc` is essentially unpopulated,
and 92% registered since 2020. Run `python src/fetch_fmcsa.py --profile` to
reproduce the table.

## Layout

```
src/
  config.py             paths, source URLs, geography toggle
  fetch_sources.py      CBP + FMC (handles the ASP.NET postback)
  fetch_fmcsa.py        FMCSA census + the documented negative result
  fetch_ttnews.py       Transport Topics sector financials
  sizing.py             revenue cascade, calibrated against EXPD
  normalize.py          name normalisation, the join key across registries
  build_universe.py     parse -> filter -> dedupe -> merge -> universe CSV
  profile_universe.py   signal distributions before enrichment
data/raw/               source files exactly as downloaded (gitignored)
data/processed/         universe CSV (gitignored)
```

`data/` is gitignored on purpose. Every file in it is reproducible from the
fetch scripts, the registry dumps are several MB, and the FMCSA census pull
contains personal email addresses belonging to individual registrants. Public
records, but not something to republish.

## Known limitations

- Registries do not distinguish an independent operator from a subsidiary of a
  public company. FedEx Logistics, C.H. Robinson and Amazon Logistics all appear
  in the universe. Separating those out is an ownership-classification problem,
  not a data problem.
- CBP port permits are not a size signal. The file is effectively one row per
  broker, maximum two.
- No registry publishes revenue or headcount, so sizing has to come from
  elsewhere. Net revenue per employee, roughly $190K at the median across the
  Transport Topics Top 100, is the current bridge.
- Mexico coverage is thin. CAAAREM's directory would not fetch cleanly.

## Licence

MIT
