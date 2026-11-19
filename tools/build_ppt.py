"""Fill the course PPT template (ADA_CourseProject.pptx) with project content."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.util import Emu, Inches, Pt
from pptx.enum.text import PP_ALIGN

ROOT = Path(__file__).resolve().parents[1]
TPL = Path(sys.argv[1])
OUT = ROOT / "deliverables" / "ByteMe_ADA_Project.pptx"
SK = Path("/root/.claude/skills/synced/19e1ce98-9721-4c92-a1f4-134dedd44be4_e3bcece0-f2a2-4ee5-b8d2-a9722bd3c271/pptx/scripts")
FIG = ROOT / "outputs" / "figures"
B = ROOT / "deliverables" / "build"

# duplicate the "Final Results" slide (slide 7) for a second results page
tmp = B / "tpl_dup.pptx"
subprocess.run([sys.executable, str(SK / "add_slide.py"), str(TPL), "slide7.xml", "--after", "slide7.xml", "-o", str(tmp)], check=True, capture_output=True)
prs = Presentation(tmp)
S = list(prs.slides)

res = pd.read_csv(ROOT / "outputs" / "tables" / "did_results.csv").set_index("spec")
summ = json.loads((ROOT / "outputs" / "did_summary.json").read_text())
m = res.iloc[0]


def by_name(slide, name):
    return [s for s in slide.shapes if s.name == name][0]


def set_lines(shape, items, size=None, bold_first=False):
    """Replace a text frame's paragraphs, reusing the first paragraph's formatting.
    items: str or (text, level) or (text, level, bold)."""
    tf = shape.text_frame
    ps = tf.paragraphs
    tmpl = copy.deepcopy(ps[0]._p)
    for p in ps[1:]:
        p._p.getparent().remove(p._p)
    first = True
    for it in items:
        text, lvl, bold = (it, 0, None) if isinstance(it, str) else (it + (None,))[:3]
        if first:
            p_el = ps[0]._p
            first = False
        else:
            p_el = copy.deepcopy(tmpl)
            tf._txBody.append(p_el)
        para = [p for p in tf.paragraphs if p._p is p_el][0]
        runs = para.runs
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
        if runs:
            runs[0].text = text
        else:
            para.add_run().text = text
        para.level = lvl
        para.alignment = PP_ALIGN.LEFT
        r = para.runs[0]
        if size:
            r.font.size = Pt(size)
        if bold is not None:
            r.font.bold = bold


def fill_table(shape, rows, size=14, start_row=1):
    t = shape.table
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(start_row + i, j)
            para = cell.text_frame.paragraphs[0]
            for p in cell.text_frame.paragraphs[1:]:
                p._p.getparent().remove(p._p)
            runs = para.runs
            for r in runs[1:]:
                r._r.getparent().remove(r._r)
            r = runs[0] if runs else para.add_run()
            r.text = val
            r.font.size = Pt(size)


def resize(shape, x=None, y=None, w=None, h=None):
    if x is not None: shape.left = Inches(x)
    if y is not None: shape.top = Inches(y)
    if w is not None: shape.width = Inches(w)
    if h is not None: shape.height = Inches(h)


def add_img(slide, path, x, y, w=None, h=None, alt=""):
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def caption(slide, text, x, y, w):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.35))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run(); r.text = text; r.font.size = Pt(12); r.font.italic = True; r.font.name = "Calibri"
    tb.text_frame.word_wrap = True


# ---- 1 title
s = S[0]
t = by_name(s, "Google Shape;48;p1")
set_lines(t, ["Did the ABPS Rollout Alter MGNREGA Worker Deletions?"], size=24)
resize(t, w=7.6, h=1.0)
tm = by_name(s, "Google Shape;92;p1")
set_lines(tm, [("Team ByteMe", 0, True), "Vivaan Atharva, PES1UG24AM071", "Vivek Varma, PES1UG24AM070"], size=18)

# ---- 2 checklist
s = S[1]
tbl = [x for x in s.shapes if x.has_table][0]
for i in range(1, 6):
    fill_table(tbl, [["Y"]], size=20, start_row=i) if False else None
t = tbl.table
for i in range(1, 6):
    c = t.cell(i, 2); para = c.text_frame.paragraphs[0]
    r = para.runs[0] if para.runs else para.add_run(); r.text = "Y"; r.font.size = Pt(20)
note = by_name(s, "TextBox 2")
set_lines(note, ["Note: Drive folder shared (view access) with the course TAs rishabhjawagal@gmail.com and rohann.rs2005@gmail.com, and faculty bhaskarjyoti01@gmail.com"], size=14)
resize(note, w=12.0, h=0.7, y=6.3)
note.text_frame.word_wrap = True

# ---- 3 problem statement
s = S[2]
b = by_name(s, "Google Shape;69;p3")
set_lines(b, [
    "On 30 Jan 2023 the Ministry of Rural Development ordered all MGNREGA wages to be paid through the Aadhaar-Based Payment System (ABPS); after five extensions it became binding on 1 Jan 2024",
    "ABPS needs three links per worker: Aadhaar seeded to the job card, Aadhaar seeded to the bank account (eKYC), and the bank mapped in the NPCI mapper",
    "Worker deletions rose from 15.0M in FY2021–22 to 51.9M in FY2022–23 (Lok Sabha reply, Jul 2023)",
    ("Question: did districts with more pre-policy account-conversion friction see larger rises in worker deletions after ABPS?", 0, True),
    "Friction is proxied by the FY2020–21 share of post-office or joint accounts; the reviewer asked us to validate this proxy before running the DiD",
], size=20)
resize(b, w=11.4, h=4.9)

# ---- 4 uniqueness
s = S[3]
b = by_name(s, "Google Shape;69;p3")
set_lines(b, [
    "Public work on ABPS and MGNREGA deletions is largely descriptive; this is a district-level, within-state dose-response test",
    "The exposure proxy is validated before use (Stage 0: six tests with pass rules fixed in advance)",
    "The first stage sits beside every estimate; a Wald-DiD rescales the effect per 10-point lower ABPS readiness",
    "We document which MIS tables are year-specific and which are only today’s snapshot, so post-treatment data are not used as pre-period readiness",
    "Estimators (FE-OLS, PPML, clustered SEs) written from scratch and checked on simulated data",
], size=20)
resize(b, w=11.4, h=4.9)

# ---- 5 dataset
s = S[4]
b = by_name(s, "Google Shape;69;p3")
set_lines(b, [
    ("Source: MGNREGA MIS (NREGASoft), Ministry of Rural Development, mnregaweb4.dord.gov.in; State = ALL, drilled to district; pulled 29 Oct 2026", 0, False),
    ("Size: 15 report-year tables, 1.7 MB raw JSON; about 710 districts in 34 states/UTs; FY2018–19 to FY2022–23; 2,823 district-year rows in the deletion panel", 0, False),
    ("Attributes:", 0, True),
    ("Accounts by type: bank or post office, individual or joint, wages paid (R1.2.3)", 1),
    ("Cumulative registered and deleted workers and job cards (gives annual deletions)", 1),
    ("Aadhaar-based payment amounts, transactions and rejections (pre-mandate readiness)", 1),
    ("Current Aadhaar seeding, NPCI-mapper and ABPS-eligibility status", 1),
    ("Cross-check: Lok Sabha USQ 294 (4 Feb 2025) state-wise active-worker deletions", 0, False),
    ("Quality: district sums = state totals in every table (0 mismatches); blanks kept missing; no imputation", 0, False),
], size=18)
resize(b, w=11.4, h=5.2)

# ---- 6 design
s = S[5]
b = by_name(s, "Google Shape;69;p3")
b._element.getparent().remove(b._element)
add_img(s, B / "design.png", 0.45, 1.75, w=12.4, alt="Overall design: extract, parse and audit, Stage 0 proxy validation, Stage 1 DiD")

# ---- 7 results (DiD)
s = S[6]
b = by_name(s, "Google Shape;69;p3")
set_lines(b, [
    ("Stage 0: GO, with conditions", 0, True),
    ("1 SD more exposure → 0.12–0.15 SD lower pre-mandate ABPS share (F = 29–65)", 1),
    ("Weak (≈3% within-state R²), driven by the high-exposure tail", 1),
    ("Stage 1 DiD (post = FY2022–23)", 0, True),
    (f"High-friction × post: {m.coef:+.1f} per 1,000 workers (SE {m.se:.1f}, p = {m.p:.2f}); 95% CI [{m.ci_lo:.1f}, {m.ci_hi:.1f}]", 1),
    (f"{int((res.p >= 0.05).sum())} of {len(res)} specifications not significant", 1),
    (f"Wald-DiD: {summ['wald_did_per_10pp']:+.1f} per 10-pt lower readiness, CI [{summ['wald_boot_ci95'][0]:.0f}, {summ['wald_boot_ci95'][1]:.0f}]", 1),
    ("No evidence that friction raised deletions in FY2022–23", 0, True),
], size=16)
resize(b, w=5.6, h=5.3)
add_img(s, FIG / "fig_event_study.png", 6.1, 1.75, w=7.0, alt="Event study of high-friction minus other districts by year")
caption(s, "Event study: high-friction vs other districts (95% CI), ref. FY2021–22", 6.1, 5.45, 7.0)

# ---- 8 results contd.
s = S[7]
by_name(s, "Google Shape;78;p4").text_frame.paragraphs[0].runs[0].text = "Final Results (contd.)"
b = by_name(s, "Google Shape;69;p3")
b._element.getparent().remove(b._element)
add_img(s, B / "binscatter_white.png", 0.35, 1.75, w=6.3, alt="Binned scatter of ABPS share of wages against exposure")
caption(s, "Stage 0 (V1): ABPS share of wages vs exposure, FY2020–21, state means removed", 0.35, 5.1, 6.3)
add_img(s, FIG / "fig_raw_trends.png", 6.75, 1.75, w=6.3, alt="Deletion rates by group and year, raw and within-state")
caption(s, "Deletions per 1,000 workers: high-friction vs other districts", 6.75, 5.1, 6.3)
tb = s.shapes.add_textbox(Inches(0.35), Inches(5.65), Inches(12.6), Inches(1.4))
tb.text_frame.word_wrap = True
p = tb.text_frame.paragraphs[0]
r = p.add_run(); r.font.size = Pt(16); r.font.name = "Calibri"
r.text = ("High-friction districts used ABPS less before the mandate and already deleted more than the rest of their state, "
          "but the gap did not widen when deletions jumped from 34 to 120 per 1,000 in FY2022–23.")

# ---- 9 done vs remaining
fill_table([x for x in S[8].shapes if x.has_table][0], [
    ["1", "MIS extraction (15 district tables) and integrity audit", "Done"],
    ["2", "Stage 0: proxy validation, tests V1–V6", "Done"],
    ["3", "DiD, event study, PPML, Wald-DiD and robustness checks", "Done (post = FY2022–23)"],
    ["4", "Deletion data for FY2023–24 and FY2024–25 (first full ABPS years)", "To be done"],
    ["5", "LGD district crosswalk and covariates (Census SC/ST, IMD rainfall)", "To be done"],
], size=15)

# ---- 10 who did what (proposed split)
fill_table([x for x in S[9].shapes if x.has_table][0], [
    ["1", "MIS data extraction and raw-page archive", "Vivaan Atharva"],
    ["2", "Parsing, integrity audit and deletion panel", "Vivek Varma"],
    ["3", "Stage-0 proxy-validation protocol and tests", "Vivaan Atharva"],
    ["4", "DiD, event study, PPML and Wald-DiD", "Vivek Varma"],
    ["5", "Report, PPT and video", "Vivaan Atharva & Vivek Varma"],
], size=15)

# ---- 11 quantity and quality
fill_table([x for x in S[10].shapes if x.has_table][0], [
    ["1", "MIS extraction and raw archive", "100%", "Y", "Index page needs a manual captcha"],
    ["2", "Parser + sum-vs-total audit", "100%", "Y", "None (0 mismatches)"],
    ["3", "Deletion panel + reconciliation", "100%", "Y", "MIS year attribution differs from official"],
    ["4", "FE-OLS and PPML estimators + tests", "100%", "Y", "None (simulation tests pass)"],
    ["5", "Stage-0 validation V1–V6", "100%", "Y", "None"],
    ["6", "DiD, event study, Wald-DiD", "100%", "Y", "Bootstrap takes ~20 s"],
    ["7", "District crosswalk (LGD codes)", "40%", "Y", "Split districts dropped, not mapped"],
], size=13)

# ---- 12 learnings
fill_table([x for x in S[11].shapes if x.has_table][0], [
    ["1", "Validate a proxy before using it: the relevance test changed our main treatment to a high-friction indicator"],
    ["2", "Government MIS tables differ: some are year-specific, some only today’s snapshot; test before use"],
    ["3", "Writing FE-OLS and PPML from scratch, and checking them on simulated data with known answers"],
    ["4", "Fixing decision rules in advance guards against tuning; exploratory results must be labelled"],
    ["5", "A null result with its first stage and confidence interval is still informative"],
], size=15)

# ---- 13 unresolved challenges
fill_table([x for x in S[12].shapes if x.has_table][0], [
    ["1", "Only one post-mandate year (FY2022–23); FY2023–24 and FY2024–25 need another captcha-gated MIS session"],
    ["2", f"Weak proxy: ≈3% within-state R²; first-stage F = {summ['first_stage_F']:.1f}, so Wald-DiD intervals are wide"],
    ["3", "MIS records 5.7M fewer deletions than official in FY2021–22 and 3.9M more in FY2022–23"],
    ["4", "ABPS eligibility exists only as today’s snapshot, measured after the deletions"],
    ["5", "District splits (e.g. Andhra Pradesh 13 → 26) need an LGD crosswalk; currently dropped"],
], size=15)

# ---- 14 references
fill_table([x for x in S[13].shapes if x.has_table][0], [
    ["1", "de Chaisemartin & D’Haultfœuille, Fuzzy Differences-in-Differences, Rev. Econ. Stud.", "2018"],
    ["2", "Callaway, Goodman-Bacon & Sant’Anna, Difference-in-Differences with a Continuous Treatment", "2024"],
    ["3", "Rambachan & Roth, A More Credible Approach to Parallel Trends, Rev. Econ. Stud.", "2023"],
    ["4", "Correia, Guimarães & Zylkin, Fast Poisson Estimation with High-Dimensional Fixed Effects, Stata J.", "2020"],
    ["5", "Bertrand, Duflo & Mullainathan, How Much Should We Trust DiD Estimates?, QJE", "2004"],
    ["6", "Muralidharan, Niehaus & Sukhtankar, Building State Capacity: Biometric Smartcards in India, AER", "2016"],
    ["7", "Lok Sabha Unstarred Q. 294, active workers deleted under MGNREGS (MoRD)", "2025"],
], size=13)

prs.save(OUT)
print("wrote", OUT)
