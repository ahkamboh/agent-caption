#!/usr/bin/env bash
# anycaption — one-time setup. Creates the venv + installs deps.
set -euo pipefail
echo "== anycaption setup =="

command -v ffmpeg  >/dev/null || { echo "!! ffmpeg required:  brew install ffmpeg (mac) / apt install ffmpeg (linux)"; exit 1; }
command -v python3 >/dev/null || { echo "!! python3 (3.10+) required"; exit 1; }
echo "ok: $(python3 -V), ffmpeg present"

# 1) system whisper (caption.py's transcribe path shells out to system python3)
echo "-- installing openai-whisper + soundfile (system) --"
python3 -m pip install --user --break-system-packages openai-whisper soundfile 2>/dev/null \
  || python3 -m pip install --user openai-whisper soundfile \
  || echo "  (install openai-whisper + soundfile manually if this failed)"

# 2) venv for whisperX / MMS forced alignment / offline translation
echo "-- creating ./.venv-whisperx --"
python3 -m venv .venv-whisperx
./.venv-whisperx/bin/pip install --upgrade pip
echo "-- installing requirements (heavy step: torch + whisperx, a few minutes) --"
./.venv-whisperx/bin/pip install -r requirements.txt \
  || echo "  (if torch failed, install the right build for your platform from https://pytorch.org/get-started/locally/ then re-run)"

echo
echo "== done =="
echo "Models (Whisper small, MMS_FA, whisperX) auto-download on first run."
echo
echo "Try it:"
echo "  ./.venv-whisperx/bin/python scripts/align.py your_video.mp4 --lang en --out work/transcript.json"
echo "  python3 scripts/export-subs.py work/transcript.json --out work/subs"
echo "  ffmpeg -i your_video.mp4 -vf subtitles=work/subs.srt -c:a copy captioned.mp4"
