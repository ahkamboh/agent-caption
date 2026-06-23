#!/usr/bin/env python3
"""
validate_timing.py — the mistake-less enforcer for aligned word timing.

validate(words, input_count=None, ...) -> (cleaned, warnings)
  words: [{"text"|"w", "start"|"t", "end"?, "score"?, "line"?, "sustained"?}]
  warnings: [{"type","index"?,"line"?,"msg"}]   (machine-readable so callers can react)

Rules:
  - monotonic starts (auto-fix: clamp to previous)
  - no overlap: end <= next start (auto-fix)
  - duration > 3.0s flagged unless `sustained` (held sung note)
  - score < 0.40 flagged; auto-fixed by interpolation IF both neighbours are confident
  - mid-line gap > 2.0s -> type 'wide_gap_line' (caller may re-align that line wider)
  - coverage: timed >= 0.9 * input_count else type 'low_coverage' (caller retries wider)
Never silently ships a flagged word: unfixable issues are returned AND echoed to stderr.
"""
import sys, json, argparse

DUR_MAX = 3.0
MIN_SCORE = 0.40
GAP_MAX = 2.0


def _s(w):
    return w.get("start", w.get("t"))


def _set_s(w, v):
    if "start" in w or "t" not in w:
        w["start"] = v
    if "t" in w:
        w["t"] = v


def validate(words, input_count=None, dur_max=DUR_MAX, min_score=MIN_SCORE, gap_max=GAP_MAX):
    ws = [dict(w) for w in words]
    warns = []
    n = len(ws)
    txt = lambda w: w.get("text", w.get("w", "?"))

    # 1. monotonic starts
    for i in range(1, n):
        if _s(ws[i]) is not None and _s(ws[i - 1]) is not None and _s(ws[i]) < _s(ws[i - 1]):
            warns.append({"type": "non_monotonic", "index": i, "msg": f"'{txt(ws[i])}' start<prev -> clamped"})
            _set_s(ws[i], _s(ws[i - 1]))

    # 2. no overlap (end <= next start)
    for i in range(n - 1):
        if ws[i].get("end") is not None and _s(ws[i + 1]) is not None and ws[i]["end"] > _s(ws[i + 1]):
            ws[i]["end"] = _s(ws[i + 1])

    # 3. over-long words (held note?)
    for i, w in enumerate(ws):
        if w.get("end") is not None and _s(w) is not None:
            d = w["end"] - _s(w)
            if d > dur_max and not w.get("sustained"):
                warns.append({"type": "long_word", "index": i, "msg": f"'{txt(w)}' dur={d:.2f}s (held note? mark sustained)"})

    # 4. low score -> interpolate if both neighbours confident, else flag
    for i, w in enumerate(ws):
        if w.get("score", 1.0) < min_score:
            prev_ok = i > 0 and ws[i - 1].get("score", 0) >= min_score and _s(ws[i - 1]) is not None
            next_ok = i < n - 1 and ws[i + 1].get("score", 0) >= min_score and _s(ws[i + 1]) is not None
            if prev_ok and next_ok:
                mid = (ws[i - 1].get("end", _s(ws[i - 1])) + _s(ws[i + 1])) / 2.0
                _set_s(ws[i], round(mid, 3))
                warns.append({"type": "low_score_fixed", "index": i, "msg": f"'{txt(w)}' score={w.get('score')} interpolated"})
            else:
                warns.append({"type": "low_score", "index": i, "msg": f"'{txt(w)}' score={w.get('score')} (no confident neighbours)"})

    # 5. mid-line gaps
    if any("line" in w for w in ws):
        from collections import defaultdict
        by_line = defaultdict(list)
        for i, w in enumerate(ws):
            by_line[w.get("line")].append(i)
        for ln, idxs in by_line.items():
            for a, b in zip(idxs, idxs[1:]):
                sa, sb = _s(ws[a]), _s(ws[b])
                if sa is not None and sb is not None and (sb - sa) > gap_max:
                    warns.append({"type": "wide_gap_line", "line": ln, "msg": f"gap {sb - sa:.2f}s in line {ln} -> re-align wider"})
                    break

    # 6. coverage
    timed = sum(1 for w in ws if _s(w) is not None and w.get("score", 1.0) >= min_score)
    if input_count:
        if timed < 0.9 * input_count:
            warns.append({"type": "low_coverage", "msg": f"{timed}/{input_count} confidently timed (<90%) -> retry wider window"})

    for w in warns:
        if w["type"] in ("low_score", "low_coverage", "wide_gap_line", "long_word"):
            sys.stderr.write(f"[validate] {w['type']}: {w['msg']}\n")
    return ws, warns


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("words_json")
    ap.add_argument("--input-count", type=int, default=None)
    a = ap.parse_args()
    data = json.loads(a.words_json) if a.words_json.strip().startswith(("[", "{")) else json.load(open(a.words_json))
    words = data["words"] if isinstance(data, dict) else data
    cleaned, warns = validate(words, input_count=a.input_count)
    print(json.dumps({"cleaned": cleaned, "warnings": warns}, ensure_ascii=False))
