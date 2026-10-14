"""Fit the MMD-standard skeleton to the verified per-frame annotations through the solved shot cameras.

Usage: python pose_fit.py <annotations_verified.json> <scene_spec.json> <out_dir> [--chars DS,CL] [--waist cl_shot3_waist_track.json]

For each character and each unique (non-duplicate) annotated frame, solve with robust least squares:
  - reprojection of skeleton joints/face points against the verified 2D keypoints (pixels, per-shot sigma)
  - head orientation against the verified viewer-centric head yaw/pitch/roll
  - a pose prior per shot (templates below, built from the verified descriptions), joint-limit-ish priors
  - temporal smoothness to the previous solved frame, small センター offset
  - contact: DS's forearms rest on the balcony handrail in shots 1-2
  - optional (--waist, CL shot 3): the tracked corset from track_cl_waist.py. The annotated hips there sit under
    the skirt and are noisy, so the corset position/tilt drives the waist instead: a first pass calibrates the
    corset-to-skeleton offset (shot mean), a second pass fits the waist joint and hip line to the corset track
    and down-weights the annotated hips. This keeps her lower body moving with her upper body as in the source.
Frames are solved in order with warm starts, then each bone's rotation is smoothed over time.
Output: pose_<CHAR>.json with per-frame local rotations (armature axes, quaternion w,x,y,z), the センター
offset (metres, armature axes), the per-shot anchor (world location + yaw) and per-frame residuals.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation as Rot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camera_math import H, SENSOR_H, W, look_at  # noqa: E402
from mmd_skeleton import BONES, FACE_POINTS, FK_BONES, HAND_TIP_UNITS, KP_TO_BONE, MMD_SCALE, mmd_to_blender, rest_positions  # noqa: E402
from pose_reference import camera_at  # noqa: E402

SOLVE_BONES = ["下半身", "上半身", "首", "頭", "左肩", "左腕", "左ひじ", "左手首", "右肩", "右腕", "右ひじ", "右手首"]


# ---------------------------------------------------------------- pose templates (character frame: facing -Y, left = +X, up = +Z)
def dir_rot(rest_dir, want_dir):
    """Rotation vector that turns rest_dir onto want_dir (shortest arc)."""
    a = np.asarray(rest_dir, float) / np.linalg.norm(rest_dir)
    b = np.asarray(want_dir, float) / np.linalg.norm(want_dir)
    v = np.cross(a, b)
    s, c = np.linalg.norm(v), float(a @ b)
    if s < 1e-9:
        return np.zeros(3)
    return v / s * math.atan2(s, c)


def template(char, shot, rp):
    """Initial / prior pose per shot, as global segment directions turned into per-bone local rotations."""
    pose = {b: np.zeros(3) for b in SOLVE_BONES}
    fwd, down, up = np.array([0, -1, 0.0]), np.array([0, 0, -1.0]), np.array([0, 0, 1.0])
    lean = {("DS", 1): 8, ("DS", 2): 25, ("CL", 2): 10, ("CL", 3): 8}.get((char, shot), 0)
    pose["上半身"] = np.array([-math.radians(lean), 0, 0])          # pitch forward about +X
    if char == "DS":
        # forearms crossed on the rail: upper arms forward/down, forearms horizontal crossing in front
        g_up = Rot.from_rotvec(pose["上半身"])
        for side, sx in (("左", 1), ("右", -1)):
            sh, el = rp[f"{side}腕"][0], rp[f"{side}ひじ"][0]
            want_upper = g_up.apply(np.array([0.18 * sx, -0.55, -0.80]))
            r_upper = dir_rot(el - sh, want_upper)
            pose[f"{side}腕"] = r_upper
            g_arm = Rot.from_rotvec(r_upper) * g_up
            wr = rp[f"{side}手首"][0]
            rest_fore = g_arm.apply(wr - el)
            want_fore = np.array([-0.85 * sx, -0.45, 0.05])           # across the body toward the other side
            pose[f"{side}ひじ"] = dir_rot(rest_fore, want_fore)
        pose["頭"] = np.array([math.radians(-20 if shot == 2 else 4), 0, 0])
    else:
        # hands resting on the thighs / hip, slight forward bow
        g_up = Rot.from_rotvec(pose["上半身"])
        for side, sx in (("左", 1), ("右", -1)):
            sh, el = rp[f"{side}腕"][0], rp[f"{side}ひじ"][0]
            pose[f"{side}腕"] = dir_rot(el - sh, g_up.apply(np.array([0.30 * sx, -0.15, -0.94])))
            g_arm = Rot.from_rotvec(pose[f"{side}腕"]) * g_up
            wr = rp[f"{side}手首"][0]
            pose[f"{side}ひじ"] = dir_rot(g_arm.apply(wr - el), np.array([0.05 * sx, -0.45, -0.89]))
    return pose


# ---------------------------------------------------------------- forward kinematics
class Skeleton:
    def __init__(self, height):
        self.rp = rest_positions(height)
        self.height = height

    def fk(self, rots, center):
        """rots: bone -> rotvec (local delta in parent's posed axes). Returns global rotations and posed heads/tails
        in armature space (figure at origin facing -Y)."""
        G, head, tail = {}, {}, {}
        for n, (parent, _, _) in BONES.items():
            r = Rot.from_rotvec(rots.get(n, np.zeros(3)))
            h0, t0 = self.rp[n]
            if parent is None:
                G[n], head[n] = r, h0.copy()
            else:
                ph0 = self.rp[parent][0]
                G[n] = G[parent] * r
                head[n] = head[parent] + G[parent].apply(h0 - ph0)
                if n == "センター":
                    head[n] = head[n] + center
            tail[n] = head[n] + G[n].apply(t0 - h0)
        return G, head, tail

    def points(self, rots, center):
        G, head, tail = self.fk(rots, center)
        pts = {}
        for kp, (bone, which) in KP_TO_BONE.items():
            if which == "hand_tip":
                d = tail[bone] - head[bone]
                pts[kp] = head[bone] + d / np.linalg.norm(d) * HAND_TIP_UNITS * MMD_SCALE * self.height / 1.6
            else:
                pts[kp] = head[bone] if which == "head" else tail[bone]
        h0 = self.rp["頭"][0]
        for kp, off in FACE_POINTS.items():
            pts[kp] = head["頭"] + G["頭"].apply(mmd_to_blender(off, self.height))
        return pts, G, head, tail


# ---------------------------------------------------------------- per-frame solve
def head_target_dirs(ypr, cam):
    """World forward/up of the head from viewer-centric yaw/pitch/roll (degrees) and the camera pose."""
    yaw, pitch, roll = (math.radians(v) for v in ypr)
    R = look_at(*cam[:3])
    f_cam = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    u_cam = np.array([math.sin(roll), math.cos(roll), 0.0])
    return R @ f_cam, R @ u_cam


def project(P, cam):
    loc, tgt, roll, lens = cam
    R = look_at(loc, tgt, roll)
    C = (np.atleast_2d(P) - np.asarray(loc)) @ R
    f_px = lens / SENSOR_H * H
    return np.stack([W / 2 + f_px * C[:, 0] / -C[:, 2], H / 2 - f_px * C[:, 1] / -C[:, 2]], 1)


SIGMA_PX = {("DS", 1): 14, ("DS", 2): 22, ("CL", 2): 5, ("CL", 3): 16}
PRIOR_SIG = {"下半身": 0.35, "上半身": 0.30, "首": 0.35, "頭": 0.45, "左肩": 0.15, "右肩": 0.15,
             "左腕": 0.7, "右腕": 0.7, "左ひじ": 0.8, "右ひじ": 0.8, "左手首": 0.5, "右手首": 0.5}


def prior_sigma(char, bone):
    if char == "CL" and bone in ("左肩", "右肩"):
        return 0.35
    return PRIOR_SIG[bone]


WAIST_SIG_PX, HIPROLL_SIG_DEG, HIP_KP_WEIGHT_WITH_WAIST = 8.0, 2.5, 0.3


def waist_and_hip_roll(sk, rots, center, loc, Ra, cam):
    """Projected waist joint (上半身 head) and image angle of the hip line (right hip -> left hip, degrees, y down)."""
    _, head, _ = sk.fk(rots, center)
    uv = project(np.array([loc + Ra.apply(head[b]) for b in ("上半身", "左足", "右足")]), cam)
    d = uv[1] - uv[2]
    return uv[0], math.degrees(math.atan2(d[1], d[0]))


def solve_frame(sk, char, shot, rec, cam, anchor, prior, prev, rail, waist=None):
    loc, yaw = np.asarray(anchor["location"], float), anchor["yaw"]
    Ra = Rot.from_euler("z", yaw)
    obs = {k: np.array([v[0] * W, v[1] * H]) for k, v in (rec.get("kp") or {}).items()
           if isinstance(v, list) and len(v) >= 2 and (k in KP_TO_BONE or k in FACE_POINTS)}
    sig = SIGMA_PX[(char, shot)]
    hy = rec.get("head_ypr")
    hdirs = head_target_dirs(hy, cam) if isinstance(hy, list) and len(hy) == 3 else None
    nb = len(SOLVE_BONES)

    def unpack(x):
        return {b: x[3 * i:3 * i + 3] for i, b in enumerate(SOLVE_BONES)}, x[3 * nb:3 * nb + 3]

    def resid(x):
        rots, center = unpack(x)
        pts, G, head, tail = sk.points(rots, center)
        r = []
        if obs:
            keys = list(obs)
            Pw = np.array([loc + Ra.apply(pts[k]) for k in keys])
            uv = project(Pw, cam)
            for k, p in zip(keys, uv):
                w = {"head_top": 0.25, "l_hand_tip": 0.5, "r_hand_tip": 0.5}.get(k, 1.0)
                if waist is not None and k in ("l_hip", "r_hip"):
                    w = HIP_KP_WEIGHT_WITH_WAIST
                r.extend(((p - obs[k]) / sig * w).tolist())
        if waist is not None:
            wp, roll = waist_and_hip_roll(sk, rots, center, loc, Ra, cam)
            r.extend(((wp - waist["px"]) / WAIST_SIG_PX * waist["w"]).tolist())
            r.append((roll - waist["roll"]) / HIPROLL_SIG_DEG * waist["w"])
        if hdirs is not None:
            fw = Ra.apply(G["頭"].apply([0, -1, 0]))
            upv = Ra.apply(G["頭"].apply([0, 0, 1]))
            r.extend(((fw - hdirs[0]) / 0.25).tolist())
            r.extend(((upv - hdirs[1]) / 0.30).tolist())
        for b in SOLVE_BONES:
            r.extend(((rots[b] - prior[b]) / prior_sigma(char, b)).tolist())
            if prev is not None:
                r.extend(((rots[b] - prev[0][b]) / 0.10).tolist())
        r.extend((center / (0.12 if char == "CL" else 0.06)).tolist())
        if prev is not None:
            r.extend(((center - prev[1]) / 0.02).tolist())
        if rail is not None:
            for side in ("左", "右"):
                mid = loc + Ra.apply((head[f"{side}ひじ"] + head[f"{side}手首"]) / 2)
                r.append((mid[2] - rail) / 0.03)
        return np.array(r)

    x0 = np.concatenate([(prev[0] if prev else prior)[b] for b in SOLVE_BONES] + [prev[1] if prev else np.zeros(3)])
    sol = least_squares(resid, x0, loss="soft_l1", f_scale=2.0, max_nfev=400)
    rots, center = unpack(sol.x)
    pts, _, _, _ = sk.points(rots, center)
    errs = {}
    if obs:
        keys = list(obs)
        uv = project(np.array([loc + Ra.apply(pts[k]) for k in keys]), cam)
        errs = {k: float(np.linalg.norm(p - obs[k])) for k, p in zip(keys, uv)}
    return rots, center, errs


def anchors_for(spec, char):
    """Per-shot placement of the character root (world location of the feet point, yaw so the figure's -Y faces
    the facing target). spec.characters[char] may carry per_shot overrides."""
    c = spec["characters"][char]
    out = {}
    for shot in (1, 2, 3):
        o = (c.get("per_shot") or {}).get(str(shot), c)
        loc = np.asarray(o["location"], float)
        tgt = np.asarray(o.get("facing_target", loc + [0, -1, 0]), float)
        d = tgt - loc
        out[shot] = {"location": loc.tolist(), "yaw": math.atan2(d[0], -d[1])}
    return out


def smooth(frames, key_rots):
    """Savitzky-Golay over each bone's rotation vector (unwrapped via relative rotations)."""
    if len(frames) < 7:
        return key_rots
    out = [dict(r) for r in key_rots]
    for b in SOLVE_BONES:
        q = Rot.from_rotvec(np.array([r[b] for r in key_rots]))
        ref = q[len(q) // 2]
        rel = (ref.inv() * q).as_rotvec()
        rel_s = savgol_filter(rel, 7, 2, axis=0)
        sm = (ref * Rot.from_rotvec(rel_s)).as_rotvec()
        for i in range(len(out)):
            out[i][b] = sm[i]
    return out


def waist_observations(sk, spec, anchor, frames, rots_list, centers, track):
    """Corset track -> per-frame waist/hip-line targets, offset-calibrated on the first-pass fit (shot means)."""
    by_f = {r["f"]: r for r in track["tracks"]["corset"]}
    loc, Ra = np.asarray(anchor["location"], float), Rot.from_euler("z", anchor["yaw"])
    fit, meas = [], []
    for f, rots, ce in zip(frames, rots_list, centers):
        if f in by_f:
            wp, roll = waist_and_hip_roll(sk, rots, ce, loc, Ra, camera_at(spec, f))
            fit.append([wp[0], wp[1], roll])
            meas.append([by_f[f]["x"], by_f[f]["y"], by_f[f]["rot_deg"]])
    off = (np.array(fit) - np.array(meas)).mean(0)
    obs = {}
    for f, r in by_f.items():
        cc = r.get("cc", 1.0)
        w = 0.0 if not np.isfinite(cc) else float(np.clip((cc - 0.55) / 0.2, 0.0, 1.0))
        obs[f] = {"px": np.array([r["x"] + off[0], r["y"] + off[1]]), "roll": r["rot_deg"] + off[2], "w": w}
    return obs, off


def fit_character(ann, spec, char, out_dir, waist_track=None):
    height = spec["characters"][char].get("height_m", 1.6)
    sk = Skeleton(height)
    anchors = anchors_for(spec, char)
    rail = spec.get("rail_top_z")
    results = []
    by_shot = {}
    for rec in ann:
        if rec.get("dup_of") or rec.get("pending"):
            continue
        c = next((c for c in rec.get("chars", []) if c.get("id") == char), None)
        if c is None or not (c.get("kp") or {}):
            continue
        by_shot.setdefault(rec["shot"], []).append((rec["f"], c))

    def run_shot(shot, items, prior, waist_obs=None):
        prev = None
        frames, rots_list, centers, errs_list = [], [], [], []
        for f, c in items:
            cam = camera_at(spec, f)
            use_rail = rail if (char == "DS" and shot in (1, 2)) else None
            wo = (waist_obs or {}).get(f)
            rots, center, errs = solve_frame(sk, char, shot, c, cam, anchors[shot], prior, prev, use_rail, wo)
            prev = (rots, center)
            frames.append(f)
            rots_list.append(rots)
            centers.append(center)
            errs_list.append(errs)
        return frames, rots_list, centers, errs_list

    for shot, items in sorted(by_shot.items()):
        prior = template(char, shot, sk.rp)
        frames, rots_list, centers, errs_list = run_shot(shot, items, prior)
        if waist_track is not None and char == "CL" and shot == 3:
            obs, off = waist_observations(sk, spec, anchors[shot], frames, rots_list, centers, waist_track)
            print(f"CL shot 3: corset track calibrated (offset x {off[0]:.1f} px, y {off[1]:.1f} px, roll {off[2]:.1f} deg); "
                  f"refitting with the waist driven by the corset")
            frames, rots_list, centers, errs_list = run_shot(shot, items, prior, obs)
        rots_s = smooth(frames, rots_list)
        cen = np.array(centers)
        if len(cen) >= 7:
            cen = savgol_filter(cen, 7, 2, axis=0)
        for f, r, ce, e in zip(frames, rots_s, cen, errs_list):
            results.append({"f": f, "shot": shot,
                            "rot_wxyz": {b: np.roll(Rot.from_rotvec(r[b]).as_quat(), 1).round(6).tolist() for b in SOLVE_BONES},
                            "center_m": ce.round(5).tolist(),
                            "reproj_px": {k: round(v, 1) for k, v in e.items()}})
        allerr = [v for e in errs_list for v in e.values()]
        if allerr:
            print(f"{char} shot {shot}: {len(frames)} frames, reprojection median {np.median(allerr):.1f} px, "
                  f"p90 {np.percentile(allerr, 90):.1f} px")
    out = {"char": char, "height_m": height, "anchors": {str(k): v for k, v in anchors.items()}, "frames": results}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    json.dump(out, open(Path(out_dir) / f"pose_{char}.json", "w"), ensure_ascii=False)
    return out


def main(ann_json, spec_json, out_dir, chars="DS,CL", waist_json=None):
    ann = json.load(open(ann_json, encoding="utf-8"))
    spec = json.load(open(spec_json, encoding="utf-8"))
    waist = json.load(open(waist_json, encoding="utf-8")) if waist_json else None
    for ch in chars.split(","):
        fit_character(ann, spec, ch, out_dir, waist)


if __name__ == "__main__":
    argv = sys.argv[1:]
    pos, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    main(pos[0], pos[1], pos[2], opts.get("--chars", "DS,CL"), opts.get("--waist"))
