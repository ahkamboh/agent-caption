# local-caption — add captions to any video, in any language, for any AI agent

**Free & open-source captioning that any AI agent can run — on Windows, macOS, and Linux.** Add accurate, perfectly-timed captions / subtitles to **any video or song**, in **any language** (English by default), for both **speech and music** — with first-class **Hinglish / code-switched** support. Words come from speech recognition; **timing comes from forced alignment on the waveform**, so captions never drift early or late.

> Built for **Claude Code, Cursor, Codex, Grok**, and any IDE/agent. Point your agent at this repo and ask it to caption your video.

## ⚡ Setup prompt — paste this into your AI agent
Clone the repo, open it in your agent (Claude Code / Cursor / Codex / Grok / any), then paste:

```
You are a captioning agent. Read ./SKILL.md in this repo and follow it exactly.

Goal: add accurate, perfectly-timed captions to the video/audio I give you, in any
language (default English; Hinglish supported), for both speech AND music.

Do this:
1. if ./.venv-whisperx isn't set up yet, run:  python setup.py
2. ask me for the media file path (and the language if it isn't English)
3. caption it with ONE command:  python caption.py <file>
     - Hinglish:           --hinglish
     - a song / music:     --content music
     - a famous look:      --style hormozi|tiktok|beast|...   (15 styles)
     - names/brands so they're not mis-heard:   --glossary "name1, name2"
     - you already have the exact words/lyrics:  --script lyrics.txt   (100% accurate)
4. show me the output path (<file>.captioned.mp4)

It uses Whisper large-v3 by default (best accuracy) and times every word by forced
alignment on the waveform, so captions never drift. Read SKILL.md, then ask me for the file.
```

Agents auto-read the pointer files, so you often don't even need the prompt:
- **Claude Code** — open the folder; it reads `CLAUDE.md`. Just say *"caption ./myvideo.mp4"*.
- **Cursor** — reads `.cursorrules`. Say *"caption ./reel.mp4 in hinglish"*.
- **Codex** — reads `AGENTS.md`. Same.
- **Grok / ChatGPT / any chat agent** — paste the prompt above + the contents of `SKILL.md`.

## ⚡ Easiest way — ONE command

```bash
python caption.py myvideo.mp4
```

That's it. It transcribes, aligns the timing to the audio, and burns clean captions that are **auto-sized and positioned to fit the video** (proportional on any resolution — landscape *or* vertical), English by default → `myvideo.captioned.mp4`. Best accuracy out of the box (**Whisper large-v3 by default**). No styling, no tweaking. Works even if your ffmpeg lacks libass (it falls back to rendering captions and compositing them with the core `overlay` filter).

**Power users** — same command, optional flags:
```bash
python caption.py reel.mp4 --hinglish --style tiktok     # Hinglish + TikTok box look
python caption.py talk.mp4 --style hormozi --pos center  # big bold caps, centered
python caption.py clip.mp4 --lang ur --size 6            # Urdu, slightly larger
python caption.py talk.mp4 --fast                        # small model = faster (lower accuracy)
python caption.py vid.mp4  --fill "#ff3da6" --box "#000a" --caps   # describe your OWN look
python caption.py vid.mp4  --srt                         # just write the .srt, no burn
python caption.py vid.mp4  --from-srt my.srt             # burn an existing .srt, proportioned
```

### 🎯 Accuracy — for when the words must be exactly right (free, local, no human)
Timing is correct by construction (forced alignment). The only thing that can go wrong is a
**mis-heard word** — a name, slang, or a homophone like *their/there*. Three free levers fix that:

```bash
python caption.py talk.mp4 --glossary "Xaibridge, Hinglish, Kamboh"   # bias ASR to your names/brands
python caption.py song.mp4 --script lyrics.txt                        # you have the text? 100% accurate words
python caption.py talk.mp4 --grammar                                  # offline their/there, your/you're fix
python caption.py talk.mp4 --glossary names.txt --grammar            # stack them for max accuracy
```
- **`--glossary`** biases recognition toward your terms (a list or a `.txt`) — biggest win on names.
- **`--script`** skips ASR and only *times* the words you give it → content is **100% correct**.
- **`--grammar`** runs **LanguageTool locally** (no upload, no tokens) to fix homophones; timing untouched.
  Enable once: `python setup.py --grammar` (needs Java/JRE 8+) — it skips cleanly if not installed.

### 🎵 Songs — isolate the vocals (`--content`)
On music, captioning the **isolated vocal stem** (Demucs) instead of the full mix makes lyric
transcription far cleaner. It's conditional — it only helps on songs — so it's gated:
```bash
python caption.py song.mp4 --content music       # force vocal isolation before ASR
python caption.py clip.mp4                        # default 'auto': detects music, isolates only then
python caption.py podcast.mp4 --content speech    # never isolate (clean speech doesn't need it)
```
`auto` runs a quick music/speech probe so podcasts/interviews are never slowed. The captions still
burn onto your original video — only the audio we transcribe is the cleaned stem.

**15 famous styles** (bundled fonts included — Poppins, Anton, Bebas Neue, Archivo Black):
`clean` · `bold` · `hormozi` · `green` · `beast` · `impact` · `bebas` · `tiktok` · `pill` · `boxed` · `yellow` · `neon` · `gradient` · `minimal` · `subtitle`

## Requirements
- **Python 3.10+** — torch supports 3.14; if `whisperx` lacks a wheel on a brand-new version, use 3.11–3.12
- **ffmpeg** — macOS `brew install ffmpeg` · Ubuntu `sudo apt install ffmpeg` · Windows `winget install ffmpeg`
- ~4 GB disk for models — `python setup.py` **downloads `large-v3` for you** (the default — best accuracy, instant first caption). Add `python setup.py --small` to also fetch the small model for `--fast`.

## Run it yourself (no agent)
Set up once, then call scripts with the venv's python.

```bash
python setup.py        # creates ./.venv-whisperx and installs everything (Win/Mac/Linux)
```

`PY` below = the venv python:
**macOS/Linux** `./.venv-whisperx/bin/python` · **Windows** `.venv-whisperx\Scripts\python`

```bash
# speech, English (default):
PY scripts/align.py video.mp4 --lang en --out work/transcript.json
PY scripts/export-subs.py work/transcript.json --out work/subs
ffmpeg -i video.mp4 -vf "subtitles=work/subs.srt" -c:a copy captioned.mp4

# Hinglish / mixed Hindi-English:
PY scripts/align.py video.mp4 --code-switch --dual hi en --out work/transcript.json

# translate captions into many languages (offline):
PY scripts/multilang-subs.py work/subs.srt --to "hi,ur,es,fr,ar"

# styled TikTok / Hormozi animated captions:
PY scripts/caption.py video.mp4 --lang en --content speech --style karaoke --preset hormozi --out out/
```

## What it does
- captions in **any language** — English by default, **Hinglish / code-switched** first-class, 1100+ languages aligned (MMS_FA)
- works on **speech and music / lyrics** — with optional **Demucs vocal isolation** for songs (`--content`)
- **Whisper large-v3 by default** (best accuracy) + an **accuracy stack** (`--glossary` / `--script` / `--grammar`) to kill mis-heard words, all local
- **forced alignment** = frame-accurate timing, never early or late
- outputs **.srt / .vtt** (great for YouTube — selectable + SEO), a burned-in video, or animated styled captions
- **15 famous burn styles** with **bundled fonts** (Poppins/Anton/Bebas Neue/Archivo Black) — hormozi, beast, tiktok, gradient, neon, pill, bebas… via `--style <name>`
- translate subtitles into 30+ languages, fully **offline**
- runs on **Windows, macOS, Linux** · 100% local · free · **MIT**

## How it works
1. **(songs) Isolate** — on music, Demucs separates the vocal stem so Whisper isn't fighting the backing track.
2. **Words** — Whisper / faster-whisper transcribes the audio (per-segment language ID handles code-switching like Hinglish); or supply your own with `--script`.
3. **Timing** — those words are force-aligned to the waveform (whisperX for 40+ languages, MMS_FA for 1100+). Timing comes from the audio, not the spelling — so text errors never cause drift.
4. **Output** — `.srt` / `.vtt`, a burned-in video, or an animated `captions.js` for motion graphics.

## License
MIT — free for anyone, including AI agents. Built by [Ali Hamza Kamboh](https://alihamzakamboh.com).
