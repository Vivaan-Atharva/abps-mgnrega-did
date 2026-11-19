# Stage 0 — Exposure-Proxy Validation Protocol

**Project:** Did the ABPS Rollout Alter MGNREGA Worker Deletions? (ADA Jackfruit Project, UE24AM343AB1)
**Status:** Pre-specified before any post-period outcome is regressed on the exposure.
**Version:** 1.0 (Month-1 review)

## 1. Why this stage exists

Reviewer feedback on the one-pager:

> "Your entire causal claim rests on the unproven assumption that 2020–21 joint account shares
> accurately proxy ABPS conversion friction; you must validate this empirically before running the DiD."

We accept the point. In the one-pager design, the DiD coefficient on
`exposure_d × post_t` is a *reduced form*: it measures how deletions moved with the
FY2020–21 account mix, not with conversion friction itself. It speaks to friction only
if the account mix actually predicts how hard it was to make a district's workers
ABPS-eligible. So the proxy has to pass a "first stage" before the reduced form is run.

## 2. The construct and the proxy

**Construct (what we want):** *ABPS conversion friction* is how hard it is to complete
the three linkages ABPS requires for each worker: (i) Aadhaar seeded to the job card,
(ii) Aadhaar seeded to the worker's bank account (with eKYC), and (iii) that Aadhaar
mapped to the right bank in the NPCI mapper.

**Proxy (what we observe):** the FY2020–21 share of workers' accounts that are
post-office accounts or joint accounts (MIS report R1.2.3, district level).

**Why the proxy could work.** Two mechanisms:

* *Post-office accounts.* A post-office account is a separate route from ordinary banks,
  so a worker paid there may have to open or seed a new account before an NPCI
  mapping exists.
* *Joint accounts.* The NPCI mapper links an Aadhaar number to a bank, not to a shared
  account. So a joint account can carry the ABPS mapping of at most one holder.

**Why the proxy could fail.**

* The account mix may mainly track remoteness, poverty or state banking policy. Those
  are confounders, not friction.
* Post-office accounts are concentrated in a few states, so the within-state variation
  that state-by-year fixed effects leave behind may be tiny.
* Account counts may be stale records that no longer match where wages are actually paid.

## 3. Pre-specified tests

All tests are district-level cross-sections or short panels. They include **state
fixed effects** (the main DiD absorbs state-by-year shocks, so only within-state
variation matters) and use **standard errors clustered by state**. The exposure is
standardised to SD = 1 within the estimation sample.

| ID | Question | Readiness measure (y) | Pass rule |
|----|----------|------------------------|-----------|
| **V1 Relevance** | Does higher exposure predict *more* ABPS friction, within state? | (a) Share of registered workers whose Aadhaar is **not** NPCI-mapped / ABPS-ineligible, at the earliest snapshot available<br>(b) ABPS share of wage transactions in a pre-mandate year (FY2021–22) and the first mandate year (FY2022–23)<br>(c) Gap between Aadhaar-seeded and ABPS-eligible workers | Coefficient has the hypothesised sign, p < 0.05, and effective F = t² ≥ 10 on at least one of (a)–(c). |
| **V2 Components** | Do the post-office and joint components each carry the signal? | Same as V1 | Reported separately. A component with the wrong sign or no signal is dropped from the exposure. This rule is fixed now so the choice can't be tuned later. |
| **V3 Within-state variation** | Is there enough exposure variation left after state FE? | Exposure only | Within-state SD and the share of total variance that is within-state are reported. If the within-state share is < 10%, the state-by-year design is underpowered for this exposure. |
| **V4 Stability** | Is the proxy a stable district trait or noise? | Exposure in FY2018–19, 2019–20, 2021–22 | Pearson r with FY2020–21 ≥ 0.8. A low r means the base-year choice matters and must be justified. |
| **V5 Discriminant / balance** | Is the proxy just standing in for something else? | Pre-period covariates: ST/SC share of workers, registered workers per household, pre-period deletion rates (levels only) | Standardised differences reported, never "tested away". Strong correlations become required controls (interacted with post) in the main DiD. |
| **V6 Robustness of V1** | Is V1 driven by one state? | Same as V1 | V1 sign stable when each state is dropped in turn (leave-one-state-out). |

**Decision rule (fixed before seeing results):**

* **GO.** V1 passes and V6 holds. The DiD uses the account-mix exposure as planned, and
  the event study is reported with the first stage alongside.
* **REVISE.** Right sign, but F < 10 or not robust. The main exposure switches to the
  *direct* readiness measure (a or b). The account mix is kept as a secondary or
  instrumental exposure.
* **NO-GO.** Wrong sign or null. The account-mix proxy is abandoned, and results are
  reported only for the direct readiness measure, as associations.

## 4. What we deliberately do *not* do in Stage 0

We do **not** regress post-period (FY2022–23 onward) deletions on the exposure until
Stage 0 is complete. Outcome data are extracted and quality-audited (definitions,
missingness, crosswalk), but the treatment-effect estimate stays unseen. That way the
validation result cannot be tuned to the answer we want.

## 5. Known threats to the validation itself

1. **Post-treatment contamination of readiness measures.** ABPS-eligibility shares
   measured after FY2022–23 are mechanically raised when ineligible workers are
   deleted. A high-deletion district can look "ready" *because* it deleted. We
   therefore (i) prefer the earliest snapshot, (ii) use measures over *registered*
   workers where available, and (iii) report the direction of the bias: it pushes V1
   toward zero, so it makes the test conservative.
2. **Snapshot vs year-specific reports.** Some MIS tables recompute from today's database
   whatever financial year is selected. Each table's year behaviour is checked
   empirically and recorded in `docs/data_audit.md`.
3. **District boundary changes.** Districts are matched across years through a
   documented crosswalk. Splits after FY2020–21 inherit the parent district's exposure
   and are flagged.

## 5a. Amendment log

| Date | Change | What had been seen at that point |
|------|--------|----------------------------------|
| 29 Oct 2026, v1.1 | Added two robustness forms of the exposure to V1: the within-state percentile rank and asinh(100 × share). Rows with an ABPS share of wages above 1.05 are excluded and counted, as a data inconsistency. The primary specification is unchanged. | Univariate distributions only. The exposure is zero-inflated and right-skewed: a third of districts have no post-office accounts. No exposure–readiness relationship had been estimated. |
| 29 Oct 2026, v1.1 | Readiness measure (b) is defined as the ABPS processed amount ÷ total wages paid to accounts in the same FY (both from the MIS). The FY2022–23 ABPS report covers only 4 states, so the pre-mandate years FY2018–19 to FY2021–22 are used. | Report coverage only. |

## 6. How a validated proxy is used later

If V1 passes, the main DiD coefficient β_RF (reduced form) can be scaled by the first
stage π (proxy → friction) to give an effect per unit of friction, β_RF / π. This is
the Wald-DiD logic of fuzzy difference-in-differences (de Chaisemartin & D'Haultfœuille, 2018,
*Review of Economic Studies*). With a continuous dose, interpreting differences across
dose levels as causal needs a stronger parallel-trends condition (Callaway,
Goodman-Bacon & Sant'Anna, 2024). We will state that assumption explicitly rather than
leave it implicit.
