"""Silent demo video: a walkthrough of the executed project notebook (no voice-over).

1. Render the executed notebook as a Jupyter-style HTML page (long module cells are shown
   truncated, with a note that the full code is in the notebook).
2. Screenshot every cell at 1280 px wide and stack them into one tall "page".
3. Build a timeline: chapter title cards, then for each cell a smooth scroll to it and a hold
   long enough to read; tall cells scroll through slowly.
4. Pipe frames to ffmpeg (1280x720, 20 fps, H.264, no audio), tuned to stay under ~2.9 MB.
"""
import base64
import html
import io
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

ROOT = Path(__file__).resolve().parents[1]
NB = json.loads((ROOT / "ByteMe_ABPS_MGNREGA.ipynb").read_text())
WORK = ROOT / "deliverables" / "build" / "demo"
WORK.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "deliverables" / "ByteMe_ADA_Demo.mp4"
W, H, FPS = 1280, 720, 15
MAX_CODE = 24

CSS = """
body{margin:0;background:#fff;font-family:'DejaVu Sans',Arial,sans-serif;color:#1f2328}
.cell{display:flex;gap:10px;padding:10px 28px 10px 14px;width:1238px;box-sizing:border-box}
.prompt{width:74px;flex:none;font-family:'DejaVu Sans Mono',monospace;font-size:14px;color:#303f9f;padding-top:9px;text-align:right}
.body{flex:1;min-width:0}
.md{font-size:17px;line-height:1.5}
.md h1{font-size:28px;margin:6px 0 10px}.md h2{font-size:22px;margin:4px 0 6px;color:#0b3d91}
.md p{margin:6px 0}.md ul{margin:4px 0 4px 18px;padding:0}.md li{margin:3px 0}
.code{background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:8px 12px;font-size:14.5px;line-height:1.4;overflow:hidden}
.code pre{margin:0;font-family:'DejaVu Sans Mono',monospace;white-space:pre}
.more{font-size:13.5px;color:#57606a;font-style:italic;margin-top:4px}
.out{margin-top:6px}
.out pre{font-family:'DejaVu Sans Mono',monospace;font-size:13.5px;line-height:1.35;margin:4px 0;white-space:pre;color:#24292f}
.out table{border-collapse:collapse;font-size:13px;margin:6px 0}
.out th,.out td{border:1px solid #d0d7de;padding:3px 8px;text-align:right}
.out th{background:#f0f3f6}
.out img{max-width:980px;display:block;margin:6px 0;border:1px solid #eee}
.oprompt{color:#d84315}
"""
FMT = HtmlFormatter(style="default", nowrap=False)


def md_html(src):
    r = subprocess.run(["pandoc", "-f", "markdown", "-t", "html"], input=src, capture_output=True, text=True)
    return r.stdout


def code_html(src):
    lines = src.splitlines()
    extra = 0
    if len(lines) > MAX_CODE + 4:
        extra = len(lines) - MAX_CODE
        lines = lines[:MAX_CODE]
    h = highlight("\n".join(lines), PythonLexer(), FMT)
    more = f'<div class="more">… {extra} more lines (full module code in the notebook)</div>' if extra else ""
    return f'<div class="code">{h}</div>{more}'


def out_html(outs):
    parts = []
    for o in outs:
        if o["output_type"] == "stream":
            t = "".join(o["text"]).splitlines()
            if len(t) > 34:
                t = t[:34] + [f"… ({len(t) - 34} more lines)"]
            parts.append(f"<pre>{html.escape(chr(10).join(t))}</pre>")
        elif "image/png" in o.get("data", {}):
            parts.append(f'<img src="data:image/png;base64,{o["data"]["image/png"]}">')
        elif "text/html" in o.get("data", {}):
            parts.append(o["data"]["text/html"] if isinstance(o["data"]["text/html"], str) else "".join(o["data"]["text/html"]))
    return f'<div class="out">{"".join(parts)}</div>' if parts else ""


def build_page():
    cells = []
    n = 0
    for i, c in enumerate(NB["cells"]):
        src = "".join(c["source"])
        if c["cell_type"] == "markdown":
            body = f'<div class="md">{md_html(src)}</div>'
            prompt = ""
        else:
            n += 1
            body = code_html(src) + out_html(c["outputs"])
            prompt = f"In&nbsp;[{n}]:"
        cells.append(f'<div class="cell" id="c{i}"><div class="prompt">{prompt}</div><div class="body">{body}</div></div>')
    page = f"<!doctype html><html><head><meta charset='utf-8'><style>{FMT.get_style_defs('.highlight')}{CSS}</style></head><body>{''.join(cells)}</body></html>"
    (WORK / "notebook.html").write_text(page)


def title_card(pg, path, kicker, title, sub=""):
    pg.set_content(f"""<html><body style="margin:0;width:{W}px;height:{H}px;background:#0f2742;display:flex;flex-direction:column;
    justify-content:center;padding:0 110px;box-sizing:border-box;font-family:'DejaVu Sans',Arial,sans-serif;color:#fff">
    <div style="font-size:20px;letter-spacing:3px;color:#9fc2ef;text-transform:uppercase">{kicker}</div>
    <div style="font-size:44px;font-weight:bold;margin:14px 0 18px;line-height:1.2">{title}</div>
    <div style="font-size:22px;color:#cfd8e3;line-height:1.5">{sub}</div></body></html>""")
    pg.screenshot(path=str(path))


def capture():
    shots = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto((WORK / "notebook.html").as_uri())
        pg.wait_for_timeout(500)
        for i in range(len(NB["cells"])):
            f = WORK / f"cell{i:02d}.png"
            pg.locator(f"#c{i}").screenshot(path=str(f))
            shots.append(f)
        cards = {}
        title_card(pg, WORK / "card_intro.png", "ADA Jackfruit Project · UE24AM343AB1 · Team ByteMe",
                   "Did the ABPS rollout alter MGNREGA worker deletions?",
                   "Demo: the project notebook, run end to end<br>Vivaan Atharva (PES1UG24AM071) · Vivek Varma (PES1UG24AM070)")
        chapters = {2: ("Step 1", "Estimators, tested on simulated data", "Fixed-effects OLS and PPML with state-clustered SEs"),
                    6: ("Step 2", "Parse the MGNREGA MIS extract", "15 district tables · sums checked against state totals"),
                    10: ("Step 3", "Build the deletion outcome", "Annual deletions per 1,000 workers, reconciled with official totals"),
                    12: ("Step 4", "Stage 0: validate the exposure proxy", "Pre-registered tests V1–V6 on pre-mandate ABPS use"),
                    19: ("Step 5", "Stage 1: difference-in-differences", "High-friction districts × post, district + state×year FE"),
                    23: ("Step 6", "Conclusions", "")}
        for k, (a, t, s) in chapters.items():
            title_card(pg, WORK / f"card_{k:02d}.png", a, t, s)
            cards[k] = WORK / f"card_{k:02d}.png"
        title_card(pg, WORK / "card_end.png", "Team ByteMe", "Thank you",
                   "Notebook, dataset, slides and IEEE report are in the ByteMe folder")
        b.close()
    return shots, cards


def ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0), 1))


def main():
    build_page()
    shots, cards = capture()
    imgs = [Image.open(s).convert("RGB") for s in shots]
    gap = 6
    tall_h = sum(im.height for im in imgs) + gap * len(imgs) + H
    tall = Image.new("RGB", (W, tall_h), "white")
    tops, y = [], 0
    for im in imgs:
        tall.paste(im, (0, y)); tops.append(y); y += im.height + gap
    ff = subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "34", "-pix_fmt", "yuv420p",
                           "-g", "200", "-an", "-movflags", "+faststart", str(OUT.with_suffix(".tmp.mp4"))],
                          stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    nframes = 0

    def emit(frame, secs):
        nonlocal nframes
        b = frame.tobytes()
        for _ in range(int(round(secs * FPS))):
            ff.stdin.write(b); nframes += 1

    def crop(y0):
        y0 = int(max(0, min(y0, tall_h - H)))
        return tall.crop((0, y0, W, y0 + H))

    def fade(a, b, secs=0.5):
        n = int(secs * FPS)
        for k in range(n):
            emit(Image.blend(a, b, (k + 1) / n), 1 / FPS)

    def scroll(y0, y1, secs):
        n = max(1, int(secs * FPS))
        for k in range(n):
            emit(crop(y0 + (y1 - y0) * ease((k + 1) / n)), 1 / FPS)

    def card(path, secs=3.2, prev=None):
        im = Image.open(path).convert("RGB")
        if prev is not None:
            fade(prev, im, 0.4)
        emit(im, secs)
        return im

    cur = card(WORK / "card_intro.png", 4.5)
    view_y = 0
    fade(cur, crop(0), 0.4)
    for i, im in enumerate(imgs):
        if i in cards:
            c = card(cards[i], 4.0, prev=crop(view_y))
            target = max(0, tops[i] - 20)
            fade(c, crop(target), 0.4)
            view_y = target
        target = max(0, tops[i] - 20)
        if abs(target - view_y) > 2:
            scroll(view_y, target, min(1.4, 0.5 + abs(target - view_y) / 1800))
            view_y = target
        cell = NB["cells"][i]
        text = "".join(cell["source"])
        n_out = len(cell.get("outputs", []))
        has_img = any("image/png" in o.get("data", {}) for o in cell.get("outputs", []))
        base = 3.0 if cell["cell_type"] == "markdown" else 3.5
        if has_img:
            base = 5.0
        hold = 1.4 * min(8.0, base + 0.02 * min(len(text.splitlines()), 40) + 0.6 * n_out)
        if im.height > H - 40:
            # read the top, then scroll slowly through the rest of the cell, pausing on images
            emit(crop(view_y), hold * 0.5)
            end = tops[i] + im.height - H + 40
            dist = end - view_y
            scroll(view_y, end, max(2.0, dist / 260))
            view_y = end
            emit(crop(view_y), hold * 0.5)
        else:
            emit(crop(view_y), hold)
    card(WORK / "card_end.png", 4.0, prev=crop(view_y))
    ff.stdin.close(); ff.wait()
    OUT.with_suffix(".tmp.mp4").rename(OUT)
    print(f"{nframes / FPS:.1f}s, {OUT.stat().st_size / 1e6:.2f} MB -> {OUT}")


if __name__ == "__main__":
    main()
