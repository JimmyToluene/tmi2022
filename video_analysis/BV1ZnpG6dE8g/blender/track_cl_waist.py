"""Track CL's corset (waist) and chest in shot 3 on the source frames, for the pose fit.

Usage: python track_cl_waist.py <frames_dir> <annotations_verified.json> <out_json>

The annotated hip keypoints in shot 3 sit under the skirt and are noisy (their image height jumps ~200 px on a
locked camera). The black corset with its gold studs is rigid and textured, so it is tracked instead: a Euclidean
(shift + in-plane rotation) ECC alignment of each unique frame against f304, warm-started from the previous frame,
so errors do not accumulate. The chest patch (brooch and cravat) is tracked the same way for comparison.
Output per frame: patch-centre image position (px, full 1080x1920 frame), rotation (deg, + = clockwise on screen)
and the ECC correlation.
"""
import json
import math
import sys

import cv2
import numpy as np

SCALE = 0.5
REF = 304
# full-resolution patch boxes (x0, y0, x1, y1) at f304
REGIONS = {"chest": (470, 600, 640, 760), "corset": (300, 880, 700, 1080)}


def load(frames_dir, f):
    g = cv2.imread(f"{frames_dir}/f{f:04d}.jpg", cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    return cv2.resize(g, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_AREA)


def main(frames_dir, ann_json, out_json):
    ann = json.load(open(ann_json, encoding="utf-8"))
    frames = [r["f"] for r in ann if r["shot"] == 3 and not r.get("dup_of")]
    ref = load(frames_dir, REF)
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)
    out = {k: [] for k in REGIONS}
    warps = {k: np.eye(2, 3, dtype=np.float32) for k in REGIONS}
    for f in frames:
        img = load(frames_dir, f)
        for k, (x0, y0, x1, y1) in REGIONS.items():
            mask = np.zeros_like(ref, np.uint8)
            mask[int(y0 * SCALE):int(y1 * SCALE), int(x0 * SCALE):int(x1 * SCALE)] = 255
            w = warps[k].copy()
            try:
                cc, w = cv2.findTransformECC(ref, img, w, cv2.MOTION_EUCLIDEAN, crit, mask, 5)
            except cv2.error:
                cc = float("nan")
            warps[k] = w
            c = w @ np.array([(x0 + x1) / 2 * SCALE, (y0 + y1) / 2 * SCALE, 1.0])
            out[k].append({"f": f, "x": round(float(c[0] / SCALE), 2), "y": round(float(c[1] / SCALE), 2),
                           "rot_deg": round(math.degrees(math.atan2(w[1, 0], w[0, 0])), 3), "cc": round(float(cc), 4)})
    json.dump({"ref_frame": REF, "regions_px": REGIONS, "tracks": out}, open(out_json, "w"), indent=0)
    xs = {k: np.array([r["x"] for r in v]) for k, v in out.items()}
    print(f"tracked {len(frames)} frames; corset/chest x correlation {np.corrcoef(xs['corset'], xs['chest'])[0, 1]:.2f}; "
          f"corset ECC median {np.nanmedian([r['cc'] for r in out['corset']]):.2f}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
