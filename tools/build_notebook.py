"""Build ByteMe_ABPS_MGNREGA.ipynb from the src/ modules and execute it in place.

No Jupyter is available in the build environment, so cells are executed here in one shared
namespace; stdout and displayed images are stored as standard nbformat v4 outputs. The
resulting notebook is self-contained: it needs only the dataset folder (data/raw,
data/reference) and runs top to bottom in Jupyter or Colab.
"""
from __future__ import annotations

import base64
import numpy as np
import contextlib
import io
import json
import re
import shutil
import sys
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
NB_PATH = ROOT / "ByteMe_ABPS_MGNREGA.ipynb"

CAPTURED: list[dict] = []


def _install_fake_ipython() -> None:
    ip = types.ModuleType("IPython")
    disp = types.ModuleType("IPython.display")

    class Image:  # noqa: D401
        def __init__(self, filename: str):
            self.filename = filename

    class Markdown:
        def __init__(self, data: str):
            self.data = data

    def display(obj):
        if isinstance(obj, Image):
            data = base64.b64encode(Path(obj.filename).read_bytes()).decode()
            CAPTURED.append({"output_type": "display_data", "data": {"image/png": data, "text/plain": ["<Image>"]}, "metadata": {}})
        elif isinstance(obj, Markdown):
            CAPTURED.append({"output_type": "display_data", "data": {"text/markdown": obj.data, "text/plain": [obj.data]}, "metadata": {}})
        elif hasattr(obj, "to_html"):
            CAPTURED.append({"output_type": "display_data", "data": {"text/html": obj.to_html(), "text/plain": str(obj)}, "metadata": {}})
        else:
            print(obj)

    disp.Image, disp.Markdown, disp.display = Image, Markdown, display
    ip.display = disp
    ip.get_ipython = lambda: None
    ip.version_info = (9, 0, 0)
    sys.modules["IPython"], sys.modules["IPython.display"] = ip, disp


def module_code(name: str) -> str:
    s = (SRC / f"{name}.py").read_text()
    s = s.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = PROJECT_ROOT")
    s = re.sub(r"^sys\.path\.insert\(.*\n", "", s, flags=re.M)
    s = re.sub(r"^from fe_ols import .*\n", "", s, flags=re.M)
    s = re.sub(r'\nif __name__ == "__main__":\n(?:    .*\n|\n)*\Z', "\n", s + "\n")
    s = s.replace('matplotlib.use("Agg")\n', "")
    return s.strip() + "\n"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}


CELLS = [
    md("""
# Did the ABPS rollout alter MGNREGA worker deletions?
**ADA Jackfruit Project · UE24AM343AB1 · Team ByteMe**
Vivaan Atharva (PES1UG24AM071) · Vivek Varma (PES1UG24AM070)

**Question.** Did districts with more pre-policy account-conversion friction see larger rises in
worker deletions after the Aadhaar-Based Payment System (ABPS) was mandated?

**Design.** Within-state difference-in-differences with district and state × year fixed effects.
Exposure: FY2020–21 share of post-office or joint accounts. Outcome: all-worker deletions per 1,000
registered workers. Before running the DiD, *Stage 0* checks that the exposure really tracks
ABPS conversion friction (reviewer feedback on the one-pager).

**How to run.** Put this notebook next to the dataset folder (`data/raw/*.json`,
`data/reference/*.csv`), set `PROJECT_ROOT` below if needed, and run all cells (≈1 minute).
Only pandas, numpy, scipy and matplotlib are needed: the fixed-effects estimators are written here.
"""),
    code("""
import sys, json, re, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from IPython.display import Image, Markdown, display
warnings.filterwarnings("ignore")
pd.set_option("display.width", 160)

PROJECT_ROOT = Path(".").resolve()          # folder that contains data/raw and data/reference
assert (PROJECT_ROOT / "data" / "raw").exists(), "set PROJECT_ROOT to the dataset folder"
for sub in ("data/interim", "data/processed", "outputs/tables", "outputs/figures"):
    (PROJECT_ROOT / sub).mkdir(parents=True, exist_ok=True)

def show(path):
    display(Image(filename=str(path)))
print("raw files:", sorted(p.name for p in (PROJECT_ROOT / "data" / "raw").glob("*.json")))
"""),
    md("""
## 1. Estimators: fixed-effects OLS and PPML with clustered standard errors
Fixed effects are absorbed by alternating projections; standard errors are clustered by state
(CR1). PPML (Poisson pseudo-maximum likelihood) is fitted by IRLS with weighted demeaning.
"""),
    code("@@fe_ols"),
    md("**Check the estimators on simulated panels with known effects.**"),
    code("""
def _panel(seed=0, n_state=30, n_dist=20, n_year=8, beta=0.5):
    rng = np.random.default_rng(seed); rows = []
    for s in range(n_state):
        shock = rng.normal(size=n_year)
        for d in range(n_dist):
            a, x = rng.normal(), rng.normal() + 0.3 * s / n_state
            for t in range(n_year):
                rows.append((s, f"{s}_{d}", t, x, int(t >= 5), a + shock[t] + beta * x * (t >= 5) + rng.normal()))
    df = pd.DataFrame(rows, columns=["state", "district", "year", "x", "post", "y"])
    df["state_year"] = df.state.astype(str) + "_" + df.year.astype(str); df["xpost"] = df.x * df.post
    return df

r = feols(_panel(), "y", ["xpost"], fe=["district", "state_year"], cluster="state")
print(f"TWFE: true 0.50, estimated {r.params['xpost']:.3f} (SE {r.se['xpost']:.3f})")
rej = np.mean([feols(_panel(100 + s, 25, 10, 6, 0.0), "y", ["xpost"], fe=["district", "state_year"], cluster="state").pvalue["xpost"] < 0.05 for s in range(100)])
print(f"Rejection rate of a true null at 5%: {rej:.2f}")
rng = np.random.default_rng(7); rows = []
for s in range(30):
    sh = rng.normal(0, .3, 6)
    for d in range(15):
        a, x, st = rng.normal(0, .5), rng.normal(), rng.integers(20_000, 200_000)
        for t in range(6):
            rows.append((s, f"{s}_{d}", f"{s}_{t}", x * (t >= 4), np.log(st), rng.poisson(st / 1000 * np.exp(1.5 + a + sh[t] + .3 * x * (t >= 4)))))
sim = pd.DataFrame(rows, columns=["state", "district", "sy", "xpost", "lstock", "y"])
rp = ppml(sim, "y", ["xpost"], fe=["district", "sy"], cluster="state", offset="lstock")
print(f"PPML: true 0.30, estimated {rp.params['xpost']:.3f} (SE {rp.se['xpost']:.3f})")
"""),
    md("""
## 2. Data: parse the MGNREGA MIS extract
The raw files hold the MIS report pages exactly as served (State = ALL, drilled to district),
pulled from `mnregaweb4.dord.gov.in`. Blank cells stay missing; every state's district rows are
checked against the state's own printed total.
"""),
    code("@@parse_mis"),
    code("""
main([str(p) for p in sorted((PROJECT_ROOT / "data" / "raw").glob("mgnrega_mis_extract_*.json"))])
display(pd.read_csv(PROJECT_ROOT / "outputs/tables/extraction_coverage.csv")[["key", "fy", "states_fetched", "districts"]])
audit = pd.read_csv(PROJECT_ROOT / "outputs/tables/parse_audit.csv")
print("district-sum vs state-total mismatches:", len(audit))
"""),
    md("## 3. Outcome: annual worker deletions, reconciled with official totals"),
    code("@@build_deletions"),
    code("""
panel = main()
display(pd.read_csv(PROJECT_ROOT / "outputs/tables/deletions_national_audit.csv"))
"""),
    md("""
## 4. Stage 0: does the account mix proxy ABPS conversion friction?
Pre-specified tests V1–V6 (protocol v1.1). Relevance (V1) uses the **pre-mandate** ABPS share of
wages, FY2018–19 to FY2021–22, because eligibility snapshots are only available for today, after
the deletions. No post-period outcome is used here.
"""),
    code("@@stage0_validation"),
    code("""
summary0 = main("2020-2021")
print(json.dumps({k: summary0[k] for k in ("n_districts_exposure", "decision", "loso_sign_stable")}, indent=1))
v1 = pd.read_csv(PROJECT_ROOT / "outputs/tables/stage0_v1_relevance_2020-2021.csv")
display(v1[["spec", "readiness", "coef_sd", "se", "p", "F_eff", "N", "pass"]].round(3))
display(pd.read_csv(PROJECT_ROOT / "outputs/tables/stage0_v2_components_2020-2021.csv").round(3))
display(pd.read_csv(PROJECT_ROOT / "outputs/tables/stage0_v4_stability_2020-2021.csv").round(3))
display(pd.read_csv(PROJECT_ROOT / "outputs/tables/stage0_v5_balance_2020-2021.csv").round(3))
"""),
    md("**Exploratory (not pre-registered): is the V1 relationship carried by the high-exposure tail?**"),
    code("@@stage0_explore_tail"),
    md("## 5. Stage-0 figures"),
    code("@@make_figures"),
    code("""
for f in (exposure_hist(), binscatter(), coef_by_spec(), deletions_audit()):
    show(f)
"""),
    md("""
## 6. Stage 1: difference-in-differences
Main treatment: high-friction district (top within-state decile of exposure), × post (FY2022–23 on).
District FE + state × year FE, SEs clustered by state. Secondary: quartiles, continuous exposure,
components, direct readiness, timing and trend checks, placebo, PPML counts, and a Wald-DiD that
rescales the effect per 10-point lower ABPS share.
"""),
    code("@@did_analysis"),
    code("""
out = main()
display(out["res"][["spec", "coef", "se", "p", "ci_lo", "ci_hi", "N", "clusters"]].round(3))
display(out["ev"].round(3))
info = out["info"]
print(json.dumps({k: info[k] for k in ("years", "districts", "states", "high_friction_districts", "negative_rows_excluded",
                                       "first_stage_pp", "first_stage_F", "wald_did_per_10pp", "wald_boot_ci95")}, indent=1, default=float))
show(PROJECT_ROOT / "outputs/figures/fig_raw_trends.png")
show(PROJECT_ROOT / "outputs/figures/fig_event_study.png")
"""),
    md("@@conclusion"),
]


def conclusion_md() -> str:
    import pandas as pd
    s = json.loads((ROOT / "outputs" / "did_summary.json").read_text())
    res = pd.read_csv(ROOT / "outputs" / "tables" / "did_results.csv").set_index("spec")
    m = res.iloc[0]
    po = res.loc["Post-office share (per SD) × post"]
    pc = res.loc["PPML count, continuous exposure (per SD)"]
    post_years = [y for y in s["years"] if y >= "2022-2023"]
    py = ", ".join(f"FY{y[:4]}–{y[-2:]}" for y in post_years)
    nsig = int((res.p < 0.05).sum())
    early = ("Only FY2022–23 is post-mandate in this extract; the order came on 30 Jan 2023, late in that "
             "year, and ABPS became binding in FY2023–24, so the effect may not be visible yet. ") if len(post_years) == 1 else ""
    return f"""
## 7. Conclusions
* **Stage 0 (proxy validation): GO, with conditions.** The FY2020–21 account mix predicts lower
  pre-mandate ABPS use within states (F = 29–65 in three of four years, stable when any state is
  dropped), but the link is weak (≈3% of within-state variance) and sits in the high-exposure tail.
* **Stage 1 (DiD, post = {py}).** High-friction districts did **not** see a larger rise in deletions:
  {m.coef:+.1f} per 1,000 workers (SE {m.se:.1f}, p = {m.p:.2f}), 95% CI [{m.ci_lo:.1f}, {m.ci_hi:.1f}].
  They already deleted more than the rest of their state before ABPS, and that gap did not widen.
* **Robustness.** {len(res) - nsig} of {len(res)} specifications are not significant at 5%. The two exceptions point
  in opposite directions: the post-office share alone shows a small rise ({po.coef:+.1f} per 1,000 per SD,
  p = {po.p:.2f}), while the count model with continuous exposure shows proportionally fewer deletions
  ({np.expm1(pc.coef) * 100:+.0f}% per SD, p = {pc.p:.2f}). Neither supports a robust friction effect.
* **Scaled by the first stage** (high-friction districts had a {abs(s['first_stage_pp']):.1f}-point lower ABPS share,
  F = {s['first_stage_F']:.1f}), the Wald-DiD is {s['wald_did_per_10pp']:+.1f} deletions per 1,000 per 10-point lower
  readiness, bootstrap 95% CI [{s['wald_boot_ci95'][0]:.1f}, {s['wald_boot_ci95'][1]:.1f}]: too wide to rule out moderate effects.
* **Limits.** {early}The MIS records 5.7M fewer deletions than the official figure in FY2021–22 and
  3.9M more in FY2022–23, and eligibility data exist only as today's snapshot. Results are
  associations under parallel trends, not proof of wrongful exclusion.
"""


def execute(cells: list[dict], workdir: Path) -> None:
    import os
    import matplotlib
    matplotlib.use('Agg')
    _install_fake_ipython()
    os.chdir(workdir)
    ns: dict = {"__name__": "__main__"}
    n = 0
    for c in cells:
        if c["cell_type"] != "code":
            continue
        n += 1
        CAPTURED.clear()
        buf = io.StringIO()
        src = "".join(c["source"])
        with contextlib.redirect_stdout(buf):
            try:
                exec(compile(src, f"<cell {n}>", "exec"), ns)
            except Exception:
                traceback.print_exc(file=buf)
                print(f"!! cell {n} failed", file=sys.stderr)
                raise
        outs = []
        text = buf.getvalue()
        if text:
            outs.append({"output_type": "stream", "name": "stdout", "text": text.splitlines(keepends=True)})
        outs += list(CAPTURED)
        c["outputs"], c["execution_count"] = outs, n
        print(f"cell {n}: ok ({len(outs)} outputs)", file=sys.stderr)


def main() -> None:
    cells = []
    for c in CELLS:
        src = "".join(c["source"])
        if src.startswith("@@"):
            name = src[2:]
            if name == "conclusion":
                continue  # added after execution
            c = code(module_code(name))
        cells.append(c)
    work = ROOT.parent / "_nb_run"
    if work.exists():
        shutil.rmtree(work)
    (work / "data").mkdir(parents=True)
    shutil.copytree(ROOT / "data" / "raw", work / "data" / "raw")
    shutil.copytree(ROOT / "data" / "reference", work / "data" / "reference")
    execute(cells, work)
    cells.append(md(conclusion_md()))
    nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                       "language_info": {"name": "python", "version": "3.11"}},
          "nbformat": 4, "nbformat_minor": 5}
    NB_PATH.write_text(json.dumps(nb, indent=1))
    print("wrote", NB_PATH)


if __name__ == "__main__":
    main()
