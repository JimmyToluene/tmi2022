"""Fit the MMD-standard skeleton to the verified per-frame annotations through the solved shot cameras.

Usage: python pose_fit.py <annotations_verified.json> <scene_spec.json> <out_dir> [--chars DS,CL] [--body cl_body_tracks.json]

For each character and each unique (non-duplicate) annotated frame, solve with robust least squares:
  - reprojection of skeleton joints/face points against the verified 2D keypoints (pixels, per-shot sigma)
  - head orientation against the verified viewer-centric head yaw/pitch/roll
  - a pose prior per shot (templates below, built from the verified descriptions), joint-limit-ish priors
  - temporal smoothness to the previous solved frame, small センター offset
  - contact: DS's forearms rest on the balcony handrail in shots 1-2
  - legs as the VMD plays them: two-bone IK from each hip to the planted 足ＩＫ target (rest position), with a
    reach barrier so the hips never leave the feet's reach (no floating feet; dips come from knee bend)
  - per-shot height: if the free fit puts the hips above the planted feet's reach (feet never in frame for these
    shots), the shot's anchor is raised by that amount (anchors[shot].lift_m, carried by 全ての親 in the VMD)
  - optional (--body, CL): tracks from track_cl_body.py. CL's annotated hips sit under her skirt and are
    unreliable, but in the source her lower body swings against her chest like a pendulum hung at the waist: the
    waist (corset studs) moves with the chest, while the skirt, with her hands resting on it, swings the other
    way and rolls with the hips. Skirt points are modelled rigidly on 下半身 (0.30 m below the waist), so the
    swing becomes 下半身 motion that drives an MMD model's skirt. A calibration pass sets offsets (shot means);
    the final pass fits, in shot 3, the waist x to the studs, the right skirt point to the skirt ornament and the
    skirt midpoint to her annotated wrists, and in shot 2 the hip midpoint relative to the neck and the hip roll
    to the hip-region track. The annotated hips are down-weighted in that pass.
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


HIP_KP_WEIGHT_WITH_BODY = 0.3
THIGH_FRAC = 0.35          # thigh point (skirt ornament / hand rest height) as a fraction of hip -> knee
REACH_MARGIN_M = 0.015     # keep the hip at least this far inside full leg extension
REACH_SIG_M = 0.003


def leg_ik(sk, G, head, side):
    """Knee position and reach excess for one leg, solved like the rig: two-bone IK from the hip (足 head) to the
    planted 足ＩＫ target at its rest position, knee bending toward the pelvis's forward (-Y)."""
    hip, tgt = head[f"{side}足"], sk.rp[f"{side}足ＩＫ"][0]
    a = np.linalg.norm(sk.rp[f"{side}ひざ"][0] - sk.rp[f"{side}足"][0])
    b = np.linalg.norm(sk.rp[f"{side}足首"][0] - sk.rp[f"{side}ひざ"][0])
    v = tgt - hip
    d = float(np.linalg.norm(v))
    u = v / d
    dc = min(d, a + b - 1e-6)
    fwd = G["下半身"].apply([0.0, -1.0, 0.0])
    pole = fwd - (fwd @ u) * u
    pole /= np.linalg.norm(pole)
    ca = float(np.clip((a * a + dc * dc - b * b) / (2 * a * dc), -1.0, 1.0))
    knee = hip + a * (ca * u + math.sqrt(1.0 - ca * ca) * pole)
    return knee, d - (a + b - REACH_MARGIN_M)


def ik_leg_points(sk, pts, G, head):
    """Replace the FK knee/ankle keypoints by the IK legs the VMD plays (ankle stays on its planted target)."""
    for side, kk, ka in (("左", "l_knee", "l_ankle"), ("右", "r_knee", "r_ankle")):
        knee, _ = leg_ik(sk, G, head, side)
        pts[kk], pts[ka] = knee, sk.rp[f"{side}足ＩＫ"][0]
    return pts


def thigh_points(sk, G, head):
    out = {}
    for side in ("左", "右"):
        knee, _ = leg_ik(sk, G, head, side)
        out[side] = head[f"{side}足"] + THIGH_FRAC * (knee - head[f"{side}足"])
    return out


SKIRT_OFF = {"左": (0.12, -0.08, -0.30), "右": (-0.12, -0.08, -0.30)}   # m in 下半身's frame at 1.6 m (left = +X)


def body_measures(sk, pts, G, head, loc, Ra, cam):
    """Image-space quantities the body tracks constrain: waist joint, hip midpoint, neck, hip-line roll (deg, y down),
    thigh points and hand tips per side (L = her left = screen right)."""
    th = thigh_points(sk, G, head)
    k = sk.height / 1.6
    sL = head["下半身"] + G["下半身"].apply(np.array(SKIRT_OFF["左"]) * k)
    sR = head["下半身"] + G["下半身"].apply(np.array(SKIRT_OFF["右"]) * k)
    names = ["waist", "neck", "hipL", "hipR", "thighL", "thighR", "handL", "handR", "skirtL", "skirtR"]
    P = [head["上半身"], head["首"], head["左足"], head["右足"], th["左"], th["右"], pts["l_hand_tip"], pts["r_hand_tip"], sL, sR]
    uv = dict(zip(names, project(np.array([loc + Ra.apply(p) for p in P]), cam)))
    uv["skirtmid"] = (uv["skirtL"] + uv["skirtR"]) / 2
    d = uv["hipL"] - uv["hipR"]
    uv["hipmid"] = (uv["hipL"] + uv["hipR"]) / 2
    uv["roll"] = math.degrees(math.atan2(d[1], d[0]))
    return uv


def waist_and_hip_roll(sk, rots, center, loc, Ra, cam):
    """Projected waist joint (上半身 head) and image angle of the hip line (right hip -> left hip, degrees, y down)."""
    _, head, _ = sk.fk(rots, center)
    uv = project(np.array([loc + Ra.apply(head[b]) for b in ("上半身", "左足", "右足")]), cam)
    d = uv[1] - uv[2]
    return uv[0], math.degrees(math.atan2(d[1], d[0]))


def solve_frame(sk, char, shot, rec, cam, anchor, prior, prev, rail, body=None, reach=True):
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
        ik_leg_points(sk, pts, G, head)
        r = []
        if obs:
            keys = list(obs)
            Pw = np.array([loc + Ra.apply(pts[k]) for k in keys])
            uv = project(Pw, cam)
            for k, p in zip(keys, uv):
                w = {"head_top": 0.25, "l_hand_tip": 0.5, "r_hand_tip": 0.5}.get(k, 1.0)
                if body is not None and k in ("l_hip", "r_hip"):
                    w = HIP_KP_WEIGHT_WITH_BODY
                r.extend(((p - obs[k]) / sig * w).tolist())
        if body is not None:
            m = body_measures(sk, pts, G, head, loc, Ra, cam)
            for key, (target, s_px) in body.get("abs", {}).items():          # e.g. waist x, thighR xy
                r.extend(((m[key][:len(target)] - target) / s_px).tolist())
            for (a_key, b_key), (target, s_px) in body.get("rel", {}).items():  # e.g. thigh - hand, hipmid - neck
                diff = m[a_key] - m[b_key]
                r.extend(((diff[:len(target)] - target) / s_px).tolist())
            if "roll" in body:
                target, s_deg = body["roll"]
                r.append((m["roll"] - target) / s_deg)
        if reach:
            for side in ("左", "右"):
                _, excess = leg_ik(sk, G, head, side)
                r.append(max(0.0, excess) / REACH_SIG_M)
        if hdirs is not None:
            fw = Ra.apply(G["頭"].apply([0, -1, 0]))
            upv = Ra.apply(G["頭"].apply([0, 0, 1]))
            r.extend(((fw - hdirs[0]) / 0.25).tolist())
            r.extend(((upv - hdirs[1]) / 0.30).tolist())
        for b in SOLVE_BONES:
            r.extend(((rots[b] - prior[b]) / prior_sigma(char, b)).tolist())
            if prev is not None:
                r.extend(((rots[b] - prev[0][b]) / 0.10).tolist())
        # small センター offset around the pre-lift height (a raised anchor is compensated by bending the knees)
        c_ref = np.array([0.0, 0.0, -anchor.get("lift_m", 0.0)])
        r.extend(((center - c_ref) / (0.12 if char == "CL" else 0.06)).tolist())
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
    pts, G, head, _ = sk.points(rots, center)
    ik_leg_points(sk, pts, G, head)
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


def body_observations(sk, spec, anchor, shot, frames, rots_list, centers, tracks, wrists=None):
    """Per-frame body targets from track_cl_body.py, offset-calibrated on the first-pass fit (shot means)."""
    loc, Ra = np.asarray(anchor["location"], float), Rot.from_euler("z", anchor["yaw"])
    first = {}
    for f, rots, ce in zip(frames, rots_list, centers):
        pts, G, head, _ = sk.points(rots, ce)
        first[f] = body_measures(sk, pts, G, head, loc, Ra, camera_at(spec, f))
    obs, report = {}, {}
    if shot == 3:
        studs = {r["f"]: r for r in tracks["shot3"]["studs"]}
        flower = {r["f"]: r for r in tracks["shot3"]["flowers"]["scr_left"]}   # skirt ornament on her right side
        fs = [f for f in frames if f in studs and f in flower and f in (wrists or {})]
        fl = {f: np.array([flower[f]["x"], flower[f]["y"]]) for f in fs}
        off_w = float(np.mean([first[f]["waist"][0] - studs[f]["cx"] for f in fs]))
        off_s = np.mean([first[f]["skirtR"] - fl[f] for f in fs], 0)
        off_m = np.mean([first[f]["skirtmid"] - wrists[f] for f in fs], 0)
        for f in fs:
            obs[f] = {"abs": {"waist": (np.array([studs[f]["cx"] + off_w]), 6.0),
                              "skirtR": (fl[f] + off_s, 10.0),
                              "skirtmid": (wrists[f] + off_m, 12.0)}}
        report = {"waist_x_off_px": round(off_w, 1), "skirt_flower_off_px": np.round(off_s, 1).tolist(),
                  "skirt_wrist_off_px": np.round(off_m, 1).tolist()}
    elif shot == 2:
        chest = {r["f"]: r for r in tracks["shot2"]["chest"]}
        hips = {r["f"]: r for r in tracks["shot2"]["hips"]}
        fs = [f for f in frames if f in chest and f in hips]
        rel = {f: hips[f]["x"] - chest[f]["x"] for f in fs}
        off_x = np.mean([(first[f]["hipmid"] - first[f]["neck"])[0] - rel[f] for f in fs])
        off_r = np.mean([first[f]["roll"] - hips[f]["rot"] for f in fs])
        for f in fs:
            obs[f] = {"rel": {("hipmid", "neck"): (np.array([rel[f] + off_x]), 3.0)},
                      "roll": (hips[f]["rot"] + off_r, 2.5)}
        report = {"hip_rel_off_px": round(off_x, 1), "roll_off_deg": round(off_r, 1)}
    return obs, report


def fit_character(ann, spec, char, out_dir, body_tracks=None):
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

    def run_shot(shot, items, prior, body_obs=None, reach=True):
        prev = None
        frames, rots_list, centers, errs_list = [], [], [], []
        for f, c in items:
            cam = camera_at(spec, f)
            use_rail = rail if (char == "DS" and shot in (1, 2)) else None
            bo = (body_obs or {}).get(f)
            rots, center, errs = solve_frame(sk, char, shot, c, cam, anchors[shot], prior, prev, use_rail, bo, reach)
            prev = (rots, center)
            frames.append(f)
            rots_list.append(rots)
            centers.append(center)
            errs_list.append(errs)
        return frames, rots_list, centers, errs_list

    base_anchor = {"location": list(anchors[1]["location"]), "yaw": anchors[1]["yaw"]}
    lifts = {}
    for shot, items in sorted(by_shot.items()):
        prior = template(char, shot, sk.rp)
        # pass A (no reach): how high does the free fit put the pelvis? Raise the shot's anchor so the planted feet
        # can reach the hips with slightly bent knees (feet are out of frame in every shot of this clip).
        frames, rots_list, centers, errs_list = run_shot(shot, items, prior, reach=False)
        cz = np.array([c[2] for c in centers])
        lift = max(0.0, float(cz.max()) + 0.01)
        lifts[shot] = round(lift, 3)
        if lift > 0.005:
            anchors[shot]["location"][2] += lift
        anchors[shot]["lift_m"] = round(lift, 3)
        # pass B: with the reach barrier at the (possibly raised) anchor
        frames, rots_list, centers, errs_list = run_shot(shot, items, prior)
        if body_tracks is not None and char == "CL" and shot in (2, 3):
            wr = {}
            for f, c in items:
                kp = c.get("kp") or {}
                if "l_wrist" in kp and "r_wrist" in kp:
                    wr[f] = np.array([(kp["l_wrist"][0] + kp["r_wrist"][0]) / 2 * W, (kp["l_wrist"][1] + kp["r_wrist"][1]) / 2 * H])
            obs, rep_ = body_observations(sk, spec, anchors[shot], shot, frames, rots_list, centers, body_tracks, wr)
            print(f"CL shot {shot}: body tracks on {len(obs)} frames, calibration {rep_}; refitting")
            # pass C: with the body tracks
            frames, rots_list, centers, errs_list = run_shot(shot, items, prior, obs)
        rots_s = smooth(frames, rots_list)
        cen = np.array(centers)
        if len(cen) >= 7:
            cen = savgol_filter(cen, 7, 2, axis=0)
        # smoothing can push a hip slightly out of the planted foot's reach: lower センター until both legs reach
        for i, r in enumerate(rots_s):
            for _ in range(6):
                _, G, head, _ = sk.points(r, cen[i])
                excess = max(leg_ik(sk, G, head, side)[1] for side in ("左", "右"))
                if excess <= 0:
                    break
                cen[i][2] -= excess + 0.002
        for f, r, ce, e in zip(frames, rots_s, cen, errs_list):
            results.append({"f": f, "shot": shot,
                            "rot_wxyz": {b: np.roll(Rot.from_rotvec(r[b]).as_quat(), 1).round(6).tolist() for b in SOLVE_BONES},
                            "center_m": ce.round(5).tolist(),
                            "reproj_px": {k: round(v, 1) for k, v in e.items()}})
        allerr = [v for e in errs_list for v in e.values()]
        if allerr:
            print(f"{char} shot {shot}: {len(frames)} frames, reprojection median {np.median(allerr):.1f} px, "
                  f"p90 {np.percentile(allerr, 90):.1f} px")
    print(f"{char}: per-shot anchor lift (m) {lifts}")
    out = {"char": char, "height_m": height, "base_anchor": base_anchor,
           "anchors": {str(k): v for k, v in anchors.items()}, "frames": results}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    json.dump(out, open(Path(out_dir) / f"pose_{char}.json", "w"), ensure_ascii=False)
    return out


def main(ann_json, spec_json, out_dir, chars="DS,CL", body_json=None):
    ann = json.load(open(ann_json, encoding="utf-8"))
    spec = json.load(open(spec_json, encoding="utf-8"))
    body = json.load(open(body_json, encoding="utf-8")) if body_json else None
    for ch in chars.split(","):
        fit_character(ann, spec, ch, out_dir, body)


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
    main(pos[0], pos[1], pos[2], opts.get("--chars", "DS,CL"), opts.get("--body"))
