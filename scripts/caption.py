#!/usr/bin/env python3
"""
CAPTION AGENT — the one tool to build perfectly-synced captions for ANY language, in one pass.
Encapsulates every hard-won rule so captions never come out early/late/missing/duplicated.

What it does:
  1. Gets frame-accurate word timings:
       - whisperX forced alignment (41 languages) via .venv-whisperx  ->  best sync
       - falls back to Whisper small.pt (scripts/transcribe.py) for other languages
  2. Cleans the events: collapses repeated words (no "oh oh oh" fl: flashing),
     continuous display (each word holds until the next onset; drops on long gaps),
     NO lead/lag (uses exact onsets).
  3. Emits a self-contained caption layer: captions.js  (+ captions.json data)
     The composition just includes it and calls window.mountCaptions(tl, opts).

Usage:
  python3 scripts/caption.py <audio_or_video> --lang en [options]

Options:
  --content music|speech  CONTENT TYPE (picks the aligner automatically):
                          music/singing -> small.pt (perfect perceived timing)
                          speech/talking -> whisperX (far better, forced alignment)
  --lang CODE        language (en, ur, hi, es, fr, ar, zh, ...) — REQUIRED for non-English accuracy
  --style word|line|karaoke  word = single centered word (IShowSpeed); line = phrase lines;
                          karaoke = paginated lines with the ACTIVE word highlighted as spoken
                          (Submagic/Hormozi/TikTok). Covers Remotion's colored/scaling/animated-bg.
  --pos center|bottom   caption position (default center for word, bottom for line/karaoke)
  --transition none|pop|fade   word transition (default none = instant; pop = scale-in)
  --font NAME        CSS font-family (default Poppins) ; --font-file path for @font-face
  --color HEX        text color (default #ffffff)
  --size PX          font size px (default 108 for word, 84 for line/karaoke)
  --maxchars N       line style: max chars per line (default 42)
  --maxwords N       karaoke: max words per line/page (default 4)
  --hl HEX           karaoke (no --box): color the active word turns (default #ffd84a)
  --box HEX          karaoke: draw a rounded pill of this color that springs word-to-word
                     (the "animated background" look). When set, active text stays --color.
  --preset NAME      karaoke famous look (CapCut/Submagic/Hormozi/etc.):
                       hormozi  = all-caps, thick black stroke, green active word + pop (business benchmark)
                       beast    = MrBeast: huge all-caps, heavy stroke, yellow active, big pop
                       pill     = white caps in a springy yellow pill (active text dark)
                       neon     = glowing text, cyan active word with bigger glow
                       gradient = teal->blue->violet gradient fill, active pops + brightens
                       minimal  = small clean white, no stroke/animation (lower-third)
                       tiktok   = white text on a rounded translucent black bar (classic)
                     CLI flags (--box/--hl/--color/--font/--size) override the preset.
  --out DIR          project dir to write captions.js/.json (default: cwd)

Then in your composition's <script> (after building tl, before registering):
  <script src="captions.js"></script>
  window.mountCaptions(tl, { suppress: [[4.15,4.95]] });   // suppress = optional [start,end] windows
"""
import sys, json, argparse, subprocess, os, re

WHISPERX_LANGS = {"ar","ca","cs","da","de","el","en","es","eu","fa","fi","fr","gl","he","hi",
"hr","hu","id","it","ja","ka","ko","lv","ml","nl","nn","no","pl","pt","ro","ru","sk","sl",
"sv","te","tl","tr","uk","ur","vi","zh"}

# Famous caption looks (CapCut / Submagic / Hormozi / Opus / Captions.ai), for --style karaoke.
# Each is a full look; CLI flags (--box/--hl/--color/--font/--size) still override.
KARAOKE_PRESETS = {
  # name        weight upper stroke strokeCol  glow  grad  base       active     activeTxt  scale  box        bar
  "default":  dict(weight=800, upper=False, stroke=0, strokeCol="#000", glow=False, grad=False, base="#ffffff", active="#ffd84a", activeTxt=None,    scale=1.12, box=None,      bar=None),
  "hormozi":  dict(weight=900, upper=True,  stroke=8, strokeCol="#000", glow=False, grad=False, base="#ffffff", active="#3bff6a", activeTxt=None,    scale=1.14, box=None,      bar=None),
  "beast":    dict(weight=900, upper=True,  stroke=9, strokeCol="#000", glow=False, grad=False, base="#ffffff", active="#ffd60a", activeTxt=None,    scale=1.18, box=None,      bar=None),
  "pill":     dict(weight=800, upper=True,  stroke=0, strokeCol="#000", glow=False, grad=False, base="#ffffff", active=None,      activeTxt="#0b0b0b",scale=1.08, box="#ffd60a", bar=None),
  "neon":     dict(weight=800, upper=False, stroke=0, strokeCol="#000", glow=True,  grad=False, base="#eafcff", active="#39e6ff", activeTxt=None,    scale=1.12, box=None,      bar=None),
  "gradient": dict(weight=800, upper=False, stroke=0, strokeCol="#000", glow=False, grad=True,  base="#ffffff", active=None,      activeTxt=None,    scale=1.14, box=None,      bar=None),
  "minimal":  dict(weight=600, upper=False, stroke=0, strokeCol="#000", glow=False, grad=False, base="#ffffff", active="#ffffff", activeTxt=None,    scale=1.0,  box=None,      bar=None),
  "tiktok":   dict(weight=700, upper=False, stroke=0, strokeCol="#000", glow=False, grad=False, base="#ffffff", active="#ffffff", activeTxt=None,    scale=1.0,  box=None,      bar="rgba(0,0,0,.55)"),
}

def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _mms_words(media, lang, content, model, root, venv, tmp):
    """Universal path: WORDS from small.pt, TIMING from MMS_FA forced alignment.
    Covers ANY language incl. pa/ur (which whisperX cannot reliably align)."""
    cmd = ["python3", os.path.join(root, "scripts/transcribe.py"), media, "--model", model, "--out", tmp]
    if lang:
        cmd += ["--lang", lang]
    subprocess.run(cmd, check=True)
    words = json.load(open(tmp))
    texts = [w["text"] for w in words if w.get("text", "").strip()]
    if not texts:
        return []
    wj = os.path.join("work", "_mms_in.json")
    json.dump(texts, open(wj, "w"), ensure_ascii=False)
    cmd2 = [venv, os.path.join(root, "scripts/mms_align.py"), media, wj, "--lang", lang or "auto"]
    if content != "music":
        cmd2.append("--no-refine")
    r = subprocess.run(cmd2, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        sys.stderr.write("[caption] MMS_FA failed, using small.pt timing\n" + r.stderr[-400:] + "\n")
        return words
    timed = json.loads(r.stdout.strip().splitlines()[-1])
    return [{"text": t["text"], "start": t["start"], "end": t["end"]}
            for t in timed if t.get("start") is not None]


def get_words(media, lang, aligner="auto", content="music", model="small", lang_mode="auto"):
    """Return [{text,start,end}] using whisperX if possible, else small.pt (model configurable).
    aligner='mms' (or auto for pa/ur) -> universal MMS_FA forced alignment."""
    root = repo_root(); tmp = "work/_caption_words.json"
    os.makedirs("work", exist_ok=True)
    venv = os.path.join(root, ".venv-whisperx/bin/python")
    # SPEECH (auto) -> intelligent language router via align.py: single small (fast) when one
    # language, large-v3 code-switch only when genuinely mixed. The song/music path below is
    # UNTOUCHED (router is speech-only).
    if content == "speech" and aligner == "auto" and os.path.exists(venv):
        cmd = [venv, os.path.join(root, "scripts/align.py"), media,
               "--lang-mode", lang_mode, "--model", model, "--out", tmp]
        if lang:
            cmd += ["--lang", lang]
        sys.stderr.write(f"[caption] speech -> language router (lang-mode={lang_mode})...\n")
        r = subprocess.run(cmd, capture_output=True, text=True)
        sys.stderr.write(r.stderr[-400:] + "\n")
        if r.returncode == 0 and os.path.exists(tmp):
            return json.load(open(tmp))
        sys.stderr.write("[caption] router failed; falling back to legacy speech path\n")
    # pa/ur have no reliable whisperX aligner -> route to universal MMS_FA forced alignment
    if aligner == "auto" and lang in ("pa", "ur"):
        aligner = "mms"
    if aligner == "mms":
        sys.stderr.write(f"[caption] universal MMS_FA forced alignment ({lang})...\n")
        return _mms_words(media, lang, content, model, root, venv, tmp)
    # CONTENT RULE (proven by testing): speech/talking -> whisperX (far better),
    #                                     music/singing  -> small.pt (perceived timing).
    if aligner=="auto":
        want_wx = (content=="speech")
    else:
        want_wx = (aligner=="whisperx")
    use_wx = want_wx and lang in WHISPERX_LANGS and os.path.exists(venv)
    if use_wx and lang in WHISPERX_LANGS and os.path.exists(venv):
        sys.stderr.write(f"[caption] aligning with whisperX ({lang})...\n")
        r = subprocess.run([venv, os.path.join(root,"scripts/align.py"), media,
                            "--lang", lang, "--out", tmp], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(tmp):
            return json.load(open(tmp))
        sys.stderr.write("[caption] whisperX failed, falling back to small.pt\n"+r.stderr[-400:]+"\n")
    sys.stderr.write(f"[caption] transcribing with small.pt ({lang})...\n")
    cmd = ["python3", os.path.join(root,"scripts/transcribe.py"), media, "--model",model,"--out",tmp]
    if lang: cmd += ["--lang", lang]
    subprocess.run(cmd, check=True)
    return json.load(open(tmp))

def build_events(words, style, maxchars, maxwords=4):
    # collapse consecutive duplicates (chants)
    merged=[]
    for w in words:
        t=w["text"].strip()
        if not t: continue
        key=re.sub(r"[^\w]","",t.lower())
        if merged and re.sub(r"[^\w]","",merged[-1]["text"].lower())==key:
            merged[-1]["end"]=w["end"]
        else:
            merged.append({"text":t,"start":float(w["start"]),"end":float(w["end"])})
    if style=="karaoke":
        # paginate into lines (punctuation / pause / maxwords) but KEEP per-word timing,
        # so the active word can be highlighted as it is spoken.
        lines=[]; cur=[]
        for i,w in enumerate(merged):
            cur.append(w)
            nxt=merged[i+1] if i+1<len(merged) else None
            gap=(nxt["start"]-w["end"]) if nxt else 9
            if (w["text"].rstrip().endswith((".","?","!","…")) or gap>=0.6
                    or len(cur)>=maxwords or nxt is None):
                ws=[]
                for j,x in enumerate(cur):
                    a=x["start"]
                    b=cur[j+1]["start"] if j+1<len(cur) else x["end"]   # active until next word onset
                    ws.append({"w":x["text"],"s":round(a,3),"e":round(max(a+0.08,b),3)})
                ls=round(cur[0]["start"],3)
                le=round(cur[-1]["end"]+min(0.35,gap),3)
                lines.append({"s":ls,"e":le,"words":ws})
                cur=[]
        return lines
    if style=="word":
        ev=[]
        for i,w in enumerate(merged):
            s=w["start"]
            nxt=merged[i+1]["start"] if i+1<len(merged) else w["end"]
            end = nxt if (nxt-w["end"])<0.6 else w["end"]+0.20   # hold to next, drop on gaps
            ev.append({"t":w["text"],"s":round(s,3),"e":round(max(s+0.12,end),3)})
        return ev
    # line style: group words into readable lines (sentence punct / pause / maxchars)
    lines=[]; cur=[]
    for i,w in enumerate(merged):
        cur.append(w); txt=" ".join(x["text"] for x in cur)
        nxt=merged[i+1] if i+1<len(merged) else None
        gap = (nxt["start"]-w["end"]) if nxt else 9
        if w["text"].rstrip().endswith((".","?","!",",","…")) or gap>=0.6 or len(txt)>=maxchars or nxt is None:
            lines.append({"t":txt.strip(),"s":round(cur[0]["start"],3),"e":round(cur[-1]["end"]+min(0.3,gap),3)})
            cur=[]
    return lines

def emit_karaoke(ev, args):
    os.makedirs(args.out, exist_ok=True)
    json.dump(ev, open(os.path.join(args.out,"captions.json"),"w"), ensure_ascii=False, indent=2)
    P = dict(KARAOKE_PRESETS["default"]); P.update(KARAOKE_PRESETS.get(args.preset, {}))
    # CLI overrides (only when explicitly different from the shared defaults)
    base   = args.color if args.color != "#ffffff" else P["base"]
    active = args.hl    if args.hl    != "#ffd84a" else (P["active"] or "#ffd84a")
    box    = args.box   if args.box   else P["box"]
    bar    = P["bar"]
    act_txt= P["activeTxt"]
    pos = args.pos or "center"
    size = args.size or 96
    GRAD = "linear-gradient(135deg,#5cffd0,#3fa9ff 55%,#7b5cff)"
    fontface = ""
    if args.font_file:
        fontface = f'@font-face{{font-family:"{args.font}";font-weight:{P["weight"]};src:url("{args.font_file}") format("truetype");}}'
    posrule = ("top:50%;transform:translateY(-50%);" if pos=="center" else "bottom:150px;")

    # active emphasis mode
    mode = "pill" if box else ("scale" if P["grad"] else ("glow" if P["glow"] else "color"))

    # ---- word CSS (built from the preset) ----
    wcss = "display:inline-block;position:relative;z-index:1;margin:0 .16em;"
    wcss += f'font-weight:{P["weight"]};'
    if P["upper"]: wcss += "text-transform:uppercase;"
    if P["grad"]:  wcss += f"background-image:{GRAD};-webkit-background-clip:text;background-clip:text;color:transparent;"
    else:          wcss += f"color:{base};"
    if P["stroke"]>0: wcss += f'-webkit-text-stroke:{P["stroke"]}px {P["strokeCol"]};paint-order:stroke fill;'
    shadow = "0 4px 18px rgba(0,0,0,.6),0 2px 5px rgba(0,0,0,.55)"
    if P["glow"]: shadow = f"0 0 14px {base},0 0 34px {active}"
    if bar:       shadow = "none"
    wcss += f"text-shadow:{shadow};will-change:transform,color,filter;"

    has_box = "true" if box else "false"
    has_bar = "true" if bar else "false"
    data = json.dumps(ev, ensure_ascii=False)
    js = """/* captions.js — karaoke style, preset=%PRESET% (active-word highlight). caption.py */
window.__CAPTIONS = %DATA%;
window.mountCaptions = function(tl, opts){
  opts = opts || {};
  var compId = opts.comp || "main";
  var sup = opts.suppress || [];
  var root = document.querySelector('[data-composition-id="'+compId+'"]');
  if(!root){ console.warn("captions: root not found"); return; }
  var HASBOX=%HASBOX%, HASBAR=%HASBAR%, MODE="%MODE%";
  var st = document.createElement("style");
  st.textContent = `%FONTFACE%
  .xcap-k{position:absolute;left:0;right:0;%POS%text-align:center;opacity:0;z-index:45;padding:0 70px;}
  .xcap-k .ln{position:relative;display:inline-block;max-width:100%;
    font-family:"%FONT%",sans-serif;font-size:%SIZEpx;line-height:1.18;letter-spacing:-.01em;}
  .xcap-k .w{%WCSS%}
  .xcap-k .bx{position:absolute;z-index:0;border-radius:.26em;background:%BOXCOLOR%;
    left:0;top:0;width:0;height:0;opacity:0;box-shadow:0 8px 30px rgba(0,0,0,.30);}
  .xcap-k .bar{position:absolute;z-index:0;border-radius:.34em;background:%BARCOLOR%;
    left:0;top:0;width:0;height:0;opacity:0;}`;
  document.head.appendChild(st);
  function hidden(s){ for(var i=0;i<sup.length;i++){ if(s>=sup[i][0]&&s<=sup[i][1]) return true; } return false; }
  var BASE="%BASE%", ACTIVE="%ACTIVE%", ACTTXT="%ACTTXT%", SC=%SCALE%;

  window.__CAPTIONS.forEach(function(c){
    if(hidden(c.s)) return;
    var d=document.createElement("div"); d.className="xcap-k";
    var ln=document.createElement("span"); ln.className="ln"; d.appendChild(ln);
    var bar=null, box=null;
    if(HASBAR){ bar=document.createElement("span"); bar.className="bar"; ln.appendChild(bar); }
    if(HASBOX){ box=document.createElement("span"); box.className="bx"; ln.appendChild(box); }
    var spans=c.words.map(function(wd){
      var s=document.createElement("span"); s.className="w"; s.textContent=wd.w; ln.appendChild(s); return s;
    });
    root.appendChild(d);
    tl.set(d,{opacity:1},c.s);
    tl.set(d,{opacity:0},c.e);

    var PADX=14, PADY=8;
    if(bar && spans.length){                       // one rounded bar behind the whole line (TikTok)
      var f=spans[0], l=spans[spans.length-1];
      var L=f.offsetLeft-PADX, T=f.offsetTop-PADY;
      var Wd=(l.offsetLeft+l.offsetWidth)-f.offsetLeft+PADX*2, Hd=f.offsetHeight+PADY*2;
      tl.set(bar,{left:L,top:T,width:Wd,height:Hd,opacity:1},c.s);
    }
    c.words.forEach(function(wd,wi){
      var sp=spans[wi];
      if(MODE==="pill"){
        var L=sp.offsetLeft-PADX,T=sp.offsetTop-PADY,Wd=sp.offsetWidth+PADX*2,Hd=sp.offsetHeight+PADY*2;
        if(wi===0){ tl.set(box,{left:L,top:T,width:Wd,height:Hd,opacity:1},wd.s); }
        else { tl.to(box,{left:L,top:T,width:Wd,height:Hd,duration:.22,ease:"back.out(1.5)"},wd.s); }
        if(ACTTXT){ tl.set(sp,{color:ACTTXT},wd.s); tl.set(sp,{color:BASE},wd.e); }
        tl.to(sp,{scale:SC,duration:.12,ease:"back.out(2)"},wd.s);
        tl.to(sp,{scale:1,duration:.18,ease:"power2.out"},wd.e);
      } else if(MODE==="scale"){                    // gradient: pop + brighten
        tl.to(sp,{scale:SC,filter:"brightness(1.3)",duration:.12,ease:"back.out(2)"},wd.s);
        tl.to(sp,{scale:1,filter:"brightness(1)",duration:.18,ease:"power2.out"},wd.e);
      } else if(MODE==="glow"){                      // neon: recolor + bigger glow
        tl.to(sp,{color:ACTIVE,scale:SC,textShadow:"0 0 18px "+ACTIVE+",0 0 46px "+ACTIVE,duration:.12,ease:"back.out(2)"},wd.s);
        tl.to(sp,{color:BASE,scale:1,duration:.2,ease:"power2.out"},wd.e);
      } else {                                       // color: recolor + scale
        if(SC>1.0){ tl.to(sp,{color:ACTIVE,scale:SC,duration:.12,ease:"back.out(2)"},wd.s);
                    tl.to(sp,{color:BASE,scale:1,duration:.18,ease:"power2.out"},wd.e); }
        else { tl.set(sp,{color:ACTIVE},wd.s); tl.set(sp,{color:BASE},wd.e); }
      }
    });
    if(box){ tl.to(box,{opacity:0,duration:.12},c.e-0.05); }
    if(bar){ tl.to(bar,{opacity:0,duration:.12},c.e-0.05); }
  });
};
"""
    repl = {"%DATA%":data,"%FONTFACE%":fontface,"%POS%":posrule,"%FONT%":args.font,
            "%SIZE":str(size),"%WCSS%":wcss,"%HASBOX%":has_box,"%HASBAR%":has_bar,"%MODE%":mode,
            "%BOXCOLOR%":(box or "#3fa9ff"),"%BARCOLOR%":(bar or "transparent"),
            "%BASE%":base,"%ACTIVE%":active,"%ACTTXT%":(act_txt or ""),"%SCALE%":str(P["scale"]),
            "%PRESET%":args.preset}
    for k,v in repl.items(): js = js.replace(k, v)
    open(os.path.join(args.out,"captions.js"),"w").write(js)
    n=sum(len(e["words"]) for e in ev)
    print(f"[caption] {len(ev)} karaoke lines ({n} words), preset={args.preset} -> {args.out}/captions.js")
    print(f"[caption] in composition: <script src=\"captions.js\"></script> then window.mountCaptions(tl, {{suppress:[]}});")

def emit(ev, args):
    if args.style=="karaoke":
        return emit_karaoke(ev, args)
    os.makedirs(args.out, exist_ok=True)
    json.dump(ev, open(os.path.join(args.out,"captions.json"),"w"), ensure_ascii=False, indent=2)
    pos = args.pos or ("center" if args.style=="word" else "bottom")
    size = args.size or (108 if args.style=="word" else 84)
    fontface = ""
    if args.font_file:
        fontface = f'@font-face{{font-family:"{args.font}";font-weight:700;src:url("{args.font_file}") format("truetype");}}'
    posrule = ("top:50%;margin-top:-{0}px;".format(int(size*0.7)) if pos=="center"
               else "bottom:130px;")
    trans = args.transition
    data = json.dumps(ev, ensure_ascii=False)
    js = """/* captions.js — generated by scripts/caption.py (the caption agent). Do not hand-edit timings. */
window.__CAPTIONS = %DATA%;
window.mountCaptions = function(tl, opts){
  opts = opts || {};
  var compId = opts.comp || "main";
  var sup = opts.suppress || [];
  var Q = function(s){ return '[data-composition-id="'+compId+'"] '+s; };
  var root = document.querySelector('[data-composition-id="'+compId+'"]');
  if(!root){ console.warn("captions: root not found"); return; }
  // inject style once
  var st = document.createElement("style");
  st.textContent = `%FONTFACE%
  .xcap{position:absolute;left:0;right:0;%POS%text-align:center;opacity:0;z-index:45;
    font-family:"%FONT%",sans-serif;font-weight:700;font-size:%SIZEpx;line-height:1.05;
    letter-spacing:-.01em;color:%COLOR%;padding:0 60px;
    text-shadow:0 4px 18px rgba(0,0,0,.6),0 2px 5px rgba(0,0,0,.55);}`;
  document.head.appendChild(st);
  function hidden(s){ for(var i=0;i<sup.length;i++){ if(s>=sup[i][0]&&s<=sup[i][1]) return true; } return false; }
  window.__CAPTIONS.forEach(function(c,idx){
    if(hidden(c.s)) return;
    var d=document.createElement("div"); d.className="xcap"; d.textContent=c.t; root.appendChild(d);
    var TR="%TRANS%";
    if(TR==="pop"){
      tl.fromTo(d,{opacity:0,scale:.82},{opacity:1,scale:1,duration:.15,ease:"back.out(2.2)"},c.s);
      tl.to(d,{opacity:0,scale:1.05,duration:.12,ease:"power2.in"},c.e-0.03);
    } else if(TR==="fade"){
      tl.fromTo(d,{opacity:0},{opacity:1,duration:.12,ease:"power1.out"},c.s);
      tl.to(d,{opacity:0,duration:.12,ease:"power1.in"},c.e-0.02);
    } else { /* none = instant */
      tl.set(d,{opacity:1},c.s); tl.set(d,{opacity:0},c.e);
    }
  });
};
"""
    js = (js.replace("%DATA%",data).replace("%FONTFACE%",fontface).replace("%POS%",posrule)
            .replace("%FONT%",args.font).replace("%SIZE",str(size)).replace("%COLOR%",args.color)
            .replace("%TRANS%",trans))
    open(os.path.join(args.out,"captions.js"),"w").write(js)
    print(f"[caption] {len(ev)} {args.style} captions -> {args.out}/captions.js (+ captions.json)")
    print(f"[caption] in composition: <script src=\"captions.js\"></script> then window.mountCaptions(tl, {{suppress:[]}});")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--style", choices=["word","line","karaoke"], default="word")
    ap.add_argument("--pos", choices=["center","bottom"], default=None)
    ap.add_argument("--transition", choices=["none","pop","fade"], default="none")
    ap.add_argument("--font", default="Poppins")
    ap.add_argument("--font-file", default=None)
    ap.add_argument("--color", default="#ffffff")
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--maxchars", type=int, default=42)
    ap.add_argument("--maxwords", type=int, default=4, help="karaoke: max words per line/page")
    ap.add_argument("--hl", default="#ffd84a", help="karaoke (no --box): active-word color")
    ap.add_argument("--box", default=None, help="karaoke: pill color that springs word-to-word")
    ap.add_argument("--preset", choices=list(KARAOKE_PRESETS.keys()), default="default",
                    help="karaoke famous look: hormozi|beast|pill|neon|gradient|minimal|tiktok|default")
    ap.add_argument("--content", choices=["music","speech"], default="music",
                    help="music/singing -> small.pt (perceived timing); speech/talking -> whisperX (forced align). "
                         "PROVEN: whisperX is far better for speech, small.pt perfect for music.")
    ap.add_argument("--aligner", choices=["auto","whisperx","small","mms"], default="auto",
                    help="auto = pick from --content (pa/ur->mms); whisperx/small; or mms = universal MMS_FA")
    ap.add_argument("--out", default=".")
    ap.add_argument("--model", default="small",
                    help="ASR model for the small.pt path (small | large-v3). Default small.")
    ap.add_argument("--lang-mode", dest="lang_mode", choices=["auto", "single", "code-switch"],
                    default="auto", help="SPEECH routing: auto = detect & pick single/code-switch "
                                         "(default); single = force small; code-switch = force large-v3")
    a=ap.parse_args()
    words=get_words(a.input, a.lang, a.aligner, a.content, a.model, a.lang_mode)
    ev=build_events(words, a.style, a.maxchars, a.maxwords)
    emit(ev, a)

if __name__=="__main__":
    main()
