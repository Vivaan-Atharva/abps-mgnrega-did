"""
Build annual worker-deletion counts and rates from the MIS 'Deleted Job Card/Applicants'
report, then audit them against official parliamentary figures.

The MIS report gives, for each FY selection, cumulative stocks as of that FY:
  workers_total   = workers ever registered (incl. deleted)
  workers_deleted = workers tagged as deleted
Annual deletions in FY t = workers_deleted(t) - workers_deleted(t-1).
Deletion rate per 1,000 = 1000 * deletions(t) / [workers_total(t-1) - workers_deleted(t-1)]
(the denominator is the stock of non-deleted registered workers at the start of FY t, reported explicitly).

District matching across years: names are matched within state. Districts created by a
split appear only in later years; they are flagged (not imputed) and listed in
outputs/tables/deletions_unmatched_districts.csv for the crosswalk (Month 2).

This script does NOT relate deletions to the exposure (Stage 0 rule).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INT, TAB = ROOT / "data" / "interim", ROOT / "outputs" / "tables"
REF = ROOT / "data" / "reference"

# Official all-worker deletion totals stated in Lok Sabha replies (see docs/data_audit.md)
OFFICIAL_ALL_WORKERS = {"2021-2022": 14_951_247, "2022-2023": 51_891_168}


def prev_fy(fy: str) -> str:
    a = int(fy[:4])
    return f"{a-1}-{a}"


def main() -> pd.DataFrame:
    d = pd.read_csv(INT / "mis_del_district.csv")
    fys = sorted(d.fy.unique())
    rows, unmatched = [], []
    for fy in fys:
        p = prev_fy(fy)
        if p not in fys:
            continue
        cur = d[d.fy == fy][["state", "district", "workers_total", "workers_deleted", "jc_total", "jc_deleted"]]
        old = d[d.fy == p][["state", "district", "workers_total", "workers_deleted", "jc_total", "jc_deleted"]]
        m = cur.merge(old, on=["state", "district"], how="outer", suffixes=("", "_prev"), indicator=True)
        for _, r in m[m._merge != "both"].iterrows():
            unmatched.append({"fy": fy, "state": r.state, "district": r.district,
                              "side": "new_in_fy" if r._merge == "left_only" else "gone_in_fy"})
        m = m[m._merge == "both"].drop(columns="_merge")
        m["fy"] = fy
        m["worker_deletions"] = m.workers_deleted - m.workers_deleted_prev
        m["jc_deletions"] = m.jc_deleted - m.jc_deleted_prev
        m["stock_start"] = m.workers_total_prev - m.workers_deleted_prev
        m["del_rate_per_1000"] = 1000 * m.worker_deletions / m.stock_start
        m["neg_flag"] = m.worker_deletions < 0  # restorations exceed deletions, or record revisions
        rows.append(m)
    panel = pd.concat(rows, ignore_index=True)
    panel.to_csv(ROOT / "data" / "processed" / "deletions_district_panel.csv", index=False)
    pd.DataFrame(unmatched).to_csv(TAB / "deletions_unmatched_districts.csv", index=False)

    # ---- audit 1: national totals vs official all-worker figures
    nat = panel.groupby("fy").agg(worker_deletions=("worker_deletions", "sum"),
                                  districts=("district", "size"),
                                  neg_districts=("neg_flag", "sum")).reset_index()
    nat["official_all_workers"] = nat.fy.map(OFFICIAL_ALL_WORKERS)
    nat["mis_over_official"] = nat.worker_deletions / nat.official_all_workers
    # national totals straight from the MIS national tables (no district matching needed)
    nat.to_csv(TAB / "deletions_national_audit.csv", index=False)

    # ---- audit 2: state totals vs Lok Sabha AU294 (active-worker deletions; a different universe)
    ls = pd.read_csv(REF / "loksabha_AU294_2025-02-04_active_worker_deletions.csv")
    ls["state"] = ls.state.str.upper().str.replace("&", "AND")
    st = panel.groupby(["fy", "state"]).worker_deletions.sum().unstack(0)
    out = []
    for fy, col in (("2022-2023", "deleted_active_2022_23"), ("2023-2024", "deleted_active_2023_24")):
        if fy not in st:
            continue
        m = st[[fy]].rename(columns={fy: "mis_all_workers"}).reset_index().merge(
            ls[["state", col]].rename(columns={col: "ls_active_workers"}), on="state", how="inner")
        m["fy"] = fy
        out.append(m)
    if out:
        sa = pd.concat(out)
        sa.to_csv(TAB / "deletions_state_vs_loksabha.csv", index=False)
        for fy, g in sa.groupby("fy"):
            print(f"{fy}: states={len(g)}  corr(MIS all-worker, LS active-worker) = "
                  f"{g.mis_all_workers.corr(g.ls_active_workers):.3f} (Pearson), "
                  f"{g.mis_all_workers.corr(g.ls_active_workers, method='spearman'):.3f} (Spearman)")
    print(nat.to_string())
    return panel


if __name__ == "__main__":
    main()
