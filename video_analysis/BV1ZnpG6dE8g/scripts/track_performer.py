"""Track the small orange-haired performer in the wide arena shot and run pose on upscaled crops.

Usage: python track_performer.py <frames_dir> <models_dir> <first> <last> <out_json> [crops_dir]

The performer is the only large saturated-orange blob in the arena frames, so a colour mask gives
a stable anchor; the crop around it is upscaled 4x before MediaPipe pose/hand inference.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from cv_metrics import POSE_NAMES


def orange_blob(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] >= 5) & (hsv[..., 0] <= 22) & (hsv[..., 1] > 110) & (hsv[..., 2] > 110)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, a = stats[k]
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "area": int(a),
            "cx": float(cent[k][0]), "cy": float(cent[k][1])}


def main(frames_dir, models_dir, first, last, out_json, crops_dir=None):
    first, last = int(first), int(last)
    models = Path(models_dir)
    pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(models / "pose_landmarker_heavy.task")),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=0.2, min_pose_presence_confidence=0.2, min_tracking_confidence=0.2))
    if crops_dir:
        Path(crops_dir).mkdir(parents=True, exist_ok=True)
    recs = []
    for n in range(first, last + 1):
        img = cv2.imread(str(Path(frames_dir) / f"f{n:04d}.jpg"))
        H, W = img.shape[:2]
        b = orange_blob(img)
        rec = {"frame": n, "blob": b, "pose": None}
        if b and b["area"] > 150:
            # the orange blob is mostly hair/head; the full-length dress extends ~3 blob-heights below it
            side = int(max(b["h"], b["w"]) * 4.2) + 40
            cx, cy = int(b["cx"]), int(b["y"] + side * 0.42)
            x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2)
            x1, y1 = min(W, x0 + side), min(H, y0 + side)
            crop = img[y0:y1, x0:x1]
            scale = 4 if side < 400 else (2 if side < 900 else 1)
            up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            rec["crop_xyxy"] = [x0, y0, x1, y1]
            rec["crop_scale"] = scale
            if crops_dir:
                cv2.imwrite(str(Path(crops_dir) / f"perf_{n:04d}.jpg"), up)
            res = pose.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                 data=cv2.cvtColor(up, cv2.COLOR_BGR2RGB)), int(n * 1000 / 30))
            if res.pose_landmarks:
                pl = res.pose_landmarks[0]
                # map back to full-frame normalized coordinates
                rec["pose"] = {nm: [round((x0 + l.x * (x1 - x0)) / W, 4), round((y0 + l.y * (y1 - y0)) / H, 4),
                                    round(l.z, 4), round(l.visibility or 0, 3)] for nm, l in zip(POSE_NAMES, pl)}
        recs.append(rec)
    json.dump(recs, open(out_json, "w"))
    got = sum(1 for r in recs if r["pose"])
    print(f"tracked {sum(1 for r in recs if r['blob'])}/{len(recs)} frames, pose on {got}")


if __name__ == "__main__":
    main(*sys.argv[1:7])
