# anycaption — SKILL

You are an AI **captioning agent**. This repo adds **accurate, perfectly-timed captions/subtitles to any video or audio, in any language** (English by default), for both **speech and music**, with first-class **Hinglish / code-switched** support.

Core principle: **words come from speech recognition, but TIMING comes from forced alignment on the waveform — never from raw ASR timestamps.** That's why captions never drift early/late, even when the transcript has spelling errors.

## One-time setup
Requires: Python 3.10+, `ffmpeg`, ~4 GB disk for models.
```bash
bash setup.sh          # creates ./.venv-whisperx and installs deps
```
Models (Whisper `small`, MMS_FA, whisperX align models) auto-download on first run.

## The scripts
- `scripts/transcribe.py` — Whisper → word-level transcript (fast; English default; `--lang xx` for others).
- `scripts/align.py` — **forced alignment** for frame-accurate timing. `--code-switch` for mixed-language (Hinglish / Punjabi-English).
- `scripts/cs_transcribe.py` — code-switch-robust word recognition (per-segment language ID).
- `scripts/mms_align.py` — universal MMS_FA forced aligner (1100+ languages, any script).
- `scripts/export-subs.py` — transcript → `.srt` + `.vtt`.
- `scripts/multilang-subs.py` — translate subtitles into many languages, **offline**.
- `scripts/caption.py` — all-in-one **styled** captions (karaoke / word / line; Hormozi / TikTok / neon …) → animated `captions.js`.

## How to caption a video (the main job)

**Default language = English.** For another language pass `--lang <code>`. For **Hinglish / mixed** use `--code-switch`.

### 1) Frame-accurate word timings
Speech (talking, podcast, UGC, explainer):
```bash
./.venv-whisperx/bin/python scripts/align.py INPUT --lang en --out work/transcript.json
```
Hinglish / mixed Hindi-English (or any code-switched audio):
```bash
./.venv-whisperx/bin/python scripts/align.py INPUT --code-switch --dual hi en --out work/transcript.json
```
Any other language (Urdu, Spanish, Arabic, Chinese, …):
```bash
./.venv-whisperx/bin/python scripts/align.py INPUT --lang ur --out work/transcript.json
```

### 2a) Subtitles (.srt / .vtt) + burn into the video
```bash
python3 scripts/export-subs.py work/transcript.json --out work/subs
ffmpeg -i INPUT -vf "subtitles=work/subs.srt" -c:a copy captioned.mp4
```
The `.srt` is also perfect to upload to YouTube directly (selectable + SEO).

### 2b) Styled / animated captions (Hormozi, TikTok, karaoke — short-form)
```bash
python3 scripts/caption.py INPUT --lang en --content speech --style karaoke --preset hormozi --out out/
```
→ writes `out/captions.js` (+ `captions.json`). Presets: `hormozi`, `beast`, `pill`, `neon`, `gradient`, `minimal`, `tiktok`. Use `--content music` for songs/lyrics (better perceived timing). See `docs/caption-styles.md`.

### 3) Translate captions into any language (optional)
```bash
./.venv-whisperx/bin/python scripts/multilang-subs.py work/subs.srt --to "hi,ur,es,fr,ar,de" [--burn INPUT]
```

## Rules (baked in — do not override)
- Timing is ALWAYS forced alignment, never raw ASR timestamps (no lead/lag).
- **Default caption language = English**; pass `--lang` for anything else.
- Music/singing → `--content music`; speech/talking → `--content speech` (caption.py auto-picks the aligner).
- Collapses repeated words; continuous display; drops captions on long gaps.
- Before delivering, spot-check a few captions at their word onsets to confirm sync.

## Language codes
`en` (default), `hi`, `ur`, `pa`, `es`, `fr`, `de`, `pt`, `ar`, `zh`, `ja`, `ko`, `ru`, `it`, `tr`, `id`, `nl`, `pl`, `uk`, … — Whisper supports ~99 languages; MMS_FA aligns 1100+.
