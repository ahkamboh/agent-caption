#!/usr/bin/env python3
"""
isolate_vocals.py — vocal isolation for SONGS (Demucs), + a conservative music/speech probe.

WHY: separating the vocal stem before ASR measurably improves lyric transcription on music
(~15-22% relative WER) because Whisper stops fighting the backing track. But on clean speech
(podcasts/interviews) it does NOTHING useful and just burns the heaviest model pass in the
pipeline. So this is CONDITIONAL by design — run it only on music.

Two entry points:
  isolate(audio, out_dir)        -> path to a clean vocal stem (cached), or None on any failure
  looks_like_music(path)         -> (is_music: bool, reason: str); errs toward 'speech'

Graceful everywhere: if demucs isn't installed (or fails), isolate() returns None so the caller
just falls back to the original audio — captions still ship, only a bit less clean on songs.

CLI:  python scripts/isolate_vocals.py <audio>            # print the vocal stem path
      python scripts/isolate_vocals.py <audio> --detect   # print {"music":bool,"reason":...}
"""
import os, sys, glob, json, hashlib, argparse, subprocess

SR = 16000


def _decode(path, seconds=None):
    """Decode ANY container to mono 16k float32 via ffmpeg (first `seconds` if given)."""
    cmd = ["ffmpeg", "-v", "error"]
    if seconds:
        cmd += ["-t", str(float(seconds))]
    cmd += ["-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    if not raw:
        return None
    import numpy as np
    return np.frombuffer(raw, dtype=np.float32).copy()


def looks_like_music(path, probe_seconds=45.0):
    """Conservative music-vs-speech probe. Returns (is_music, reason).
    Deliberately biased toward 'speech' so podcasts/interviews are never slowed by a needless
    Demucs pass — a false 'speech' just means the user can force it with --content music."""
    try:
        import numpy as np, librosa
    except Exception:
        return False, "librosa not installed -> assume speech (use --content music to force)"
    y = _decode(path, probe_seconds)
    if y is None or len(y) < SR * 3:
        return False, "audio too short to probe -> assume speech"
    try:
        # 1) percussive energy share: drums/instruments vs sustained voice
        harm, perc = librosa.effects.hpss(y)
        pe, he = float((perc ** 2).sum()), float((harm ** 2).sum())
        perc_ratio = pe / (pe + he + 1e-9)
        # 2) pulse clarity: a steady, strong beat is the music signature (speech has none)
        onset = librosa.onset.onset_strength(y=y, sr=SR)
        tempo = float(librosa.beat.beat_track(onset_envelope=onset, sr=SR)[0])
        ac = librosa.autocorrelate(onset)
        pulse = float(ac[1:].max() / (ac[0] + 1e-9)) if len(ac) > 1 else 0.0
    except Exception as e:
        return False, f"probe failed ({e}) -> assume speech"
    is_music = (perc_ratio > 0.30 and pulse > 0.30) or perc_ratio > 0.50
    return is_music, f"perc_ratio={perc_ratio:.2f} pulse={pulse:.2f} tempo={tempo:.0f}bpm"


def isolate(audio, out_dir=None, model="htdemucs"):
    """Demucs two-stems -> clean vocal stem (cached by content hash). Returns path or None.
    None on ANY problem (demucs missing, CLI error, no stem) so the caller falls back cleanly."""
    out_dir = out_dir or os.path.join("work", "_demucs")
    key = hashlib.md5(os.path.abspath(audio).encode()).hexdigest()[:12]
    cached = os.path.join(out_dir, key + ".vocals.wav")
    if os.path.exists(cached):
        return cached
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "raw_" + key)
    cmd = [sys.executable, "-m", "demucs", "-n", model, "--two-stems=vocals", "-o", work, audio]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except (FileNotFoundError, OSError):
        sys.stderr.write("[isolate] demucs not available — `python setup.py` (or pip install demucs). "
                         "Using original audio.\n")
        return None
    if r.returncode != 0:
        sys.stderr.write("[isolate] demucs failed — using original audio.\n")
        if r.stderr:
            sys.stderr.write("          " + r.stderr.strip().splitlines()[-1] + "\n")
        return None
    found = (glob.glob(os.path.join(work, "*", "*", "vocals.wav")) +
             glob.glob(os.path.join(work, "*", "*", "vocals.mp3")))
    if not found:
        return None
    try:
        os.replace(found[0], cached)
        return cached
    except OSError:
        return found[0]


def main():
    ap = argparse.ArgumentParser(description="isolate vocals (demucs) / probe music vs speech")
    ap.add_argument("input")
    ap.add_argument("--out", default=None, help="output dir for the cached stem")
    ap.add_argument("--detect", action="store_true", help="only print the music/speech verdict, don't isolate")
    a = ap.parse_args()
    if a.detect:
        m, why = looks_like_music(a.input)
        print(json.dumps({"music": m, "reason": why}))
    else:
        print(isolate(a.input, a.out) or "")


if __name__ == "__main__":
    main()
