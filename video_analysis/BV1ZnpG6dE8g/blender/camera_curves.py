"""Per-frame camera parameters from the solved shot cameras in a scene spec.

Usage: python camera_curves.py <scene_spec.json> <out_json>

For every frame: shot, yaw (deg, heading of the optical axis measured from +Y toward +X), pitch (deg below
horizontal), roll (deg), lens (mm), camera position, and distance to the shot's subject (DS face in shot 1,
CL head in shots 2-3). Keys are interpolated linearly, as in the Blender file.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pose_reference import camera_at  # noqa: E402

SUBJECT_HEIGHT = {"DS": 1.45, "CL": 1.45}


def main(spec_json, out_json):
    spec = json.load(open(spec_json, encoding="utf-8"))
    chars = spec.get("characters", {})
    rows = []
    for f in range(spec["meta"]["frame_start"], spec["meta"]["frame_end"] + 1):
        cam = camera_at(spec, f)
        if cam is None:
            continue
        loc, tgt, roll, lens = cam
        shot = next(C["shot"] for C in spec["cameras"] if C["frames"][0] <= f <= C["frames"][1])
        d = np.asarray(tgt, float) - np.asarray(loc, float)
        yaw = math.degrees(math.atan2(d[0], d[1]))
        pitch = math.degrees(math.atan2(-d[2], math.hypot(d[0], d[1])))
        subj = "DS" if shot == 1 else "CL"
        dist = None
        if subj in chars:
            p = np.asarray(chars[subj]["location"], float) + np.array([0, 0, SUBJECT_HEIGHT[subj]])
            dist = float(np.linalg.norm(p - np.asarray(loc, float)))
        rows.append({"f": f, "shot": shot, "yaw_deg": round(yaw, 3), "pitch_down_deg": round(pitch, 3),
                     "roll_deg": round(float(roll), 3), "lens_mm": round(float(lens), 2),
                     "location": [round(float(v), 4) for v in loc], "subject": subj,
                     "distance_m": round(dist, 4) if dist is not None else None})
    json.dump(rows, open(out_json, "w"), ensure_ascii=False)
    for s in (1, 2, 3):
        r = [x for x in rows if x["shot"] == s]
        a, b = r[0], r[-1]
        print(f"shot {s}: yaw {a['yaw_deg']:.1f}->{b['yaw_deg']:.1f}  pitch {a['pitch_down_deg']:.1f}->{b['pitch_down_deg']:.1f}  "
              f"roll {a['roll_deg']:.2f}->{b['roll_deg']:.2f}  lens {a['lens_mm']}->{b['lens_mm']}  "
              f"dist to {a['subject']} {a['distance_m']:.2f}->{b['distance_m']:.2f} m")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
