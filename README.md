# Did the ABPS rollout alter MGNREGA worker deletions?

ADA Jackfruit Project (UE24AM343AB1) · Team ByteMe · Vivaan Atharva (PES1UG24AM071) · Vivek Varma (PES1UG24AM070)

**Question.** In January 2023 MGNREGA wages had to move to the Aadhaar-Based Payment System (ABPS).
Worker deletions rose from 15.0M (FY2021–22) to 51.9M (FY2022–23). Did deletions rise more in
districts where converting worker accounts to ABPS was harder?

## Design

1. **Extract and audit.** 15 district-level tables from the MGNREGA MIS, FY2018–19 to FY2022–23,
   about 706 districts in 33 states. Every table's district rows sum exactly to its state totals.
   The rebuilt deletion counts match 97% of the official all-India figures.
2. **Stage 0: validate the exposure proxy.** The reviewer's point was that everything depends on
   the FY2020–21 post-office/joint-account share standing in for ABPS conversion friction. So the
   proxy is tested first (V1–V6), with GO/REVISE/NO-GO rules fixed in advance.
3. **Stage 1: difference-in-differences.** Top within-state decile of exposure (`high`) × post,
   with district and state×year fixed effects and SEs clustered by state. Alongside it: an event
   study, quartile and continuous versions, PPML, a Wald-DiD with a state-cluster bootstrap, and
   other robustness checks.

## Results

- **Stage 0: GO, but weak.** Within states, districts with more exposure used ABPS less before
  the mandate. No single state drives this, but within-state R² is only about 3%. In the top
  decile, ABPS use is 6.8 pp lower (first-stage F ≈ 9).
- **Stage 1: no detectable effect.** High-friction districts saw −1.2 deletions per 1,000
  workers relative to others (SE 9.3, p = 0.90; 95% CI about −19 to +17). 12 of the 14
  specifications are not significant. The leads show no clear pre-trend (max |t| = 1.4).
  High-friction districts already deleted more before ABPS (46.8 vs 34.1 per 1,000). That gap
  did not widen when the average rate jumped to 120 per 1,000.
- **Main limitation.** There is only one post year (FY2022–23). The ABPS order came late in that
  year and was binding only from January 2024. Adding FY2023–24 and FY2024–25 is the key next step.

## Repository layout

```
ByteMe_ABPS_MGNREGA.ipynb   the whole pipeline, run end to end with outputs (start here)
data/raw/                   MIS tables exactly as served, 3 JSON parts (the only input needed)
data/reference/             Lok Sabha USQ 294 (4 Feb 2025) state deletions, used as a cross-check
data/interim/, processed/   tidy tables and analysis panels (generated)
data/README.md              dataset dictionary and handling rules
src/                        parse_mis, build_deletions, fe_ols (FE-OLS + PPML), stage0_validation,
                            stage0_explore_tail, did_analysis, make_figures
tests/test_fe_ols.py        estimators recover known effects on simulated data
docs/                       Stage 0 protocol (v1.1 with amendment log), data audit
outputs/                    every table, figure and summary JSON
tools/                      builders for the notebook, slides, design diagram and demo video
deliverables/               one-pager, slides, IEEE-style report (PDF + LaTeX), demo video
```

## Rerun

Python 3.11+ with pandas, numpy, scipy and matplotlib. No statsmodels is needed, because the
estimators are in `src/fe_ols.py`.

```
python tests/test_fe_ols.py
python src/parse_mis.py
python src/build_deletions.py
python src/stage0_validation.py --base-fy 2020-2021
python src/stage0_explore_tail.py   # exploratory, labelled as such
python src/did_analysis.py
python src/make_figures.py
```

Or open `ByteMe_ABPS_MGNREGA.ipynb` and run all cells.

## Data source

MGNREGA MIS (NREGASoft), Ministry of Rural Development,
`https://mnregaweb4.dord.gov.in/netnregarep/MISreport4.aspx`. State = ALL, drilled to district
level, pulled 29 Oct 2026. The data are public and district-level, with no personal records. See
`docs/data_audit.md` for which reports are year-specific and which are only a current snapshot.
