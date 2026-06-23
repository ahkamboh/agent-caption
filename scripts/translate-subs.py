#!/usr/bin/env python3
"""
Translate an .srt subtitle file to another language — fully OFFLINE, no API key.
Uses Argos Translate (neural MT, downloads a language pack once, then offline).

Setup (one time):  python3 -m pip install --user argostranslate
Usage:             python3 scripts/translate-subs.py subs.srt --to es [--from en] [--out subs.es.srt]

Language codes: en es fr de it pt ru zh ja ar hi tr nl pl uk ...
If the pack isn't installed it is downloaded automatically on first run.
"""
import sys, re, argparse

def parse_srt(path):
    blocks = re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip())
    out = []
    for b in blocks:
        lines = b.splitlines()
        if len(lines) >= 3:
            out.append((lines[0], lines[1], " ".join(lines[2:])))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srt"); ap.add_argument("--to", required=True)
    ap.add_argument("--from", dest="src", default="en")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or args.srt.rsplit(".", 1)[0] + f".{args.to}.srt"

    try:
        import argostranslate.package, argostranslate.translate
    except ImportError:
        sys.exit("Install first:  python3 -m pip install --user argostranslate")

    # ensure language pair installed
    installed = {(l.code) for l in argostranslate.translate.get_installed_languages()}
    if args.src not in installed or args.to not in installed:
        print(f"[translate] downloading {args.src}->{args.to} pack...")
        argostranslate.package.update_package_index()
        avail = argostranslate.package.get_available_packages()
        pkg = next((p for p in avail if p.from_code == args.src and p.to_code == args.to), None)
        if not pkg:
            sys.exit(f"No offline pack for {args.src}->{args.to}.")
        argostranslate.package.install_from_path(pkg.download())

    langs = argostranslate.translate.get_installed_languages()
    src = next(l for l in langs if l.code == args.src)
    dst = next(l for l in langs if l.code == args.to)
    tr = src.get_translation(dst)

    blocks = parse_srt(args.srt)
    with open(out, "w", encoding="utf-8") as f:
        for idx, ts, text in blocks:
            f.write(f"{idx}\n{ts}\n{tr.translate(text)}\n\n")
    print(f"[translate] {len(blocks)} cues {args.src}->{args.to} -> {out}")

if __name__ == "__main__":
    main()
