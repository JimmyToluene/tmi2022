"""Pose model + kinematics from verified per-frame keypoints.

Usage: python kinematics.py <annotations_verified.json> <out_json>

For every character track (DS, CL, AUD_n) and every frame, computes a camera-invariant body model:
keypoints re-expressed in a body frame centred on the neck and scaled by shoulder width, plus joint
angles (elbow flexion, upper-arm abduction, shoulder-line tilt, trunk lean, head roll), hand-to-hip
distances, lateral hip sway and per-joint speeds. Speeds are computed on unique (non-duplicate)
frames at the native 24 fps cadence so the 30 fps padding does not create fake stops.
"""
import json
import math
import sys
from collections import defaultdict

import numpy as np

W, H = 1080, 1920


def px(p):
    return np.array([p[0] * W, p[1] * H], dtype=float)


def angle_at(a, b, c):
    """interior angle at b (deg) for points a-b-c"""
    v1, v2 = a - b, c - b
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    if n < 1e-6:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, float(v1 @ v2 / n)))))


def tilt_deg(left, right):
    """screen-space angle of the right->left line; 0 = level, >0 = character's left side lower on screen"""
    d = left - right
    return math.degrees(math.atan2(d[1], abs(d[0]) + 1e-9)) * (1 if d[0] >= 0 else -1)


def body_model(kp):
    P = {k: px(v) for k, v in kp.items() if isinstance(v, (list, tuple)) and len(v) >= 2}
    m = {"joints_px": {k: [round(v[0], 1), round(v[1], 1)] for k, v in P.items()}}
    ls, rs = P.get("l_shoulder"), P.get("r_shoulder")
    neck = P.get("neck")
    if neck is None and ls is not None and rs is not None:
        neck = (ls + rs) / 2
    sw = float(np.linalg.norm(ls - rs)) if ls is not None and rs is not None else None
    m["shoulder_width_px"] = round(sw, 1) if sw else None
    if ls is not None and rs is not None:
        m["shoulder_tilt_deg"] = round(tilt_deg(ls, rs), 2)
    lh, rh = P.get("l_hip"), P.get("r_hip")
    hipc = (lh + rh) / 2 if lh is not None and rh is not None else None
    if hipc is not None and neck is not None:
        v = neck - hipc
        m["trunk_lean_deg"] = round(math.degrees(math.atan2(v[0], -v[1])), 2)  # >0 = upper body leans screen-right
        if sw:
            m["hip_offset_sw"] = round(float((hipc[0] - neck[0]) / sw), 3)  # lateral hip displacement vs neck
    if lh is not None and rh is not None:
        m["hip_tilt_deg"] = round(tilt_deg(lh, rh), 2)
    for side in ("l", "r"):
        s, e, w = P.get(f"{side}_shoulder"), P.get(f"{side}_elbow"), P.get(f"{side}_wrist")
        if s is not None and e is not None and w is not None:
            a = angle_at(s, e, w)
            m[f"{side}_elbow_flex_deg"] = round(180 - a, 1) if a is not None else None
        if s is not None and e is not None and hipc is not None and neck is not None:
            a = angle_at(e, s, s + (hipc - neck))
            m[f"{side}_arm_abduction_deg"] = round(a, 1) if a is not None else None
        hip = P.get(f"{side}_hip")
        if w is not None and hip is not None and sw:
            m[f"{side}_wrist_to_hip_sw"] = round(float(np.linalg.norm(w - hip) / sw), 3)
    nose, top = P.get("nose"), P.get("head_top")
    if nose is not None and top is not None:
        v = nose - top
        m["head_axis_roll_deg"] = round(math.degrees(math.atan2(-v[0], v[1])), 2)
    if neck is not None and sw:
        m["body_frame"] = {k: [round(float((v[0] - neck[0]) / sw), 3), round(float((v[1] - neck[1]) / sw), 3)]
                           for k, v in P.items()}
    return m


def main(ann_json, out_json):
    ann = json.load(open(ann_json))
    tracks = defaultdict(list)
    for r in ann:
        for c in r.get("chars", []):
            cid = c.get("id")
            # audience ids (AUD_n) are numbered per annotation chunk, so they are not tracks across the video
            if cid not in ("DS", "CL"):
                continue
            kp = c.get("kp") or {}
            rec = {"f": r["f"], "t": r["t"], "shot": r["shot"], "dup": r.get("dup_of") is not None,
                   "head_ypr": c.get("head_ypr"), "kp_src": c.get("kp_src"), "action": c.get("action")}
            rec.update(body_model(kp))
            tracks[cid].append(rec)
    # speeds on unique frames, per shot, in shoulder-widths per second (camera zoom-invariant)
    for cid, recs in tracks.items():
        uniq = [r for r in recs if not r["dup"]]
        for a, b in zip(uniq, uniq[1:]):
            if a["shot"] != b["shot"] or "body_frame" not in a or "body_frame" not in b:
                continue
            dt = (b["f"] - a["f"]) / 30.0  # real elapsed time; duplicate frames are skipped, so gaps are 1-2 frames
            sp = {}
            for j, v in b["body_frame"].items():
                if j in a["body_frame"]:
                    d = math.hypot(v[0] - a["body_frame"][j][0], v[1] - a["body_frame"][j][1])
                    sp[j] = round(d / dt, 3)
            b["joint_speed_sw_per_s"] = sp
            if b.get("head_ypr") and a.get("head_ypr") and len(b["head_ypr"]) == 3 and len(a["head_ypr"]) == 3:
                b["head_ang_speed_deg_per_s"] = [round((y - x) / dt, 1) for x, y in zip(a["head_ypr"], b["head_ypr"])]
    summary = {}
    for cid, recs in tracks.items():
        def stat(key):
            v = [r[key] for r in recs if r.get(key) is not None and not r["dup"]]
            return {"n": len(v), "min": round(min(v), 2), "max": round(max(v), 2), "mean": round(float(np.mean(v)), 2),
                    "std": round(float(np.std(v)), 2)} if v else None
        summary[cid] = {"frames": len(recs), "shots": sorted({r["shot"] for r in recs}),
                        **{k: stat(k) for k in ("shoulder_tilt_deg", "trunk_lean_deg", "hip_offset_sw", "hip_tilt_deg",
                                                "l_elbow_flex_deg", "r_elbow_flex_deg", "l_arm_abduction_deg",
                                                "r_arm_abduction_deg", "l_wrist_to_hip_sw", "r_wrist_to_hip_sw",
                                                "head_axis_roll_deg")}}
    json.dump({"summary": summary, "tracks": tracks}, open(out_json, "w"), ensure_ascii=False)
    for cid, s in summary.items():
        print(cid, json.dumps(s, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
