"""Export the three shot cameras of the rebuilt set as one MMD camera motion (camera.vmd).

Usage: python export_camera_vmd.py <scene.blend> <scene_spec.json> <mmd_tools_dir> <out.vmd> [--check report.json]

- Source frame f maps to MMD frame f-1 (the .blend starts at frame 1; mmd_tools subtracts frame_start).
- The active shot camera (timeline markers) is baked frame by frame into one helper camera, holds included,
  so cuts become one-frame jumps and the source's repeated frames stay frozen.
- The MMD camera target is the shot's subject: DS's face point in shot 1, CL's head in shots 2-3.
- VMD stores the view angle as whole degrees. For every frame the distance is rescaled by
  tan(fov/2) / tan(round(fov)/2) so the subject keeps its on-screen size (matters for the long-lens shot 3).
- --check re-imports the written file onto a fresh MMD camera and reports the pixel error of projected
  test points against the original cameras.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

MMD_SCALE = 0.08  # metres per MMD unit (mmd_tools default)


def subject_points(spec):
    """Per-shot focus points: DS's face point (shot 1: 0.10 m in front of the feet axis, 1.45 m up, as in the
    shot-1 solve), CL's head (shots 2-3)."""
    ds = spec["characters"]["DS"]
    cl = spec["characters"]["CL"]["location"]
    feet = Vector(ds["location"])
    face_dir = Vector(ds.get("facing_target", (feet.x, feet.y - 1, feet.z))) - feet
    face_dir.z = 0
    face_dir.normalize()
    ds_face = feet + face_dir * 0.10 + Vector((0, 0, 1.45))
    cl_head = Vector((cl[0], cl[1], cl[2] + 1.45))
    return {1: ds_face, 2: cl_head, 3: cl_head}


# probe offsets on the subject itself (what the frame actually shows): face, both shoulders, chest, rail/hands
PROBES = {1: ((0, 0, 0), (0.18, 0, -0.22), (-0.18, 0, -0.22), (0, 0, -0.35), (0.12, 0.08, -0.45)),
          2: ((0, 0, 0), (0.25, 0, -0.3), (0, 0, -1.3), (-0.6, -0.6, -1.4)),
          3: ((0, 0, 0), (0.2, 0, -0.25), (0, 0, -0.7), (-0.25, 0, -0.6))}


def active_camera(scene, f):
    marks = sorted((m.frame, m.camera) for m in scene.timeline_markers if m.camera)
    shot = max(i for i, (mf, _) in enumerate(marks) if mf <= f) + 1
    return shot, marks[shot - 1][1]


def bake_helper(scene, spec):
    data = bpy.data.cameras.new("CAM_All")
    data.sensor_fit = "VERTICAL"
    data.sensor_height = spec["meta"].get("sensor_height_mm", 36)
    cam = bpy.data.objects.new("CAM_All", data)
    scene.collection.objects.link(cam)
    target = bpy.data.objects.new("CAM_All_Target", None)
    scene.collection.objects.link(target)
    pts = subject_points(spec)
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        shot, src = active_camera(scene, f)
        cam.matrix_world = src.matrix_world.copy()
        data.lens = src.data.lens
        target.location = pts[shot]
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        data.keyframe_insert("lens", frame=f)
        target.keyframe_insert("location", frame=f)
    return cam, target


def fcurves_of(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def integer_fov_compensation(rig_root, rig_cam):
    """Snap each frame's view angle to whole degrees and rescale the distance to keep framing."""
    fov_fc = next(fc for fc in fcurves_of(rig_root) if fc.data_path == "mmd_camera.angle")
    dis_fc = next(fc for fc in fcurves_of(rig_cam) if fc.data_path == "location" and fc.array_index == 1)
    dis_by_frame = {int(round(k.co[0])): k for k in dis_fc.keyframe_points}
    worst = 0.0
    for k in fov_fc.keyframe_points:
        f = int(round(k.co[0]))
        fov = k.co[1]
        fov_int = math.radians(round(math.degrees(fov)))
        ratio = math.tan(fov / 2) / math.tan(fov_int / 2)
        k.co[1] = fov_int
        k.handle_left[1] = k.handle_right[1] = fov_int
        dk = dis_by_frame[f]
        dk.co[1] *= ratio
        dk.handle_left[1] = dk.handle_right[1] = dk.co[1]
        worst = max(worst, abs(ratio - 1))
    fov_fc.update()
    dis_fc.update()
    return worst


def check(scene, spec, vmd_path, mmd_tools_dir):
    """Project probe points through the original shot cameras, then re-import the VMD into a fresh scene
    (the way a user loads it) and project the same points through the imported MMD camera."""
    from bpy_extras.object_utils import world_to_camera_view
    from mmd_tools.core.camera import MMDCamera
    from mmd_tools.core.vmd.importer import VMDImporter

    pts = subject_points(spec)
    W, H = scene.render.resolution_x, scene.render.resolution_y
    frames = list(range(scene.frame_start, scene.frame_end + 1, 3))
    expected = {}
    for f in frames:
        scene.frame_set(f)
        shot, src = active_camera(scene, f)
        probes = [pts[shot] + Vector(d) for d in PROBES[shot]]
        expected[f] = (shot, probes, [world_to_camera_view(scene, src, p) for p in probes])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    import mmd_tools
    try:
        mmd_tools.register()
    except ValueError:
        pass  # classes stay registered across a factory reset in the bpy module
    fresh = bpy.context.scene
    fresh.render.resolution_x, fresh.render.resolution_y = W, H
    cam_data = bpy.data.cameras.new("VMD_Check")
    cam_obj = bpy.data.objects.new("VMD_Check", cam_data)
    fresh.collection.objects.link(cam_obj)
    # the importer converts the plain camera into an MMD camera rig itself; VMD frame 0 lands on frame 1
    VMDImporter(filepath=vmd_path, scale=MMD_SCALE, frame_margin=0).assign(cam_obj)
    cam_obj = MMDCamera(cam_obj).camera()
    res, errs = [], []
    for f in frames:
        fresh.frame_set(f)
        shot, probes, exp = expected[f]
        e = []
        for p, a in zip(probes, exp):
            b = world_to_camera_view(fresh, cam_obj, p)
            e.append(math.hypot((a.x - b.x) * W, (a.y - b.y) * H))
        errs.append(max(e))
        res.append({"f": f, "shot": shot, "max_err_px": round(max(e), 3)})
    errs.sort()
    summary = {"frames_checked": len(errs), "median_px": round(errs[len(errs) // 2], 3),
               "p95_px": round(errs[int(len(errs) * 0.95)], 3), "max_px": round(errs[-1], 3)}
    return summary, res


def main(blend, spec_json, mmd_tools_dir, out_vmd, check_json=None):
    sys.path.insert(0, mmd_tools_dir)
    bpy.ops.wm.open_mainfile(filepath=blend)
    import mmd_tools
    mmd_tools.register()
    from mmd_tools.core.camera import MMDCamera
    from mmd_tools.core.vmd.exporter import VMDExporter

    spec = json.load(open(spec_json, encoding="utf-8"))
    scene = bpy.context.scene
    cam, target = bake_helper(scene, spec)
    rig = MMDCamera.newMMDCameraAnimation(cam, target, scale=MMD_SCALE, bake_mode="ALL")
    rig_root, rig_cam = rig.object(), rig.camera()
    worst = integer_fov_compensation(rig_root, rig_cam)
    VMDExporter().export(camera=rig_root, filepath=out_vmd, scale=1 / MMD_SCALE, use_frame_range=True)
    print(f"wrote {out_vmd} ({os.path.getsize(out_vmd)} bytes); max distance rescale for integer FOV {worst * 100:.2f}%")
    if check_json:
        summary, rows = check(scene, spec, out_vmd, mmd_tools_dir)
        json.dump({"summary": summary, "frames": rows}, open(check_json, "w"), indent=1)
        print("round-trip check:", summary)


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
    main(pos[0], pos[1], pos[2], pos[3], opts.get("--check"))
