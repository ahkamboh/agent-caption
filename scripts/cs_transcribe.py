#!/usr/bin/env python3
"""
cs_transcribe.py — code-switch-robust transcription (ordered WORDS only; TIMING is MMS's job).

Pipeline:
  1. Silero VAD -> short utterances (1-8s) so language is decided per-utterance.
  2. Per-segment language ID via faster-whisper auto-detect (fixes Whisper's
     one-language-per-30s-window slip on mixed Hinglish/Punjabi-English audio).
  3. Transcribe each segment in ITS detected language, large-v3, temperature=0.0,
     condition_on_previous_text=False (deterministic, no cross-segment bleed).
  4. Optional --dual A B : decode each segment in both languages, keep the higher
     avg-logprob result (best for known bilingual content).
  5. Optional --initial-prompt to bias name/slang/brand retention (both languages).

Returns ordered words: [{"w","start","end","lang","score"}] in time order.
These words feed mms_align.force_align(refine=False) for final timing — text errors
never cause drift because uroman+MMS time the waveform, not the spelling.

Run: .venv-whisperx/bin/python scripts/cs_transcribe.py <audio> [--model large-v3] [--dual hi en] [--initial-prompt "..."]
"""
import sys, json, argparse, re

SR = 16000


def _clean_tok(t):
    """Collapse Whisper character-loop hallucinations (e.g. 'ਹੱੱੱੱੱ…' -> 'ਹੱ')."""
    return re.sub(r"(.)\1{3,}", r"\1\1", t)
_MODEL = None
_MODEL_NAME = None


def _load_model(name):
    global _MODEL, _MODEL_NAME
    if _MODEL is None or _MODEL_NAME != name:
        from faster_whisper import WhisperModel
        sys.stderr.write(f"[cs] loading faster-whisper {name} (cpu/int8)...\n")
        _MODEL = WhisperModel(name, device="cpu", compute_type="int8")
        _MODEL_NAME = name
    return _MODEL


def _load_audio(path):
    from faster_whisper.audio import decode_audio
    return decode_audio(path, sampling_rate=SR)          # float32 mono @16k


def vad_windows(wav, min_s=1.0, max_s=8.0):
    """Silero VAD -> merged 1-8s speech windows (seconds)."""
    import torch
    from silero_vad import load_silero_vad, get_speech_timestamps
    vad = load_silero_vad()
    t = torch.from_numpy(wav) if not hasattr(wav, "dim") else wav
    ts = get_speech_timestamps(t, vad, sampling_rate=SR, return_seconds=True,
                               min_silence_duration_ms=200, speech_pad_ms=120)
    import math
    merged, cur = [], None
    for seg in ts:
        s, e = float(seg["start"]), float(seg["end"])
        if cur is None:
            cur = [s, e]
        elif e - cur[0] <= max_s:
            cur[1] = e
        else:
            merged.append(cur); cur = [s, e]
    if cur:
        merged.append(cur)
    # SPLIT any window longer than max_s into equal chunks — a single continuous VAD
    # segment that code-switches internally (no pause, e.g. a verse flowing into an
    # English bridge) must be chunked so each chunk gets its OWN per-segment langID.
    out = []
    for s, e in merged:
        dur = e - s
        if dur <= max_s:
            out.append((s, max(e, s + min_s)))
        else:
            n = math.ceil(dur / max_s)
            step = dur / n
            for k in range(n):
                out.append((round(s + k * step, 3), round(s + (k + 1) * step, 3)))
    return out


def _decode(model, audio_slice, lang, initial_prompt):
    segs, info = model.transcribe(
        audio_slice, language=lang, temperature=0.0,
        condition_on_previous_text=False, word_timestamps=True,
        beam_size=5, initial_prompt=initial_prompt, vad_filter=False)
    segs = list(segs)
    words, logps = [], []
    for s in segs:
        logps.append(getattr(s, "avg_logprob", -5.0))
        for w in (s.words or []):
            tok = _clean_tok(w.word.strip())
            if not tok:
                continue
            words.append({"w": tok, "start": float(w.start),
                          "end": float(w.end), "score": float(getattr(w, "probability", 0.0))})
    avg = sum(logps) / len(logps) if logps else -10.0
    detected = getattr(info, "language", lang)
    return words, avg, detected


# ---------------------------------------------------------------------------
# language-ID guard — keep per-segment detection inside the languages that are
# actually PRESENT in the file. Without this, a noisy/ambiguous chunk can be
# auto-detected as a wholly unrelated language (the Punjabi-clip → Sinhala
# garbage bug) because Whisper's langID is over-confident on short audio.
# ---------------------------------------------------------------------------

def _all_lang_probs(model, audio_slice):
    """faster-whisper detect_language -> {lang: prob}. Empty dict if unavailable."""
    try:
        res = model.detect_language(audio_slice)
    except Exception:
        return {}
    if isinstance(res, tuple) and len(res) >= 3 and res[2]:
        return {l: float(p) for (l, p) in res[2]}
    if isinstance(res, tuple) and len(res) >= 2 and res[0]:
        return {res[0]: float(res[1])}
    return {}


def _candidates(scan, explicit=None):
    """The allowed languages for this file. `explicit` (e.g. ['ur','pa','hi','en'])
    overrides. Otherwise VOTE: a language must be the top guess in >=2 segments to
    qualify — so a single confidently-wrong detection (the Punjabi→Sinhala garbage)
    is excluded, while genuine code-switch languages (present in several segments)
    survive. The dominant language + English are always kept."""
    if explicit:
        return {l.strip() for l in explicit if l.strip()} | {"en"}
    votes = {}
    for pr in scan:
        if pr:
            top = max(pr, key=pr.get)
            votes[top] = votes.get(top, 0) + 1
    if not votes:
        return None
    thr = 2 if len(scan) >= 4 else 1
    cands = {l for l, v in votes.items() if v >= thr}
    cands.add(max(votes, key=votes.get))   # always keep the dominant language
    cands.add("en")
    return cands


def _pick(pr, cands):
    """Highest-probability language that's IN the candidate set (else None -> auto)."""
    if not cands or not pr:
        return None
    inset = [(l, p) for l, p in pr.items() if l in cands]
    return max(inset, key=lambda x: x[1])[0] if inset else None


def transcribe(audio_path, model_name="large-v3", dual=None, initial_prompt=None, langs=None,
               force_lang=None):
    """force_lang: decode every segment in this ONE language (skips per-segment langID) —
    used by the router's SINGLE path (small model + forced language, fast)."""
    model = _load_model(model_name)
    wav = _load_audio(audio_path)
    windows = vad_windows(wav)
    skip_scan = bool(dual or force_lang)
    # detect each window's language ONCE, reuse for voting + per-segment constraint
    scan = [] if skip_scan else [_all_lang_probs(model, wav[int(s * SR):int(e * SR)]) for (s, e) in windows]
    cands = None if skip_scan else _candidates(scan, explicit=langs)
    if cands:
        sys.stderr.write(f"[cs] language candidates (constrained): {sorted(cands)}\n")
    all_words, seg_report = [], []
    for i, (s, e) in enumerate(windows):
        a, b = int(s * SR), int(e * SR)
        chunk = wav[a:b]
        if dual:
            best = None
            for lc in dual:
                w, avg, det = _decode(model, chunk, lc, initial_prompt)
                if best is None or avg > best[1]:
                    best = (w, avg, lc)
            words, _, lang = best
        elif force_lang:
            words, _, lang = _decode(model, chunk, force_lang, initial_prompt)
        else:
            lc = _pick(scan[i], cands)   # None -> auto fallback
            words, _, lang = _decode(model, chunk, lc, initial_prompt)
        for w in words:
            w["start"] = round(w["start"] + s, 3)
            w["end"] = round(w["end"] + s, 3)
            w["lang"] = lang
        all_words.extend(words)
        seg_report.append({"start": round(s, 2), "end": round(e, 2), "lang": lang, "words": len(words)})
    all_words.sort(key=lambda w: w["start"])
    return _dedup(all_words), seg_report


def _dedup(words, max_run=2):
    """Drop runs of the same repeated token — Whisper loops on instrumental/outro tails."""
    out, run_w, run_n = [], None, 0
    for w in words:
        t = w["w"].strip().lower()
        if t == run_w:
            run_n += 1
        else:
            run_w, run_n = t, 1
        if run_n <= max_run:
            out.append(w)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--dual", nargs=2, default=None, metavar=("LANG_A", "LANG_B"))
    ap.add_argument("--initial-prompt", default=None)
    ap.add_argument("--langs", default=None,
                    help="comma-separated codes to constrain detection (e.g. ur,pa,hi,en); "
                         "default = auto-scan which languages are in the file")
    a = ap.parse_args()
    langs = [x for x in a.langs.split(",")] if a.langs else None
    words, report = transcribe(a.audio, a.model, a.dual, a.initial_prompt, langs=langs)
    sys.stderr.write(f"[cs] {len(words)} words across {len(report)} segments; "
                     f"langs={sorted(set(r['lang'] for r in report))}\n")
    print(json.dumps({"words": words, "segments": report}, ensure_ascii=False))
