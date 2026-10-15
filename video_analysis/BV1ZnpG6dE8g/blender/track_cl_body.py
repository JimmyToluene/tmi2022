"""Track CL's waist and thigh-level features on the source frames, for the pose fit.

Usage: python track_cl_body.py <frames_dir> <annotations_verified.json> <performer_track.json> <out_json>

Why: CL's annotated hips sit under her skirt and wander +-80 px against her rigid corset, and the legs are not
visible, so the fit had no real signal for her lower body. In the source her pelvis swings against her chest
(the waist moves with the chest; the thighs, where her hands rest, swing the other way and roll with the hips).

Shot 3 (f304-452, locked camera), every unique frame, all relative to f304 templates:
  studs   - the four gold corset studs, chained LK then rotation-searched NCC; centre and tilt of the stud grid
  flowers - the two sunflower ornaments on the skirt at upper-thigh height (under her hands), NCC template
            search with rotation/scale, warm-started from the previous frame
Shot 2 (f206-303, CL is ~200 px tall): chained LK + RANSAC similarity on 4x upsampled crops around her
(performer_track.json), for her chest and hip regions, tracked forward and backward from f250.
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
S2_REF = 250
S2_REGIONS = {"chest": [[600, 330], [780, 330], [780, 480], [600, 480]],      # f250 crop coords (4x)
              "hips": [[520, 640], [960, 640], [960, 860], [520, 860]]}


def track_shot2(frames_dir, frames, perf):
    def load(f):
        g = gray(frames_dir, f)
        x0, y0, _, _ = perf[f]["crop_xyxy"]
        x0 = min(max(0, x0), g.shape[1] - 360)
        y0 = min(max(0, y0), g.shape[0] - 360)
        return cv2.resize(g[y0:y0 + 360, x0:x0 + 360], None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC), np.array([x0, y0], float)

    to_full = lambda p, o: p / 4 + o
    to_crop = lambda p, o: (p - o) * 4
    lk = dict(winSize=(31, 31), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 0.01),
              flags=cv2.OPTFLOW_USE_INITIAL_FLOW)

    def run(seq):
        im0, o0 = load(seq[0])
        polys = {k: to_full(np.array(v, float), o0) for k, v in S2_REGIONS.items()}
        c0 = {k: polys[k].mean(0) for k in S2_REGIONS}
        Mc = {k: np.eye(3) for k in S2_REGIONS}
        out = {k: {seq[0]: {"x": float(c0[k][0]), "y": float(c0[k][1]), "rot": 0.0}} for k in S2_REGIONS}
        prev = (im0, o0)
        for f in seq[1:]:
            im, o = load(f)
            pim, po = prev
            for k in S2_REGIONS:
                m = np.zeros(pim.shape, np.uint8)
                cv2.fillPoly(m, [to_crop(polys[k], po).astype(np.int32)], 255)
                pts = cv2.goodFeaturesToTrack(pim, 300, 0.005, 8, mask=m)
                M = np.eye(3)
                if pts is not None and len(pts) >= 8:
                    P0 = to_full(pts[:, 0], po)
                    guess = to_crop(P0, o).astype(np.float32)[:, None]
                    p1, st, _ = cv2.calcOpticalFlowPyrLK(pim, im, pts, guess.copy(), **lk)
                    back = to_crop(to_full(p1[:, 0], o), po).astype(np.float32)[:, None]
                    p0r, st2, _ = cv2.calcOpticalFlowPyrLK(im, pim, p1, back.copy(), **lk)
                    ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.linalg.norm(p0r - pts, axis=2).ravel() < 1.5)
                    if ok.sum() >= 8:
                        A, _ = cv2.estimateAffinePartial2D(P0[ok], to_full(p1[ok, 0], o), method=cv2.RANSAC,
                                                           ransacReprojThreshold=0.6)
                        if A is not None:
                            M[:2] = A
                Mc[k] = M @ Mc[k]
                polys[k] = cv2.transform(polys[k][None], M[:2])[0]
                c = Mc[k][:2, :2] @ c0[k] + Mc[k][:2, 2]
                out[k][f] = {"x": round(float(c[0]), 2), "y": round(float(c[1]), 2),
                             "rot": round(math.degrees(math.atan2(Mc[k][1, 0], Mc[k][0, 0])), 3)}
            prev = (im, o)
        return out

    i = frames.index(S2_REF)
    fw, bw = run(frames[i:]), run(frames[i::-1])
    return {k: [dict(f=f, **v) for f, v in sorted({**bw[k], **fw[k]}.items())] for k in S2_REGIONS}


def main(frames_dir, ann_json, perf_json, out_json):
    ann = json.load(open(ann_json, encoding="utf-8"))
    perf = {r["frame"]: r for r in json.load(open(perf_json))}
    s3 = [r["f"] for r in ann if r["shot"] == 3 and not r.get("dup_of")]
    s2 = [r["f"] for r in ann if r["shot"] == 2 and not r.get("dup_of") and r["f"] >= 206
          and (perf.get(r["f"]) or {}).get("crop_xyxy")]
    studs = track_studs(frames_dir, s3)
    flowers = track_flowers(frames_dir, s3)
    shot2 = track_shot2(frames_dir, s2, perf)
    json.dump({"shot3": {"studs": studs, "flowers": flowers}, "shot2": shot2}, open(out_json, "w"), indent=0)
    sx = np.array([r["cx"] for r in studs])
    fm = np.array([(a["x"] + b["x"]) / 2 for a, b in zip(flowers["scr_left"], flowers["scr_right"])])
    print(f"shot 3: {len(s3)} frames; studs x p5-p95 {np.ptp(np.percentile(sx, [5, 95])):.0f} px; "
          f"flower-mid x p5-p95 {np.ptp(np.percentile(fm, [5, 95])):.0f} px; corr {np.corrcoef(sx, fm)[0, 1]:.2f}")
    print(f"shot 2: {len(s2)} frames tracked from f{S2_REF}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
