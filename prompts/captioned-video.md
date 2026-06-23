# Prompt: Any Video → Add Captions / Lyrics / Graphics

Paste into Claude Code inside `xotion-studio`. Works for talking-head, UGC ads, Pinterest clips,
reels — any video where you want captions + optional graphics burned on top.

```
Add captions and graphics to my video in the xotion-studio house style (see CLAUDE.md).

INPUTS:
- VIDEO = "<absolute path to the video>"
- LANGUAGE = "english"     (caption language; transcribe in this language)
- STYLE = "auto"           (auto | lyric | ugc-ad | reactive-hud)
- BRAND = ""               (optional: logo path + brand name for ad-style callouts)
- NOTES = ""               (anything specific: "no shadow", "blue scheme", "Meta-ad safe", etc.)

DO:
1. Probe the video (orientation, fps, duration). Re-encode with dense keyframes if needed.
2. Create projects/<name>/, copy video -> assets/source.mp4, fonts from repo.
3. Transcribe the video's audio with scripts/transcribe.py (model small, --lang if needed).
4. Pick template:
   - lyric/music     -> lyric-video-(vertical|landscape).html
   - UGC ad w/ brand -> ugc-ad-vertical.html  (3-tier captions, logo chip, callout graphics)
   - talking-head    -> reactive-captions-landscape.html (HUD + captions)
   The original video is the base layer; captions/graphics overlay on top.
5. Build captions synced to word timings. Keep them legible (house caption rules).
   Only add graphic callouts at the few key moments (Meta-ad: keep it minimal + add a
   "simulated / educational" disclaimer if it's a prop-firm/finance ad).
6. Lint 0/0, render, verify frames, fix, deliver. Offer reels if it's vertical.
```
