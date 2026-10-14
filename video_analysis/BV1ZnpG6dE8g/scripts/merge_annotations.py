"""Apply verifier patches to annotator output and expand to all 452 frames.

Usage: python merge_annotations.py <raw_dir> <frame_signals_json> <out_dir>

raw_dir holds chunk_KK.annot.json (annotator output: {chunk, frames, events, chunk_summary}) and
chunk_KK.patches.json (verifier output: {corrections, events_final, ...}).
Writes annotations_verified.json (one record per frame, duplicates copied from their source frame),
events_verified.json and patch_log.json.
"""
import copy
import json
import sys
from pathlib import Path


def parse_value(s):
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


def find_char(rec, cid):
    for c in rec.setdefault("chars", []):
        if c.get("id") == cid:
            return c
    return None


def apply_patch(rec, target, value):
    """target grammar: cam.<k> | env | delta | inter | <CHAR> | -<CHAR> | <CHAR>.<field> | <CHAR>.kp.<joint>"""
    if target.startswith("-"):
        rec["chars"] = [c for c in rec.get("chars", []) if c.get("id") != target[1:]]
        return "removed"
    parts = target.split(".")
    head = parts[0]
    if head == "cam":
        rec.setdefault("cam", {})
        if len(parts) == 1:
            rec["cam"] = value
        else:
            rec["cam"][parts[1]] = value
        return "set"
    if head in ("env", "delta", "inter", "shot"):
        rec[head] = value
        return "set"
    if head in ("chars",):
        rec["chars"] = value
        return "set"
    c = find_char(rec, head)
    if len(parts) == 1:
        if isinstance(value, dict):
            value.setdefault("id", head)
            if c is None:
                rec["chars"].append(value)
                return "added"
            c.clear()
            c.update(value)
            return "replaced"
        return "skipped:non-object for char"
    if c is None:
        c = {"id": head}
        rec["chars"].append(c)
    if parts[1] == "kp":
        c.setdefault("kp", {})
        if len(parts) == 2:
            c["kp"] = value
        elif value is None:
            c["kp"].pop(parts[2], None)
        else:
            c["kp"][parts[2]] = value
        return "set"
    c[parts[1]] = value
    return "set"


def main(raw_dir, signals_json, out_dir):
    raw, out = Path(raw_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sig = {s["frame"]: s for s in json.load(open(signals_json))}
    frames, events, log = {}, [], []
    for ap in sorted(raw.glob("chunk_*.annot.json")):
        a = json.load(open(ap))
        pp = ap.with_name(ap.name.replace(".annot.", ".patches."))
        p = json.load(open(pp)) if pp.exists() else None
        for r in a["frames"]:
            frames[r["f"]] = r
        for cor in (p or {}).get("corrections", []):
            f = cor["f"]
            if f not in frames:
                frames[f] = {"f": f, "shot": sig[f]["shot"], "cam": {}, "chars": [], "inter": [], "env": "", "delta": ""}
            res = apply_patch(frames[f], cor["target"], parse_value(cor["value_json"]))
            log.append({"chunk": a["chunk"], "f": f, "target": cor["target"], "result": res, "reason": cor["reason"]})
        evs = p["events_final"] if p else a["events"]
        for e in evs:
            e["chunk"] = a["chunk"]
            e["verified"] = p is not None
        events.extend(evs)
    # expand duplicates: frame n with dup_of_prev copies its source frame; a non-duplicate frame with no
    # annotation (its chunk is still being annotated) becomes an explicit pending record, never a neighbour copy
    full, missing = [], []
    for n in range(1, len(sig) + 1):
        if n in frames and not sig[n]["dup_of_prev"]:
            r = frames[n]
            r["dup_of"] = None
        elif sig[n]["dup_of_prev"] and (n - 1) in frames:
            r = copy.deepcopy(frames[n - 1])
            r["f"] = n
            r["dup_of"] = frames[n - 1].get("dup_of") or (n - 1)
            r["delta"] = "identical to frame %d (24->30 fps pad)" % r["dup_of"]
        else:
            missing.append(n)
            r = {"f": n, "pending": True, "dup_of": None, "cam": {}, "chars": [], "inter": [], "env": "",
                 "delta": "annotation for this frame is still in progress"}
        frames[n] = r
        r["t"] = round((n - 1) / 30, 4)
        r["shot"] = sig[n]["shot"]
        full.append(r)
    events.sort(key=lambda e: (e["start"], e["end"]))
    json.dump(full, open(out / "annotations_verified.json", "w"), ensure_ascii=False)
    json.dump(events, open(out / "events_verified.json", "w"), ensure_ascii=False, indent=1)
    json.dump(log, open(out / "patch_log.json", "w"), ensure_ascii=False, indent=1)
    print(f"{len(full)} frames, {len(events)} events, {len(log)} patches applied; "
          f"pending (not yet annotated) frames: {len(missing)} {missing[:3]}...{missing[-3:]}" if missing else "no pending frames")


if __name__ == "__main__":
    main(*sys.argv[1:4])
