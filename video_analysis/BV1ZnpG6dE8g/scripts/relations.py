"""Aggregate per-frame interaction annotations into a relationship timeline.

Usage: python relations.py <annotations_verified.json> <out_json>

Each frame record carries inter: [{from, to, channel, desc}]. This groups them by
(from, to, channel), merges consecutive frames into intervals, and reports frame coverage,
so every pairwise relation can be traced to exact frame ranges.
"""
import json
import re
import sys
from collections import defaultdict

CHANNELS = ["gaze", "attention", "spatial-hierarchy", "framing/occlusion", "proximity", "timing/response",
            "address-to-camera", "other"]


def norm_id(s):
    s = (s or "").strip().upper()
    if s.startswith("AUD"):
        return "AUD"  # individual audience members are pooled; their per-frame identity is not stable across chunks
    if s in ("VIEWER", "CAMERA", "LENS"):
        return "CAM"
    return s


def norm_channel(c):
    c = (c or "").lower()
    for k in CHANNELS:
        if c.startswith(k.split("/")[0].split("-")[0]):
            return k
    return "other"


def intervals(frames):
    frames = sorted(set(frames))
    out = []
    for f in frames:
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return out


def main(ann_json, out_json):
    ann = json.load(open(ann_json))
    rel = defaultdict(lambda: {"frames": [], "examples": []})
    for r in ann:
        seen = set()
        for i in r.get("inter", []):
            key = (norm_id(i.get("from")), norm_id(i.get("to")), norm_channel(i.get("channel")))
            if key in seen:
                continue
            seen.add(key)
            rel[key]["frames"].append(r["f"])
            d = re.sub(r"\s+", " ", i.get("desc", "")).strip()
            if r.get("dup_of") is None and d and len(rel[key]["examples"]) < 400:
                rel[key]["examples"].append([r["f"], d])
    out = []
    for (a, b, ch), v in sorted(rel.items(), key=lambda kv: -len(kv[1]["frames"])):
        iv = intervals(v["frames"])
        ex = v["examples"]
        # keep a spread of examples (first, last, evenly spaced) instead of the first N
        step = max(1, len(ex) // 8)
        out.append({"from": a, "to": b, "channel": ch, "n_frames": len(set(v["frames"])),
                    "seconds": round(len(set(v["frames"])) / 30, 2), "intervals": iv,
                    "examples": ex[::step][:10]})
    json.dump(out, open(out_json, "w"), ensure_ascii=False, indent=1)
    for o in out[:40]:
        print(f"{o['from']:>6} -> {o['to']:<6} {o['channel']:<18} {o['n_frames']:4d}f  {o['intervals'][:6]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
