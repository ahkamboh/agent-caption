#!/usr/bin/env python3
"""
Multi-language subtitle export — translate an English .srt into many languages (OFFLINE, no API),
for YouTube upload or burned-in versions. Run with the whisperX venv (it has argostranslate):

  .venv-whisperx/bin/python scripts/multilang-subs.py subs.en.srt --to "es,fr,de,pt,hi,ar,ja" [--burn video.mp4]

  --to LIST     comma languages (es fr de it pt ru zh ja ko hi ar tr vi id nl pl uk ...)
  --top N       instead of --to, use the N biggest YouTube languages
  --burn VIDEO  also burn each language as <video>.<lang>.mp4 (ffmpeg subtitles filter)
  --out DIR     output dir (default: alongside the srt)

YouTube tip: upload the .srt files directly (Subtitles -> add language) — selectable + SEO.
Argos downloads a small en->XX pack per language on first use, then works offline.
"""
import sys, os, re, argparse, subprocess

TOP = ["es","pt","hi","ar","fr","de","ru","ja","zh","ko","id","it","tr","vi","th","pl","nl",
       "uk","ro","ms","bn","fa","sv","el","cs","hu","da","fi","he","ur"]

def parse_srt(p):
    blocks=re.split(r"\n\s*\n", open(p,encoding="utf-8").read().strip())
    out=[]
    for b in blocks:
        L=b.splitlines()
        if len(L)>=3: out.append((L[0],L[1]," ".join(L[2:])))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("srt"); ap.add_argument("--to",default=None); ap.add_argument("--top",type=int,default=None)
    ap.add_argument("--from",dest="src",default="en"); ap.add_argument("--burn",default=None)
    ap.add_argument("--out",default=None)
    a=ap.parse_args()
    out=a.out or os.path.dirname(os.path.abspath(a.srt)) or "."
    os.makedirs(out,exist_ok=True)
    langs = ([x.strip() for x in a.to.split(",")] if a.to else TOP[:a.top] if a.top else TOP)

    import argostranslate.package, argostranslate.translate
    argostranslate.package.update_package_index()
    avail=argostranslate.package.get_available_packages()
    blocks=parse_srt(a.srt); done=[]
    for lg in langs:
        pkg=next((p for p in avail if p.from_code==a.src and p.to_code==lg),None)
        if not pkg: print(f"  {lg}: no pack, skip"); continue
        try:
            installed={l.code for l in argostranslate.translate.get_installed_languages()}
            if lg not in installed or a.src not in installed:
                argostranslate.package.install_from_path(pkg.download())
            Ls=argostranslate.translate.get_installed_languages()
            tr=next(l for l in Ls if l.code==a.src).get_translation(next(l for l in Ls if l.code==lg))
        except Exception as e:
            print(f"  {lg}: pack error {e}"); continue
        dst=os.path.join(out,f"subs.{lg}.srt")
        with open(dst,"w",encoding="utf-8") as f:
            for idx,ts,text in blocks:
                f.write(f"{idx}\n{ts}\n{tr.translate(text)}\n\n")
        done.append(lg); print(f"  {lg}: {dst}")
        if a.burn:
            base=os.path.splitext(os.path.basename(a.burn))[0]
            bout=os.path.join(out,f"{base}.{lg}.mp4")
            style="FontName=Arial,Fontsize=22,PrimaryColour=&HFFFFFF&,Outline=1,BorderStyle=1"
            subprocess.run(["ffmpeg","-y","-i",a.burn,"-vf",f"subtitles={dst}:force_style='{style}'",
                "-c:v","libx264","-crf","20","-preset","medium","-movflags","+faststart","-c:a","copy",bout],
                capture_output=True)
            print(f"       burned -> {bout}")
    print(f"\n[multilang] {len(done)} languages: {', '.join(done)}")

if __name__=="__main__":
    main()
