"""
Minimal OLS with absorbed fixed effects and cluster-robust standard errors.

Written in plain numpy/pandas so the pipeline runs anywhere (our cloud workspace
had no statsmodels/pyfixest). Results were checked against a simulation with a
known effect (tests/test_fe_ols.py). On your own machine you can cross-check any
estimate with pyfixest:  pf.feols("y ~ x | state", data=df, vcov={"CRV1": "state"}).

Absorption uses the method of alternating projections (iterative demeaning),
which handles one-way and multi-way fixed effects (e.g. district + state-by-year).
Clustered SEs use the CR1 small-sample correction:  G/(G-1) * (N-1)/(N-K).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


def _demean(mat: np.ndarray, groups: list[np.ndarray], tol: float = 1e-10, max_iter: int = 10_000) -> np.ndarray:
    """Remove fixed effects from each column of `mat` by alternating projections."""
    out = mat.astype(float).copy()
    if not groups:
        return out
    if len(groups) == 1:
        g = groups[0]
        n_g = g.max() + 1
        counts = np.bincount(g, minlength=n_g).astype(float)
        for j in range(out.shape[1]):
            means = np.bincount(g, weights=out[:, j], minlength=n_g) / counts
            out[:, j] -= means[g]
        return out
    for _ in range(max_iter):
        prev = out.copy()
        for g in groups:
            n_g = g.max() + 1
            counts = np.bincount(g, minlength=n_g).astype(float)
            for j in range(out.shape[1]):
                means = np.bincount(g, weights=out[:, j], minlength=n_g) / counts
                out[:, j] -= means[g]
        if np.max(np.abs(out - prev)) < tol:
            break
    return out


@dataclass
class FEResult:
    params: pd.Series
    se: pd.Series
    tstat: pd.Series
    pvalue: pd.Series
    nobs: int
    n_clusters: int | None
    r2_within: float
    fe: list[str] = field(default_factory=list)
    cluster: str | None = None
    dof_resid: int = 0

    def summary(self) -> pd.DataFrame:
        ci_lo = self.params - 1.96 * self.se
        ci_hi = self.params + 1.96 * self.se
        return pd.DataFrame({"coef": self.params, "se": self.se, "t": self.tstat,
                             "p": self.pvalue, "ci95_lo": ci_lo, "ci95_hi": ci_hi})

    def __repr__(self) -> str:  # pragma: no cover - display helper
        s = self.summary().round(4).to_string()
        return (f"{s}\nN={self.nobs}  clusters={self.n_clusters} ({self.cluster})  "
                f"FE={self.fe}  within-R2={self.r2_within:.3f}")


def feols(df: pd.DataFrame, y: str, x: list[str], fe: list[str] | None = None,
          cluster: str | None = None, add_const: bool = False) -> FEResult:
    """OLS of y on x, absorbing `fe` columns, with CR1 clustered SEs on `cluster`.

    Rows with any missing value in y, x, fe or cluster are dropped (complete-case);
    the number dropped is not silent: it is the difference between len(df) and nobs.
    """
    fe = fe or []
    cols = list(dict.fromkeys([y] + x + fe + ([cluster] if cluster else [])))
    d = df[cols].dropna().copy()
    n = len(d)
    groups = [pd.factorize(d[f])[0] for f in fe]
    Y = d[[y]].to_numpy(float)
    X = d[x].to_numpy(float)
    if add_const and not fe:
        X = np.column_stack([np.ones(n), X])
        names = ["const"] + x
    else:
        names = list(x)
    Yd = _demean(Y, groups)
    Xd = _demean(X, groups)
    XtX = Xd.T @ Xd
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (Xd.T @ Yd)
    resid = (Yd - Xd @ beta).ravel()
    k = Xd.shape[1]
    # degrees of freedom absorbed by fixed effects (conservative count)
    k_fe = sum(len(np.unique(g)) for g in groups) - (len(groups) - 1 if len(groups) > 1 else 0)
    dof = n - k - k_fe
    tss_w = float(((Yd - Yd.mean()) ** 2).sum())
    r2_w = 1 - float(resid @ resid) / tss_w if tss_w > 0 else np.nan

    if cluster:
        cl = pd.factorize(d[cluster])[0]
        G = cl.max() + 1
        meat = np.zeros((k, k))
        scores = Xd * resid[:, None]
        for gi in range(G):
            s = scores[cl == gi].sum(axis=0)
            meat += np.outer(s, s)
        # CR1 correction; with FE nested in clusters, pyfixest/Stata use (N-1)/(N-K) with K excl. nested FE
        corr = (G / (G - 1)) * ((n - 1) / (n - k))
        V = corr * XtX_inv @ meat @ XtX_inv
        df_t = G - 1
    else:
        G = None
        sigma2 = float(resid @ resid) / dof
        V = sigma2 * XtX_inv
        df_t = dof
    se = np.sqrt(np.diag(V))
    b = beta.ravel()
    t = b / se
    p = 2 * stats.t.sf(np.abs(t), df=df_t)
    idx = pd.Index(names)
    return FEResult(pd.Series(b, idx), pd.Series(se, idx), pd.Series(t, idx), pd.Series(p, idx),
                    n, G, r2_w, fe, cluster, dof)


def partial_r2(df: pd.DataFrame, y: str, x: list[str], fe: list[str] | None = None) -> float:
    """Within-FE R-squared of y on x (share of within-group variance in y explained by x)."""
    res = feols(df, y, x, fe=fe)
    return res.r2_within


def first_stage_F(res: FEResult, var: str) -> float:
    """Effective F for a single excluded instrument = t^2 (cluster-robust)."""
    return float(res.tstat[var] ** 2)


# ---------------------------------------------------------------------------
# Poisson pseudo-maximum likelihood (PPML) with absorbed fixed effects
# ---------------------------------------------------------------------------
def _wdemean(mat: np.ndarray, groups: list[np.ndarray], w: np.ndarray,
             tol: float = 1e-10, max_iter: int = 5_000) -> np.ndarray:
    """Weighted alternating projections: remove weighted group means."""
    out = mat.astype(float).copy()
    for _ in range(max_iter):
        prev = out.copy()
        for g in groups:
            n_g = g.max() + 1
            wsum = np.bincount(g, weights=w, minlength=n_g)
            for j in range(out.shape[1]):
                means = np.bincount(g, weights=w * out[:, j], minlength=n_g) / wsum
                out[:, j] -= means[g]
        if len(groups) == 1 or np.max(np.abs(out - prev)) < tol:
            break
    return out


def ppml(df: pd.DataFrame, y: str, x: list[str], fe: list[str], cluster: str,
         offset: str | None = None, tol: float = 1e-8, max_iter: int = 200) -> FEResult:
    """PPML with high-dimensional FE via IRLS (Correia, Guimaraes & Zylkin 2020 logic).

    Groups whose outcome is all zero are dropped (their FE is -inf). Cluster-robust
    sandwich SEs with CR1 correction. Coefficients are semi-elasticities: exp(b)-1 is
    the proportional change in the expected count.
    """
    cols = list(dict.fromkeys([y] + x + fe + [cluster] + ([offset] if offset else [])))
    d = df[cols].dropna().copy()
    for f in fe:  # drop FE groups with all-zero outcome
        d = d[d.groupby(f)[y].transform("sum") > 0]
    n = len(d)
    groups = [pd.factorize(d[f])[0] for f in fe]
    Y = d[y].to_numpy(float)
    X = d[x].to_numpy(float)
    off = d[offset].to_numpy(float) if offset else np.zeros(n)
    mu = (Y + Y.mean()) / 2
    eta = np.log(mu)
    beta = np.zeros(X.shape[1])
    dev_old = np.inf
    for _ in range(max_iter):
        z = eta - off + (Y - mu) / mu       # working response net of offset
        w = mu
        Zd = _wdemean(z[:, None], groups, w).ravel()
        Xd = _wdemean(X, groups, w)
        XtWX = Xd.T @ (w[:, None] * Xd)
        beta = np.linalg.solve(XtWX, Xd.T @ (w * Zd))
        resid_w = Zd - Xd @ beta
        eta = z - resid_w + off             # fitted linear predictor incl. FE
        eta = np.clip(eta, -30, 30)
        mu = np.exp(eta)
        with np.errstate(divide="ignore", invalid="ignore"):
            dev = 2 * np.sum(np.where(Y > 0, Y * np.log(Y / mu), 0) - (Y - mu))
        if abs(dev - dev_old) / max(abs(dev), 1) < tol:
            break
        dev_old = dev
    w = mu
    Xd = _wdemean(X, groups, w)
    bread = np.linalg.inv(Xd.T @ (w[:, None] * Xd))
    scores = Xd * (Y - mu)[:, None]
    cl = pd.factorize(d[cluster])[0]
    G = cl.max() + 1
    k = X.shape[1]
    meat = np.zeros((k, k))
    for gi in range(G):
        s = scores[cl == gi].sum(axis=0)
        meat += np.outer(s, s)
    V = (G / (G - 1)) * ((n - 1) / (n - k)) * bread @ meat @ bread
    se = np.sqrt(np.diag(V))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), df=G - 1)
    idx = pd.Index(x)
    return FEResult(pd.Series(beta, idx), pd.Series(se, idx), pd.Series(t, idx), pd.Series(p, idx),
                    n, G, np.nan, fe, cluster, n - k)
