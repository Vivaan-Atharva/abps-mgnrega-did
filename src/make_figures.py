"""
Figures for the Month-1 review (static PNGs, sized for 16:9 slides).

Palette: the dataviz reference palette's first two categorical slots (blue #2a78d6,
orange #eb6834), validated for CVD separation. Text stays in ink tones, never series colours.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TAB, FIG = ROOT / "outputs" / "tables", ROOT / "outputs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

BG = "#FBFAF7"
INK, INK2, MUTED, GRID = "#1B2230", "#4A5260", "#8A909A", "#E4E2DC"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 15, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": BG,
    "axes.facecolor": BG, "savefig.facecolor": BG, "axes.spines.top": False, "axes.spines.right": False,
})


def coef_by_spec(base_fy: str = "2020-2021") -> Path:
    v1 = pd.read_csv(TAB / f"stage0_v1_relevance_{base_fy}.csv")
    v1 = v1[v1.readiness.str.startswith("abps_share@")].copy()
    v1["year"] = v1.readiness.str.replace("abps_share@", "FY", regex=False).str.replace("-20", "–", regex=False)
    specs = [("primary: expo (z)", "Share (primary)", BLUE),
             ("robust: asinh(100*expo)", "asinh(share)", "#6b8fc0"),
             ("robust: within-state rank", "Within-state rank", ORANGE)]
    years = sorted(v1.year.unique())
    fig, ax = plt.subplots(figsize=(11.5, 6.0), dpi=170)
    off = {s[0]: o for s, o in zip(specs, (-0.22, 0, 0.22))}
    for spec, lab, col in specs:
        d = v1[v1.spec == spec].set_index("year").reindex(years)
        x = np.arange(len(years)) + off[spec]
        ax.errorbar(x, d.coef_sd, yerr=1.96 * d.se, fmt="o", ms=9, color=col, ecolor=col,
                    elinewidth=2.2, capsize=0, label=lab, zorder=3)
        for xi, (_, r) in zip(x, d.iterrows()):
            if spec.startswith("primary"):
                ax.annotate(f"F={r.F_eff:.0f}", (xi, r.coef_sd - 1.96 * r.se), xytext=(0, -20),
                            textcoords="offset points", ha="center", fontsize=12, color=INK2)
    ax.axhline(0, color=MUTED, lw=1.2)
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel("SD change in ABPS share of wages\nper 1 SD of exposure (95% CI)")
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower left", ncol=3, fontsize=13)
    ax.set_ylim(-0.32, 0.12)
    fig.tight_layout()
    p = FIG / "fig_v1_coef_by_spec.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def binscatter(base_fy: str = "2020-2021", yfy: str = "2020-2021", nbins: int = 20) -> Path:
    df = pd.read_csv(ROOT / "data" / "processed" / f"stage0_analysis_frame_{base_fy}.csv")
    y = f"abps_share@{yfy}"
    d = df[["state", "expo", y]].dropna().copy()
    d["xr"] = d.expo - d.groupby("state").expo.transform("mean") + d.expo.mean()
    d["yr"] = d[y] - d.groupby("state")[y].transform("mean") + d[y].mean()
    d["bin"] = pd.qcut(d.xr.rank(method="first"), nbins, labels=False)
    g = d.groupby("bin")[["xr", "yr"]].mean()
    fig, ax = plt.subplots(figsize=(11.5, 6.0), dpi=170)
    ax.scatter(100 * d.xr, 100 * d.yr, s=10, color=MUTED, alpha=0.25, linewidths=0, label="District")
    ax.scatter(100 * g.xr, 100 * g.yr, s=70, color=BLUE, zorder=3, edgecolors=BG, linewidths=1.5,
               label="Mean of 20 equal-count bins")
    k = np.polyfit(d.xr, d.yr, 1)
    xs = np.linspace(d.xr.quantile(0.01), d.xr.quantile(0.99), 50)
    ax.plot(100 * xs, 100 * np.polyval(k, xs), color=BLUE, lw=2)
    ax.set_xlim(100 * d.xr.quantile(0.003), 100 * d.xr.quantile(0.997))
    ax.set_ylim(-5, 105)
    ax.set_xlabel(f"Exposure: % of accounts that are post-office or joint, FY{base_fy[:4]}–{base_fy[-2:]}  (state means removed)")
    ax.set_ylabel(f"ABPS share of wages, FY{yfy[:4]}–{yfy[-2:]} (%)\n(state means removed)")
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper right", fontsize=13)
    fig.tight_layout()
    p = FIG / f"fig_v1_binscatter_{yfy}.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def exposure_hist(base_fy: str = "2020-2021") -> Path:
    df = pd.read_csv(ROOT / "data" / "processed" / f"stage0_analysis_frame_{base_fy}.csv")
    fig, ax = plt.subplots(figsize=(11.5, 5.6), dpi=170)
    bins = np.arange(0, 82, 2)
    ax.hist((100 * df.expo).clip(upper=80), bins=bins, color=BLUE, edgecolor=BG, linewidth=1.5)
    ax.set_xlabel(f"Exposure: % of accounts that are post-office or joint, FY{base_fy[:4]}–{base_fy[-2:]}")
    ax.set_ylabel("Districts")
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    med, p90 = df.expo.median(), df.expo.quantile(0.9)
    for v, lab in ((med, f"median {100*med:.1f}%"), (p90, f"90th pct {100*p90:.1f}%")):
        ax.axvline(100 * v, color=ORANGE, lw=2, ls="--")
        ax.annotate(lab, (100 * v, ax.get_ylim()[1] * 0.92), xytext=(8, 0), textcoords="offset points",
                    color=INK, fontsize=13)
    fig.tight_layout()
    p = FIG / "fig_exposure_hist.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def deletions_audit() -> Path:
    """National annual worker deletions from MIS cumulative stocks vs official all-worker totals."""
    import glob
    import json
    T = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "*.json"))):
        T.update(json.load(open(f))["tables"])
    cum = {}
    for k, t in T.items():
        if k.startswith("del_"):
            tot = [r for r in t["national"] if len(r) > 3 and r[1] == "Total"][0]
            cum[t["fy"]] = float(tot[7].replace(",", ""))
    fys = sorted(cum)
    ann = {fy: (cum[fy] - cum[p]) / 1e6 for p, fy in zip(fys, fys[1:])}
    official = {"2021-2022": 14.951247, "2022-2023": 51.891168}
    labs = [f"FY{fy[:4]}–{fy[-2:]}" for fy in ann]
    fig, ax = plt.subplots(figsize=(11.5, 6.0), dpi=170)
    x = np.arange(len(ann))
    ax.bar(x - 0.18, list(ann.values()), width=0.34, color=BLUE, label="MIS (rebuilt from cumulative stocks)")
    ov = [official.get(fy, np.nan) for fy in ann]
    ax.bar(x + 0.18, ov, width=0.34, color=ORANGE, label="Official, Lok Sabha reply (all workers)")
    for xi, v in zip(x, ann.values()):
        ax.annotate(f"{v:.1f}M", (xi - 0.18, v), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=13, color=INK)
    for xi, v in zip(x, ov):
        if not np.isnan(v):
            ax.annotate(f"{v:.1f}M", (xi + 0.18, v), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=13, color=INK)
    ax.set_xticks(x, labs)
    ax.set_ylabel("Workers deleted in the year (millions)")
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", fontsize=13)
    fig.tight_layout()
    p = FIG / "fig_deletions_audit.png"
    fig.savefig(p)
    plt.close(fig)
    return p


if __name__ == "__main__":
    for f in (coef_by_spec(), binscatter(), exposure_hist(), deletions_audit()):
        print(f)
