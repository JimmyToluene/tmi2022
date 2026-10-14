"""Write DS.vmd / CL.vmd (bone + morph motion) from the pose fits, through mmd_tools.

Usage: python export_motion_vmd.py <pose_dir> <scene_spec.json> <mmd_tools_dir> <out_dir> [--chars DS,CL] [--check 1]

- Bone keys on every frame 1..452 (MMD frames 0..451). Frames the source repeats repeat the previous pose;
  frames where the character is not annotated (off-screen) hold the nearest solved pose.
- Fitted rotations are local deltas in armature axes (R); Blender pose-bone rotations are R expressed in the
  bone's rest frame: Q = Rest^-1 R Rest. mmd_tools converts those to VMD.
- The character is placed once in Blender with MMD_<ID>_Root at its shot-1 anchor. Placement changes between
  shots (DS moves along the rail for shot 2) go into 全ての親 keys relative to that first anchor.
- Morph weights follow the verified expression timeline (standard morph names; models may name them
  differently, see README).
- --check re-imports each VMD onto a fresh skeleton and reports joint-position differences.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from scipy.spatial.transform import Rotation as Rot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mmd_skeleton import MMD_SCALE, build_mmd_model  # noqa: E402

N_FRAMES = 452


def hold_rule(spec):
    return {int(k): set(v) for k, v in spec["meta"].get("hold_residues", {}).items()}


def shot_of(spec, f):
    return next(C["shot"] for C in spec["cameras"] if C["frames"][0] <= f <= C["frames"][1])


def morph_timeline(char, f):
    """Morph weights per frame from the verified expression findings."""
    def ramp(f, a, b, va, vb):
        if f <= a:
            return va
        if f >= b:
            return vb
        return va + (vb - va) * (f - a) / (b - a)
    w = {}
    if char == "DS":
        g = min(f, 148)  # face hidden after the cut; hold the end of shot 1
        w["あ"] = ramp(g, 12, 29, 0.45, 0.0)
        w["笑い"] = ramp(g, 12, 29, 0.5, 0.15) if g < 59 else ramp(g, 59, 86, 0.15, 0.0)
        w["にこり"] = ramp(g, 59, 80, 1.0, 0.35) if g < 80 else ramp(g, 80, 86, 0.35, 0.0)
        w["∧"] = ramp(g, 89, 148, 0.0, 0.4)
        w["困る"] = ramp(g, 89, 148, 0.0, 0.2)
        w["まばたき"] = 0.0
    else:
        if f <= 303:
            w["まばたき"] = 0.85   # eyes closed or near-closed through shot 2
            w["にこり"] = 0.4
        else:
            w["まばたき"] = 0.35   # half-lidded, steady gaze in shot 3
            w["にこり"] = 0.55
    return w


def export_character(spec, pose, char, out_vmd):
    import mmd_tools  # noqa: F401
    from mmd_tools.core.vmd.exporter import VMDExporter

    height = pose["height_m"]
    root, arm, mesh = build_mmd_model(f"{char}_rig", height)
    pb = arm.pose.bones
    rest_rot = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}
    by_f = {fr["f"]: fr for fr in pose["frames"]}
    solved = sorted(by_f)
    anchors = {int(k): v for k, v in pose["anchors"].items()}
    a1 = anchors[min(anchors)] if char == "CL" else anchors[1]
    holds = hold_rule(spec)

    def nearest(f):
        return min(solved, key=lambda s: (abs(s - f), s))

    prev = None
    for f in range(1, N_FRAMES + 1):
        shot = shot_of(spec, f)
        if prev is not None and f % 5 in holds.get(shot, set()) and shot_of(spec, f - 1) == shot:
            fr = prev
        else:
            fr = by_f.get(f) or by_f[nearest(f)]
        prev = fr
        for bone, q in fr["rot_wxyz"].items():
            R = Quaternion(q).to_matrix()
            Rr = rest_rot[bone]
            pb[bone].rotation_quaternion = (Rr.inverted() @ R @ Rr).to_quaternion()
            pb[bone].keyframe_insert("rotation_quaternion", frame=f)
        c = Vector(fr["center_m"])
        pb["センター"].location = rest_rot["センター"].inverted() @ c
        pb["センター"].keyframe_insert("location", frame=f)
        # per-shot placement relative to the shot-1 anchor, carried by 全ての親
        an = anchors.get(shot, a1)
        d = Vector(an["location"]) - Vector(a1["location"])
        local = Matrix.Rotation(-a1["yaw"], 3, "Z") @ d
        dyaw = an["yaw"] - a1["yaw"]
        Rr = rest_rot["全ての親"]
        pb["全ての親"].location = Rr.inverted() @ local
        pb["全ての親"].rotation_quaternion = (Rr.inverted() @ Matrix.Rotation(dyaw, 3, "Z") @ Rr).to_quaternion()
        pb["全ての親"].keyframe_insert("location", frame=f)
        pb["全ての親"].keyframe_insert("rotation_quaternion", frame=f)
        for side in ("左", "右"):
            pb[f"{side}足ＩＫ"].location = (0, 0, 0)
            pb[f"{side}足ＩＫ"].keyframe_insert("location", frame=f)
        kb = mesh.data.shape_keys.key_blocks
        for name, val in morph_timeline(char, f).items():
            kb[name].value = float(val)
            kb[name].keyframe_insert("value", frame=f)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, N_FRAMES
    VMDExporter().export(armature=arm, mesh=mesh, filepath=out_vmd, scale=1 / MMD_SCALE, model_name=char,
                         use_frame_range=True)
    return root, arm, mesh, a1


def joint_positions(arm, frames):
    out = {}
    for f in frames:
        bpy.context.scene.frame_set(f)
        out[f] = {b.name: np.array(arm.matrix_world @ b.head) for b in arm.pose.bones}
    return out


def check(char, height, vmd_path, ref):
    from mmd_tools.core.vmd.importer import VMDImporter
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import mmd_tools
    try:
        mmd_tools.register()
    except ValueError:
        pass
    root, arm, mesh = build_mmd_model(f"{char}_check", height)
    VMDImporter(filepath=vmd_path, scale=MMD_SCALE, frame_margin=0).assign(arm)
    got = joint_positions(arm, list(ref))
    errs = [float(np.linalg.norm(got[f][b] - ref[f][b])) for f in ref for b in ref[f]]
    return {"frames": len(ref), "median_cm": round(np.median(errs) * 100, 3), "max_cm": round(max(errs) * 100, 3)}


def main(pose_dir, spec_json, mmd_tools_dir, out_dir, chars="DS,CL", do_check="0"):
    sys.path.insert(0, mmd_tools_dir)
    import mmd_tools
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        mmd_tools.register()
    except ValueError:
        pass
    spec = json.load(open(spec_json, encoding="utf-8"))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for char in chars.split(","):
        pose = json.load(open(Path(pose_dir) / f"pose_{char}.json", encoding="utf-8"))
        out_vmd = str(Path(out_dir) / f"{char}.vmd")
        root, arm, mesh, a1 = export_character(spec, pose, char, out_vmd)
        print(f"wrote {out_vmd} ({Path(out_vmd).stat().st_size} bytes); shot-1 anchor {a1['location']} yaw {math.degrees(a1['yaw']):.1f}")
        if do_check == "1":
            ref = joint_positions(arm, [1, 60, 120, 200, 260, 330, 400, 452])
            print(char, "round-trip:", check(char, pose["height_m"], out_vmd, ref))
            bpy.ops.wm.read_factory_settings(use_empty=True)


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
    main(pos[0], pos[1], pos[2], pos[3], opts.get("--chars", "DS,CL"), opts.get("--check", "0"))
