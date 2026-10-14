"""Package deterministic measurements (camera, cadence, audio, MediaPipe head yaw, performer track, beat sync).

Usage: python measured.py <frame_signals.json> <per_frame_cv.json> <shots.json> <audio_metrics.json>
                          <performer_track.json> <kinematics.json|-> <out_json>
"""
import json
import math
import sys

import numpy as np

FPS = 30.0


def camera_curves(sig):
    zoom, roll, pan = [], [], []
    z = rr = px = py = 0.0
    prev = None
    for s in sig:
        if s["shot"] != prev:
            z, rr, px, py, prev = 1.0, 0.0, 0.0, 0.0, s["shot"]
        c = s["cam"]
        if c and c["inlier_ratio"] > 0.4:
            z *= c["scale"]
            rr += c["rot_deg"]
            px += c["dx"] * 4
            py += c["dy"] * 4
        zoom.append(round(z, 4))
        roll.append(round(rr, 3))
        pan.append([round(px, 1), round(py, 1)])
    return zoom, roll, pan


def pushin_fixed_point(cv, first, last):
    pts = []
    for x in cv[first:last]:
        g = x.get("global_motion")
        if not g or g["scale"] < 1.003 or g["inlier_ratio"] < 0.6:
            continue
        s, th = g["scale"], math.radians(g["rot_deg"])
        A = np.array([[s * math.cos(th), -s * math.sin(th)], [s * math.sin(th), s * math.cos(th)]])
        try:
            pts.append(np.linalg.solve(np.eye(2) - A, np.array([g["dx"], g["dy"]])) * 4)
        except np.linalg.LinAlgError:
            pass
    P = np.array(pts)
    return {"median_px": np.median(P, 0).round(1).tolist(), "n": len(P),
            "iqr_x": np.percentile(P[:, 0], [25, 75]).round(0).tolist(),
            "iqr_y": np.percentile(P[:, 1], [25, 75]).round(0).tolist()}


def beat_sync(track_points, beat_frames, lo, hi):
    """Correlate a lateral-sway series with the beat grid: dominant period (frames) and phase of sway extrema
    relative to the nearest beat. Returns None when there is too little data."""
    pts = [(f, v) for f, v in track_points if v is not None and lo <= f <= hi]
    if len(pts) < 24:
        return None
    f = np.array([p[0] for p in pts], float)
    v = np.array([p[1] for p in pts], float)
    grid = np.arange(f.min(), f.max() + 1)
    vi = np.interp(grid, f, v)
    vi = vi - np.convolve(vi, np.ones(31) / 31, mode="same")  # remove slow drift (~1 s)
    ac = np.correlate(vi - vi.mean(), vi - vi.mean(), mode="full")[len(vi) - 1:]
    ac /= ac[0] if ac[0] else 1
    lags = np.arange(len(ac))
    win = (lags >= 8) & (lags <= 70)
    period = int(lags[win][np.argmax(ac[win])]) if win.any() else None
    # extrema
    ext = [int(grid[i]) for i in range(1, len(vi) - 1)
           if (vi[i] > vi[i - 1] and vi[i] >= vi[i + 1]) or (vi[i] < vi[i - 1] and vi[i] <= vi[i + 1])]
    beats = np.array([b for b in beat_frames if lo <= b <= hi])
    offs = []
    for e in ext:
        if len(beats):
            k = int(np.argmin(np.abs(beats - e)))
            offs.append(int(e - beats[k]))
    return {"frames": [int(lo), int(hi)], "n_points": len(pts), "dominant_period_frames": period,
            "dominant_period_s": round(period / FPS, 3) if period else None,
            "autocorr_at_period": round(float(ac[period]), 3) if period else None,
            "beat_period_frames": 15, "extrema_frames": ext,
            "extrema_offset_to_nearest_beat_frames": offs,
            "share_extrema_within_2f_of_beat": round(float(np.mean(np.abs(offs) <= 2)), 3) if offs else None,
            "chance_share_within_2f": round(5 / 15, 3)}


def main(sig_json, cv_json, shots_json, audio_json, perf_json, kin_json, out_json):
    sig, cv = json.load(open(sig_json)), json.load(open(cv_json))
    shots, au = json.load(open(shots_json)), json.load(open(audio_json))
    perf = json.load(open(perf_json))
    zoom, roll, pan = camera_curves(sig)
    dups = [s["frame"] for s in sig if s["dup_of_prev"]]
    ds_yaw = [[x["frame"], (x["faces_mp"][0]["head_pose_deg"]["yaw"] if x["faces_mp"] and x["frame"] <= 148 else None)]
              for x in cv]
    out = {
        "shots": shots,
        "cadence": {"native_fps_estimate": 24, "container_fps": 30, "duplicate_frames": dups,
                    "rule": "frames with f % 5 == 2 repeat f-1 (4 new + 1 repeated per 5)",
                    "n_unique": len(sig) - len(dups)},
        "camera": {"zoom": zoom, "roll": roll, "pan_px": pan,
                   "per_shot": [{"shot": s["shot"], "zoom_total": zoom[s["end_frame"] - 1],
                                 "roll_total_deg": roll[s["end_frame"] - 1],
                                 "pan_total_px": pan[s["end_frame"] - 1]} for s in shots],
                   "shot1_pushin_fixed_point": pushin_fixed_point(cv, 1, 148)},
        "ds_head_yaw_mp": ds_yaw,
        "ds_face_box_growth": {"f1_px": cv[0]["anime_faces_xywh"][0][2], "f148_px": cv[147]["anime_faces_xywh"][0][2]},
        "audio": {k: au[k] for k in ("tempo_bpm", "beat_frames", "beat_times_s", "onset_frames", "global_chroma_profile")},
        "performer_track": [{"f": r["frame"], "cx": r["blob"]["cx"], "cy": r["blob"]["cy"], "h": r["blob"]["h"]}
                            for r in perf if r.get("on_track")],
    }
    if kin_json != "-":
        kin = json.load(open(kin_json))
        cl = kin["tracks"].get("CL", [])
        pts = [[r["f"], r.get("hip_offset_sw")] for r in cl if not r["dup"]]
        roll_pts = [[r["f"], (r["head_ypr"][2] if r.get("head_ypr") and len(r["head_ypr"]) == 3 else None)]
                    for r in cl if not r["dup"]]
        out["beat_sync"] = {
            "CL_hip_offset_shot2": beat_sync(pts, au["beat_frames"], 149, 303),
            "CL_hip_offset_shot3": beat_sync(pts, au["beat_frames"], 304, 452),
            "CL_head_roll_shot3": beat_sync(roll_pts, au["beat_frames"], 304, 452),
            "camera_roll_shot3": beat_sync([[i + 1, r] for i, r in enumerate(roll)], au["beat_frames"], 304, 452),
        }
    json.dump(out, open(out_json, "w"), ensure_ascii=False)
    print("camera per shot:", out["camera"]["per_shot"])
    print("push-in fixed point:", out["camera"]["shot1_pushin_fixed_point"])
    if "beat_sync" in out:
        for k, v in out["beat_sync"].items():
            print(k, {kk: vv for kk, vv in (v or {}).items() if kk not in ("extrema_frames", "extrema_offset_to_nearest_beat_frames")})


if __name__ == "__main__":
    main(*sys.argv[1:8])
