"""
Stage 0: does the FY2020-21 account-mix exposure actually track ABPS conversion friction?

Implements docs/stage0_proxy_validation_protocol.md (tests V1-V6). Uses only the
exposure, ABPS-readiness measures and pre-period covariates. It never touches
post-period deletion outcomes.

Usage:  python src/stage0_validation.py [--base-fy 2020-2021]
Outputs: outputs/tables/stage0_*.csv, outputs/stage0_summary.json, outputs/figures/stage0_*.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fe_ols import feols  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data" / "interim"
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
for p in (TAB, FIG):
    p.mkdir(parents=True, exist_ok=True)

# Flags are applied, counted and reported. Nothing is silently recoded.
SHARE_MAX = 1.05  # an ABPS share of wages above this is a data inconsistency, so the row is excluded and counted


# --------------------------------------------------------------------------- builders
def exposure(acc: pd.DataFrame, fy: str) -> pd.DataFrame:
    a = acc[acc.fy == fy].copy()
    a = a[a.tot_accounts > 0]
    a["po_share"] = (a.po_ind + a.po_joint) / a.tot_accounts
    a["joint_share"] = (a.bank_joint + a.po_joint) / a.tot_accounts
    a["expo"] = (a.po_ind + a.po_joint + a.bank_joint) / a.tot_accounts  # PO or joint (union)
    return a[["state", "district", "fy", "tot_accounts", "tot_amt_lakh", "po_share", "joint_share", "expo"]]


def abps_readiness(abps: pd.DataFrame, acc: pd.DataFrame, fy: str) -> tuple[pd.DataFrame, dict]:
    b = abps[abps.fy == fy].copy()
    amt = [c for c in b.columns if c.endswith("proc_amt")]
    rej = [c for c in b.columns if c.endswith("rej_n")]
    b["abps_amt_rs"] = b[amt].sum(axis=1, min_count=1)
    b["abps_rej_n"] = b[rej].sum(axis=1, min_count=1)
    w = acc[acc.fy == fy][["state", "district", "tot_amt_lakh"]]
    m = b.merge(w, on=["state", "district"], how="inner")
    m["abps_share"] = m.abps_amt_rs / (m.tot_amt_lakh * 1e5)
    m["abps_rej_rate"] = np.where(m.abps_txn_total > 0, m.abps_rej_n / m.abps_txn_total, np.nan)
    flags = {"fy": fy, "rows": len(m),
             "share_gt_max": int((m.abps_share > SHARE_MAX).sum()),
             "zero_wage_denominator": int((m.tot_amt_lakh <= 0).sum())}
    m.loc[(m.abps_share > SHARE_MAX) | (m.tot_amt_lakh <= 0), "abps_share"] = np.nan
    return m[["state", "district", "abps_share", "abps_rej_rate", "abps_txn_total"]], flags


def current_readiness(auth: pd.DataFrame, npci: pd.DataFrame) -> pd.DataFrame:
    a = auth.copy()
    a["not_abps_eligible"] = 1 - a.abps_eligible / a.workers_total
    a["seeded_not_eligible"] = (a.aadhaar_seeded - a.abps_eligible) / a.aadhaar_seeded
    n = npci.copy()
    n["npci_failure"] = n.npci_total_failure / n.sent_npci
    out = a[["state", "district", "not_abps_eligible", "seeded_not_eligible"]].merge(
        n[["state", "district", "npci_failure"]], on=["state", "district"], how="outer")
    return out.replace([np.inf, -np.inf], np.nan)


def zstd(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def within_rank(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("state")[col].rank(pct=True)


# --------------------------------------------------------------------------- tests
EXPECTED_SIGN = {"abps_share": -1, "abps_rej_rate": +1, "not_abps_eligible": +1,
                 "seeded_not_eligible": +1, "npci_failure": +1}
LABEL = {"abps_share": "ABPS share of wages", "abps_rej_rate": "ABPS rejection rate",
         "not_abps_eligible": "Share not ABPS-eligible (current)",
         "seeded_not_eligible": "Seeded but not eligible (current)",
         "npci_failure": "NPCI mapper failure (current)"}


def v1_relevance(df: pd.DataFrame, ys: list[str], xvar: str, tag: str) -> pd.DataFrame:
    rows = []
    for y in ys:
        d = df[["state", "district", xvar, y]].dropna().copy()
        # only states with >= 2 districts contribute within-state variation
        d = d[d.groupby("state")[y].transform("size") >= 2]
        if len(d) < 30:
            continue
        d["x_z"] = zstd(d[xvar])
        d["y_z"] = zstd(d[y])
        r = feols(d, "y_z", ["x_z"], fe=["state"], cluster="state")
        b, se, p = r.params["x_z"], r.se["x_z"], r.pvalue["x_z"]
        sign_ok = np.sign(b) == EXPECTED_SIGN[y.split("@")[0]]
        rows.append({"spec": tag, "readiness": y, "exposure": xvar, "coef_sd": b, "se": se, "p": p,
                     "F_eff": (b / se) ** 2, "N": r.nobs, "states": r.n_clusters,
                     "within_r2": r.r2_within, "expected_sign": EXPECTED_SIGN[y.split("@")[0]],
                     "sign_ok": bool(sign_ok),
                     "pass": bool(sign_ok and p < 0.05 and (b / se) ** 2 >= 10)})
    return pd.DataFrame(rows)


def v2_components(df: pd.DataFrame, ys: list[str]) -> pd.DataFrame:
    rows = []
    for y in ys:
        d = df[["state", "district", "po_share", "joint_share", y]].dropna().copy()
        d = d[d.groupby("state")[y].transform("size") >= 2]
        if len(d) < 30:
            continue
        d["po_z"], d["joint_z"], d["y_z"] = zstd(d.po_share), zstd(d.joint_share), zstd(d[y])
        r = feols(d, "y_z", ["po_z", "joint_z"], fe=["state"], cluster="state")
        for v in ("po_z", "joint_z"):
            rows.append({"readiness": y, "component": v.replace("_z", "_share"), "coef_sd": r.params[v],
                         "se": r.se[v], "p": r.pvalue[v], "N": r.nobs, "states": r.n_clusters})
    return pd.DataFrame(rows)


def v3_variation(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for c in cols:
        x = df[c].dropna()
        w = df[c] - df.groupby("state")[c].transform("mean")
        rows.append({"variable": c, "N": len(x), "mean": x.mean(), "median": x.median(),
                     "sd": x.std(), "within_state_sd": w.std(), "within_share_of_var": w.var() / x.var(),
                     "share_zero": (x == 0).mean(), "p90": x.quantile(0.9), "max": x.max()})
    return pd.DataFrame(rows)


def v4_stability(acc: pd.DataFrame, base_fy: str) -> pd.DataFrame:
    base = exposure(acc, base_fy)[["state", "district", "expo", "po_share", "joint_share"]]
    rows = []
    for fy in sorted(acc.fy.unique()):
        if fy == base_fy:
            continue
        o = exposure(acc, fy)[["state", "district", "expo", "po_share", "joint_share"]]
        m = base.merge(o, on=["state", "district"], suffixes=("_base", "_other"))
        for v in ("expo", "po_share", "joint_share"):
            rows.append({"base_fy": base_fy, "other_fy": fy, "variable": v, "N_matched": len(m),
                         "pearson_r": m[f"{v}_base"].corr(m[f"{v}_other"]),
                         "spearman_r": m[f"{v}_base"].corr(m[f"{v}_other"], method="spearman"),
                         "pass_r_ge_0.8": bool(m[f"{v}_base"].corr(m[f"{v}_other"]) >= 0.8)})
    return pd.DataFrame(rows)


def v5_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Exposure vs PRE-period deletion-rate levels (FY2019-20 to FY2021-22) and register size.
    Descriptive balance only: coefficients are reported, never 'tested away'."""
    path = ROOT / "data" / "processed" / "deletions_district_panel.csv"
    if not path.exists():
        return pd.DataFrame()
    p = pd.read_csv(path)
    p = p[(p.fy <= "2021-2022") & (~p.neg_flag)]
    rows = []
    for fy, g in p.groupby("fy"):
        d = df[["state", "district", "expo"]].merge(g[["state", "district", "del_rate_per_1000", "stock_start"]],
                                                    on=["state", "district"], how="inner")
        d = d.replace([np.inf, -np.inf], np.nan).dropna()
        d = d[d.groupby("state").expo.transform("size") >= 2]
        for y in ("del_rate_per_1000", "log_stock"):
            if y == "log_stock":
                d["log_stock"] = np.log(d.stock_start)
            dd = d.copy()
            # winsorise the outcome at 1/99 for this descriptive check (raw kept in the panel)
            lo, hi = dd[y].quantile([0.01, 0.99])
            dd["y_w"] = dd[y].clip(lo, hi)
            dd["x_z"], dd["y_z"] = zstd(dd.expo), zstd(dd.y_w)
            r = feols(dd, "y_z", ["x_z"], fe=["state"], cluster="state")
            rows.append({"pre_fy": fy, "covariate": y, "coef_sd": r.params["x_z"], "se": r.se["x_z"],
                         "p": r.pvalue["x_z"], "N": r.nobs, "states": r.n_clusters})
    return pd.DataFrame(rows)


def v6_leave_one_state_out(df: pd.DataFrame, y: str, xvar: str) -> pd.DataFrame:
    rows = []
    d0 = df[["state", "district", xvar, y]].dropna()
    for s in sorted(d0.state.unique()):
        d = d0[d0.state != s].copy()
        d = d[d.groupby("state")[y].transform("size") >= 2]
        d["x_z"], d["y_z"] = zstd(d[xvar]), zstd(d[y])
        r = feols(d, "y_z", ["x_z"], fe=["state"], cluster="state")
        rows.append({"dropped_state": s, "coef_sd": r.params["x_z"], "se": r.se["x_z"], "p": r.pvalue["x_z"], "N": r.nobs})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- figures
def binscatter(df: pd.DataFrame, x: str, y: str, path: Path, title: str, nbins: int = 20) -> None:
    d = df[["state", x, y]].dropna().copy()
    d["xr"] = d[x] - d.groupby("state")[x].transform("mean") + d[x].mean()
    d["yr"] = d[y] - d.groupby("state")[y].transform("mean") + d[y].mean()
    d["bin"] = pd.qcut(d.xr.rank(method="first"), nbins, labels=False)
    g = d.groupby("bin")[["xr", "yr"]].mean()
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=160)
    ax.scatter(d.xr, d.yr, s=6, alpha=0.18, color="#8a8f98", linewidths=0)
    ax.scatter(g.xr, g.yr, s=28, color="#2b5fab", zorder=3)
    k = np.polyfit(d.xr, d.yr, 1)
    xs = np.linspace(d.xr.quantile(0.01), d.xr.quantile(0.99), 50)
    ax.plot(xs, np.polyval(k, xs), color="#2b5fab", lw=1.5)
    ax.set_xlim(d.xr.quantile(0.005), d.xr.quantile(0.995))
    ax.set_xlabel("Exposure: PO-or-joint share of accounts (within-state, re-centred)")
    ax.set_ylabel(LABEL.get(y.split("@")[0], y) + " (within-state)")
    ax.set_title(title, fontsize=10, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- main
def main(base_fy: str) -> dict:
    acc = pd.read_csv(INT / "mis_acc_district.csv")
    abps = pd.read_csv(INT / "mis_abps_district.csv")
    auth = pd.read_csv(INT / "mis_auth_district.csv")
    npci = pd.read_csv(INT / "mis_npci_district.csv")

    ex = exposure(acc, base_fy)
    ex["expo_rank"] = within_rank(ex, "expo")
    ex["expo_asinh"] = np.arcsinh(100 * ex.expo)

    # readiness: pre-mandate FY ABPS use (same-FY district master as exposure), plus current snapshot
    flags = []
    df = ex.copy()
    ready_cols = []
    for fy in sorted(abps.fy.unique()):
        r, f = abps_readiness(abps, acc if fy in acc.fy.unique() else acc, fy)
        if fy not in acc.fy.unique():
            continue  # need same-FY wage denominator
        flags.append(f)
        r = r.rename(columns={"abps_share": f"abps_share@{fy}", "abps_rej_rate": f"abps_rej_rate@{fy}",
                              "abps_txn_total": f"abps_txn@{fy}"})
        df = df.merge(r, on=["state", "district"], how="left")
        ready_cols += [f"abps_share@{fy}", f"abps_rej_rate@{fy}"]
    cur = current_readiness(auth, npci)
    n_before = len(df)
    df = df.merge(cur, on=["state", "district"], how="left")
    cur_match = int(df["not_abps_eligible"].notna().sum())
    ready_cols += ["not_abps_eligible", "seeded_not_eligible", "npci_failure"]

    # Tests
    v1 = pd.concat([v1_relevance(df, ready_cols, "expo", "primary: expo (z)"),
                    v1_relevance(df, ready_cols, "expo_rank", "robust: within-state rank"),
                    v1_relevance(df, ready_cols, "expo_asinh", "robust: asinh(100*expo)")], ignore_index=True)
    v2 = v2_components(df, ready_cols)
    v3 = v3_variation(df, ["expo", "po_share", "joint_share"] + ready_cols)
    v4 = v4_stability(acc, base_fy)
    prim = [c for c in ready_cols if c.startswith("abps_share@")]
    key_y = None
    if len(v1):
        cand = v1[(v1.spec.str.startswith("primary")) & (v1.readiness.isin(prim))]
        if len(cand):
            key_y = cand.sort_values("readiness").iloc[-1]["readiness"]  # latest pre-mandate FY
    v6 = v6_leave_one_state_out(df, key_y, "expo") if key_y else pd.DataFrame()

    v5 = v5_balance(df)
    for name, t in {"v1_relevance": v1, "v2_components": v2, "v3_variation": v3,
                    "v4_stability": v4, "v5_balance": v5, "v6_loso": v6}.items():
        t.to_csv(TAB / f"stage0_{name}_{base_fy}.csv", index=False)
    df.to_csv(ROOT / "data" / "processed" / f"stage0_analysis_frame_{base_fy}.csv", index=False)

    # figures
    for y in prim + ["not_abps_eligible"]:
        if y in df and df[y].notna().sum() > 30:
            binscatter(df, "expo", y, FIG / f"stage0_binscatter_{y.replace('@', '_')}_{base_fy}.png",
                       f"{LABEL.get(y.split('@')[0], y)} vs FY{base_fy} exposure (state FE removed)")

    # decision
    prim_v1 = v1[v1.spec.str.startswith("primary")] if len(v1) else v1
    pre_pass = prim_v1[prim_v1.readiness.str.contains("@") & prim_v1["pass"]] if len(prim_v1) else prim_v1
    any_pass = prim_v1[prim_v1["pass"]] if len(prim_v1) else prim_v1
    loso_stable = bool(len(v6) and (np.sign(v6.coef_sd) == np.sign(v6.coef_sd.median())).all())
    if len(pre_pass) and loso_stable:
        decision = "GO"
    elif len(prim_v1) and prim_v1.sign_ok.any():
        decision = "REVISE"
    else:
        decision = "NO-GO"
    summary = {"base_fy": base_fy, "n_districts_exposure": int(len(ex)),
               "current_snapshot_matched": cur_match, "of": n_before,
               "abps_flags": flags, "key_readiness_for_loso": key_y,
               "v1_primary_passes": any_pass[["readiness", "coef_sd", "p", "F_eff"]].to_dict("records") if len(any_pass) else [],
               "loso_sign_stable": loso_stable, "decision": decision}
    (ROOT / "outputs" / f"stage0_summary_{base_fy}.json").write_text(json.dumps(summary, indent=2, default=float))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-fy", default="2020-2021")
    s = main(ap.parse_args().base_fy)
    print(json.dumps(s, indent=2, default=float))
