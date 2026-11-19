"""
Parse the raw MIS extract (data/raw/mgnrega_mis_extract_*.json) into tidy district tables.

The raw file is exactly what the MIS pages returned: every table cell as text, one
record per (report, financial year), with the national page and one child page per
state. Nothing is recoded at extraction time; all cleaning happens here so it is
reproducible and reviewable.

Rules (from the one-pager's data-handling commitments):
  * True zeros stay zeros. Blank / non-numeric cells become NaN, never 0.
  * Every state's district rows are summed and compared with that state's own "Total"
    row; mismatches are written to outputs/tables/parse_audit.csv, not hidden.
  * No imputation.

Usage:  python src/parse_mis.py            # reads every data/raw/mgnrega_mis_extract_*.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Column layouts as printed in each report's header (column numbers in comments)
LAYOUTS: dict[str, list[str]] = {
    # R1.2.3 Account Opened and Amount Disbursed through Bank/Post Office
    "acc": ["sno", "district", "reg_hh", "reg_persons",
            "bank_ind", "bank_joint", "bank_amt_lakh",
            "po_ind", "po_joint", "po_amt_lakh",
            "tot_ind", "tot_joint", "tot_accounts", "tot_amt_lakh"],
    # Deleted Job Card/Applicants with A/C No, Photos Uploaded (cumulative to FY end)
    "del": ["sno", "district", "hh_total", "hh_deleted", "jc_total", "jc_deleted",
            "workers_total", "workers_deleted", "workers_with_acno", "workers_with_acno_pct",
            "jc_photo_n", "jc_photo_pct", "worker_photo_n", "worker_photo_pct"],
    # Aadhar Based Payment Report (transactions in the FY)
    "abps": ["sno", "district", "abps_txn_total"] + [
        f"{b}_{m}" for b in ("t0", "t1", "t2", "t3", "gt3")
        for m in ("proc_n", "proc_amt", "rej_n", "rej_amt")],
    # Aadhaar Status with NPCI Mapper (current snapshot)
    "npci": ["sno", "district", "workers_total", "aadhaar_seeded", "aadhaar_seeded_pct",
             "sent_uidai", "sent_uidai_pct", "auth_success", "auth_success_pct",
             "sent_npci", "sent_npci_pct", "npci_active", "npci_active_pct",
             "npci_inactive", "npci_inactive_pct", "npci_not_mapped", "npci_not_mapped_pct",
             "npci_total_failure"],
    # Aadhaar Authentication Status Report (current snapshot)
    "auth": ["sno", "district", "workers_total", "aadhaar_seeded", "ekyc_done", "ekyc_pct",
             "demo_sent", "demo_success", "demo_failed", "demo_to_send", "abps_eligible"],
    # Category wise Household/Workers
    "cat": ["sno", "district", "jc_applied", "jc_issued",
            "reg_sc", "reg_st", "reg_oth", "reg_total", "reg_women",
            "act_sc", "act_st", "act_oth", "act_total", "act_women"],
}

PCT_COLS = {c for cols in LAYOUTS.values() for c in cols if c.endswith("_pct")}


def to_num(x: str) -> float:
    """'1,234' -> 1234.0 ; '.60' -> 0.6 ; '' / '-' / 'NA' -> NaN (never 0)."""
    if x is None:
        return np.nan
    s = str(x).replace(",", "").strip()
    if s in {"", "-", "NA", "N/A", "na", "--"}:
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def norm_name(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip().upper()
    s = s.replace("&", "AND")
    return s


def parse_table(rec: dict, kind: str) -> tuple[pd.DataFrame, list[dict]]:
    cols = LAYOUTS[kind]
    n = len(cols)
    out, audit = [], []
    for child in rec.get("child", []):
        state = norm_name(child["state"])
        data, total = [], None
        for r in child["rows"]:
            if len(r) < n - 1:
                continue
            # data row: serial number in col 0 and a non-numeric name in col 1
            # (the printed column-number row "1 | 2 | 3 ..." must not count as a district)
            if re.fullmatch(r"\d+", r[0].strip()) and r[1].strip() and not re.fullmatch(r"[\d.=+ ]+", r[1].strip()):
                data.append(r[:n])
            elif r[1].strip().lower() == "total" or r[0].strip().lower() == "total":
                total = r[:n] if r[1].strip().lower() == "total" else [""] + r[:n - 1]
        if not data:
            audit.append({"key": rec["key"], "state": state, "issue": "no district rows"})
            continue
        df = pd.DataFrame(data, columns=cols)
        df.insert(0, "state", state)
        df["district"] = df["district"].map(norm_name)
        for c in cols[2:]:
            df[c] = df[c].map(to_num)
        # integrity: district sum vs printed state total (count columns only)
        if total is not None:
            tvals = {c: to_num(v) for c, v in zip(cols, total)}
            for c in cols[2:]:
                if c in PCT_COLS or np.isnan(tvals.get(c, np.nan)):
                    continue
                s = df[c].sum(min_count=1)
                if not np.isclose(s, tvals[c], rtol=1e-3, atol=2):
                    audit.append({"key": rec["key"], "state": state, "issue": "sum!=total",
                                  "column": c, "district_sum": s, "printed_total": tvals[c]})
        else:
            audit.append({"key": rec["key"], "state": state, "issue": "no total row"})
        out.append(df)
    res = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["state"] + cols)
    res["fy"] = rec["fy"]
    return res.drop(columns=["sno"]), audit


def kind_of(key: str) -> str:
    return key.split("_")[0]


def main(paths: list[str]) -> None:
    tables: dict = {}
    for path in paths:  # later parts override earlier ones for the same key (re-pulls)
        raw = json.loads(Path(path).read_text())
        tables.update(raw["tables"])
        print(f"read {Path(path).name}: {len(raw['tables'])} tables (exported {raw.get('exported_utc')})")
    interim = ROOT / "data" / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    frames: dict[str, list[pd.DataFrame]] = {}
    audit_all, coverage = [], []
    for key, rec in tables.items():
        kind = kind_of(key)
        if kind not in LAYOUTS:
            continue
        df, audit = parse_table(rec, kind)
        frames.setdefault(kind, []).append(df)
        audit_all += audit
        coverage.append({"key": key, "report": rec.get("report"), "fy": rec.get("fy"),
                         "status": rec.get("status"), "states_fetched": len(rec.get("child", [])),
                         "states_linked": rec.get("nChild"), "districts": len(df),
                         "fetch_errors": "; ".join(rec.get("errors", [])),
                         "fetched_utc": rec.get("t0")})
    for kind, fs in frames.items():
        allf = pd.concat(fs, ignore_index=True)
        allf.to_csv(interim / f"mis_{kind}_district.csv", index=False)
        print(f"{kind}: {len(allf):,} district-year rows -> data/interim/mis_{kind}_district.csv")
    (ROOT / "outputs" / "tables").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audit_all, columns=["key", "state", "issue", "column", "district_sum", "printed_total"]
                 ).to_csv(ROOT / "outputs" / "tables" / "parse_audit.csv", index=False)
    pd.DataFrame(coverage).sort_values("key").to_csv(ROOT / "outputs" / "tables" / "extraction_coverage.csv", index=False)
    print(f"audit issues: {len(audit_all)} (outputs/tables/parse_audit.csv)")


if __name__ == "__main__":
    main(sys.argv[1:] or [str(p) for p in sorted((ROOT / "data" / "raw").glob("mgnrega_mis_extract_*.json"))])
