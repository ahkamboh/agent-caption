#!/usr/bin/env python3
"""
Export YouTube-ready subtitles (.srt + .vtt) from a word-level transcript.json.

Usage:
  python3 scripts/export-subs.py work/transcript.json [--out subs] [--max-chars 42] [--max-gap 0.8]

Groups words into readable caption lines (breaks on sentence punctuation, long pauses, or
max character count). Produces <out>.srt and <out>.vtt.
"""
import sys, json, argparse, os

def fmt_ts(t, vtt=False):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"

def group(words, max_chars, max_gap):
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        text = " ".join(x["text"] for x in cur)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_punct = w["text"].rstrip().endswith((".", "?", "!", ",", "…", "—"))
        long_pause = nxt and (nxt["start"] - w["end"]) >= max_gap
        too_long = len(text) >= max_chars
        if end_punct or long_pause or too_long or nxt is None:
            lines.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                          "text": " ".join(x["text"] for x in cur).strip()})
            cur = []
    return lines

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--out", default="subs")
    ap.add_argument("--max-chars", type=int, default=42)
    ap.add_argument("--max-gap", type=float, default=0.8)
    args = ap.parse_args()

    words = json.load(open(args.transcript))
    if words and "words" in (words[0] if isinstance(words, list) else {}):
        # segments file fallback: flatten
        flat = []
        for s in words:
            flat += s.get("words", [])
        words = flat
    lines = group(words, args.max_chars, args.max_gap)

    # SRT
    with open(args.out + ".srt", "w", encoding="utf-8") as f:
        for i, ln in enumerate(lines, 1):
            f.write(f"{i}\n{fmt_ts(ln['start'])} --> {fmt_ts(ln['end'])}\n{ln['text']}\n\n")
    # VTT
    with open(args.out + ".vtt", "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for ln in lines:
            f.write(f"{fmt_ts(ln['start'], True)} --> {fmt_ts(ln['end'], True)}\n{ln['text']}\n\n")

    print(f"[export-subs] {len(lines)} cues -> {args.out}.srt + {args.out}.vtt")

if __name__ == "__main__":
    main()
