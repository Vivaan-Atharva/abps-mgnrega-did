"""Narrated video presentation (synthetic voice, Flite CMU SLT) over the project slides.

Each scene = one slide image + its narration. Scenes are encoded separately with identical
settings, concatenated with -c copy, and the narration track is muxed in.
Also writes a subtitle file (.srt) with the on-screen wording of the narration.
"""
import ctypes
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "deliverables" / "build" / "ByteMe_ADA_Project.pdf"
WORK = ROOT / "deliverables" / "build" / "video"
OUT = ROOT / "deliverables" / "ByteMe_ADA_Video.mp4"
WORK.mkdir(parents=True, exist_ok=True)

# (slide number in PDF, spoken text, caption text)
SCENES = [
    (1, "Hello. We are team Byte Me: Vivaan Atharva and Vivek Varma. Our Advanced Data Analytics project asks one question. "
        "Did the rollout of the Aadhaar based payment system, A B P S, change how many workers were deleted from the rural employment scheme, M G N REGA?",
        "Team ByteMe: Vivaan Atharva and Vivek Varma. Did the ABPS rollout change how many workers were deleted from MGNREGA?"),
    (3, "In January twenty twenty three, the Ministry of Rural Development ordered that all wages be paid through A B P S. "
        "After five extensions, it became binding in January twenty twenty four. "
        "A B P S needs three links for each worker: Aadhaar on the job card, Aadhaar on the bank account, and the bank in the N P C I mapper. "
        "In the same period, worker deletions rose from fifteen million to almost fifty two million in a single year. "
        "We ask whether deletions rose more in districts where converting accounts to A B P S was harder.",
        "ABPS became mandatory in 2023–24, and deletions rose from 15.0M to 51.9M. Did they rise more where conversion was harder?"),
    (4, "What makes this study different? Most public work on A B P S deletions is descriptive. "
        "We run a district level, within state test. And because our reviewer pointed out that everything rests on a proxy, "
        "we validate that proxy before we use it, with pass rules written down in advance.",
        "A within-state district test, with the exposure proxy validated before use."),
    (5, "Our data come from the scheme's own management information system. "
        "We pulled fifteen district level tables, covering about seven hundred and ten districts, from financial year twenty eighteen to twenty twenty three. "
        "They give account types, registered and deleted workers, and Aadhaar based payments. "
        "Every table's district rows add up exactly to its state totals, and our rebuilt deletion counts match ninety seven percent of the official figures.",
        "15 MIS tables, ~710 districts, FY2018–19 to FY2022–23; district sums match state totals; deletions match 97% of official."),
    (6, "Here is the design. We extract and audit the data. Then, in stage zero, we test whether the share of post office or joint accounts "
        "really tracks how hard it was to move a district onto A B P S. Only if it passes do we run stage one: a difference in differences "
        "with district and state by year fixed effects, standard errors clustered by state, and a set of checks.",
        "Extract and audit → Stage 0 proxy validation → Stage 1 difference-in-differences with checks."),
    (7, "The results. Stage zero passes our rule. Districts with more post office or joint accounts used A B P S less before it was mandatory, "
        "and no single state drives this. But the link is weak, explaining about three percent of the variation. "
        "Stage one finds no larger rise in deletions in high friction districts: minus one point two per thousand workers, "
        "with a confidence interval from minus nineteen to plus seventeen. Twelve of fourteen specifications agree.",
        "Stage 0: GO, but weak. Stage 1: −1.2 per 1,000 workers (95% CI −19.4 to 17.0); 12 of 14 specifications not significant."),
    (8, "These charts show why. On the left, high exposure districts really did use A B P S less before the mandate. "
        "On the right, they already deleted more workers than the rest of their state before A B P S. "
        "When deletions jumped from thirty four to one hundred and twenty per thousand, that gap did not widen.",
        "High-exposure districts used ABPS less and already deleted more; the gap did not widen when deletions jumped."),
    (9, "What is done, and what remains. Extraction, proxy validation and the full difference in differences are complete. "
        "The most important next step is adding financial years twenty twenty three to twenty five, "
        "because the A B P S order came late in our only post year, and only became binding the year after.",
        "Done: extraction, validation, DiD. Next: FY2023–24 and FY2024–25, crosswalk, covariates."),
    (10, "The work was split between us: Vivaan led data extraction and the proxy validation; "
         "Vivek led the parsing, audit and the difference in differences; and we built the report, slides and this video together.",
         "Who did what: Vivaan – extraction, Stage 0; Vivek – parsing, audit, DiD; both – report, slides, video."),
    (12, "Our main lessons. Validate a proxy before you trust it. Check whether a government table is year specific or just today's snapshot. "
         "Test your estimators on simulated data. And report a null result honestly, with its confidence interval.",
         "Validate proxies, test data tables and estimators, and report nulls honestly."),
    (13, "Open challenges remain: only one post mandate year, a weak proxy, timing differences between the system and official figures, "
         "and district splits that still need a crosswalk.",
         "Open: one post year, weak proxy, timing differences, district splits."),
    (15, "Thank you for watching. All code, data and the report are in our team folder.",
         "Thank you. Code, data and report are in the ByteMe folder."),
]

L = "/usr/lib/x86_64-linux-gnu/"
for n in ("libflite.so.1", "libflite_usenglish.so.1", "libflite_cmulex.so.1"):
    ctypes.CDLL(L + n, mode=ctypes.RTLD_GLOBAL)
FL = ctypes.CDLL(L + "libflite.so.1")
VO = ctypes.CDLL(L + "libflite_cmu_us_slt.so.1")
FL.flite_init()
VO.register_cmu_us_slt.restype = ctypes.c_void_p
VOICE = VO.register_cmu_us_slt(None)
FL.flite_text_to_speech.restype = ctypes.c_float
FL.flite_text_to_speech.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(1)


def wav_dur(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def ts(t):
    h, rem = divmod(t, 3600); m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def main():
    # slide images at 1920x1080
    run(["pdftoppm", "-png", "-scale-to-x", "1920", "-scale-to-y", "1080", str(PDF), str(WORK / "slide")])
    pad_before, pad_after = 0.6, 0.9
    parts, srt, t0 = [], [], 0.0
    for k, (n, spoken, cap) in enumerate(SCENES, 1):
        raw = WORK / f"n{k:02d}_raw.wav"
        FL.flite_text_to_speech(spoken.encode(), VOICE, str(raw).encode())
        aud = WORK / f"n{k:02d}.wav"
        # slightly slower speech is easier to follow; pad with silence; 48 kHz stereo
        run(["ffmpeg", "-y", "-i", str(raw), "-af", f"atempo=0.94,adelay={int(pad_before*1000)}:all=1,apad=pad_dur={pad_after},aresample=48000",
             "-ac", "2", str(aud)])
        d = wav_dur(aud)
        img = sorted(WORK.glob(f"slide-{n:02d}.png"))[0]
        tmp = WORK / f"scene{k:02d}.tmp.mp4"
        fade_out = max(d - 0.35, 0)
        run(["ffmpeg", "-y", "-framerate", "30", "-i", str(img), "-vf",
             f"scale=1920:1080,format=yuv420p,loop=-1:1,trim=duration={d:.3f},fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.3f}:d=0.35",
             "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30", str(tmp)])
        final = WORK / f"scene{k:02d}.mp4"
        tmp.rename(final)
        parts.append((final, aud))
        srt.append(f"{k}\n{ts(t0 + pad_before)} --> {ts(t0 + d - pad_after)}\n{cap}\n")
        t0 += d
        print(f"scene {k}: slide {n}, {d:.1f}s", file=sys.stderr)
    (WORK / "list.txt").write_text("".join(f"file '{v.name}'\n" for v, _ in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / "list.txt"), "-c", "copy", str(WORK / "video_only.mp4")])
    (WORK / "alist.txt").write_text("".join(f"file '{a.name}'\n" for _, a in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / "alist.txt"), "-c:a", "pcm_s16le", str(WORK / "audio.wav")])
    tmp = OUT.with_suffix(".tmp.mp4")
    run(["ffmpeg", "-y", "-i", str(WORK / "video_only.mp4"), "-i", str(WORK / "audio.wav"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp)])
    tmp.rename(OUT)
    OUT.with_suffix(".srt").write_text("\n".join(srt))
    print(f"total {t0:.1f}s -> {OUT}")


if __name__ == "__main__":
    main()
