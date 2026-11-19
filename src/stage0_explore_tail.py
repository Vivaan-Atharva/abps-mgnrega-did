"""Exploratory (NOT pre-registered): is the V1 relationship driven by the high-exposure tail?
Labelled exploratory in every output. Uses only exposure and pre-mandate readiness."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fe_ols import feols

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data/processed/stage0_analysis_frame_2020-2021.csv")
rows = []
for yfy in ["2019-2020", "2020-2021", "2021-2022"]:
    y = f"abps_share@{yfy}"
    d = df[["state", "district", "expo", y]].dropna().copy()
    d = d[d.groupby("state")[y].transform("size") >= 2]
    d["xw"] = d.expo - d.groupby("state").expo.transform("mean")
    cut90, cut95 = d.xw.quantile(0.90), d.xw.quantile(0.95)
    d["top10"] = (d.xw >= cut90).astype(float)
    d["y_pp"] = 100 * d[y]
    for lab, sub in (("all", d), ("drop top 5% (within-state exposure)", d[d.xw < cut95]),
                     ("drop top 10%", d[d.xw < cut90])):
        s = sub.copy(); s["x_z"] = (s.expo - s.expo.mean()) / s.expo.std(); s["y_z"] = (s[y] - s[y].mean()) / s[y].std()
        r = feols(s, "y_z", ["x_z"], fe=["state"], cluster="state")
        rows.append({"readiness": y, "sample": lab, "coef_sd": r.params["x_z"], "se": r.se["x_z"], "p": r.pvalue["x_z"], "N": r.nobs})
    r = feols(d, "y_pp", ["top10"], fe=["state"], cluster="state")
    rows.append({"readiness": y, "sample": "top-10% dummy (pp difference in ABPS share)", "coef_sd": r.params["top10"], "se": r.se["top10"], "p": r.pvalue["top10"], "N": r.nobs})
out = pd.DataFrame(rows)
out.insert(0, "status", "EXPLORATORY - not pre-registered")
out.to_csv(ROOT / "outputs/tables/stage0_explore_tail_2020-2021.csv", index=False)
print(out.round(4).to_string())
