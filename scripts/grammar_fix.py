#!/usr/bin/env python3
"""
grammar_fix.py — offline homophone / grammar correction for caption .srt files.

The ONE thing forced alignment can't fix is whether a word was HEARD right
("their" vs "there", "your" vs "you're", "its" vs "it's"). Those are decidable
from CONTEXT by a grammar engine — no LLM, no tokens, no upload. This runs
LanguageTool LOCALLY (via language_tool_python) over each cue's text and rewrites
the .srt in place. Timing is NEVER touched: same cues, same start/end times — only
the words change. Conservative by design: it applies only confused-word/homophone
and core grammar/typo fixes, not style or rephrasing nags.

Optional dependency (kept OUT of the default install so the base stays light and
Java-free):  pip install language_tool_python   + a Java runtime (JRE 8+).
If either is missing, this exits 0 WITHOUT changing the file — captions still ship.

Usage:  python scripts/grammar_fix.py work/<base>.srt [--lang en]
English-family only for now; other languages pass through untouched.
"""
import sys, re, argparse, os

# Categories/rules safe to auto-apply. Homophones live in CONFUSED_WORDS; we also take
# core GRAMMAR + TYPOS. We deliberately skip STYLE/REDUNDANCY/whitespace nags — those
# can reword a caption or change its meaning, which we never want to do silently.
_SAFE_CATS = {"GRAMMAR", "TYPOS", "CONFUSED_WORDS", "NONSTANDARD_PHRASES", "MISC"}


def _attr(m, *names):
    for n in names:
        v = getattr(m, n, None)
        if v:
            return v
    return ""


def _correct(tool, text):
    """Apply only safe homophone/grammar replacements; return corrected text."""
    try:
        matches = tool.check(text)
    except Exception:
        return text
    edits = []
    for m in matches:
        reps = getattr(m, "replacements", None) or []
        if not reps:
            continue
        cat = str(_attr(m, "category")).upper()
        rule = str(_attr(m, "ruleId", "ruleIssueType")).upper()
        if "CONFUSED" in rule or "HOMOPHONE" in rule or cat in _SAFE_CATS:
            off = getattr(m, "offset", None)
            length = getattr(m, "errorLength", None)
            if off is None or length is None:
                continue
            edits.append((off, length, reps[0]))
    # apply right-to-left so earlier offsets stay valid
    for off, length, rep in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:off] + rep + text[off + length:]
    return text


def process_srt(path, tool):
    """Rewrite each cue's text through the corrector; keep index + timing lines verbatim."""
    text = open(path, encoding="utf-8").read()
    blocks, changed = [], 0
    for blk in re.split(r"\n\s*\n", text.strip()):
        lines = blk.splitlines()
        ti = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if ti is None:
            blocks.append(blk)
            continue
        head = lines[:ti + 1]                               # index + "start --> end"
        body = " ".join(l for l in lines[ti + 1:] if l.strip()).strip()
        if body:
            fixed = _correct(tool, body)
            if fixed != body:
                changed += 1
            body = fixed
        blocks.append("\n".join(head + ([body] if body else [])))
    open(path, "w", encoding="utf-8").write("\n\n".join(blocks) + "\n")
    return changed


def main():
    ap = argparse.ArgumentParser(description="offline homophone/grammar fix for an .srt (timing preserved)")
    ap.add_argument("srt")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()

    if not a.lang.lower().startswith("en"):
        print(f"[grammar] lang={a.lang}: grammar pass is English-only for now — skipping.", file=sys.stderr)
        return
    if not os.path.exists(a.srt):
        print(f"[grammar] no such file: {a.srt} — skipping.", file=sys.stderr)
        return

    try:
        import language_tool_python
    except ImportError:
        print("[grammar] optional grammar pass skipped (not installed). To enable:", file=sys.stderr)
        print("          pip install language_tool_python      (needs Java/JRE 8+)", file=sys.stderr)
        print("          or: python setup.py --grammar", file=sys.stderr)
        return
    try:
        tool = language_tool_python.LanguageTool("en-US")
    except Exception as e:
        print(f"[grammar] couldn't start LanguageTool (is Java installed?). Skipping. [{e}]", file=sys.stderr)
        return

    changed = process_srt(a.srt, tool)
    try:
        tool.close()
    except Exception:
        pass
    print(f"[grammar] homophone/grammar pass: {changed} cue(s) corrected -> {a.srt}")


if __name__ == "__main__":
    main()
