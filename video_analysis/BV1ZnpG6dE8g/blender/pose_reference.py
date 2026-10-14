"""Back-project annotated 2D keypoints into 3D joint guides for posing the MMD models.

Usage: python pose_reference.py <annotations_verified.json> <scene_spec.json> <out_json>

For every unique frame and each of DS / CL, each keypoint pixel is cast as a ray from that shot's camera
(keys linearly interpolated, as in the Blender file) and intersected with a vertical plane through the
character's MMD root, facing the camera. The result is a 2.5D guide: exact in the image, approximate in
depth. It is a reference for posing, not a motion capture.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camera_math import H, SENSOR_H, W, look_at  # noqa: E402


def camera_at(spec, f):
    for C in spec["cameras"]:
        a, b = C["frames"]
        if a <= f <= b:
            keys = sorted(C["keys"], key=lambda k: k["f"])
            if f <= keys[0]["f"]:
                k = keys[0]
                return k["location"], k["target"], k.get("roll_deg", 0), k["lens_mm"]
            for k0, k1 in zip(keys, keys[1:]):
                if k0["f"] <= f <= k1["f"]:
                    t = (f - k0["f"]) / max(1, k1["f"] - k0["f"])
                    lerp = lambda x, y: (np.asarray(x, float) * (1 - t) + np.asarray(y, float) * t).tolist()
                    return (lerp(k0["location"], k1["location"]), lerp(k0["target"], k1["target"]),
                            k0.get("roll_deg", 0) * (1 - t) + k1.get("roll_deg", 0) * t,
                            k0["lens_mm"] * (1 - t) + k1["lens_mm"] * t)
            k = keys[-1]
            return k["location"], k["target"], k.get("roll_deg", 0), k["lens_mm"]
    return None


def backproject(uv, cam, anchor):
    loc, tgt, roll, lens = cam
    R = look_at(loc, tgt, roll)
    f_px = lens / SENSOR_H * H
    d_cam = np.array([(uv[0] - W / 2) / f_px, -(uv[1] - H / 2) / f_px, -1.0])
    d = R @ d_cam
    o = np.asarray(loc, float)
    a = np.asarray(anchor, float)
    n = o - a
    n[2] = 0.0
    if np.linalg.norm(n) < 1e-6:
        return None
    n /= np.linalg.norm(n)
    denom = d @ n
    if abs(denom) < 1e-9:
        return None
    t = ((a - o) @ n) / denom
    return (o + t * d).round(4).tolist() if t > 0 else None


def main(ann_json, spec_json, out_json):
    ann = json.load(open(ann_json, encoding="utf-8"))
    spec = json.load(open(spec_json, encoding="utf-8"))
    out = {}
    for r in ann:
        if r.get("dup_of"):
            continue
        cam = camera_at(spec, r["f"])
        if cam is None:
            continue
        for c in r.get("chars", []):
            cid = c.get("id")
            if cid not in spec.get("characters", {}):
                continue
            anchor = spec["characters"][cid]["location"]
            for joint, xy in (c.get("kp") or {}).items():
                if not isinstance(xy, list) or len(xy) < 2:
                    continue
                p = backproject((xy[0] * W, xy[1] * H), cam, anchor)
                if p:
                    out.setdefault(cid, {}).setdefault(joint, []).append([r["f"], p])
    json.dump(out, open(out_json, "w"), ensure_ascii=False)
    for cid, js in out.items():
        print(cid, {j: len(v) for j, v in js.items()})


if __name__ == "__main__":
    main(*sys.argv[1:4])
