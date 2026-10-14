"""Load DS.vmd / CL.vmd onto neutral mannequin rigs placed at the MMD anchors of a built set, save the file,
and optionally render key frames through the shot cameras.

Usage: python assemble_vmd_preview.py <set.blend> <vmd_dir> <mmd_tools_dir> <out.blend> [--render out_dir --frames 1,60,...]

The mannequins are the generic skeleton from mmd_skeleton.py (no character likeness); swap them for the
real MMD models by importing the .pmx with mmd_tools and loading the same VMD onto it.
"""
import os
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mmd_skeleton import MMD_SCALE, build_mmd_model  # noqa: E402

HEIGHTS = {"DS": 1.58, "CL": 1.6}


def main(blend, vmd_dir, mmd_tools_dir, out_blend, render_dir=None, frames=None):
    sys.path.insert(0, mmd_tools_dir)
    bpy.ops.wm.open_mainfile(filepath=blend)
    import mmd_tools
    try:
        mmd_tools.register()
    except ValueError:
        pass
    from mmd_tools.core.vmd.importer import VMDImporter

    col = bpy.data.collections.get("Stand-ins (hide after importing MMD)")
    if col:
        col.hide_render = col.hide_viewport = True
    for char, h in HEIGHTS.items():
        anchor = bpy.data.objects.get(f"MMD_{char}_Root")
        root, arm, mesh = build_mmd_model(f"{char}_mannequin", h)
        root.parent = anchor
        root.location = (0, 0, 0)
        root.rotation_euler = (0, 0, 0)
        VMDImporter(filepath=os.path.join(vmd_dir, f"{char}.vmd"), scale=MMD_SCALE, frame_margin=0).assign(arm)
        mat = bpy.data.materials.new(f"{char}_mannequin")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.57, 0.62, 1)
        mesh.data.materials.append(mat)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
    print("saved", out_blend)
    if render_dir:
        os.makedirs(render_dir, exist_ok=True)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 8
        sc.cycles.use_denoising = True
        sc.cycles.volume_step_rate = 4.0
        sc.render.resolution_percentage = 25
        marks = sorted((m.frame, m.camera) for m in sc.timeline_markers if m.camera)
        for f in frames:
            sc.frame_set(f)
            sc.camera = [c for mf, c in marks if mf <= f][-1]
            sc.render.filepath = os.path.join(render_dir, f"vmd_F{f:03d}.png")
            bpy.ops.render.render(write_still=True)
            print("rendered", f)


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
    fr = [int(x) for x in opts["--frames"].split(",")] if "--frames" in opts else None
    main(pos[0], pos[1], pos[2], pos[3], opts.get("--render"), fr)
