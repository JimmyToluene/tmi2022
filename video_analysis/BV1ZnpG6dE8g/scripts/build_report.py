"""Assemble the interactive report page from the analysis outputs.

Usage: python build_report.py <final_dir> <template_html> <out_html>

final_dir must contain: annotations_verified.json, events_verified.json, relations.json, kinematics.json,
measured.json, frame_signals.json, analysis_model.json, context_cards.json, method_cards.json, meta.json
"""
import json
import sys
from pathlib import Path


def load(d, name):
    return json.load(open(Path(d) / name, encoding="utf-8"))


def series(track, key, idx=None, scale=1.0):
    pts = []
    for r in track:
        v = r.get(key)
        if idx is not None:
            v = v[idx] if isinstance(v, list) and len(v) > idx else None
        pts.append([r["f"], None if v is None else round(v * scale, 3)])
    return pts


def main(final_dir, template, out_html):
    d = final_dir
    ann = load(d, "annotations_verified.json")
    sig = load(d, "frame_signals.json")
    meas = load(d, "measured.json")
    kin = load(d, "kinematics.json")
    meta = load(d, "meta.json")

    frames = []
    for r in ann:
        if r.get("dup_of"):
            frames.append({"f": r["f"], "t": r["t"], "shot": r["shot"], "dup_of": r["dup_of"]})
        else:
            keep = {k: r.get(k) for k in ("f", "t", "shot", "cam", "chars", "inter", "env", "delta")}
            keep["dup_of"] = None
            for c in keep["chars"] or []:
                c.pop("bbox", None)
            frames.append(keep)

    cam = load(d, "camera_solved.json") if (Path(d) / "camera_solved.json").exists() else None
    signals = []
    for i, s in enumerate(sig):
        c = cam[i] if cam else {}
        signals.append({"lens": c.get("lens_mm"), "yaw": c.get("yaw_deg"), "pitch": c.get("pitch_down_deg"),
                        "roll": c.get("roll_deg"), "dist": c.get("distance_m"), "rms": s["audio"]["rms_db"],
                        "beat": s["audio"]["beat"], "danmaku": s["danmaku_here"]})

    tr = kin["tracks"]
    ds, cl = tr.get("DS", []), tr.get("CL", [])
    blue, orange, slate = "var(--ds)", "var(--cl)", "var(--crowd)"
    panels = [
        {"title": "摄影机到主体距离（解算）", "unit": "米", "dp": 1,
         "series": [{"label": "距离", "color": "var(--cam)", "points": [[c["f"], c["distance_m"]] for c in (cam or [])]}]},
        {"title": "DS 头部偏航 yaw（MediaPipe 实测）", "unit": "°", "dp": 0, "zero": True,
         "series": [{"label": "DS yaw", "color": blue, "points": meas["ds_head_yaw_mp"]}]},
        {"title": "头部滚转 roll（标注估计）", "unit": "°", "dp": 0, "zero": True,
         "series": [{"label": "DS", "color": blue, "points": series(ds, "head_ypr", 2)},
                    {"label": "CL", "color": orange, "points": series(cl, "head_ypr", 2)}]},
        {"title": "CL 胯部侧移（肩宽）+ 节拍", "unit": "肩宽", "dp": 2, "zero": True, "beats": True,
         "series": [{"label": "CL", "color": orange, "points": series(cl, "hip_offset_sw")}]},
        {"title": "肩线倾斜", "unit": "°", "dp": 0, "zero": True,
         "series": [{"label": "DS", "color": blue, "points": series(ds, "shoulder_tilt_deg")},
                    {"label": "CL", "color": orange, "points": series(cl, "shoulder_tilt_deg")}]},
        {"title": "躯干侧倾", "unit": "°", "dp": 0, "zero": True,
         "series": [{"label": "DS", "color": blue, "points": series(ds, "trunk_lean_deg")},
                    {"label": "CL", "color": orange, "points": series(cl, "trunk_lean_deg")}]},
        {"title": "CL 手腕到同侧胯距离（肩宽）", "unit": "肩宽", "dp": 2,
         "series": [{"label": "左手", "color": orange, "points": series(cl, "l_wrist_to_hip_sw")},
                    {"label": "右手", "color": slate, "points": series(cl, "r_wrist_to_hip_sw")}]},
    ]
    # drop panels with no data at all
    panels = [p for p in panels if any(v is not None for s in p["series"] for _, v in s["points"])]

    data = {
        "meta": meta,
        "frames": frames,
        "signals": signals,
        "events": load(d, "events_verified.json"),
        "relations": load(d, "relations.json"),
        "kin_panels": panels,
        "analysis": load(d, "analysis_model.json"),
        "context": load(d, "context_cards.json"),
        "method": load(d, "method_cards.json"),
        "start_frame": 1,
    }
    if (Path(d) / "status.json").exists():
        data["status"] = load(d, "status.json")
    html = open(template, encoding="utf-8").read()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", blob)
    open(out_html, "w", encoding="utf-8").write(html)
    print(f"wrote {out_html}: {len(html) / 1024:.0f} KB, {len(frames)} frames, {len(panels)} kinematics panels")


if __name__ == "__main__":
    main(*sys.argv[1:4])
