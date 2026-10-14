"""Build the BV1ZnpG6dE8g club set in Blender from scene_spec.json (everything except the two characters).

Run headless with the bpy module or inside Blender:
    python build_scene.py scene_spec.json out.blend [--pose pose_reference.json] [--engine EEVEE|CYCLES]
    blender -b -P build_scene.py -- scene_spec.json out.blend

Conventions are those of camera_math.py: Z-up metres, origin at the stage-disc centre on the pit floor,
+Y from DS's balcony toward the far side, cameras = {location, target, roll_deg, lens_mm} on a 36 mm
vertical sensor. Frame numbers equal the source video's frame numbers (30 fps, f1-f452).

Characters are NOT modelled. Each gets an MMD_<ID>_Root empty at the measured spot (feet on the floor,
facing its target) plus a neutral grey stand-in in the "Stand-ins" collection; import the MMD model
with mmd_tools, parent its root to the empty, then hide the stand-in.
"""
import json
import math
import os
import random
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camera_math import euler_xyz  # noqa: E402


# ---------------------------------------------------------------- helpers
def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)


def collection(name, parent=None):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in [c.name for c in (parent or bpy.context.scene.collection).children]:
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(obj, col):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def mesh_object(name, bm, col, material=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if material:
        ob.data.materials.append(material)
    return ob


def look_rotation(location, target, roll_deg=0.0):
    return euler_xyz(location, target, roll_deg)


# ---------------------------------------------------------------- materials
MATS = {}


def make_material(name, p):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_rgba(p.get("base_color", "#808080"))
    bsdf.inputs["Metallic"].default_value = p.get("metallic", 0.0)
    bsdf.inputs["Roughness"].default_value = p.get("roughness", 0.5)
    if p.get("emission_strength", 0) > 0:
        bsdf.inputs["Emission Color"].default_value = hex_rgba(p.get("emission_color", p.get("base_color", "#ffffff")))
        bsdf.inputs["Emission Strength"].default_value = p["emission_strength"]
    if p.get("transmission", 0) > 0:
        bsdf.inputs["Transmission Weight"].default_value = p["transmission"]
        bsdf.inputs["IOR"].default_value = p.get("ior", 1.45)
    if p.get("alpha", 1.0) < 1.0:
        bsdf.inputs["Alpha"].default_value = p["alpha"]
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
    MATS[name] = m
    return m


def mat(name):
    if name not in MATS:
        make_material(name, {"base_color": "#ff00ff"})  # loud fallback so a missing material is visible
    return MATS[name]


def emission_material(name, color, strength):
    return make_material(name, {"base_color": "#000000", "emission_color": color, "emission_strength": strength,
                                "roughness": 1.0})


# ---------------------------------------------------------------- geometry
def g_box(e, col):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(e["size"]), verts=bm.verts)
    ob = mesh_object(e["name"], bm, col, mat(e["material"]))
    ob.location = e["center"]
    ob.rotation_euler = [math.radians(a) for a in e.get("rotation_deg", [0, 0, 0])]
    return ob


def g_cylinder(e, col):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=e.get("vertices", 64), radius1=e["radius"],
                          radius2=e["radius"], depth=e["depth"])
    ob = mesh_object(e["name"], bm, col, mat(e["material"]))
    ob.location = e["center"]
    ob.rotation_euler = [math.radians(a) for a in e.get("rotation_deg", [0, 0, 0])]
    return ob


def g_steps(e, col):
    x0, y0, x1, y1 = e["rect"]
    n, rise, z0, axis = e["count"], e["rise"], e["z0"], e.get("axis", "+y")
    obs = []
    for k in range(n):
        f0, f1 = k / n, (k + 1) / n
        if axis in ("+y", "-y"):
            ya, yb = (y0 + (y1 - y0) * f0, y1) if axis == "+y" else (y0, y1 - (y1 - y0) * f0)
            cx, cy, sx, sy = (x0 + x1) / 2, (ya + yb) / 2, abs(x1 - x0), abs(yb - ya)
        else:
            xa, xb = (x0 + (x1 - x0) * f0, x1) if axis == "+x" else (x0, x1 - (x1 - x0) * f0)
            cx, cy, sx, sy = (xa + xb) / 2, (y0 + y1) / 2, abs(xb - xa), abs(y1 - y0)
        top = z0 + rise * (k + 1)
        obs.append(g_box({"name": f"{e['name']}_{k + 1}", "center": [cx, cy, (z0 + top) / 2],
                          "size": [sx, sy, top - z0], "material": e["material"]}, col))
    return obs


def g_tube_rail(e, col):
    pts = [Vector(p) for p in e["points"]]
    cu = bpy.data.curves.new(e["name"], "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = e["radius"]
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts):
        p.co = (*v, 1.0)
    ob = bpy.data.objects.new(e["name"], cu)
    col.objects.link(ob)
    ob.data.materials.append(mat(e["material"]))
    posts = e.get("posts")
    if posts:
        for a, b in zip(pts, pts[1:]):
            seg = (b - a)
            n = max(1, int(seg.length / posts["spacing"]))
            for k in range(n + 1):
                p = a + seg * (k / n)
                g_cylinder({"name": f"{e['name']}_post", "center": [p.x, p.y, p.z - posts["height"] / 2],
                            "radius": posts["radius"], "depth": posts["height"], "vertices": 16,
                            "material": posts["material"]}, col)
    return ob


def g_glass_panel(e, col):
    a, b = Vector(e["from"]), Vector(e["to"])
    d = b - a
    ob = g_box({"name": e["name"], "center": list((a + b) / 2 + Vector((0, 0, e["height"] / 2))),
                "size": [d.length, e.get("thickness", 0.012), e["height"]], "material": e["material"]}, col)
    ob.rotation_euler = (0, 0, math.atan2(d.y, d.x))
    return ob


def g_table_cluster(e, col):
    rnd = random.Random(e.get("seed", 0))
    x0, y0, x1, y1 = e["rect"]
    rows, cols, jit = e["rows"], e["cols"], e.get("jitter", 0.2)
    tr, th = e.get("table_radius", 0.3), e.get("table_height", 0.75)
    lamp = e.get("lamp")
    lamp_mat = emission_material(f"{e['name']}_lamp", lamp["color"], lamp["strength"]) if lamp else None
    tmat = mat(e.get("table_material", "table"))
    sub = collection(e["name"], col)
    bm_t, bm_l = bmesh.new(), bmesh.new()
    for r in range(rows):
        for c in range(cols):
            x = x0 + (c + 0.5) / cols * (x1 - x0) + rnd.uniform(-jit, jit)
            y = y0 + (r + 0.5) / rows * (y1 - y0) + rnd.uniform(-jit, jit)
            z = e["z"]
            top = bmesh.ops.create_cone(bm_t, cap_ends=True, segments=24, radius1=tr, radius2=tr, depth=0.03)
            bmesh.ops.translate(bm_t, vec=(x, y, z + th), verts=top["verts"])
            stem = bmesh.ops.create_cone(bm_t, cap_ends=True, segments=8, radius1=0.03, radius2=0.03, depth=th)
            bmesh.ops.translate(bm_t, vec=(x, y, z + th / 2), verts=stem["verts"])
            if lamp:
                lp = bmesh.ops.create_cone(bm_l, cap_ends=True, segments=12, radius1=lamp["radius"],
                                           radius2=lamp["radius"] * 0.9, depth=lamp["height"])
                bmesh.ops.translate(bm_l, vec=(x, y, z + th + 0.015 + lamp["height"] / 2), verts=lp["verts"])
    mesh_object(f"{e['name']}_tables", bm_t, sub, tmat)
    if lamp:
        mesh_object(f"{e['name']}_lamps", bm_l, sub, lamp_mat)
        # a few real point lights at lamp positions so the warm pools also light faces and table tops
        n_lights = lamp.get("point_lights", 4)
        rr = random.Random(e.get("seed", 0) + 99)
        for k in range(n_lights):
            ld = bpy.data.lights.new(f"{e['name']}_glow{k}", "POINT")
            ld.color = hex_rgba(lamp["color"])[:3]
            ld.energy = lamp.get("light_w", 15)
            ld.shadow_soft_size = 0.1
            lo = bpy.data.objects.new(ld.name, ld)
            sub.objects.link(lo)
            lo.location = (rr.uniform(x0, x1), rr.uniform(y0, y1), e["z"] + th + 0.25)
    return sub


def skyline_image(name, w_px, h_px, seed, density, colors):
    rnd = np.random.default_rng(seed)
    img = np.zeros((h_px, w_px, 4), np.float32)
    img[..., 3] = 1.0
    x = 0
    pal = [np.array(hex_rgba(c)[:3]) for c in colors]
    while x < w_px:
        bw = int(rnd.integers(w_px // 16, w_px // 6))
        bh = int(rnd.integers(h_px // 4, int(h_px * 0.95)))
        body = np.array([0.006, 0.008, 0.016]) * rnd.uniform(0.6, 1.4)
        img[:bh, x:x + bw, :3] = body
        step_x, step_y = max(4, w_px // 120), max(5, h_px // 70)
        for yy in range(4, bh - 4, step_y):
            for xx in range(x + 3, x + bw - 3, step_x):
                if rnd.random() < density:
                    img[yy:yy + step_y // 2, xx:xx + step_x // 2, :3] = pal[int(rnd.integers(len(pal)))] * rnd.uniform(0.4, 1.0)
        x += bw + int(rnd.integers(0, w_px // 40))
    im = bpy.data.images.new(name, w_px, h_px, float_buffer=True)
    im.pixels.foreach_set(img.ravel())
    im.pack()
    return im


def g_skyline(e, col):
    w, h = e["size"]
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(bm, vec=(w, h, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
    me = bpy.data.meshes.new(e["name"])
    bm.to_mesh(me)
    bm.free()
    uv = me.uv_layers.new()
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        uv.data[li].uv = (co.x / w + 0.5, co.z / h + 0.5)
    ob = bpy.data.objects.new(e["name"], me)
    col.objects.link(ob)
    ob.location = e["center"]
    ob.rotation_euler = [math.radians(a) for a in e.get("rotation_deg", [0, 0, 0])]
    m = bpy.data.materials.new(e["name"])
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = skyline_image(e["name"] + "_img", 2048, int(2048 * h / w), e.get("seed", 3),
                              e.get("window_density", 0.35), e.get("colors", ["#ffd9a0", "#fff2d6", "#9fc4ff"]))
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = e.get("strength", 2.0)
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    ob.data.materials.append(m)
    return ob


def g_sparkles(e, col):
    rnd = np.random.default_rng(e.get("seed", 7))
    xmin, ymin, zmin, xmax, ymax, zmax = e["box"]
    bm = bmesh.new()
    s = e.get("size", 0.01)
    for _ in range(e["count"]):
        p = (rnd.uniform(xmin, xmax), rnd.uniform(ymin, ymax), rnd.uniform(zmin, zmax))
        ico = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=s * rnd.uniform(0.5, 1.5))
        bmesh.ops.translate(bm, vec=p, verts=ico["verts"])
    ob = mesh_object(e["name"], bm, col, emission_material(e["name"], e.get("color", "#fff1c8"), e.get("strength", 20)))
    ob.visible_shadow = False
    # slow drift so they read as floating dust in shot 3
    ob.keyframe_insert("location", frame=1)
    ob.location = (ob.location.x + 0.05, ob.location.y, ob.location.z + 0.25)
    ob.keyframe_insert("location", frame=452)
    return ob


GEOM = {"box": g_box, "cylinder": g_cylinder, "steps": g_steps, "tube_rail": g_tube_rail,
        "glass_panel": g_glass_panel, "table_cluster": g_table_cluster, "skyline": g_skyline, "sparkles": g_sparkles}


# ---------------------------------------------------------------- people (generic mannequins)
def mannequin_bmesh(height, arms_up=False, seated=False):
    """Neutral, featureless proxy figure (capsule limbs, sphere head), feet at z=0, facing -Y."""
    bm = bmesh.new()
    s = height / 1.75

    def limb(a, b, r):
        a, b = Vector(a) * s, Vector(b) * s
        d = b - a
        ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r * s, radius2=r * s * 0.85, depth=d.length)
        rot = d.to_track_quat("Z", "Y").to_matrix()
        bmesh.ops.rotate(bm, verts=ret["verts"], cent=(0, 0, 0), matrix=rot)
        bmesh.ops.translate(bm, vec=(a + b) / 2, verts=ret["verts"])

    hip_z = 0.45 if seated else 0.92
    if seated:
        limb((-0.1, 0, 0.45), (-0.1, -0.42, 0.45), 0.065)
        limb((0.1, 0, 0.45), (0.1, -0.42, 0.45), 0.065)
        limb((-0.1, -0.42, 0.45), (-0.1, -0.45, 0.0), 0.05)
        limb((0.1, -0.42, 0.45), (0.1, -0.45, 0.0), 0.05)
    else:
        limb((-0.1, 0, 0.92), (-0.1, 0, 0.0), 0.07)
        limb((0.1, 0, 0.92), (0.1, 0, 0.0), 0.07)
    top = hip_z + 0.55
    limb((0, 0, hip_z), (0, 0, top), 0.16)
    head = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.11 * s)
    bmesh.ops.translate(bm, vec=(0, 0, (top + 0.13) * s), verts=head["verts"])
    sh = top - 0.03
    if arms_up:
        limb((-0.2, 0, sh), (-0.3, -0.05, sh + 0.55), 0.045)
        limb((0.2, 0, sh), (0.3, -0.05, sh + 0.55), 0.045)
    else:
        limb((-0.2, 0, sh), (-0.24, -0.02, sh - 0.6), 0.045)
        limb((0.2, 0, sh), (0.24, -0.02, sh - 0.6), 0.045)
    return bm


def crowd_material(palette):
    m = bpy.data.materials.new("crowd_clothes")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.8
    info = nt.nodes.new("ShaderNodeObjectInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    for i, c in enumerate(palette):
        el = els[0] if i == 0 else els.new(i / len(palette))
        el.position = i / len(palette)
        el.color = hex_rgba(c)
    nt.links.new(info.outputs["Random"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def build_crowd(spec, root):
    cr = spec.get("crowd")
    if not cr:
        return
    rnd = random.Random(cr.get("seed", 11))
    anim = cr.get("animation", {})
    period = anim.get("period_frames", 15)
    lib = collection("CrowdVariants", root)
    lib.hide_render = False
    variants = []
    pal = sorted({c for z in cr["zones"] for c in z.get("palette", ["#202028"])})
    cmat = crowd_material(pal)
    # 12 animated variants: (arms up?, seated?) x 3 phases; members instance one of them
    for k, (up, seated) in enumerate([(False, False), (True, False), (False, True)] * 4):
        vc = bpy.data.collections.new(f"crowd_v{k:02d}")
        lib.children.link(vc)
        ob = mesh_object(f"crowd_v{k:02d}", mannequin_bmesh(1.75, up, seated), vc, cmat)
        if not seated:
            phase = (k // 3) * period / 4
            for f in range(1, 453, max(1, period // 2)):
                t = (f - 1 - phase) / period * 2 * math.pi
                ob.location.z = anim.get("bounce_m", 0.03) * max(0.0, math.sin(t))
                ob.rotation_euler.y = math.radians(anim.get("sway_deg", 4)) * math.sin(t / 2)
                ob.keyframe_insert("location", index=2, frame=f)
                ob.keyframe_insert("rotation_euler", index=1, frame=f)
        variants.append((vc, up, seated))
    lib.hide_viewport = True
    bpy.context.view_layer.layer_collection.children[root.name].children[lib.name].exclude = True
    members = collection("Crowd", root)
    for z in cr["zones"]:
        x0, y0, x1, y1 = z["rect"]
        excl = z.get("exclude_circles", [])
        placed = []
        tries = 0
        while len(placed) < z["count"] and tries < z["count"] * 60:
            tries += 1
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            if any((x - a) ** 2 + (y - b) ** 2 < r * r for a, b, r in excl):
                continue
            if any((x - a) ** 2 + (y - b) ** 2 < 0.42 ** 2 for a, b in placed):
                continue
            placed.append((x, y))
        up_n = int(round(len(placed) * z.get("arms_up_fraction", 0.2)))
        seat_n = int(round(len(placed) * z.get("seated_fraction", 0.0)))
        for i, (x, y) in enumerate(placed):
            want = (i < up_n, up_n <= i < up_n + seat_n)
            choices = [v for v in variants if (v[1], v[2]) == want] or variants
            vc = rnd.choice(choices)[0]
            e = bpy.data.objects.new(f"{z['name']}_{i:03d}", None)
            e.instance_type = "COLLECTION"
            e.instance_collection = vc
            members.objects.link(e)
            h = rnd.uniform(*z.get("height_range", [1.6, 1.85]))
            e.scale = (h / 1.75,) * 3
            e.location = (x, y, z["z"])
            tx, ty = z.get("facing_target", [0, 0])[:2]
            e.rotation_euler.z = math.atan2(-(tx - x), (ty - y)) + math.pi + rnd.uniform(-0.35, 0.35)


# ---------------------------------------------------------------- characters, cameras, lights
def build_characters(spec, root, pose=None):
    standins = collection("Stand-ins (hide after importing MMD)", root)
    anchors = collection("MMD anchors", root)
    for cid, c in spec.get("characters", {}).items():
        loc = Vector(c["location"])
        tgt = Vector(c.get("facing_target", [loc.x, loc.y - 1, loc.z]))
        e = bpy.data.objects.new(f"MMD_{cid}_Root", None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.5
        anchors.objects.link(e)
        e.location = loc
        # MMD models face -Y in Blender after mmd_tools import; rotate so -Y points at the facing target
        d = tgt - loc
        e.rotation_euler.z = math.atan2(d.x, -d.y)
        e["height_m"] = c.get("height_m", 1.6)
        e["note"] = c.get("lean_note", "")
        sb = mannequin_bmesh(c.get("height_m", 1.6))
        so = mesh_object(f"StandIn_{cid}", sb, standins, make_material(f"standin_{cid}", {"base_color": "#9a9a9a", "roughness": 0.6}))
        so.parent = e
        head = bpy.data.objects.new(f"MMD_{cid}_HeadTarget", None)
        head.empty_display_type = "SPHERE"
        head.empty_display_size = 0.12
        anchors.objects.link(head)
        head.parent = e
        head.location = (0, 0, c.get("height_m", 1.6) - 0.12)


def build_lights(spec, root, cut_frames):
    col = collection("Lights", root)
    for L in spec.get("lights", []):
        ld = bpy.data.lights.new(L["name"], L["type"])
        ld.color = hex_rgba(L.get("color", "#ffffff"))[:3]
        ld.energy = L.get("energy_w", 100)
        if L["type"] == "SPOT":
            ld.spot_size = math.radians(L.get("spot_size_deg", 30))
            ld.spot_blend = L.get("spot_blend", 0.3)
        if L["type"] == "AREA":
            ld.size = L.get("size_m", 1.0)
        elif hasattr(ld, "shadow_soft_size"):
            ld.shadow_soft_size = L.get("size_m", 0.1)
        if hasattr(ld, "volume_factor"):
            ld.volume_factor = L.get("volume_factor", 1.0)
        ob = bpy.data.objects.new(L["name"], ld)
        col.objects.link(ob)
        ob.location = L["location"]
        if "target" in L:
            ob.rotation_euler = look_rotation(L["location"], L["target"])
        shots = L.get("shots")
        if shots:
            bounds = [1] + cut_frames + [10 ** 6]
            for s in (1, 2, 3):
                on = s in shots
                ob.hide_render = ob.hide_viewport = not on
                ob.keyframe_insert("hide_render", frame=bounds[s - 1])
                ob.keyframe_insert("hide_viewport", frame=bounds[s - 1])


def unwrap(prev, ang):
    while ang - prev > math.pi:
        ang -= 2 * math.pi
    while ang - prev < -math.pi:
        ang += 2 * math.pi
    return ang


def build_cameras(spec, root):
    col = collection("Cameras", root)
    scene = bpy.context.scene
    cams = {}
    for C in spec["cameras"]:
        cd = bpy.data.cameras.new(C["name"])
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = spec["meta"].get("sensor_height_mm", 36)
        cd.clip_start, cd.clip_end = 0.05, 400
        ob = bpy.data.objects.new(C["name"], cd)
        col.objects.link(ob)
        ob["shot"] = C["shot"]
        prev = None
        dof = C.get("dof", {})
        if dof.get("enabled"):
            cd.dof.use_dof = True
            cd.dof.aperture_fstop = dof.get("fstop", 2.8)
        for k in sorted(C["keys"], key=lambda k: k["f"]):
            rot = look_rotation(k["location"], k["target"], k.get("roll_deg", 0))
            if prev is not None:
                rot = tuple(unwrap(p, a) for p, a in zip(prev, rot))
            prev = rot
            ob.location = k["location"]
            ob.rotation_euler = rot
            cd.lens = k["lens_mm"]
            ob.keyframe_insert("location", frame=k["f"])
            ob.keyframe_insert("rotation_euler", frame=k["f"])
            cd.keyframe_insert("lens", frame=k["f"])
            if dof.get("enabled"):
                focus = Vector(dof.get("focus", k["target"]))
                cd.dof.focus_distance = (focus - Vector(k["location"])).length
                cd.keyframe_insert("dof.focus_distance", frame=k["f"])
        for fc in list(_fcurves(ob)) + list(_fcurves(cd)):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        cams[C["shot"]] = ob
        m = scene.timeline_markers.new(f"Shot{C['shot']}", frame=C["frames"][0])
        m.camera = ob
    scene.camera = cams[min(cams)]
    return cams


def _fcurves(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return act.fcurves
    out = []  # Blender 4.4+/5.x layered actions
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def bake_cadence_holds(cams, spec):
    """Re-key every camera channel once per frame with CONSTANT interpolation, repeating the previous frame's
    value on the frames the source video repeats (meta.hold_residues: {shot: [f % 5 residues]}). Without this
    the rebuilt cameras move smoothly at 30 fps while the source moves on only 4 (shots 2-3) or 3 (shot 1)
    of every 5 frames, and frame-by-frame comparisons drift by up to a frame."""
    rule = spec["meta"].get("hold_residues")
    if not rule:
        return
    for C in spec["cameras"]:
        ob = cams[C["shot"]]
        holds = set(rule.get(str(C["shot"]), []))
        a, b = C["frames"]
        for fc in list(_fcurves(ob)) + list(_fcurves(ob.data)):
            vals = {}
            for f in range(a, b + 1):
                vals[f] = vals[f - 1] if (f % 5 in holds and f - 1 in vals) else fc.evaluate(f)
            fc.keyframe_points.clear()
            for f, v in vals.items():
                kp = fc.keyframe_points.insert(f, v, options={"FAST"})
                kp.interpolation = "CONSTANT"
            fc.update()


def attach_plates(cams, plates_dir):
    """Show the user's own extracted source frames (plates_dir/f0001.jpg ...) behind every shot camera in the
    viewport, frame-locked to the timeline. Only the path is stored; no frames are packed into the file."""
    first = os.path.join(os.path.abspath(plates_dir), "f0001.jpg")
    img = bpy.data.images.load(first, check_existing=True)
    img.source = "SEQUENCE"
    for ob in cams.values():
        cd = ob.data
        cd.show_background_images = True
        bg = cd.background_images.new()
        bg.image = img
        bg.image_user.frame_start = 1
        bg.image_user.frame_duration = 452
        bg.image_user.frame_offset = 0
        bg.image_user.use_auto_refresh = True
        bg.alpha = 0.5
        bg.display_depth = "FRONT"
        bg.frame_method = "FIT"


def build_world(spec):
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = hex_rgba(spec["world"].get("bg_color", "#05070f"))
    bg.inputs["Strength"].default_value = spec["world"].get("bg_strength", 0.2)


def build_haze(spec, root):
    hz = spec["world"].get("haze")
    if not hz or hz.get("density", 0) <= 0:
        return
    xmin, ymin, zmin, xmax, ymax, zmax = hz["box"]
    m = bpy.data.materials.new("haze")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = hz["density"]
    vol.inputs["Color"].default_value = hex_rgba(hz.get("color", "#9fb4ff"))
    vol.inputs["Anisotropy"].default_value = hz.get("anisotropy", 0.3)
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    MATS["haze"] = m
    col = collection("Atmosphere", root)
    ob = g_box({"name": "HazeVolume", "center": [(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2],
                "size": [xmax - xmin, ymax - ymin, zmax - zmin], "material": "haze"}, col)
    ob.display_type = "BOUNDS"
    ob.visible_shadow = False


def build_pose_reference(pose, root):
    """Animated empties at each annotated joint, placed on a vertical plane through the character's
    anchor (2D keypoints back-projected through the shot camera at the character's depth)."""
    col = collection("Pose reference (from annotations)", root)
    col.hide_render = True
    for cid, tracks in pose.items():
        for joint, keys in tracks.items():
            e = bpy.data.objects.new(f"POSE_{cid}_{joint}", None)
            e.empty_display_type = "SPHERE"
            e.empty_display_size = 0.025
            col.objects.link(e)
            for f, xyz in keys:
                e.location = xyz
                e.keyframe_insert("location", frame=f)


def render_settings(spec, engine):
    sc = bpy.context.scene
    meta = spec["meta"]
    sc.render.fps = meta.get("fps", 30)
    sc.frame_start, sc.frame_end = meta.get("frame_start", 1), meta.get("frame_end", 452)
    sc.render.resolution_x, sc.render.resolution_y = meta["resolution"]
    sc.render.engine = "CYCLES" if engine == "CYCLES" else "BLENDER_EEVEE"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    sc.view_settings.exposure = spec["world"].get("exposure", 0.0)
    if engine == "CYCLES":
        sc.cycles.samples = 128
        sc.cycles.use_denoising = True
    else:
        ee = sc.eevee
        for attr, val in (("use_volumetric_shadows", True), ("volumetric_tile_size", "4"),
                          ("use_raytracing", True), ("taa_render_samples", 64)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except TypeError:
                    pass


def build(spec_path, out_blend, pose_path=None, engine="EEVEE", plates_dir=None):
    spec = json.load(open(spec_path, encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = collection("BV1ZnpG6dE8g_Set")
    for name, p in spec.get("materials", {}).items():
        make_material(name, p)
    set_col = collection("Architecture", root)
    props = collection("Props", root)
    for e in spec.get("geometry", []):
        fn = GEOM.get(e["type"])
        if fn is None:
            print("skip unsupported geometry type", e["type"], e.get("name"))
            continue
        fn(e, props if e["type"] in ("table_cluster", "sparkles", "skyline") else set_col)
    build_world(spec)
    build_haze(spec, root)
    cut_frames = sorted(C["frames"][0] for C in spec["cameras"])[1:]
    build_lights(spec, root, cut_frames)
    build_crowd(spec, root)
    build_characters(spec, root)
    cams = build_cameras(spec, root)
    bake_cadence_holds(cams, spec)
    if plates_dir and os.path.exists(os.path.join(plates_dir, "f0001.jpg")):
        attach_plates(cams, plates_dir)
    for m in spec.get("markers", []):
        if m["name"].lower().startswith("beat"):
            bpy.context.scene.timeline_markers.new(m["name"], frame=m["f"])
    if pose_path and os.path.exists(pose_path):
        build_pose_reference(json.load(open(pose_path)), root)
    render_settings(spec, engine)
    bpy.context.scene["source_video"] = "https://www.bilibili.com/video/BV1ZnpG6dE8g"
    bpy.context.scene["hold_residues"] = json.dumps(spec["meta"].get("hold_residues", {}))
    bpy.context.scene["notes"] = "\n".join(spec.get("notes", []))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
    print("saved", out_blend)


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
    build(pos[0], pos[1], opts.get("--pose"), opts.get("--engine", "EEVEE"), opts.get("--plates"))
