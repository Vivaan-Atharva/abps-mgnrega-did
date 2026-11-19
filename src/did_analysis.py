"""
Stage 1: difference-in-differences of worker deletions on ABPS conversion friction.

Implements the four design changes fixed after Stage 0 (protocol v2):
  1. Main treatment = high-friction indicator (top within-state decile of FY2020-21 exposure);
     within-state exposure quartiles and the continuous share are secondary.
  2. Joint-account share is reported as the leading component; the direct readiness measure
     (1 - FY2021-22 ABPS share of wages) is the alternative exposure.
  3. Every reduced-form estimate sits beside its first stage; a Wald-DiD rescales the
     high-friction estimate per 10-point lower ABPS share, with a state-cluster bootstrap CI.
  4. Pre-period guard: event-study leads, an exposure-specific-trend check, and a
     timing-shift check that drops FY2021-22.

Outcome: all-worker deletions per 1,000 non-deleted registered workers at the start of the FY
(OLS, district FE + state-by-year FE, SEs clustered by state). PPML on the deletion count with
log(start-of-year stock) as offset is the count-model robustness check.

Post period = FY2022-23 onward (ABPS order of 30 Jan 2023 falls in FY2022-23; mandate binding
from 1 Jan 2024 falls in FY2023-24). Reference year for the event study = FY2021-22.

Usage: python src/did_analysis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fe_ols import feols, ppml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TAB, FIG = ROOT / "outputs" / "tables", ROOT / "outputs" / "figures"
for p in (TAB, FIG):
    p.mkdir(parents=True, exist_ok=True)

POST_START = "2022-2023"
REF_YEAR = "2021-2022"
BLUE, ORANGE, INK2, MUTED, GRID = "#2a78d6", "#eb6834", "#4A5260", "#8A909A", "#E4E2DC"


def zstd(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def build_panel() -> tuple[pd.DataFrame, dict]:
    p = pd.read_csv(ROOT / "data" / "processed" / "deletions_district_panel.csv")
    e = pd.read_csv(ROOT / "data" / "processed" / "stage0_analysis_frame_2020-2021.csv")
    e = e[["state", "district", "expo", "po_share", "joint_share", "abps_share@2020-2021", "abps_share@2021-2022"]]
    # high-friction = top within-state decile; only states with >= 5 districts can define a decile
    e["n_state"] = e.groupby("state").district.transform("size")
    e["pct"] = e.groupby("state").expo.rank(pct=True, method="average")
    e["high"] = ((e.pct > 0.9) & (e.n_state >= 5)).astype(float)
    e["quart"] = np.ceil(4 * e.pct).clip(1, 4).astype(int)
    e["readiness_gap"] = 1 - e["abps_share@2021-2022"]
    d = p.merge(e, on=["state", "district"], how="inner")
    info = {"panel_rows_before_merge": int(len(p)), "rows_matched_to_exposure": int(len(d))}
    d["post"] = (d.fy >= POST_START).astype(float)
    d["state_year"] = d.state + "_" + d.fy
    # outcome: negative net deletions (restorations / record revisions) are excluded, counted
    info["negative_rows_excluded"] = int(d.neg_flag.sum())
    d = d[~d.neg_flag].copy()
    lo, hi = d.del_rate_per_1000.quantile([0.01, 0.99])
    d["rate_w"] = d.del_rate_per_1000.clip(lo, hi)
    info["winsor_bounds_per_1000"] = [float(lo), float(hi)]
    d["log_stock"] = np.log(d.stock_start)
    d["deletions"] = d.worker_deletions.clip(lower=0)
    for v in ("expo", "joint_share", "po_share", "readiness_gap"):
        d[f"{v}_z"] = zstd(d[v])
    d["high_post"] = d.high * d.post
    for q in (2, 3, 4):
        d[f"q{q}_post"] = (d.quart == q).astype(float) * d.post
    for v in ("expo_z", "joint_share_z", "po_share_z", "readiness_gap_z"):
        d[f"{v}_post"] = d[v] * d.post
    years = sorted(d.fy.unique())
    info["years"] = years
    info["districts"] = int(d.district.nunique())
    info["states"] = int(d.state.nunique())
    info["high_friction_districts"] = int(d.drop_duplicates(["state", "district"]).high.sum())
    return d, info


def row(name: str, r, var: str, extra: dict | None = None) -> dict:
    out = {"spec": name, "coef": r.params[var], "se": r.se[var], "p": r.pvalue[var],
           "ci_lo": r.params[var] - 1.96 * r.se[var], "ci_hi": r.params[var] + 1.96 * r.se[var],
           "N": r.nobs, "clusters": r.n_clusters}
    out.update(extra or {})
    return out


def main() -> dict:
    d, info = build_panel()
    FE = ["district", "state_year"]
    rows = []
    pre_mean_high = d[(d.post == 0) & (d.high == 1)].rate_w.mean()
    info["pre_mean_rate_high"] = float(pre_mean_high)
    info["pre_mean_rate_all"] = float(d[d.post == 0].rate_w.mean())
    info["post_mean_rate_all"] = float(d[d.post == 1].rate_w.mean())

    # (1) main: high-friction indicator
    r = feols(d, "rate_w", ["high_post"], fe=FE, cluster="state")
    rows.append(row("Main: high-friction × post (per 1,000)", r, "high_post"))
    main_b, main_se = r.params["high_post"], r.se["high_post"]
    # (2) quartiles
    rq = feols(d, "rate_w", ["q2_post", "q3_post", "q4_post"], fe=FE, cluster="state")
    for q in (2, 3, 4):
        rows.append(row(f"Quartile {q} vs Q1 × post", rq, f"q{q}_post"))
    # (3) continuous exposures (per SD)
    for v, lab in (("expo_z", "Continuous exposure (per SD) × post"),
                   ("joint_share_z", "Joint-account share (per SD) × post"),
                   ("po_share_z", "Post-office share (per SD) × post"),
                   ("readiness_gap_z", "Direct: 1 − FY2021–22 ABPS share (per SD) × post")):
        rv = feols(d, "rate_w", [f"{v}_post"], fe=FE, cluster="state")
        rows.append(row(lab, rv, f"{v}_post"))
    # (4) pre-period guards
    dn = d[d.fy != REF_YEAR]
    rt = feols(dn, "rate_w", ["high_post"], fe=FE, cluster="state")
    rows.append(row("Timing check: drop FY2021–22", rt, "high_post"))
    d["trend"] = d.fy.str[:4].astype(int) - 2019
    d["high_trend"] = d.high * d.trend
    rtr = feols(d, "rate_w", ["high_post", "high_trend"], fe=FE, cluster="state")
    rows.append(row("With high-friction linear trend", rtr, "high_post"))
    dpre = d[d.post == 0].copy()
    dpre["placebo"] = dpre.high * (dpre.fy == REF_YEAR)
    rpl = feols(dpre, "rate_w", ["placebo"], fe=FE, cluster="state")
    rows.append(row("Placebo: FY2021–22 as fake post (pre years only)", rpl, "placebo"))
    # (5) PPML count model
    rp = ppml(d, "deletions", ["high_post"], fe=FE, cluster="state", offset="log_stock")
    rows.append(row("PPML count, offset log stock (semi-elasticity)", rp, "high_post",
                    {"pct_effect": float(np.expm1(rp.params["high_post"]) * 100)}))
    rpc = ppml(d, "deletions", ["expo_z_post"], fe=FE, cluster="state", offset="log_stock")
    rows.append(row("PPML count, continuous exposure (per SD)", rpc, "expo_z_post",
                    {"pct_effect": float(np.expm1(rpc.params["expo_z_post"]) * 100)}))
    # (6) raw (unwinsorised) outcome
    rr = feols(d, "del_rate_per_1000", ["high_post"], fe=FE, cluster="state")
    rows.append(row("Unwinsorised rate", rr, "high_post"))
    res = pd.DataFrame(rows)
    res.to_csv(TAB / "did_results.csv", index=False)

    # (7) event study
    years = sorted(d.fy.unique())
    ev_vars = []
    for y in years:
        if y == REF_YEAR:
            continue
        c = f"ev_{y[:4]}"
        d[c] = d.high * (d.fy == y)
        ev_vars.append((y, c))
    re_ = feols(d, "rate_w", [c for _, c in ev_vars], fe=FE, cluster="state")
    ev = pd.DataFrame([{"fy": y, "coef": re_.params[c], "se": re_.se[c], "p": re_.pvalue[c]} for y, c in ev_vars]
                      + [{"fy": REF_YEAR, "coef": 0.0, "se": 0.0, "p": np.nan}]).sort_values("fy")
    ev.to_csv(TAB / "did_event_study.csv", index=False)
    lead_vars = [c for y, c in ev_vars if y < REF_YEAR]
    # joint test of leads = 0 (Wald, cluster-robust)
    if lead_vars:
        b = re_.params[lead_vars].to_numpy()
        se = re_.se[lead_vars].to_numpy()
        info["lead_coefs"] = dict(zip(lead_vars, b.round(3).tolist()))
        info["max_abs_lead_t"] = float(np.max(np.abs(b / se)))

    # (8) first stage + Wald-DiD with state-cluster bootstrap
    st = d.drop_duplicates(["state", "district"])[["state", "district", "high", "abps_share@2020-2021"]].dropna()
    st["abps_pct"] = 100 * st["abps_share@2020-2021"]
    st = st[st["abps_share@2020-2021"] <= 1.05]
    fs = feols(st, "abps_pct", ["high"], fe=["state"], cluster="state")
    pi, pi_se = fs.params["high"], fs.se["high"]
    info["first_stage_pp"] = float(pi)
    info["first_stage_se"] = float(pi_se)
    info["first_stage_F"] = float((pi / pi_se) ** 2)
    wald = main_b / (-pi / 10)  # per 10-pp LOWER ABPS share
    rng = np.random.default_rng(2026)
    states = d.state.unique()
    boot = []
    for _ in range(300):
        pick = rng.choice(states, size=len(states), replace=True)
        parts_d, parts_s = [], []
        for i, s_ in enumerate(pick):
            a = d[d.state == s_].copy(); a["state"] = f"{s_}#{i}"; a["district"] = a.district + f"#{i}"
            a["state_year"] = a.state + "_" + a.fy
            b_ = st[st.state == s_].copy(); b_["state"] = f"{s_}#{i}"
            parts_d.append(a); parts_s.append(b_)
        bd, bs = pd.concat(parts_d), pd.concat(parts_s)
        if bd.high_post.sum() == 0 or bs.high.sum() == 0:
            continue
        try:
            rb = feols(bd, "rate_w", ["high_post"], fe=FE)
            fb = feols(bs, "abps_pct", ["high"], fe=["state"])
            if abs(fb.params["high"]) > 1e-6:
                boot.append(rb.params["high_post"] / (-fb.params["high"] / 10))
        except Exception:
            continue
    boot = np.array(boot)
    info["wald_did_per_10pp"] = float(wald)
    info["wald_boot_ci95"] = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))] if len(boot) > 50 else None
    info["wald_boot_reps"] = int(len(boot))

    # figure: event study
    fig, ax = plt.subplots(figsize=(11.5, 6.0), dpi=170)
    x = np.arange(len(ev))
    ax.axhline(0, color=MUTED, lw=1.2)
    post_mask = ev.fy >= POST_START
    ax.axvspan(x[post_mask.to_numpy()].min() - 0.5 if post_mask.any() else len(ev), len(ev) - 0.5, color="#F3E6DD", zorder=0)
    ax.errorbar(x, ev.coef, yerr=1.96 * ev.se, fmt="o", ms=10, color=BLUE, ecolor=BLUE, elinewidth=2.4, capsize=0, zorder=3)
    for xi, (_, r_) in zip(x, ev.iterrows()):
        lab = "ref." if r_.fy == REF_YEAR else f"{r_.coef:+.1f}"
        ax.annotate(lab, (xi, r_.coef), xytext=(14, 0), textcoords="offset points", va="center", fontsize=13, color=INK2)
    ax.set_xticks(x, [f"FY{f[:4]}–{f[-2:]}" for f in ev.fy])
    ax.set_ylabel("High-friction minus other districts\n(deletions per 1,000 workers, 95% CI)")
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.text(x[post_mask.to_numpy()].min() if post_mask.any() else 0, ax.get_ylim()[1] * 0.92, "  ABPS period", color="#B4461A", fontsize=13)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_event_study.png")
    plt.close(fig)

    # figure: national level (left) and within-state gap (right)
    g = d.groupby(["fy", "high"]).rate_w.mean().unstack()
    d["rate_ws"] = d.rate_w - d.groupby("state_year").rate_w.transform("mean")
    gw = d.groupby(["fy", "high"]).rate_ws.mean().unstack()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 6.0), dpi=170)
    xs = np.arange(len(g))
    labs = [f"FY{f[:4][2:]}–{f[-2:]}" for f in g.index]
    ax = axes[0]
    ax.plot(xs, g[1.0], "-o", color=ORANGE, lw=2.4, ms=9, label="High-friction (top within-state decile)")
    ax.plot(xs, g[0.0], "-o", color=BLUE, lw=2.4, ms=9, label="Other districts")
    ax.set_xticks(xs, labs)
    ax.set_title("Mean deletions per 1,000 workers", fontsize=14, loc="left")
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", fontsize=12)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax = axes[1]
    ax.axhline(0, color=MUTED, lw=1.2)
    ax.plot(xs, gw[1.0], "-o", color=ORANGE, lw=2.4, ms=9)
    ax.plot(xs, gw[0.0], "-o", color=BLUE, lw=2.4, ms=9)
    ax.set_xticks(xs, labs)
    ax.set_title("Same, minus own state-year mean", fontsize=14, loc="left")
    (TAB / "did_group_means.csv").write_text(pd.concat({"mean": g, "within_state": gw}, axis=1).to_csv())
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_raw_trends.png")
    plt.close(fig)


    info["main"] = {"coef": float(main_b), "se": float(main_se), "p": float(res.iloc[0].p)}
    (ROOT / "outputs" / "did_summary.json").write_text(json.dumps(info, indent=2, default=float))
    return {"info": info, "res": res, "ev": ev}


if __name__ == "__main__":
    out = main()
    pd.set_option("display.width", 200)
    print(out["res"][["spec", "coef", "se", "p", "N", "clusters"]].round(3).to_string())
    print(out["ev"].round(3).to_string())
    print(json.dumps(out["info"], indent=1, default=float))
