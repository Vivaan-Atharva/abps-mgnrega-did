"""Overall design diagram for the PPT, report and video."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
fig, ax = plt.subplots(figsize=(12.5, 5.0), dpi=180)
ax.set_xlim(0, 125); ax.set_ylim(0, 50); ax.axis("off")
def box(x, y, w, h, title, body, fc="#F3F5F9", ec="#2E4A7D", tc="#1B2A4A"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w/2, y + h - 3.2, title, ha="center", va="top", fontsize=12.5, fontweight="bold", color=tc)
    ax.text(x + w/2, y + h - 8.2, body, ha="center", va="top", fontsize=10.2, color="#333", linespacing=1.35)
def arr(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=18, lw=1.8, color="#555"))
box(1, 27, 22, 20, "1. Extract", "MGNREGA MIS\n15 district tables\nFY2018–19 to 2022–23\nraw pages archived")
box(27, 27, 22, 20, "2. Parse & audit", "tidy district tables\nsum = state total check\ndeletions rebuilt\n(97% of official)")
box(53, 27, 30, 20, "3. Stage 0: proxy validation", "exposure = FY2020–21\nPO or joint account share\nvs pre-mandate ABPS share\ntests V1–V6, fixed in advance", fc="#FFF4EC", ec="#C2571A", tc="#8A3A0E")
box(87, 27, 37, 20, "4. Stage 1: DiD", "deletions per 1,000 workers\nhigh-friction × post\ndistrict + state×year FE\nclustered by state", fc="#EAF3EA", ec="#3D7A3D", tc="#24502A")
arr(23.6, 37, 26.4, 37); arr(49.6, 37, 52.4, 37); arr(83.6, 37, 86.4, 37)
ax.text(66.5, 23.3, "GO / REVISE / NO-GO", ha="right", va="center", fontsize=10.5, fontweight="bold", color="#8A3A0E")
box(53, 1, 30, 19, "Decision rule", "GO: relevant (F ≥ 10) and\nno single state drives it\n→ result: GO, with conditions", fc="#FFFFFF", ec="#C2571A", tc="#8A3A0E")
box(87, 1, 37, 19, "Checks", "event study (leads) · placebo\ntrend & timing checks\nPPML counts · Wald-DiD\n(first stage beside every estimate)", fc="#FFFFFF", ec="#3D7A3D", tc="#24502A")
arr(68, 26.4, 68, 20.6); arr(105.5, 26.4, 105.5, 20.6)
box(1, 1, 48, 19, "Data rules", "true zeros stay zero · blanks stay missing\nno outcome imputation · split districts flagged\nexploratory results labelled", fc="#FFFFFF", ec="#2E4A7D")
fig.tight_layout(pad=0.2); fig.savefig("deliverables/build/design.png", facecolor="white")
