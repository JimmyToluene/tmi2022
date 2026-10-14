"""A generic MMD-standard skeleton (bone names, hierarchy, rest positions) shared by the pose fitter and the
Blender/mmd_tools VMD exporter, plus a builder that creates it as an mmd_tools model with a neutral mannequin.

Rest positions are given in MMD units (Y up, model facing -Z, character's left = +X) for a 20-unit (1.60 m)
figure with arms ~40 deg below horizontal, then scaled to the character height. Blender coordinates are
(x, z, y) * 0.08 m, so the figure faces -Y with its left side at +X, as mmd_tools imports PMX models.

VMD bone rotations are relative to the rest pose, so a target model whose arms rest at a different angle
will show the arms offset by that difference; the README explains how to re-fit on the real model.
"""
import numpy as np

MMD_SCALE = 0.08

# name: (parent, head_xyz_mmd, tail_xyz_mmd)
BONES = {
    "全ての親": (None, (0, 0, 0), (0, 0, -1.5)),
    "センター": ("全ての親", (0, 8.0, 0), (0, 6.5, 0)),
    "下半身": ("センター", (0, 11.8, 0.2), (0, 10.0, 0.2)),
    "上半身": ("センター", (0, 11.8, 0.2), (0, 13.8, 0.4)),
    "首": ("上半身", (0, 16.3, 0.4), (0, 17.2, 0.3)),
    "頭": ("首", (0, 17.2, 0.3), (0, 19.9, 0.3)),
    "左肩": ("上半身", (0.4, 16.0, 0.6), (1.5, 15.8, 0.7)),
    "左腕": ("左肩", (1.5, 15.8, 0.7), (3.8, 13.9, 0.8)),
    "左ひじ": ("左腕", (3.8, 13.9, 0.8), (5.6, 12.1, 0.6)),
    "左手首": ("左ひじ", (5.6, 12.1, 0.6), (6.3, 11.4, 0.5)),
    "右肩": ("上半身", (-0.4, 16.0, 0.6), (-1.5, 15.8, 0.7)),
    "右腕": ("右肩", (-1.5, 15.8, 0.7), (-3.8, 13.9, 0.8)),
    "右ひじ": ("右腕", (-3.8, 13.9, 0.8), (-5.6, 12.1, 0.6)),
    "右手首": ("右ひじ", (-5.6, 12.1, 0.6), (-6.3, 11.4, 0.5)),
    "左足": ("下半身", (0.95, 11.2, 0.25), (0.95, 6.2, 0.1)),
    "左ひざ": ("左足", (0.95, 6.2, 0.1), (0.95, 1.2, 0.45)),
    "左足首": ("左ひざ", (0.95, 1.2, 0.45), (0.95, 0.2, -1.0)),
    "右足": ("下半身", (-0.95, 11.2, 0.25), (-0.95, 6.2, 0.1)),
    "右ひざ": ("右足", (-0.95, 6.2, 0.1), (-0.95, 1.2, 0.45)),
    "右足首": ("右ひざ", (-0.95, 1.2, 0.45), (-0.95, 0.2, -1.0)),
    "左足ＩＫ": ("全ての親", (0.95, 1.2, 0.45), (0.95, 1.2, 2.0)),
    "右足ＩＫ": ("全ての親", (-0.95, 1.2, 0.45), (-0.95, 1.2, 2.0)),
}
ORDER = list(BONES)  # parents precede children
FK_BONES = ["センター", "下半身", "上半身", "首", "頭", "左肩", "左腕", "左ひじ", "左手首",
            "右肩", "右腕", "右ひじ", "右手首"]
LEG_CHAINS = {"左": ("左足", "左ひざ", "左足首", "左足ＩＫ"), "右": ("右足", "右ひざ", "右足首", "右足ＩＫ")}

# annotation keypoint -> (bone whose head or tail it sits on, "head"|"tail", extra offset along the bone in MMD units)
KP_TO_BONE = {
    "neck": ("首", "head"), "head_top": ("頭", "tail"),
    "l_shoulder": ("左腕", "head"), "r_shoulder": ("右腕", "head"),
    "l_elbow": ("左ひじ", "head"), "r_elbow": ("右ひじ", "head"),
    "l_wrist": ("左手首", "head"), "r_wrist": ("右手首", "head"),
    "l_hand_tip": ("左手首", "hand_tip"), "r_hand_tip": ("右手首", "hand_tip"),
    "l_hip": ("左足", "head"), "r_hip": ("右足", "head"),
    "l_knee": ("左ひざ", "head"), "r_knee": ("右ひざ", "head"),
    "l_ankle": ("左足首", "head"), "r_ankle": ("右足首", "head"),
}
# face points expressed in the head bone's rest frame (MMD units, relative to 頭 head)
HAND_TIP_UNITS = 2.1  # wrist -> middle fingertip, MMD units (~17 cm on a 1.6 m figure)
FACE_POINTS = {"nose": (0, 0.9, -1.15), "chin": (0, 0.1, -0.85)}

MORPHS = ["まばたき", "笑い", "なごみ", "じと目", "あ", "い", "う", "にやり", "にこり", "∧", "困る", "真面目", "怒り"]


def mmd_to_blender(p, height_m=1.6):
    s = MMD_SCALE * height_m / 1.6
    return np.array([p[0] * s, p[2] * s, p[1] * s], dtype=float)


def rest_positions(height_m=1.6):
    """Blender-space rest head/tail for every bone, figure at the origin facing -Y."""
    return {n: (mmd_to_blender(h, height_m), mmd_to_blender(t, height_m)) for n, (_, h, t) in BONES.items()}


def build_mmd_model(name, height_m, collection=None):
    """Create an mmd_tools model (root + armature with Japanese bone names + mannequin mesh with morph shape
    keys) in the current Blender scene. Requires mmd_tools to be registered. Returns (root, armature, mesh)."""
    import bmesh
    import bpy
    from mathutils import Vector
    from mmd_tools.core.model import Model

    rig = Model.create(name, name, scale=MMD_SCALE)
    root = rig.rootObject()
    arm = rig.armature()
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    rp = rest_positions(height_m)
    for n in ORDER:
        b = eb.new(n)
        b.head, b.tail = Vector(rp[n][0]), Vector(rp[n][1])
        parent = BONES[n][0]
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
    bpy.ops.object.mode_set(mode="POSE")
    for n in ORDER:
        pb = arm.pose.bones[n]
        pb.rotation_mode = "QUATERNION"
        pb.mmd_bone.name_j = n
        pb.mmd_bone.name_e = n
    for side, (thigh, knee, ankle, ik) in LEG_CHAINS.items():
        c = arm.pose.bones[ankle].constraints.new("IK")
        c.target, c.subtarget, c.chain_count = arm, ik, 2
        c.use_tail = False
        arm.pose.bones[knee].lock_ik_y = arm.pose.bones[knee].lock_ik_z = True
    bpy.ops.object.mode_set(mode="OBJECT")

    # mannequin: one capsule per bone, rigidly weighted, plus morph shape keys
    bm = bmesh.new()
    groups = []
    for n in ORDER:
        if n in ("全ての親", "センター", "左足ＩＫ", "右足ＩＫ"):
            continue
        h, t = (Vector(v) for v in rp[n])
        d = t - h
        r = 0.05 if "足" in n or "ひざ" in n else 0.04
        if n == "頭":
            r = 0.1
        if n in ("上半身", "下半身"):
            r = 0.11
        ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=r * 0.85, depth=max(d.length, 0.02))
        bmesh.ops.rotate(bm, verts=ret["verts"], cent=(0, 0, 0), matrix=d.to_track_quat("Z", "Y").to_matrix())
        bmesh.ops.translate(bm, vec=(h + t) / 2, verts=ret["verts"])
        groups.append((n, [v.index for v in ret["verts"]]))
        bm.verts.index_update()
    bm.verts.index_update()
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    mesh = bpy.data.objects.new(name + "_mesh", me)
    (collection or bpy.context.scene.collection).objects.link(mesh)
    mesh.parent = arm
    for n, idx in groups:
        vg = mesh.vertex_groups.new(name=n)
        vg.add(idx, 1.0, "REPLACE")
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mesh.shape_key_add(name="Basis")
    for m in MORPHS:
        k = mesh.shape_key_add(name=m)
        k.data[0].co = k.data[0].co + Vector((0, 0, 1e-4))  # distinct, invisible
    return root, arm, mesh
