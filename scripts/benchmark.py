#!/usr/bin/env python3
"""
benchmark.py — measure the REAL accuracy gain with word-error-rate (WER).

Compares the OLD default (small model, no vocal isolation) against the NEW default
(whisper large-v3, + Demucs isolation for songs) on a clip whose correct transcript
you provide. Prints WER for each and the relative improvement.

You provide:
  • a media file
  • its KNOWN-CORRECT transcript: a plain .txt (or an .srt/.vtt — timing is ignored)

Run with the venv python (it needs the engine + model):
  .venv-whisperx/bin/python scripts/benchmark.py CLIP.mp4 --ref truth.txt
  .venv-whisperx/bin/python scripts/benchmark.py SONG.mp4 --ref lyrics.txt --music
  (add --hinglish for mixed Hindi-English)

WER is computed with standard normalization (lowercase, punctuation stripped) and a
word-level Levenshtein distance — no external deps.
"""
import os, sys, re, argparse, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(ROOT, "caption.py")


def norm(text):
    """Standard WER normalization → word list."""
    text = (text or "").lower()
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    return text.split()


def strip_srt(raw):
    """Drop index lines, timestamps, and WEBVTT header — keep just the spoken text."""
    keep = []
    for l in raw.splitlines():
        s = l.strip()
        if not s or "-->" in s or s.isdigit() or s.upper() == "WEBVTT":
            continue
        keep.append(s)
    return " ".join(keep)


def read_text(path):
    raw = open(path, encoding="utf-8").read()
    return strip_srt(raw) if path.lower().endswith((".srt", ".vtt")) else raw


def wer(ref, hyp):
    """Levenshtein word distance / len(ref). Returns (wer, distance, n_ref)."""
    n, m = len(ref), len(hyp)
    if n == 0:
        return (0.0 if m == 0 else 1.0), m, 0
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m] / n, prev[m], n


def run_config(media, base, extra, label):
    """Run caption.py in --srt mode (transcribe+align only, no burn) and return the hypothesis text."""
    srt = os.path.join("work", base + ".srt")
    if os.path.exists(srt):
        os.remove(srt)
    print(f"\n=== running: {label} ===", file=sys.stderr)
    subprocess.run([sys.executable, CAP, media, "--srt"] + extra, check=False)
    if not os.path.exists(srt):
        print(f"!! {label}: no transcript produced (is the venv set up? run `python setup.py`)", file=sys.stderr)
        return None
    return strip_srt(open(srt, encoding="utf-8").read())


def main():
    ap = argparse.ArgumentParser(description="WER benchmark: old default (small) vs new default (large-v3)")
    ap.add_argument("media")
    ap.add_argument("--ref", required=True, help="known-correct transcript (.txt or .srt/.vtt)")
    ap.add_argument("--music", action="store_true", help="treat as a song (Demucs isolation on the new run)")
    ap.add_argument("--hinglish", action="store_true", help="mixed Hindi-English audio")
    a = ap.parse_args()

    if not os.path.exists(a.media):
        sys.exit(f"!! no such media: {a.media}")
    if not os.path.exists(a.ref):
        sys.exit(f"!! no such reference: {a.ref}")

    ref = norm(read_text(a.ref))
    if not ref:
        sys.exit("!! the reference transcript is empty.")
    base = os.path.splitext(os.path.basename(a.media))[0]
    hl = ["--hinglish"] if a.hinglish else []

    # OLD default = small model, no vocal isolation, speech path
    old_hyp = run_config(a.media, base, ["--fast", "--no-isolate", "--content", "speech"] + hl,
                         "OLD default — small, no isolation")
    # NEW default = large-v3 (default), + Demucs isolation when it's a song
    new_extra = (["--content", "music"] if a.music else []) + hl
    new_hyp = run_config(a.media, base, new_extra, "NEW default — large-v3" + (" + demucs" if a.music else ""))

    if old_hyp is None or new_hyp is None:
        sys.exit("!! benchmark aborted — a run produced no transcript.")

    ow, od, n = wer(ref, norm(old_hyp))
    nw, nd, _ = wer(ref, norm(new_hyp))
    rel = ((ow - nw) / ow * 100) if ow > 0 else 0.0

    print("\n" + "=" * 56)
    print(f"  reference words: {n}")
    print(f"  OLD (small, no isolation):  WER {ow*100:5.1f}%   ({od} errors)")
    print(f"  NEW (large-v3{' + demucs' if a.music else ''}):       WER {nw*100:5.1f}%   ({nd} errors)")
    print("-" * 56)
    if rel >= 0:
        print(f"  improvement: {rel:.0f}% fewer errors (relative)")
    else:
        print(f"  regression:  {-rel:.0f}% MORE errors — investigate")
    print("=" * 56)
    print("\n(tip: also try --glossary / --script for the accuracy stack; --script → ~0 errors when you have the text.)")


if __name__ == "__main__":
    main()
