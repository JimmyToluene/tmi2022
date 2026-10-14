"""Merge CV, audio, danmaku and performer-tracking signals into compact per-frame digests.

Usage: python build_digest.py <cv_json> <shots_json> <audio_json> <danmaku_xml> <perf_json> <out_dir> [chunk=36]

Writes frame_signals.json (all frames) and chunk_XX.json files (one per annotation chunk).
"""
import html
import json
import re
import sys
from pathlib import Path

FPS = 30.0
KEY_JOINTS = ["nose", "l_eye", "r_eye", "l_ear", "r_ear", "mouth_l", "mouth_r", "l_shoulder", "r_shoulder",
              "l_elbow", "r_elbow", "l_wrist", "r_wrist", "l_index", "r_index", "l_hip", "r_hip",
              "l_knee", "r_knee", "l_ankle", "r_ankle"]
KEY_BLEND = ["eyeBlinkLeft", "eyeBlinkRight", "eyeSquintLeft", "eyeSquintRight", "jawOpen", "mouthSmileLeft",
             "mouthSmileRight", "mouthClose", "browInnerUp", "browDownLeft", "browDownRight", "mouthPucker",
             "eyeLookUpLeft", "eyeLookDownLeft", "eyeLookInLeft", "eyeLookOutLeft"]


def danmaku(path):
    x = open(path, encoding="utf-8").read()
    rows = []
    for p, t in re.findall(r'<d p="([^"]+)">([^<]*)</d>', x):
        f = p.split(",")
        rows.append({"t": float(f[0]), "text": html.unescape(t)})
    return sorted(rows, key=lambda r: r["t"])


def main(cv_json, shots_json, audio_json, dm_xml, perf_json, out_dir, chunk=36):
    chunk = int(chunk)
    cv = json.load(open(cv_json))
    shots = json.load(open(shots_json))
    au = json.load(open(audio_json))
    perf = {r["frame"]: r for r in json.load(open(perf_json))} if Path(perf_json).exists() else {}
    dms = danmaku(dm_xml)
    beats, onsets = set(au["beat_frames"]), set(au["onset_frames"])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def shot_of(n):
        return next(s["shot"] for s in shots if s["start_frame"] <= n <= s["end_frame"])

    sig = []
    for r in cv:
        n = r["frame"]
        gm = r.get("global_motion") or {}
        a = au["per_frame"][n - 1] if n - 1 < len(au["per_frame"]) else {}
        d = {
            "frame": n, "t": r["t"], "shot": shot_of(n),
            "absdiff_prev": round(r.get("absdiff_prev", 0), 3),
            # 24 fps source padded to 30 fps: every 5th frame repeats its predecessor
            "dup_of_prev": n > 1 and r.get("absdiff_prev", 99) < 0.5 and shot_of(n) == shot_of(n - 1),
            "luma": round(r["luma_mean"], 1), "orange_frac": round(r["orange_frac"], 4), "blue_frac": round(r["blue_frac"], 4),
            "cam": {k: round(gm[k], 4) for k in ("dx", "dy", "scale", "rot_deg", "inlier_ratio")} if gm else None,
            "flow_mean": round(r.get("flow_mean", 0), 3), "residual_flow_mean": round(r.get("residual_flow_mean", 0), 3),
            "residual_grid3x3": [round(v, 2) for v in r.get("residual_grid3x3", [])],
            "anime_faces_xywh": r["anime_faces_xywh"],
            "mp_poses": [{j: p[j][:2] + [p[j][3]] for j in KEY_JOINTS} for p in r["poses"]],
            "mp_hands": [{"handedness": h["handedness"], "score": h["score"],
                          "wrist": h["landmarks"][0][:2], "index_tip": h["landmarks"][8][:2],
                          "thumb_tip": h["landmarks"][4][:2]} for h in r["hands"]],
            "mp_faces": [{"bbox": f["bbox"], "head_pose_deg": f.get("head_pose_deg"),
                          "blend": {k: v for k, v in (f.get("blendshapes") or {}).items() if k in KEY_BLEND}}
                         for f in r["faces_mp"]],
            "audio": {"beat": n in beats, "onset": n in onsets, "rms_db": a.get("rms_db"),
                      "centroid_hz": a.get("centroid_hz")},
            "danmaku_here": [x["text"] for x in dms if (n - 1) / FPS <= x["t"] < n / FPS],
        }
        p = perf.get(n)
        if p and p.get("blob"):
            d["performer_blob"] = {k: p["blob"][k] for k in ("cx", "cy", "w", "h", "area")}
            if p.get("pose"):
                d["performer_pose_upscaled"] = {j: p["pose"][j][:2] + [p["pose"][j][3]] for j in KEY_JOINTS}
        sig.append(d)
    json.dump(sig, open(out / "frame_signals.json", "w"), ensure_ascii=False)
    k = 0
    for s in range(0, len(sig), chunk):
        k += 1
        json.dump(sig[s:s + chunk], open(out / f"chunk_{k:02d}.json", "w"), ensure_ascii=False)
    print(f"{len(sig)} frames -> {k} chunks of {chunk}")


if __name__ == "__main__":
    main(*sys.argv[1:8])
