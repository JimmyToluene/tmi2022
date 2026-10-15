"""Track CL's waist and thigh-level features on the source frames, for the pose fit.

Usage: python track_cl_body.py <frames_dir> <annotations_verified.json> <out_json>

Why: CL's annotated hips sit under her skirt and wander +-80 px against her rigid corset, and the legs are not
visible, so the fit had no real signal for her lower body. In the source her pelvis swings against her chest
(the waist moves with the chest; the thighs, where her hands rest, swing the other way and roll with the hips).

Shot 3 (f304-452, locked camera), every unique frame, all relative to f304 templates:
  studs   - the four gold corset studs, chained LK then rotation-searched NCC; centre and tilt of the stud grid
  flowers - the two sunflower ornaments on the skirt at upper-thigh height (under her hands), NCC template
            search with rotation/scale, warm-started from the previous frame
Shot 2 (f221-303, CL is ~300 px tall): DIS dense optical flow on a 3x upsampled crop for her chest, corset and the
thigh-level skirt band just below the corset.
Output in full-frame pixels (1080x1920); rotations in degrees, + = clockwise on screen.
"""
import json
import math
import sys

import cv2
import numpy as np

# ------------------------------------------------------------------ shot 3
STUDS = {"UL": (438, 962), "UR": (558, 971), "LL": (436, 1008), "LR": (551, 1015)}   # f304
FLOWERS = {"scr_left": (215, 1340), "scr_right": (742, 1352)}                        # f304; her right / left thigh


def gray(frames_dir, f):
    return cv2.imread(f"{frames_dir}/f{f:04d}.jpg", cv2.IMREAD_GRAYSCALE)


def subpix(r, ml):
    dx = dy = 0.0
    x, y = ml
    if 0 < x < r.shape[1] - 1:
        a, c, b = r[y, x - 1], r[y, x], r[y, x + 1]
        dx = 0.5 * (a - b) / (a - 2 * c + b + 1e-9)
    if 0 < y < r.shape[0] - 1:
        a, c, b = r[y - 1, x], r[y, x], r[y + 1, x]
        dy = 0.5 * (a - b) / (a - 2 * c + b + 1e-9)
    return dx, dy


def track_studs(frames_dir, frames):
    R, W = 16, 14
    g0 = gray(frames_dir, frames[0]).astype(np.float32)
    bank = {}
    for k, (x, y) in STUDS.items():
        t0 = g0[y - R:y + R, x - R:x + R]
        bank[k] = [(a, cv2.warpAffine(t0, cv2.getRotationMatrix2D((R, R), -a, 1.0), (2 * R, 2 * R),
                                      borderMode=cv2.BORDER_REFLECT)[5:-5, 5:-5]) for a in np.arange(-24, 25, 2.0)]
    pos = {k: np.array(v, float) for k, v in STUDS.items()}
    lk = dict(winSize=(25, 25), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01))
    prev, ang_prev, out = None, 0.0, []
    for f in frames:
        g = gray(frames_dir, f)
        if prev is not None:
            p0 = np.array([pos[k] for k in STUDS], np.float32)[:, None]
            p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, **lk)
            for i, k in enumerate(STUDS):
                if st[i, 0]:
                    pos[k] = p1[i, 0].astype(float)
        gf = g.astype(np.float32)
        rec = {"f": f}
        for k in STUDS:
            x, y = pos[k]
            x0, y0 = int(round(x)) - R - W, int(round(y)) - R - W
            win = gf[y0:y0 + 2 * (R + W), x0:x0 + 2 * (R + W)]
            best = (-2.0, 0.0, pos[k])
            for a, t in bank[k]:
                if abs(a - ang_prev) > 14:
                    continue
                r = cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(r)
                if mv > best[0]:
                    dx, dy = subpix(r, ml)
                    best = (mv, a, np.array([x0 + ml[0] + dx + R, y0 + ml[1] + dy + R]))
            pos[k] = best[2]
            rec[k] = [round(float(best[2][0]), 2), round(float(best[2][1]), 2), round(float(best[0]), 3), float(best[1])]
        ang_prev = float(np.mean([rec[k][3] for k in STUDS]))  # rotation search follows the matched template angle
        up = math.degrees(math.atan2(rec["UR"][1] - rec["UL"][1], rec["UR"][0] - rec["UL"][0]))
        lo = math.degrees(math.atan2(rec["LR"][1] - rec["LL"][1], rec["LR"][0] - rec["LL"][0]))
        rec["cx"] = round(float(np.mean([rec[k][0] for k in STUDS])), 2)
        rec["cy"] = round(float(np.mean([rec[k][1] for k in STUDS])), 2)
        rec["tilt_abs"] = round((up + lo) / 2, 3)
        out.append(rec)
        prev = g
    t0 = out[0]["tilt_abs"]
    for r in out:
        r["tilt"] = round(r["tilt_abs"] - t0, 3)
    return out


def track_flowers(frames_dir, frames):
    R, SEARCH = 34, 60
    im0 = cv2.imread(f"{frames_dir}/f{frames[0]:04d}.jpg")
    tmpl = {k: im0[y - R:y + R, x - R:x + R].copy() for k, (x, y) in FLOWERS.items()}
    bank = {k: [(a, s, cv2.warpAffine(t, cv2.getRotationMatrix2D((R, R), -a, s), (2 * R, 2 * R),
                                      borderMode=cv2.BORDER_REFLECT)[10:-10, 10:-10])
                for a in range(-36, 37, 3) for s in (0.92, 1.0, 1.08)] for k, t in tmpl.items()}
    cur = {k: np.array(v, float) for k, v in FLOWERS.items()}
    out = {k: [] for k in FLOWERS}
    for f in frames:
        im = cv2.imread(f"{frames_dir}/f{f:04d}.jpg")
        for k in FLOWERS:
            cx, cy = cur[k]
            x0, y0 = max(0, int(cx) - R - SEARCH), max(0, int(cy) - R - SEARCH)
            win = im[y0:int(cy) + R + SEARCH, x0:int(cx) + R + SEARCH]
            best = (-2.0, cur[k], 0)
            for a, s, t in bank[k]:
                r = cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(r)
                if mv > best[0]:
                    dx, dy = subpix(r, ml)
                    best = (mv, np.array([x0 + ml[0] + dx + R - 10, y0 + ml[1] + dy + R - 10]), a)
            cur[k] = best[1]
            out[k].append({"f": f, "x": round(float(best[1][0]), 2), "y": round(float(best[1][1]), 2),
                           "rot": best[2], "cc": round(float(best[0]), 3)})
    return out


# ------------------------------------------------------------------ shot 2
# boxes at f221 (full-res px): chest, corset, and the skirt band just below the corset (thigh level). The band
# excludes the lower skirt, which lags the thigh level by ~8 frames.
S2_START, S2_END = 221, 303
S2_BOXES = {"chest": [518, 1050, 572, 1095], "corset": [510, 1100, 568, 1130], "thigh": [500, 1138, 580, 1182]}
S2_CROP, S2_SCALE = [420, 860, 780, 1320], 3.0


def track_shot2(frames_dir, keep):
    """DIS dense optical flow on a 3x upsampled crop, forward-backward checked; each box moves by the median flow of
    a point grid inside it, and accumulates the in-plane rotation of a RANSAC partial affine."""
    def load(f):
        g = gray(frames_dir, f)[S2_CROP[1]:S2_CROP[3], S2_CROP[0]:S2_CROP[2]]
        return cv2.resize(g, None, fx=S2_SCALE, fy=S2_SCALE, interpolation=cv2.INTER_CUBIC)

    def samp(flow, p):
        m = cv2.remap(flow, p[:, 0].astype(np.float32).reshape(-1, 1), p[:, 1].astype(np.float32).reshape(-1, 1),
                      cv2.INTER_LINEAR)
        return m.reshape(-1, 2)

    tf = lambda p: (np.asarray(p, float) - S2_CROP[:2]) * S2_SCALE
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    ctr = {k: tf([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]) for k, b in S2_BOXES.items()}
    half = {k: (tf(b[2:]) - tf(b[:2])) / 2 for k, b in S2_BOXES.items()}
    ang = {k: 0.0 for k in S2_BOXES}
    out = {k: [] for k in S2_BOXES}
    back = lambda c: c / S2_SCALE + S2_CROP[:2]

    def emit(f):
        if f in keep:
            for k in S2_BOXES:
                x, y = back(ctr[k])
                out[k].append({"f": f, "x": round(float(x), 2), "y": round(float(y), 2), "rot": round(ang[k], 3)})

    prev = load(S2_START)
    emit(S2_START)
    for f in range(S2_START + 1, S2_END + 1):
        cur = load(f)
        fw, bw = dis.calc(prev, cur, None), dis.calc(cur, prev, None)
        h_, w_ = prev.shape
        for k in S2_BOXES:
            c, h = ctr[k], half[k]
            gx, gy = np.meshgrid(np.linspace(c[0] - h[0], c[0] + h[0], 24), np.linspace(c[1] - h[1], c[1] + h[1], 24))
            p = np.stack([gx.ravel(), gy.ravel()], 1)
            p = p[(p[:, 0] > 2) & (p[:, 0] < w_ - 3) & (p[:, 1] > 2) & (p[:, 1] < h_ - 3)]
            d = samp(fw, p)
            q = p + d
            ok = (q[:, 0] > 2) & (q[:, 0] < w_ - 3) & (q[:, 1] > 2) & (q[:, 1] < h_ - 3)
            p, q, d = p[ok], q[ok], d[ok]
            fb = np.linalg.norm(q + samp(bw, q) - p, axis=1)
            good = fb < 1.0 * S2_SCALE
            if good.sum() < 20:
                good = fb < np.percentile(fb, 50)
            M, _ = cv2.estimateAffinePartial2D(p[good].astype(np.float32), q[good].astype(np.float32),
                                               method=cv2.RANSAC, ransacReprojThreshold=1.0 * S2_SCALE)
            ctr[k] = c + np.median(d[good], 0)
            ang[k] += float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))) if M is not None else 0.0
        emit(f)
        prev = cur
    return out


def main(frames_dir, ann_json, out_json):
    ann = json.load(open(ann_json, encoding="utf-8"))
    s3 = [r["f"] for r in ann if r["shot"] == 3 and not r.get("dup_of")]
    s2 = {r["f"] for r in ann if r["shot"] == 2 and not r.get("dup_of") and S2_START <= r["f"] <= S2_END}
    studs = track_studs(frames_dir, s3)
    flowers = track_flowers(frames_dir, s3)
    shot2 = track_shot2(frames_dir, s2)
    json.dump({"shot3": {"studs": studs, "flowers": flowers}, "shot2": shot2}, open(out_json, "w"), indent=0)
    sx = np.array([r["cx"] for r in studs])
    fm = np.array([(a["x"] + b["x"]) / 2 for a, b in zip(flowers["scr_left"], flowers["scr_right"])])
    print(f"shot 3: {len(s3)} frames; studs x p5-p95 {np.ptp(np.percentile(sx, [5, 95])):.0f} px; "
          f"flower-mid x p5-p95 {np.ptp(np.percentile(fm, [5, 95])):.0f} px; corr {np.corrcoef(sx, fm)[0, 1]:.2f}")
    print(f"shot 2: {len(shot2['chest'])} unique frames tracked f{S2_START}-{S2_END}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
