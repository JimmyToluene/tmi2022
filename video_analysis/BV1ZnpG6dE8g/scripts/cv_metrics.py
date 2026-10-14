"""Per-frame computer-vision measurements for BV1ZnpG6dE8g.

Usage:
    python cv_metrics.py <frames_dir> <models_dir> <out_dir>

frames_dir holds f0001.jpg ... f0452.jpg (ffmpeg -vsync 0 dump of the 30 fps video).
Writes per_frame_cv.json (one record per frame) and shots.json to out_dir.
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

FPS = 30.0
POSE_NAMES = [
    "nose", "l_eye_in", "l_eye", "l_eye_out", "r_eye_in", "r_eye", "r_eye_out",
    "l_ear", "r_ear", "mouth_l", "mouth_r", "l_shoulder", "r_shoulder",
    "l_elbow", "r_elbow", "l_wrist", "r_wrist", "l_pinky", "r_pinky",
    "l_index", "r_index", "l_thumb", "r_thumb", "l_hip", "r_hip",
    "l_knee", "r_knee", "l_ankle", "r_ankle", "l_heel", "r_heel",
    "l_foot_idx", "r_foot_idx",
]


def hsv_hist(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [36, 16], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def global_motion(prev_g, cur_g, orb, bf):
    """Similarity transform prev->cur: dx, dy (px @ analysis scale), scale, rot (deg), inlier ratio."""
    k1, d1 = orb.detectAndCompute(prev_g, None)
    k2, d2 = orb.detectAndCompute(cur_g, None)
    if d1 is None or d2 is None or len(k1) < 12 or len(k2) < 12:
        return None
    m = bf.match(d1, d2)
    if len(m) < 12:
        return None
    p1 = np.float32([k1[x.queryIdx].pt for x in m])
    p2 = np.float32([k2[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if M is None:
        return None
    s = math.hypot(M[0, 0], M[1, 0])
    rot = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    return {"dx": float(M[0, 2]), "dy": float(M[1, 2]), "scale": float(s), "rot_deg": float(rot),
            "inlier_ratio": float(inl.mean()) if inl is not None else 0.0, "n_matches": int(len(m))}


def main(frames_dir, models_dir, out_dir):
    frames = sorted(Path(frames_dir).glob("f*.jpg"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    models = Path(models_dir)

    anime_face = cv2.CascadeClassifier(str(models / "lbpcascade_animeface.xml"))
    pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(models / "pose_landmarker_heavy.task")),
        running_mode=vision.RunningMode.IMAGE, num_poses=3,
        min_pose_detection_confidence=0.3, min_pose_presence_confidence=0.3))
    hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(models / "hand_landmarker.task")),
        running_mode=vision.RunningMode.IMAGE, num_hands=4,
        min_hand_detection_confidence=0.3, min_hand_presence_confidence=0.3))
    face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(models / "face_landmarker.task")),
        running_mode=vision.RunningMode.IMAGE, num_faces=2,
        output_face_blendshapes=True, output_facial_transformation_matrixes=True,
        min_face_detection_confidence=0.3, min_face_presence_confidence=0.3))

    orb = cv2.ORB_create(2000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    recs = []
    prev_small = prev_g = prev_hist = None
    for i, fp in enumerate(frames):
        idx = i + 1
        img = cv2.imread(str(fp))
        H, W = img.shape[:2]
        small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)  # 270x480
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = hsv_hist(small)
        rec = {
            "frame": idx, "t": round(i / FPS, 4),
            "luma_mean": float(g.mean()), "luma_std": float(g.std()),
            "sat_mean": float(hsv[..., 1].mean()),
            "hue_circ_mean_deg": None,
            "bgr_mean": [float(x) for x in small.reshape(-1, 3).mean(0)],
            "orange_frac": float(((hsv[..., 0] >= 5) & (hsv[..., 0] <= 22) & (hsv[..., 1] > 90) & (hsv[..., 2] > 80)).mean()),
            "blue_frac": float(((hsv[..., 0] >= 95) & (hsv[..., 0] <= 130) & (hsv[..., 1] > 70) & (hsv[..., 2] > 50)).mean()),
        }
        hue = hsv[..., 0].astype(np.float32) * 2 * math.pi / 180
        wts = hsv[..., 1].astype(np.float32) / 255
        rec["hue_circ_mean_deg"] = float((math.degrees(math.atan2((np.sin(hue) * wts).sum(), (np.cos(hue) * wts).sum())) + 360) % 360)

        if prev_g is not None:
            rec["hist_corr_prev"] = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
            rec["absdiff_prev"] = float(cv2.absdiff(prev_g, g).mean())
            flow = cv2.calcOpticalFlowFarneback(prev_g, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.linalg.norm(flow, axis=2)
            rec["flow_mean"] = float(mag.mean())
            rec["flow_p95"] = float(np.percentile(mag, 95))
            gm = global_motion(prev_g, g, orb, bf)
            rec["global_motion"] = gm
            if gm is not None:
                # residual (object) motion after removing the similarity transform
                ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]].astype(np.float32)
                a = gm["scale"] * math.cos(math.radians(gm["rot_deg"]))
                b = gm["scale"] * math.sin(math.radians(gm["rot_deg"]))
                px = a * xs - b * ys + gm["dx"] - xs
                py = b * xs + a * ys + gm["dy"] - ys
                res = np.hypot(flow[..., 0] - px, flow[..., 1] - py)
                rec["residual_flow_mean"] = float(res.mean())
                rec["residual_flow_p95"] = float(np.percentile(res, 95))
                # where in the frame is the local motion concentrated (3x3 grid, row-major)
                gh, gw = res.shape[0] // 3, res.shape[1] // 3
                rec["residual_grid3x3"] = [float(res[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw].mean()) for r in range(3) for c in range(3)]
        prev_g, prev_hist, prev_small = g, hist, small

        # anime face detector (full-res grayscale, equalized)
        gray_full = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        faces = anime_face.detectMultiScale(gray_full, scaleFactor=1.08, minNeighbors=4, minSize=(24, 24))
        rec["anime_faces_xywh"] = [[int(v) for v in f] for f in faces]

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mpimg = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        pr = pose.detect(mpimg)
        rec["poses"] = []
        for pl in pr.pose_landmarks:
            rec["poses"].append({n: [round(l.x, 4), round(l.y, 4), round(l.z, 4), round(l.visibility or 0, 3), round(l.presence or 0, 3)]
                                 for n, l in zip(POSE_NAMES, pl)})
        hr = hands.detect(mpimg)
        rec["hands"] = []
        for hl, hd in zip(hr.hand_landmarks, hr.handedness):
            rec["hands"].append({"handedness": hd[0].category_name, "score": round(hd[0].score, 3),
                                 "landmarks": [[round(l.x, 4), round(l.y, 4), round(l.z, 4)] for l in hl]})
        fr = face.detect(mpimg)
        rec["faces_mp"] = []
        for k, fl in enumerate(fr.face_landmarks):
            entry = {"n_landmarks": len(fl),
                     "bbox": [round(min(l.x for l in fl), 4), round(min(l.y for l in fl), 4),
                              round(max(l.x for l in fl), 4), round(max(l.y for l in fl), 4)],
                     "key": {name: [round(fl[j].x, 4), round(fl[j].y, 4), round(fl[j].z, 4)] for name, j in
                             [("nose_tip", 1), ("chin", 152), ("forehead", 10), ("l_eye_outer", 263), ("r_eye_outer", 33),
                              ("mouth_l", 291), ("mouth_r", 61), ("upper_lip", 13), ("lower_lip", 14),
                              ("l_eye_top", 386), ("l_eye_bot", 374), ("r_eye_top", 159), ("r_eye_bot", 145)]}}
            if fr.face_blendshapes:
                entry["blendshapes"] = {b.category_name: round(b.score, 3) for b in fr.face_blendshapes[k] if b.score > 0.05}
            if fr.facial_transformation_matrixes:
                M = np.array(fr.facial_transformation_matrixes[k])[:3, :3]
                yaw = math.degrees(math.atan2(-M[2, 0], math.hypot(M[2, 1], M[2, 2])))
                pitch = math.degrees(math.atan2(M[2, 1], M[2, 2]))
                roll = math.degrees(math.atan2(M[1, 0], M[0, 0]))
                entry["head_pose_deg"] = {"yaw": round(yaw, 2), "pitch": round(pitch, 2), "roll": round(roll, 2)}
            rec["faces_mp"].append(entry)
        recs.append(rec)
        if idx % 50 == 0:
            print(f"frame {idx}/{len(frames)} poses={len(rec['poses'])} hands={len(rec['hands'])} "
                  f"faces_mp={len(rec['faces_mp'])} anime_faces={len(rec['anime_faces_xywh'])}", flush=True)

    # shot boundaries: low histogram correlation AND high abs diff relative to local median
    cuts = [1]
    for r in recs[1:]:
        if r.get("hist_corr_prev", 1) < 0.6 and r.get("absdiff_prev", 0) > 18:
            cuts.append(r["frame"])
    shots = []
    for k, s in enumerate(cuts):
        e = (cuts[k + 1] - 1) if k + 1 < len(cuts) else len(recs)
        shots.append({"shot": k + 1, "start_frame": s, "end_frame": e,
                      "start_t": round((s - 1) / FPS, 3), "end_t": round(e / FPS, 3), "n_frames": e - s + 1})
    json.dump(recs, open(out_dir / "per_frame_cv.json", "w"), ensure_ascii=False)
    json.dump(shots, open(out_dir / "shots.json", "w"), ensure_ascii=False, indent=1)
    print("shots:", shots)


if __name__ == "__main__":
    main(*sys.argv[1:4])
