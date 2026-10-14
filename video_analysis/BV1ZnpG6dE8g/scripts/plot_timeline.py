"""Measured timeline of BV1ZnpG6dE8g as small multiples on one shared time axis.

Usage: python plot_timeline.py <frame_signals.json> <shots.json> <audio_metrics.json> <camera_solved.json> <out_png>

Camera panels use the solved shot cameras (camera_solved.json from blender/camera_curves.py). The raw
frame-to-frame ORB similarity in frame_signals.json is not used for camera motion: it follows DS's body,
her hair and the dancing crowd as much as the camera.
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
SURF = "#fcfcfb"


def main(sig_json, shots_json, audio_json, cam_json, out_png):
    if not out_png.lower().endswith((".png", ".svg", ".pdf")):
        raise SystemExit(f"output must be an image path, got {out_png}")
    font_manager.fontManager.addfont("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
    plt.rcParams.update({"font.family": "WenQuanYi Zen Hei", "font.size": 9, "axes.edgecolor": AXIS,
                         "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.unicode_minus": False})
    sig = json.load(open(sig_json))
    shots = json.load(open(shots_json))
    au = json.load(open(audio_json))
    cam = json.load(open(cam_json))
    t = [s["t"] for s in sig]
    rms = [s["audio"]["rms_db"] for s in sig]
    bins = [0] * 31
    for s in sig:
        bins[int(s["t"] // 0.5)] += len(s["danmaku_here"])

    fig, ax = plt.subplots(5, 1, figsize=(10, 9.2), sharex=True, facecolor=SURF,
                           gridspec_kw={"height_ratios": [0.55, 1, 1.1, 1, 0.9], "hspace": 0.42})
    for a in ax:
        a.set_facecolor(SURF)
        a.grid(axis="y", color=GRID, linewidth=0.6)
        for s in shots[1:]:
            a.axvline(s["start_t"], color=INK2, linewidth=1, linestyle=(0, (3, 3)))

    names = {1: "镜头1  推轨靠近 DS · 50 mm", 2: "镜头2  DS 肩后俯视舞池 · 36 mm", 3: "镜头3  同一位置长焦 · 235 mm"}
    cols = {1: BLUE, 2: "#7a8fb0", 3: ORANGE}
    for s in shots:
        ax[0].barh(0, s["end_t"] - s["start_t"] + 1 / 30, left=s["start_t"], height=0.7, color=cols[s["shot"]],
                   edgecolor=SURF, linewidth=2)
        ax[0].text((s["start_t"] + s["end_t"]) / 2, 0, f"{names[s['shot']]}\nf{s['start_frame']}–{s['end_frame']}",
                   ha="center", va="center", color="white", fontsize=8.5)
    ax[0].set_yticks([])
    ax[0].set_title("镜头结构（硬切 f149 = 4.933 s，f304 = 10.100 s）", loc="left", color=INK, fontsize=10)

    for s in (1, 2, 3):
        r = [c for c in cam if c["shot"] == s]
        ax[1].plot([(c["f"] - 1) / 30 for c in r], [c["distance_m"] for c in r],
                   color=VIOLET if s == 2 else cols[s], linewidth=2)
    d1 = [c for c in cam if c["shot"] == 1]
    ax[1].annotate(f"{d1[0]['distance_m']:.2f} m → {d1[-1]['distance_m']:.2f} m（推轨，不是变焦）",
                   ((d1[-1]["f"] - 1) / 30, d1[-1]["distance_m"]), xytext=(-170, 22), textcoords="offset points",
                   color=INK2)
    ax[1].set_ylabel("米")
    ax[1].set_title("摄影机到主体的距离（镜头1 量到 DS 面部，镜头2/3 量到 CL 头部）", loc="left", color=INK, fontsize=10)

    for key, lab, colr in (("yaw_rel", "偏航（相对镜头起点）", AQUA), ("pitch_down_deg", "俯角", VIOLET),
                           ("roll_deg", "滚转", ORANGE)):
        for s in (1, 2, 3):
            r = [c for c in cam if c["shot"] == s]
            y0 = r[0]["yaw_deg"]
            vals = [(c["yaw_deg"] - y0) if key == "yaw_rel" else c[key] for c in r]
            ax[2].plot([(c["f"] - 1) / 30 for c in r], vals, color=colr, linewidth=2, label=lab if s == 1 else None)
    ax[2].axhline(0, color=AXIS, linewidth=0.8)
    ax[2].legend(loc="lower left", frameon=False, ncol=3, fontsize=8.5)
    ax[2].set_ylabel("度")
    ax[2].set_title("摄影机角度（勘测解算）：镜头2 左摇 16°、下俯 5°，滚转始终在 ±2° 以内", loc="left", color=INK, fontsize=10)

    ax[3].plot(t, rms, color=INK2, linewidth=1.6)
    for b in au["beat_times_s"]:
        ax[3].axvline(b, ymin=0, ymax=0.08, color=ORANGE, linewidth=1.4)
    ax[3].set_ylabel("响度 dB")
    ax[3].set_title("音频：RMS 响度（相对峰值），橙色刻度 = 节拍（120 BPM）；6.0 s 处鼓点进入 +10 dB", loc="left",
                    color=INK, fontsize=10)

    ax[4].bar([i * 0.5 + 0.25 for i in range(31)], bins, width=0.46, color=BLUE)
    ax[4].set_ylabel("条 / 0.5 s")
    ax[4].set_title("弹幕密度（80 条，按出现时间）", loc="left", color=INK, fontsize=10)
    ax[4].set_xlabel("时间 (s)")
    ax[4].set_xlim(0, 15.1)
    fig.savefig(out_png, dpi=160, bbox_inches="tight", facecolor=SURF)
    print("wrote", out_png)


if __name__ == "__main__":
    main(*sys.argv[1:6])
