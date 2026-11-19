# Data audit — MGNREGA MIS reports (Month 1)

Extraction date: 29 Oct 2026 (IST). Source: MGNREGA MIS (NREGASoft), national report index
`https://mnregaweb4.dord.gov.in/netnregarep/MISreport4.aspx` (State = ALL), drilled to
district for each financial year. The MIS moved from `nreganarep.nic.in` to `*.dord.gov.in`.
The old host now times out. The index page is behind an arithmetic captcha, which a team member
solved by hand; no automated captcha solving was used. Raw pages are stored verbatim as text
in `data/raw/mgnrega_mis_extract_part*.json` (one record per report × FY, with fetch time).

## 1. Which reports are usable, and how they behave across years

We checked each report empirically by selecting two different FYs and comparing national
totals. This matters because some MIS tables are recomputed from **today's** database
whatever year is selected, and cannot give a historical value.

| Report (MIS label) | Level | Behaviour across FY selection | Evidence | Role in project |
|---|---|---|---|---|
| R1.2.3 *Account Opened and Amount Disbursed through Bank/Post Office* | District | **Year-specific** | Individual bank accounts: 134.3M (FY2020–21 view) vs 103.8M (FY2026–27 view) | **Exposure** (account mix) and wage denominator |
| *Deleted Job Card/Applicants with A/C No, Photos Uploaded* | District | **Cumulative stock as of the FY** | Workers tagged deleted: 120.7M (FY2020–21) → 185.8M (FY2022–23). The difference of 65.1M matches official all-worker deletions for FY2021–22 + FY2022–23 (14.95M + 51.89M = 66.8M) within 3% | **Outcome** (annual deletions = year-on-year difference) |
| *Aadhar Based Payment Report* | District | **Year-specific**, but coverage collapses in FY2022–23 (4 states: KA, MP, NL, RJ) | Covers 28–30 states in FY2018–19 to FY2021–22 | **Pre-mandate readiness**: ABPS share of wages, ABPS rejection rate |
| *Aadhaar Status with NPCI Mapper* | District | **Current snapshot only** | Identical national totals under FY2020–21 and FY2022–23 | Current readiness (post-treatment, contaminated) |
| *Aadhaar Authentication Status Report* | District | **Current snapshot only** | Identical totals across FY selections | Current ABPS-eligible count (contaminated) |
| *Category wise Household/Workers* | District | **Recomputed from today's database** | Active workers 10.83 crore under "FY2020–21", close to today's 10.99 crore, not the historical ~14 crore | Covariates only (SC/ST shares); **not** a historical denominator |

**Consequence for the design.** The only clean, pre-mandate, district-level measure of ABPS
readiness is the ABPS share of wages in FY2018–19 to FY2021–22. Current eligibility and NPCI
status are measured *after* the deletion wave. Districts that deleted ineligible workers look
more "ready", which biases any proxy–readiness correlation toward zero.

## 2. Integrity checks on the parsed tables

* **District sums vs printed state totals.** For every report, FY and state, the district
  rows were summed column by column and compared with the state's own "Total" row. After a
  parser fix (the printed column-number row "1 | 2 | 3 …" had been read as a district),
  there are **0 mismatches** across all tables. Log: `outputs/tables/parse_audit.csv`.
* **ABPS transaction identity.** Total ABPS transactions = processed + rejected holds for
  79% of district rows; the rest likely carry pending transactions. This is recorded, not
  corrected.
* **ABPS share of wages > 1.** 17–18 districts per year have ABPS amounts exceeding wages
  paid to accounts in R1.2.3. These are treated as data inconsistencies: excluded and counted
  (`outputs/stage0_summary_*.json`, `abps_flags`). One district per year has a zero-wage
  denominator.
* **Blanks.** Blank or non-numeric cells are kept as missing, never set to 0. True zeros
  stay zeros.

## 3. District geography

The MIS reports each FY on **that year's district list**. For example, Andhra Pradesh appears
with its 13 pre-2022 districts in FY2021–22 and 26 districts in later years. The
cross-sectional Stage-0 tests match exposure and readiness within the same FY, so they need no
crosswalk. The deletion panel does: districts created by splits are listed in
`outputs/tables/deletions_unmatched_districts.csv` and are excluded (not imputed) until the
LGD-code crosswalk is built in Month 2.

## 4. Facts in the one-pager, checked against primary sources

| Claim | Status | Source |
|---|---|---|
| First ABPS order on 30 Jan 2023 | Confirmed | MoRD order, reported widely, e.g. Deccan Herald (1 Jan 2024); J. Drèze, *Mainstream* (Jun 2023) |
| Extensions during 2023; mixed NACH/ABPS route allowed until 31 Dec 2023 | Confirmed (fifth extension, announced 30 Aug 2023) | MoRD statement, reported by ETV Bharat and IANS (30 Aug 2023) |
| Guidance that a job card should not be deleted only because a worker is not ABPS-eligible | Confirmed | MoRD statement (Oct 2023), reported by Housing.com (10 Oct 2023) |
| 8,617,887 and 6,886,532 *active* workers deleted/cancelled in FY2022–23 and FY2023–24 | Confirmed exactly; state annexure saved in `data/reference/` | Lok Sabha Unstarred Q. 294, 4 Feb 2025 |

**Definitional note to carry into the outcome.** Two official deletion series exist: *all*
workers deleted (14.95M in FY2021–22 and 51.89M in FY2022–23, Lok Sabha July 2023) and *active*
workers deleted (8.62M in FY2022–23). The MIS report we use counts *all* registered workers. The
outcome is therefore "all-worker deletions per 1,000 non-deleted registered workers at the start
of the year". The active-worker figures serve as a state-level cross-check.
