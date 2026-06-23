# Prompt: Add perfectly-synced captions (any language)

Use the **caption agent** — `scripts/caption.py` — for ALL captioning. It bakes in every rule so
captions come out right the first time: frame-accurate, no early/late, no missing words, no
duplicate flashing, any language.

```
Add captions to my video/audio with the caption agent (scripts/caption.py).

INPUTS:
- MEDIA = "<audio or video path>"
- LANG    = "en"      (en, ur, hi, es, fr, ar, zh, ... — REQUIRED for non-English)
- CONTENT = "music"   (music/singing -> small.pt; speech/talking -> whisperX) — PROVEN, always set this
- STYLE = "word"      (word = single centered word / IShowSpeed; line = phrase lines;
                       karaoke = paginated lines, ACTIVE word highlighted as spoken — short-form speech)
- LOOK  = ""          (font, color, size, transition: none|pop|fade — optional;
                       karaoke: --preset hormozi|beast|pill|neon|gradient|minimal|tiktok (famous looks),
                       or --box "#3fa9ff" springy pill / --hl "#ffd84a" color; --maxwords 4)

DO:
1. Run the agent (it auto-uses whisperX for accuracy, small.pt fallback):
   python3 scripts/caption.py MEDIA --lang LANG --content CONTENT --style STYLE \
     [--pos center|bottom] [--transition none|pop|fade] \
     [--font Poppins --font-file assets/fonts/poppins-700.ttf --color "#ffffff" --size 108] \
     --out projects/<name>
   -> writes captions.js + captions.json into the project.
2. In the composition's <script> (after building tl, before registering it):
     <script src="captions.js"></script>
     window.mountCaptions(tl, { suppress: [[a,b], ...] });   // suppress = optional overlay windows
   (suppress only tiny windows where a full-screen graphic like a big "2026" must own the frame.)
3. Lint, render, run the acceptance loop (read frames AT word onsets to confirm sync).

RULES the agent already enforces (do not re-add manually):
- whisperX forced alignment (41 langs) -> exact vocal onsets; small.pt fallback otherwise.
- NO lead/lag offset. Continuous display (word holds to next onset; drops on >0.6s gaps).
- Collapses repeated words (chants) into one caption.
- Caption layer z-index ABOVE the video (z-index:45) — never behind it.
- Pre-rendered DOM, instant on/off by default (no transition) for tight sync.
```
