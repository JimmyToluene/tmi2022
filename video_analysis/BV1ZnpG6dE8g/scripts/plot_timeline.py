"""Measured timeline of BV1ZnpG6dE8g as small multiples on one shared time axis.

Usage: python plot_timeline.py <frame_signals.json> <shots.json> <audio_metrics.json> <out_png>
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURF = "#fcfcfb"


def main(sig_json, shots_json, audio_json, out_png):
    font_manager.fontManager.addfont("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
    plt.rcParams.update({"font.family": "WenQuanYi Zen Hei", "font.size": 9, "axes.edgecolor": AXIS,
                         "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.unicode_minus": False})
    sig = json.load(open(sig_json))
    shots = json.load(open(shots_json))
    au = json.load(open(audio_json))
    t = [s["t"] for s in sig]

    # cumulative camera zoom / roll, reset at each cut
    zoom, roll = [], []
    z = r = 1.0
    rr = 0.0
    prev_shot = None
    for s in sig:
        if s["shot"] != prev_shot:
            z, rr, prev_shot = 1.0, 0.0, s["shot"]
        c = s["cam"]
        if c and c["inlier_ratio"] > 0.4:
            z *= c["scale"]
            rr += c["rot_deg"]
        zoom.append(z)
        roll.append(rr)
    resid = [s["residual_flow_mean"] for s in sig]
    rms = [s["audio"]["rms_db"] for s in sig]
    dm = [len(s["danmaku_here"]) for s in sig]
    # danmaku density per 0.5 s
    bins = [0] * 31
    for s in sig:
        bins[int(s["t"] // 0.5)] += len(s["danmaku_here"])

    fig, ax = plt.subplots(5, 1, figsize=(10, 8.6), sharex=True, facecolor=SURF,
                           gridspec_kw={"height_ratios": [0.55, 1, 1, 1, 0.9], "hspace": 0.38})
    for a in ax:
        a.set_facecolor(SURF)
        a.grid(axis="y", color=GRID, linewidth=0.6)
        for s in shots[1:]:
            a.axvline(s["start_t"], color=INK2, linewidth=1, linestyle=(0, (3, 3)))

    names = {1: "镜头1  DS 倚栏 · 推近", 2: "镜头2  DS 背影俯瞰 · 舞台上的 CL", 3: "镜头3  CL 近景 · 扭胯直视镜头"}
    cols = {1: BLUE, 2: "#7a8fb0", 3: ORANGE}
    for s in shots:
        ax[0].barh(0, s["end_t"] - s["start_t"] + 1 / 30, left=s["start_t"], height=0.7, color=cols[s["shot"]],
                   edgecolor=SURF, linewidth=2)
        ax[0].text((s["start_t"] + s["end_t"]) / 2, 0, f"{names[s['shot']]}\nf{s['start_frame']}–{s['end_frame']}",
                   ha="center", va="center", color="white", fontsize=8.5)
    ax[0].set_yticks([])
    ax[0].set_title("镜头结构（硬切 f149 = 4.933 s，f304 = 10.100 s）", loc="left", color=INK, fontsize=10)

    ax[1].plot(t, zoom, color=BLUE, linewidth=2)
    ax[1].set_ylabel("累计缩放 ×")
    ax[1].set_title("摄影机推拉：镜头内累计缩放（ORB+RANSAC 相似变换），镜头1 推近 2.10×", loc="left", color=INK, fontsize=10)
    ax[1].annotate("×2.10", (shots[0]["end_t"], zoom[shots[0]["end_frame"] - 1]), xytext=(-46, -16),
                   textcoords="offset points", color=INK2)

    ax[2].plot(t, roll, color=AQUA, linewidth=2)
    ax[2].axhline(0, color=AXIS, linewidth=0.8)
    ax[2].set_ylabel("累计滚转 °")
    ax[2].set_title("摄影机滚转：镜头2 绕轴 +12°（揭示舞台），镜头3 手持式左右摇摆", loc="left", color=INK, fontsize=10)

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
    main(*sys.argv[1:5])
