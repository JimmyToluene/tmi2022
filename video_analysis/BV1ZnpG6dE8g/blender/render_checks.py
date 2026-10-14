"""Render chosen frames of the rebuilt set and compare them with the original video frames.

Usage: python render_checks.py <scene.blend> <frames_dir> <out_dir> <f1,f2,...> [--scale 0.25] [--samples 16] [--engine CYCLES]

For each frame writes render_FNNN.png and compare_FNNN.jpg (original | render | 50% overlay with the
render's edges drawn on the original), so camera alignment and lighting can be judged frame by frame.
"""
import os
import sys

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def main(blend, frames_dir, out_dir, frames, scale=0.25, samples=16, engine="CYCLES"):
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES" if engine == "CYCLES" else "BLENDER_EEVEE"
    if engine == "CYCLES":
        sc.cycles.device = "CPU"
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.volume_step_rate = 4.0
    sc.render.resolution_percentage = int(scale * 100)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for f in frames:
        sc.frame_set(f)
        # the active camera follows the bound timeline markers
        cams = [m for m in sc.timeline_markers if m.camera and m.frame <= f]
        if cams:
            sc.camera = max(cams, key=lambda m: m.frame).camera
        path = os.path.join(out_dir, f"render_F{f:03d}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        rend = Image.open(path).convert("RGB")
        w, h = rend.size
        orig = Image.open(os.path.join(frames_dir, f"f{f:04d}.jpg")).convert("RGB").resize((w, h), Image.LANCZOS)
        edges = rend.convert("L").filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 40 else 0)
        over = Image.blend(orig, rend, 0.5)
        ov = np.array(orig).copy()
        ov[np.array(edges) > 0] = (0, 255, 120)
        sheet = Image.new("RGB", (w * 4 + 18, h + 26), (255, 255, 255))
        for k, (im, lab) in enumerate([(orig, f"original f{f}"), (rend, "render"), (over, "50% blend"), (Image.fromarray(ov), "render edges on original")]):
            sheet.paste(im, (k * (w + 6), 26))
            ImageDraw.Draw(sheet).text((k * (w + 6) + 4, 4), lab, fill=(0, 0, 0), font=font)
        sheet.save(os.path.join(out_dir, f"compare_F{f:03d}.jpg"), quality=88)
        print("rendered", f, sc.camera.name)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    pos, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    main(pos[0], pos[1], pos[2], [int(x) for x in pos[3].split(",")], float(opts.get("--scale", 0.25)),
         int(opts.get("--samples", 16)), opts.get("--engine", "CYCLES"))
