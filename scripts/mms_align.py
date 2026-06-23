#!/usr/bin/env python3
"""
mms_align.py — UNIVERSAL local forced aligner (Meta MMS_FA via torchaudio).

force_align(audio_path, words, lang="auto", window=None, refine=True)
    -> [{"text","start","end","score"}]   (ABSOLUTE times; +window start if windowed)

CORE PRINCIPLE: words (text) come from curated lyric or ASR; TIMING comes from forcing
those exact words onto the waveform. One MMS model aligns 1100+ languages AND code-switched
text in a single pass — uroman romanizes any script to the MMS Latin dictionary, while the
returned `text` stays the ORIGINAL display script.

Run with:  .venv-whisperx/bin/python scripts/mms_align.py <audio> <words.json> [--lang xx] ...
Verified against torchaudio 2.8.0 (torchaudio.pipelines.MMS_FA + functional.forced_align/merge_tokens).
"""
import sys, json, argparse, subprocess
import numpy as np
import torch
import torchaudio
import torchaudio.functional as F


def _decode_audio(path, window=None):
    """Decode ANY container (mp4/mov/webm/mp3/wav) to mono 16k float32 via ffmpeg.
    torchaudio/soundfile cannot open video containers; ffmpeg handles everything."""
    cmd = ["ffmpeg", "-v", "error"]
    if window:
        cmd += ["-ss", str(float(window[0])), "-to", str(float(window[1]))]
    cmd += ["-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

DEVICE = "cpu"
SR = 16000                       # MMS_FA bundle sample rate
# uroman language-code hints (script auto-detects regardless; this just disambiguates)
_LCODE = {"hi": "hin", "pa": "pan", "ur": "urd", "en": "eng", "es": "spa",
          "fr": "fra", "auto": None, "": None, None: None}

_BUNDLE = _MODEL = _DICT = _DICTKEYS = _UROMAN = None


def _load():
    global _BUNDLE, _MODEL, _DICT, _DICTKEYS, _UROMAN
    if _MODEL is None:
        from uroman import Uroman
        _BUNDLE = torchaudio.pipelines.MMS_FA
        _MODEL = _BUNDLE.get_model().to(DEVICE).eval()
        _DICT = _BUNDLE.get_dict()          # {token_char: index}, blank index = 0
        # exclude the blank token (idx 0, the char '-') — uroman can emit hyphens, and
        # forced_align rejects any target containing the blank index.
        _DICTKEYS = {k for k, v in _DICT.items() if v != 0}
        _UROMAN = Uroman()
    return _MODEL, _DICT


def _normalize_word(w, lcode):
    """Romanize ANY script -> latin, lowercase, keep only MMS dictionary chars."""
    try:
        r = _UROMAN.romanize_string(w, lcode=lcode)
    except Exception:
        r = w
    r = (r or "").lower().strip()
    return "".join(c for c in r if c in _DICTKEYS)


def _unflatten(spans, lengths):
    """Split a flat list of per-token spans back into per-word groups."""
    out, i = [], 0
    for L in lengths:
        out.append(spans[i:i + L]); i += L
    return out


def _fill_none(out):
    """Interpolate words that had no alignable tokens (punctuation-only) between neighbours."""
    n = len(out)
    anchors = [i for i, w in enumerate(out) if w["start"] is not None]
    if not anchors:
        for i, w in enumerate(out):
            w["start"], w["end"], w["score"] = float(i), float(i) + 0.3, 0.0
        return out
    # head
    fa = anchors[0]
    for i in range(fa):
        out[i]["start"] = max(0.0, out[fa]["start"] - (fa - i) * 0.3)
        out[i]["end"] = out[i]["start"] + 0.2; out[i]["score"] = 0.0
    # tail
    la = anchors[-1]
    for i in range(la + 1, n):
        out[i]["start"] = out[la]["end"] + (i - la) * 0.3
        out[i]["end"] = out[i]["start"] + 0.2; out[i]["score"] = 0.0
    # interior gaps
    for k in range(len(anchors) - 1):
        a, b = anchors[k], anchors[k + 1]
        for j in range(a + 1, b):
            frac = (j - a) / (b - a)
            t = out[a]["end"] + frac * (out[b]["start"] - out[a]["end"])
            out[j]["start"] = t; out[j]["end"] = t + 0.2; out[j]["score"] = 0.0
    return out


def _onset_refine(out, audio_path, window):
    """PART B: snap each word start to the nearest spectral-flux onset (backtracked to the
    energy trough = true syllable start) within +/-80ms, never crossing neighbours, monotonic."""
    import librosa
    off = float(window[0]) if window else 0.0
    y = _decode_audio(audio_path, window)            # ffmpeg decode (handles any container)
    # backtrack=True already walks each onset back to the preceding local-energy minimum
    onsets = librosa.onset.onset_detect(y=y, sr=SR, backtrack=True, units="time")
    onset_times = [float(t) + off for t in onsets]
    if not onset_times:
        return out
    for i, w in enumerate(out):
        if w["start"] is None:
            continue
        near = [o for o in onset_times if abs(o - w["start"]) <= 0.080]
        if not near:
            continue
        best = min(near, key=lambda o: abs(o - w["start"]))
        lo = (out[i - 1]["start"] + 1e-3) if i > 0 and out[i - 1]["start"] is not None else 0.0
        hi = w["end"] - 1e-3
        w["start"] = round(min(max(best, lo), hi), 3)
    # keep monotonic after snapping
    for i in range(1, len(out)):
        if out[i]["start"] is not None and out[i - 1]["start"] is not None and out[i]["start"] < out[i - 1]["start"]:
            out[i]["start"] = out[i - 1]["start"]
    return out


def force_align(audio_path, words, lang="auto", window=None, refine=True):
    model, DICT = _load()
    lcode = _LCODE.get(lang, None)

    offset = max(0.0, float(window[0])) if window else 0.0
    arr = _decode_audio(audio_path, window)          # mono 16k float32 (ffmpeg handles the slice)
    wav = torch.from_numpy(arr).unsqueeze(0)         # (1, N)
    num_samples = wav.size(1)
    if num_samples < SR // 10:
        return [{"text": w, "start": None, "end": None, "score": 0.0} for w in words]

    norm = [_normalize_word(w, lcode) for w in words]
    idx_with = [i for i, nrm in enumerate(norm) if nrm]
    tokens_per_word = [[DICT[c] for c in norm[i]] for i in idx_with]
    flat = [t for grp in tokens_per_word for t in grp]
    if not flat:
        return [{"text": w, "start": None, "end": None, "score": 0.0} for w in words]

    with torch.inference_mode():
        emission, _ = model(wav.to(DEVICE))            # (1, T, V) log-probs
    targets = torch.tensor([flat], dtype=torch.int32, device=DEVICE)
    aligned_tokens, scores = F.forced_align(emission, targets, blank=0)
    aligned_tokens, scores = aligned_tokens[0], scores[0].exp()
    token_spans = F.merge_tokens(aligned_tokens, scores)    # one span per target token
    word_spans = _unflatten(token_spans, [len(g) for g in tokens_per_word])

    num_frames = emission.size(1)
    ratio = num_samples / num_frames                        # samples per emission frame
    by_word = {}
    for wi, spans in zip(idx_with, word_spans):
        if not spans:
            continue
        st = spans[0].start * ratio / SR + offset
        en = spans[-1].end * ratio / SR + offset
        tot = sum((s.end - s.start) for s in spans) or 1
        sc = sum(s.score * (s.end - s.start) for s in spans) / tot
        by_word[wi] = (st, en, float(sc))

    out = []
    for i, w in enumerate(words):
        if i in by_word:
            st, en, sc = by_word[i]
            out.append({"text": w, "start": round(st, 3), "end": round(en, 3), "score": round(sc, 3)})
        else:
            out.append({"text": w, "start": None, "end": None, "score": 0.0})
    _fill_none(out)
    if refine:
        out = _onset_refine(out, audio_path, window)
    # final monotonic guard
    for i in range(1, len(out)):
        if out[i]["start"] < out[i - 1]["start"]:
            out[i]["start"] = out[i - 1]["start"]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("words_json", help="JSON list of display words (or {'words':[...]})")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--window", nargs=2, type=float, default=None, metavar=("START", "END"))
    ap.add_argument("--no-refine", action="store_true")
    a = ap.parse_args()
    data = json.loads(a.words_json) if a.words_json.strip().startswith(("[", "{")) else json.load(open(a.words_json))
    words = data["words"] if isinstance(data, dict) else data
    res = force_align(a.audio, words, lang=a.lang,
                      window=tuple(a.window) if a.window else None,
                      refine=not a.no_refine)
    print(json.dumps(res, ensure_ascii=False))
