"""Checks that src/fe_ols.py recovers known coefficients and gives sane clustered SEs.

Run:  python -m pytest tests/ -q    (or  python tests/test_fe_ols.py)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fe_ols import feols  # noqa: E402


def _panel(seed=0, n_state=30, n_dist=20, n_year=8, beta=0.5):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_state):
        state_shock = rng.normal(size=n_year)
        for d in range(n_dist):
            a_d = rng.normal()
            x_d = rng.normal() + 0.3 * s / n_state
            for t in range(n_year):
                post = int(t >= 5)
                y = a_d + state_shock[t] + beta * x_d * post + rng.normal()
                rows.append((s, f"{s}_{d}", t, x_d, post, y))
    return pd.DataFrame(rows, columns=["state", "district", "year", "x", "post", "y"])


def test_cross_section_with_state_fe():
    rng = np.random.default_rng(1)
    n = 3000
    df = pd.DataFrame({"state": rng.integers(0, 30, n)})
    alpha = rng.normal(size=30)
    df["x"] = rng.normal(size=n) + alpha[df.state]
    df["y"] = 2.0 * df.x + 3 * alpha[df.state] + rng.normal(size=n)
    r = feols(df, "y", ["x"], fe=["state"], cluster="state")
    assert abs(r.params["x"] - 2.0) < 0.1
    assert r.n_clusters == 30


def test_twfe_dose_response():
    df = _panel()
    df["state_year"] = df.state.astype(str) + "_" + df.year.astype(str)
    df["xpost"] = df.x * df.post
    r = feols(df, "y", ["xpost"], fe=["district", "state_year"], cluster="state")
    assert abs(r.params["xpost"] - 0.5) < 0.1, r
    # coverage sanity: SE should be in a plausible range, not ~0 or huge
    assert 0.01 < r.se["xpost"] < 0.2


def test_null_effect_rejection_rate():
    """Under the null, a 5% test should reject roughly 5% of the time (loose bounds)."""
    rej = 0
    reps = 200
    for s in range(reps):
        df = _panel(seed=100 + s, n_state=25, n_dist=10, n_year=6, beta=0.0)
        df["state_year"] = df.state.astype(str) + "_" + df.year.astype(str)
        df["xpost"] = df.x * df.post
        r = feols(df, "y", ["xpost"], fe=["district", "state_year"], cluster="state")
        rej += r.pvalue["xpost"] < 0.05
    assert 0.01 <= rej / reps <= 0.11, rej / reps




def test_ppml_recovers_semi_elasticity():
    from fe_ols import ppml
    rng = np.random.default_rng(7)
    rows = []
    for s in range(30):
        shock = rng.normal(0, 0.3, size=6)
        for d in range(15):
            a = rng.normal(0, 0.5)
            x = rng.normal()
            stock = rng.integers(20_000, 200_000)
            for t in range(6):
                post = int(t >= 4)
                lam = stock / 1000 * np.exp(1.5 + a + shock[t] + 0.30 * x * post)
                rows.append((s, f"{s}_{d}", f"{s}_{t}", x * post, np.log(stock), rng.poisson(lam)))
    df = pd.DataFrame(rows, columns=["state", "district", "sy", "xpost", "lstock", "y"])
    r = ppml(df, "y", ["xpost"], fe=["district", "sy"], cluster="state", offset="lstock")
    assert abs(r.params["xpost"] - 0.30) < 0.03, r.params


if __name__ == "__main__":
    test_cross_section_with_state_fe()
    test_twfe_dose_response()
    test_null_effect_rejection_rate()
    test_ppml_recovers_semi_elasticity()
    print("all fe_ols tests passed")
