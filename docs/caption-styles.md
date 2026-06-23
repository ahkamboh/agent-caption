# Caption style presets

Drop-in GSAP caption looks. All follow the golden rule: **pre-render the word `<span>`s into the
DOM first**, then animate them. Pick a style to match the vibe (or let the user choose).

Shared scaffold (all styles use this):
```js
const Q = s => '[data-composition-id="main"] ' + s;
// pre-render: for each caption line build <div class="ll" data-idx="i"><span class="w">WORD</span>…</div>
// then per line: tl.set(line,{visibility:"visible"},start); ...animate .w...; tl.set(line,{visibility:"hidden"},end);
```

---

## 1. House (blur-clear rise) — calm, premium  *(default)*
```js
tl.to(words,{opacity:1,y:0,scale:1,filter:"blur(0px)",duration:.65,stagger:.06,ease:"power3.out"},start);
tl.to(words,{opacity:0,y:-14,filter:"blur(4px)",duration:.5,stagger:.03,ease:"power2.in"},end-.55);
// CSS .w start: opacity:0; transform:translateY(22px) scale(.96); filter:blur(6px);
```

## 2. Karaoke highlight — each word lights up as sung  *(lyrics, music)*
```js
// words start dim white; light the active word to accent on its own start time.
WORD_TIMINGS.forEach(({sel,start,end})=>{
  tl.to(sel,{color:"#ffd84a",scale:1.06,duration:.12,ease:"power2.out"},start);
  tl.to(sel,{color:"#ffffff",scale:1,duration:.2,ease:"power2.out"},end);
});
// CSS .w { color:rgba(255,255,255,.5) } — needs per-word start/end (from word-level transcript).
```

## 3. Bold punch-in — TikTok/MrBeast energy  *(hype, ads, shorts)*
```js
tl.from(words,{scale:1.6,opacity:0,duration:.18,stagger:.05,ease:"back.out(2.5)"},start);
tl.to(words,{opacity:0,duration:.12,stagger:.02,ease:"power1.in"},end-.2);
// CSS: font-weight 900, ALL CAPS, big (90px+), thick dark stroke or shadow for punch.
//   -webkit-text-stroke:6px #000; text-shadow:0 6px 0 #000;  accent every 2nd-3rd word.
```

## 4. Typewriter — technical / suspense
```js
// reveal words one at a time with no overlap (stagger == per-word dwell), hard cut.
tl.to(words,{opacity:1,duration:.01,stagger:0.12,ease:"none"},start);
tl.to(words,{opacity:0,duration:.01},end-.1);
// add a blinking caret via a trailing <span class="caret">|</span> animated opacity yoyo.
```

## 5. Slide-up mask — editorial / clean
```js
// wrap each line in an overflow:hidden mask; slide the text up from below.
tl.from(lineInner,{yPercent:120,duration:.7,ease:"expo.out"},start);
tl.to(lineInner,{yPercent:-120,duration:.5,ease:"power2.in"},end-.5);
// CSS: .ll{overflow:hidden} .ll-inner{display:inline-block}
```

## 6. Word-pop scale — playful / social
```js
tl.from(words,{scale:0,opacity:0,duration:.4,stagger:.07,ease:"back.out(2)"},start);
tl.to(words,{scale:0,opacity:0,duration:.25,stagger:.03,ease:"back.in(1.6)"},end-.3);
```

## 7. Active-word karaoke — Submagic / Hormozi / TikTok  *(short-form speech)*  — BUILT IN
Don't hand-roll this — `caption.py` generates it directly (paginated lines, active word lit as
spoken, using real word-level timing). Covers all three Remotion "Animated Captions" looks:
```bash
# springy rounded PILL that jumps word-to-word (the "animated background" look):
python3 scripts/caption.py vo.wav --lang en --content speech --style karaoke \
  --box "#3fa9ff" --font Poppins --font-file assets/fonts/poppins-800.ttf --maxwords 4 --out projects/<name>

# no box -> active word recolors + scales (the "colored words" / "scaling words" looks):
python3 scripts/caption.py vo.wav --lang en --content speech --style karaoke --hl "#ffd84a" --out projects/<name>
```
`--maxwords N` words per line · `--box HEX` pill color (omit for color highlight) · `--hl HEX`
active-word color when no box. The pill position is measured from each word's live layout and
animated with a `back.out` spring. Then include `captions.js` + `mountCaptions(tl)` as usual.

### Famous presets — `--preset` (CapCut / Submagic / Hormozi / Opus / Captions.ai)
One flag = a complete trending look (verified on render). CLI flags still override.
```bash
python3 scripts/caption.py vo.wav --content speech --style karaoke --preset hormozi \
  --font Montserrat --font-file assets/fonts/montserrat-900.ttf --out projects/<name>
```
| `--preset` | Look |
|---|---|
| `hormozi` | all-caps, thick black stroke, **green** active word + pop — the business benchmark |
| `beast`   | MrBeast: huge all-caps, heavy stroke, **yellow** active, big pop |
| `pill`    | white caps in a springy **yellow pill** (active text dark) |
| `neon`    | glowing text, **cyan** active word with a bigger glow |
| `gradient`| teal→blue→violet **gradient fill**, active pops + brightens |
| `minimal` | small clean white, no stroke/animation (lower-third) |
| `tiktok`  | white text on a rounded translucent **black bar** (classic) |
| `default` | white text, yellow active word + scale |

Hormozi/beast read best with Montserrat/Anton (heavy). For dark text on bright pills use `pill`.

---

### Choosing
- music/lyrics → House or Karaoke highlight
- short-form talking / UGC / reels → Active-word karaoke (#7, `caption.py --style karaoke --box`)
- ads / shorts / hype → Bold punch-in or Word-pop
- explainer / corporate → Slide-up mask or Typewriter
- always: pure-white default unless brand says otherwise; legibility via shadow/stroke when the
  background is busy (footage) — skip shadow on clean/solid backgrounds.
