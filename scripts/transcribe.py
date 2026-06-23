#!/usr/bin/env python3
"""
Transcribe audio/video to word-level + segment-level JSON with Whisper.

Usage:
  python3 scripts/transcribe.py <audio_or_video> [--model small] [--lang en] [--out work/transcript.json]

Defaults:
  model = small      (NOT base — base hallucinates lyrics/rap; NOT *.en for non-English)
  lang  = auto       (whisper auto-detects; pass --lang for known language)

Outputs two files next to --out:
  <out>            : flat word list   [{text,start,end}, ...]
  <out>.segments   : segment list     [{text,start,end}, ...]

Language rule:
  - Known English  -> --model small.en  (faster, English only)
  - Known other    -> --lang <code> with --model small (NEVER *.en, it translates)
  - Unknown        -> leave --lang off, model small (auto-detect)
"""
import sys, json, argparse, warnings, subprocess, os, tempfile
warnings.filterwarnings("ignore")

def ensure_wav(src):
    if src.lower().endswith(".wav"):
        return src, False
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", tmp],
                   check=True, capture_output=True)
    return tmp, True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--out", default="work/transcript.json")
    args = ap.parse_args()

    import whisper
    wav, is_tmp = ensure_wav(args.input)
    sys.stderr.write(f"[transcribe] loading {args.model}...\n")
    m = whisper.load_model(args.model)
    sys.stderr.write("[transcribe] transcribing...\n")
    kw = dict(word_timestamps=True, verbose=False, fp16=False,
              condition_on_previous_text=False, temperature=0.0)
    if args.lang:
        kw["language"] = args.lang
    r = m.transcribe(wav, **kw)

    words, segs = [], []
    for s in r["segments"]:
        segs.append({"start": round(s["start"], 2), "end": round(s["end"], 2),
                     "text": s["text"].strip()})
        for w in s.get("words", []):
            words.append({"text": w["word"].strip(),
                          "start": round(w["start"], 2), "end": round(w["end"], 2)})

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(words, open(args.out, "w"), ensure_ascii=False, indent=2)
    json.dump(segs, open(args.out + ".segments", "w"), ensure_ascii=False, indent=2)

    if is_tmp:
        os.unlink(wav)

    print(f"[transcribe] language: {r.get('language')}")
    print(f"[transcribe] {len(words)} words, {len(segs)} segments -> {args.out}")
    for s in segs:
        print(f"  {s['start']:6.2f} - {s['end']:6.2f}  {s['text']}")

if __name__ == "__main__":
    main()
