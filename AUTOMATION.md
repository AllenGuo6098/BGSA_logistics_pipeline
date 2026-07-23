# Automating the workflow: source → profile → outreach → CRM

This answers the two questions from the 23 July note: how the dataset scales,
and how a list of companies becomes a running workflow. It describes the whole
system and marks, honestly, which parts run today and which need something from
the client side.

## The division of labour

The design keeps the analytical core separate from the plumbing, because they
have different requirements. The core has to be **auditable** — every number
traceable to a filing. The plumbing has to be **reliable** — scheduled, retried,
credentialed.

```
   ┌─────────────── analytical core (Python, stdlib, runs cold) ──────────────┐
   │  source  →  dedupe  →  score  →  profile  →  CRM-ready CSVs              │
   │  registries + Form 5500     tenure/size/ownership      one row/company    │
   └───────────────────────────────┬──────────────────────────────────────────┘
                                    │  outputs/*.csv, *.html
   ┌────────────────────────────────▼──── orchestration (n8n) ─────────────────┐
   │  weekly trigger → run core → enrich → upsert to CRM → draft mail          │
   └───────────────────────────────────────────────────────────────────────────┘
```

**Why Python for the core, not an LLM.** Scoring, dedupe and sizing are
deterministic and have to be defensible to a client. An LLM is the wrong tool
for a number that ends up in a valuation. Claude is used for exactly one thing —
writing the outreach copy — where language, not fact, is the task.

**Why n8n for the plumbing.** It self-hosts (the target data need not touch a
third-party cloud), it has native nodes for the CRMs and mail systems below, and
its Execute-Command and Code nodes let the Python core drop straight in. Zapier
or Make would also work and are lower-code; n8n is the better fit for
self-hosting plus custom code. The reference graph is in
`n8n/tgt_sourcing_workflow.json` — importable, with credential-dependent nodes
marked and disabled.

## The stages

| Stage | What it does | Status |
|---|---|---|
| Source | registries (FMC, FMCSA, CBP, CBSA) + DOL Form 5500 | **built** |
| Dedupe | one row per real company, keyed on EIN / domain | **built** |
| Score | tenure (age) · headcount (size) · ownership → in-band flag | **built** |
| Profile | one-page target profile per firm, source on every field | **built (this slice)** |
| CRM export | HubSpot-shaped Companies + Contacts CSV, dedupe key | **built (this slice)** |
| Enrich | domain → contact email | **needs an enrichment seat** |
| CRM sync | upsert into the live CRM | **needs the CRM confirmed** |
| Outreach | personalised draft, human sends, gated on do-not-contact | **pattern built on the other project; needs the mail system** |

## What this slice produces today

Run `python src/run_pipeline.py` and it emits, from public data only:

- `outputs/target_profiles.html` — 12 profiles, 3 confirmed in band (Powell,
  Shapiro, Rogers & Brown), each field labelled with its source.
- `outputs/crm_companies.csv` and `outputs/crm_contacts.csv` — import-ready,
  linked by a dedupe key, with the email column deliberately blank.

Every contact carries a named principal where the research found one (Margie
Shapiro, the Browns, Asim Faiz, Charles Schayer Jr., Chas Watson Jr.). None
carries an email, because no registry publishes one. That blank is not a
failure — it is the precise seam where enrichment plugs in.

## Assumptions baked in (so nothing is blocked) and what would change them

| Assumption used | Confirm with client → effect |
|---|---|
| **CRM = HubSpot** for the sample schema | If **Affinity** or **DealCloud** (the PE-native ones), swap the export adapter — one rename per column, mapping below. The pipeline is unchanged. |
| **Enrichment = Apollo** | Confirm the corporate seat. No seat → contact email stays a manual lookup and the Apollo node stays disabled. |
| **Send from individual mailboxes, draft-first** | If they use a sequencer (Outreach / Salesloft), the last node becomes that service's node instead of Gmail/Outlook. |
| **Stand up a fresh n8n instance** | If Zapier/Make already exists, the same graph rebuilds there. |
| **A do-not-contact / current-client list exists** | Share it and it becomes the gate before any draft — the same iron-rule gate already built and proven on the boutique campaign. |

## CRM field mapping (portable across systems)

The export uses HubSpot's internal property names. To point at another CRM,
rename the header row; the data does not change.

| Pipeline column | HubSpot | Salesforce | Affinity / DealCloud |
|---|---|---|---|
| Company name | Company name | Account Name | Name |
| Company domain name | Company domain name | Website | Domain |
| tgt_est_ebitda_low_mm | custom property | custom field | custom field |
| tgt_ownership | custom property | custom field | custom field |
| tgt_dedupe_key | unique property (dedupe) | External ID | Unique ID |

The dedupe key is EIN where a Form 5500 gives one, else the domain — never the
display name, because the same firm files under several legal-entity spellings.

## Open questions for the client (the honest dependencies)

1. Which CRM does the team run — HubSpot, Salesforce, Affinity, DealCloud?
2. Is there a corporate enrichment seat (Apollo / ZoomInfo / Cognism)?
3. How does the team send outreach today — individual Outlook/Gmail, or a
   sequencer?
4. Is there already an n8n / Zapier / Make instance, or do we stand one up?
5. Is there a do-not-contact or current-engagement list to gate against?

None of these blocks the core. They decide only how the last three stages wire
up, and each has a working default in the meantime.
