# Asset-light logistics sourcing pipeline

Builds a deduplicated universe of privately held, **asset-light** logistics and
supply-chain companies in North America from public licensing registries, then
sizes them against published sector financials.

The premise: rather than buying a commercial database and filtering it down,
start from registries where every entity is asset-light *by definition*. A
licensed customs broker, an ocean freight forwarder and an NVOCC are all
licensed intermediaries. None of them own trucks. The universe comes out
asset-light without having to filter for it, and it is not a list anyone is
selling off the shelf.

**Standard library only.** No `pip install`, no virtualenv, no API keys, no
config. Clone it and run it.

---

## Quick start

```bash
python src/fetch_sources.py     # CBP + FMC registries      -> data/raw/
python src/fetch_ttnews.py      # Transport Topics financials -> data/raw/
python src/build_universe.py    # parse, dedupe, merge      -> data/processed/
python src/profile_universe.py  # what signals exist pre-enrichment
python src/sizing.py            # revenue cascade vs EXPD actuals
```

The committed output is already in `data/processed/`, so you can skip straight
to reading it. The fetch steps only need re-running to refresh.

---

## Navigating the codebase

Read them in this order. Each file does one thing.

| File | What it does | Read it if you want to know |
|---|---|---|
| **`config.py`** | Every source URL, file path and toggle in one place. No magic strings anywhere else. | Where the data comes from, or how to change scope |
| **`fetch_sources.py`** | Downloads CBP + FMC. Handles the ASP.NET postback (below). | How the registries are actually retrieved |
| **`normalize.py`** | Strips legal suffixes so `FOO LOGISTICS, INC.` and `Foo Logistics LLC` collapse to one key. | How companies are matched across registries |
| **`build_universe.py`** | The core. Parse each registry's quirks, filter by geography, dedupe within, merge across. | How 14,724 raw rows become 7,124 companies |
| **`profile_universe.py`** | Distributions across the finished universe. Read-only. | What signals exist before spending on enrichment |
| **`sizing.py`** | Revenue cascade, calibrated against Expeditors' real SEC filings. | How a revenue target becomes a screen |
| **`fetch_ttnews.py`** | Transport Topics sector rankings: gross revenue, net revenue, headcount. | Where sector financials come from |
| **`fetch_fmcsa.py`** | An approach that **does not work**, kept deliberately. | Why truck brokerage can't be sourced this way |

**The dependency chain is linear.** `config` ← `normalize` ← `build_universe`.
The three `fetch_*` modules only depend on `config`. `sizing` depends on
nothing and can be run or imported on its own.

### Two implementation details worth knowing

**The FMC CSV button is not a link.** It is an ASP.NET WebForms postback, so
you have to GET the page, carry the `__VIEWSTATE` / `__VIEWSTATEGENERATOR` /
`__EVENTVALIDATION` tokens plus the session cookie, and replay the form as an
image-button click with x/y coordinates. That is all in `fetch_sources.py`.
Both fetchers fall back to a cached copy rather than failing, because CBP
embeds the release date in the filename and it rotates every quarter.

**FMCSA types its numeric columns as text.** `power_units = 0` throws a SoQL
type mismatch; it has to be `power_units = '0'`. Blank is treated as unknown
and excluded rather than assumed zero, since a registrant who never filed
equipment counts is not evidence of being asset-light.

---

## Reading the output

`data/processed/universe_pilot.csv` — **7,124 rows, one per company.**

| Column | What it is | How to read it |
|---|---|---|
| `company_name` | Name as the registry has it | Casing and punctuation are inconsistent by source. Cosmetic only. |
| `normalized_name` | Legal suffixes stripped, uppercased | The join key. Use this to match against other lists, not `company_name`. |
| `city` / `state` / `country` | Principal address | Physical address where given, mailing otherwise |
| `phone` | Formatted `(xxx) xxx-xxxx` | 6,445 of 7,124 have one |
| `email` | Only where a registry disclosed it | Only 388 have one. CBP publishes email; FMC does not. |
| `sources` | Pipe-delimited registry list | e.g. `cbp_customs_broker\|fmc_nvocc` |
| **`n_sources`** | **How many of the three licences the firm holds (1–3)** | **The most useful single column. See below.** |
| `cbp_permit_count` | Number of CBP port permits | Not a size signal. See limitations. |
| `cbp_filer_codes` | CBP filer codes | Useful for matching to customs entry data |
| `fmc_org_no` | FMC organisation number | Stable identifier for FMC lookups |
| `fmc_trade_names` | DBA names | Sometimes reveals a brand the legal name hides |

### The one column that matters most

**`n_sources` is the closest thing to a quality signal available before
spending anything on enrichment.** A company holding all three licences is
running customs brokerage *and* ocean forwarding *and* NVOCC operations. That
takes real infrastructure, so it is a decent proxy for a built-out operation
rather than a one-desk shop.

```
n_sources = 3   →   301 companies   ← start here
n_sources = 2   → 2,443 companies
n_sources = 1   → 4,380 companies
```

The file is sorted with `n_sources` descending, so **the top 301 rows are the
tri-licence group.** Open the CSV and the most interesting companies are
already at the top.

Sanity check when you open it: the first row should be `FedEx Logistics`, and
row 3 should be `721 Logistics LLC` in Philadelphia. If that is what you see,
the file is intact.

### Interpreting it honestly

Two things this file does **not** tell you, and one trap.

**It does not tell you size.** No registry publishes revenue or headcount. A
tri-licence firm could be doing $5M or $500M. Sizing has to come from
elsewhere — see the cascade below.

**It does not tell you ownership.** Registries make no distinction between an
independent operator and a subsidiary of a public company. FedEx Logistics is
literally the first row. C.H. Robinson and Amazon Logistics are both in the
tri-licence group. **Treat this file as raw material, not a target list.**
Separating independents from subsidiaries is a classification problem that has
to happen downstream.

**The trap:** sorting by `cbp_permit_count` looks like sorting by size. It is
not. The file is effectively one row per broker and the maximum is 2. It was
an idea that did not survive contact with the data.

### The other committed outputs

| File | What it is |
|---|---|
| `outputs/phase1_summary.txt` | Row counts at each stage. Diff it after a refresh to see what moved. |
| `data/raw/ttnews_top100_logistics_2026.csv` | 100 companies with gross revenue, net revenue and headcount |
| `data/raw/ttnews_freight_brokerage_2026.csv` | 100 brokerages with gross and net revenue |

Raw registry dumps are gitignored. They are reproducible from
`src/fetch_sources.py`, run to several MB, and the FMCSA census pull contains
personal email addresses belonging to individual registrants — public record,
but not something to republish.

---

## Sizing

Freight is largely pass-through, so gross revenue means very little. The model
works off net revenue:

```
net revenue = 25% of gross revenue
EBITDA      = 30% of net revenue        →  EBITDA ≈ 7.5% of gross
```

`sizing.py` checks that against Expeditors' (EXPD) actual reported figures,
pulled from SEC XBRL rather than a data vendor. Run it and you get:

| FY | Net / gross | EBITDA / net |
|---|---|---|
| 2021 | 27.0% | 43.9% |
| 2022 | 26.3% | 41.9% |
| 2023 | 34.9% | 31.1% |
| 2024 | 32.2% | 32.3% |
| 2025 | 33.1% | 30.2% |

The 30% holds up well against the last three years. The 25% is conservative in
a normal year but lands almost exactly on 2021–22, when the rate spike inflated
gross revenue without moving net revenue much — so the ratio largely tracks
where freight rates sit.

**The ratio is sector specific.** Across the 60 Transport Topics brokerage
firms reporting both figures, net revenue is **14.7% of gross at the median**,
roughly half what forwarding converts. Running a forwarder ratio on a truck
broker overstates net revenue by about 70%, and EBITDA with it.

**Net revenue per employee is the bridge to private companies.** 45 of the
Transport Topics Top 100 report both, median ≈ **$190K per head**. Since
headcount is observable from the outside for private firms and revenue is not,
that is what converts a profit target into something screenable.

---

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

Both survivors are trucking companies with stale filings — the longest-tenured
reports zero trucks. About 41% of the starting pool is classified private
passenger and non-business (individuals, not firms), `business_org_desc` is
essentially unpopulated, and 92% registered since 2020.

```bash
python src/fetch_fmcsa.py            # pull the census slice
python src/fetch_fmcsa.py --profile  # reproduce the table above
```

---

## Sources

| Source | What it gives | How it is fetched |
|---|---|---|
| CBP Permitted Broker list | ~2.4k licensed US customs brokers | Static CSV, refreshed quarterly |
| FMC OTI (Ocean Freight Forwarders) | ~3.3k licensed forwarders | CSV export behind an ASP.NET postback |
| FMC OTI (NVOCCs) | ~9.0k, 4.4k US-domiciled | Same |
| FMCSA Company Census | 4.47M registrants, equipment counts | Socrata API |
| Transport Topics Top 100 Logistics | Gross + net revenue + headcount | HTML table |
| Transport Topics Top 100 Brokerage | Gross + net revenue | HTML table |

---

## Known limitations

- **Ownership is unresolved.** Registries do not distinguish an independent
  operator from a subsidiary. This is the largest open problem.
- **CBP port permits are not a size signal.** Maximum of 2 per broker.
- **No registry publishes revenue or headcount.** Sizing has to come from
  Transport Topics or from headcount inference.
- **Mexico coverage is thin** — 5 NVOCCs. CAAAREM's directory would not fetch
  cleanly, so Mexican customs brokers are missing entirely.
- **Canada is partial.** 111 NVOCCs, but CBSA's ~600-firm licensed broker list
  (which publishes emails) is defined in `config.py` and not yet wired in.

## Licence

MIT
