"""Render the rebuilt set as a silent video, frame-aligned with the source.

Usage: python render_video.py <scene.blend> <out_dir> [--scale 0.333] [--samples 12] [--frames 1-452] [--label 1]

Only frames on which the source shows a new image are rendered; frames the source repeats
(scene_spec meta.hold_residues, stored on the scene) are copied from the previous frame, exactly as the
source does. Output: out_dir/frames/rNNNN.png and out_dir/<blend name>.mp4 (H.264, 30 fps, no audio).
"""
import json
import os
import shutil
import subprocess
import sys

import bpy


def main(blend, out_dir, scale=0.333, samples=12, frames="1-452", label=True):
    os.makedirs(os.path.join(out_dir, "frames"), exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.volume_step_rate = 4.0
    sc.render.resolution_percentage = max(1, int(round(scale * 100)))
    sc.render.image_settings.file_format = "PNG"
    holds = json.loads(sc.get("hold_residues", "{}"))
    cut_marks = sorted((m.frame, m.camera) for m in sc.timeline_markers if m.camera)
    a, b = (int(x) for x in frames.split("-"))
    prev_path = None
    for f in range(a, b + 1):
        shot_idx = max(i for i, (mf, _) in enumerate(cut_marks) if mf <= f)
        shot = shot_idx + 1
        out = os.path.join(out_dir, "frames", f"r{f:04d}.png")
        is_hold = f % 5 in set(holds.get(str(shot), [])) and prev_path and cut_marks[shot_idx][0] < f
        if is_hold:
            shutil.copyfile(prev_path, out)
        else:
            sc.frame_set(f)
            sc.camera = cut_marks[shot_idx][1]
            sc.render.filepath = out
            bpy.ops.render.render(write_still=True)
        prev_path = out
        print(f"frame {f} shot {shot} {'hold' if is_hold else 'render'}", flush=True)
    name = os.path.splitext(os.path.basename(blend))[0]
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    if label:
        vf += (",drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:"
               f"text='f%{{eif\\:n+{a}\\:d\\:3}}':x=10:y=10:fontsize=h/40:fontcolor=white@0.8:box=1:boxcolor=black@0.4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-start_number", str(a),
           "-i", os.path.join(out_dir, "frames", "r%04d.png"), "-vf", vf,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", os.path.join(out_dir, f"{name}.mp4")]
    subprocess.run(cmd, check=True)
    print("video:", os.path.join(out_dir, f"{name}.mp4"))


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
    main(pos[0], pos[1], float(opts.get("--scale", 0.333)), int(opts.get("--samples", 12)),
         opts.get("--frames", "1-452"), opts.get("--label", "1") == "1")
