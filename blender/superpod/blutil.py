"""bpy helpers: materials (incl. procedural hex perforation and metal foam), a batched mesh
builder, collection/instance helpers and curve batches for cables.

Performance note: the hall has ~40k parts. Instead of one object per screw, parts are
accumulated in a MeshBuilder and written as ONE mesh per (asset, bevel class) with material
slots; cables go into a few curve objects with many splines.
"""
from __future__ import annotations

import math
import os

import bpy

from . import layout

# ---------------------------------------------------------------- materials -----------------
_MATS = {}


def _lin(hexcol):
    return (*layout.srgb_to_linear(layout.hex_rgb(hexcol)), 1.0)


def _principled(nt):
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return nt.nodes.new("ShaderNodeBsdfPrincipled")


def _new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True           # deprecated (always on) in 5.x; harmless where it exists
    except Exception:                # noqa: BLE001
        pass
    return m


def plain(name, colour, metallic=0.0, rough=0.5, emission=None, strength=0.0, alpha=1.0,
          coat=0.0, spec=0.5, transmission=0.0):
    """Principled material with the given look; cached by name."""
    if name in _MATS:
        return _MATS[name]
    m = _new_material(name)
    p = _principled(m.node_tree)
    p.inputs["Base Color"].default_value = _lin(colour)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Transmission Weight"].default_value = transmission
    if alpha < 1.0:
        p.inputs["Alpha"].default_value = alpha
    if emission:
        p.inputs["Emission Color"].default_value = _lin(emission)
        p.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = _lin(colour)   # solid-view colour
    _MATS[name] = m
    return m


def _obj_xz(nt, plane="XZ"):
    """Object-space coordinates projected onto a face plane, as a vector (u, v, 0)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    a, b = {"XZ": ("X", "Z"), "XY": ("X", "Y"), "YZ": ("Y", "Z")}[plane]
    nt.links.new(sep.outputs[a], comb.inputs["X"])
    nt.links.new(sep.outputs[b], comb.inputs["Y"])
    return comb.outputs[0]


def _vmath(nt, op, a, b=None, value=None):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    nt.links.new(a, n.inputs[0])
    if b is not None:
        if isinstance(b, (tuple, list)):
            n.inputs[1].default_value = b
        else:
            nt.links.new(b, n.inputs[1])
    return n.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs["Vector"]


def _math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _smooth_mask(nt, d, r, soft):
    """1 where d < r (anti-aliased), else 0."""
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    nt.links.new(d, mr.inputs["Value"])
    mr.inputs["From Min"].default_value = r - soft
    mr.inputs["From Max"].default_value = r + soft
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    return mr.outputs["Result"]


def hex_mask(nt, pitch, radius, plane="XZ"):
    """Round holes on a hex lattice (pitch in metres, radius as a fraction of pitch).
    Built from vector maths: nearest point of two offset rectangular lattices."""
    p = _obj_xz(nt, plane)
    p = _vmath(nt, "MULTIPLY", p, (1 / pitch, 1 / pitch, 0))
    s3 = math.sqrt(3)
    ds = []
    for off in ((0.0, 0.0, 0.0), (0.5, s3 / 2, 0.0)):
        q = _vmath(nt, "SUBTRACT", p, off)
        q = _vmath(nt, "DIVIDE", q, (1.0, s3, 1.0))
        q = _vmath(nt, "FRACTION", q)
        q = _vmath(nt, "SUBTRACT", q, (0.5, 0.5, 0.0))
        q = _vmath(nt, "MULTIPLY", q, (1.0, s3, 0.0))
        ds.append(_vmath(nt, "LENGTH", q))
    d = _math(nt, "MINIMUM", ds[0], ds[1])
    return _smooth_mask(nt, d, radius, 0.06)


def square_mask(nt, pitch, half, plane="XZ", stretch=(1.0, 1.0)):
    p = _obj_xz(nt, plane)
    p = _vmath(nt, "MULTIPLY", p, (1 / (pitch * stretch[0]), 1 / (pitch * stretch[1]), 0))
    q = _vmath(nt, "FRACTION", p)
    q = _vmath(nt, "SUBTRACT", q, (0.5, 0.5, 0.0))
    q = _vmath(nt, "ABSOLUTE", q)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(q, sep.inputs[0])
    d = _math(nt, "MAXIMUM", sep.outputs["X"], sep.outputs["Y"])
    return _smooth_mask(nt, d, half, 0.05)


def perforated(name, metal, hole="#050505", pitch=0.006, radius=0.36, metallic=0.85, rough=0.35,
               plane="XZ", square=False, hole_rough=0.9):
    """Sheet with holes: hole areas become near-black and rough (reads as depth at distance),
    with a bump at the hole rims for close-ups."""
    if name in _MATS:
        return _MATS[name]
    m = _new_material(name)
    nt = m.node_tree
    p = _principled(nt)
    mask = square_mask(nt, pitch, radius, plane) if square else hex_mask(nt, pitch, radius, plane)
    col = nt.nodes.new("ShaderNodeMix")
    col.data_type = "RGBA"
    nt.links.new(mask, col.inputs["Factor"])
    col.inputs["A"].default_value = _lin(metal)
    col.inputs["B"].default_value = _lin(hole)
    nt.links.new(col.outputs["Result"], p.inputs["Base Color"])
    nt.links.new(_math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, mask), metallic), p.inputs["Metallic"])
    rgh = _math(nt, "ADD", _math(nt, "MULTIPLY", mask, hole_rough - rough), rough)
    nt.links.new(rgh, p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0008
    nt.links.new(_math(nt, "SUBTRACT", 1.0, mask), bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    m.diffuse_color = _lin(metal)
    _MATS[name] = m
    return m


def metal_foam(name="dgx_foam"):
    """DGX bezel: reticulated metal foam, fully procedural. Voronoi distance-to-edge gives the
    strut network; a second, finer Voronoi breaks the regularity. Drives colour, metalness,
    roughness and TRUE displacement (the bezel mesh is finely subdivided)."""
    if name in _MATS:
        return _MATS[name]
    m = _new_material(name)
    nt = m.node_tree
    p = _principled(nt)
    tc = nt.nodes.new("ShaderNodeTexCoord")

    def vor(scale, seed_off):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (seed_off, seed_off * 0.7, 0.0)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        v = nt.nodes.new("ShaderNodeTexVoronoi")
        v.feature = "DISTANCE_TO_EDGE"
        v.inputs["Scale"].default_value = scale
        v.inputs["Randomness"].default_value = 1.0
        nt.links.new(mp.outputs["Vector"], v.inputs["Vector"])
        return v.outputs["Distance"]

    coarse, fine = vor(125.0, 0.0), vor(290.0, 3.1)          # ~8 mm cells, as in the NVIDIA figure
    # struts: thin band near cell edges; the fine cells add secondary struts inside pores
    s1 = _smooth_mask(nt, coarse, 0.055, 0.035)
    s2 = _smooth_mask(nt, fine, 0.04, 0.03)
    strut = _math(nt, "MAXIMUM", s1, _math(nt, "MULTIPLY", s2, 0.4), clamp=True)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 60.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeMix")
    ramp.data_type = "RGBA"
    nt.links.new(strut, ramp.inputs["Factor"])
    ramp.inputs["A"].default_value = _lin("#120D07")        # pore depths
    ramp.inputs["B"].default_value = _lin("#C4B08A")        # lit struts (#CDBFA5 highlights)
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 0.35
    nt.links.new(ramp.outputs["Result"], tint.inputs["A"])
    nt.links.new(noise.outputs["Fac"], tint.inputs["B"])
    nt.links.new(tint.outputs["Result"], p.inputs["Base Color"])
    nt.links.new(_math(nt, "MULTIPLY", strut, 0.9), p.inputs["Metallic"])
    nt.links.new(_math(nt, "ADD", _math(nt, "MULTIPLY", strut, -0.45), 0.85), p.inputs["Roughness"])
    height = _math(nt, "ADD", strut, _math(nt, "MULTIPLY", noise.outputs["Fac"], 0.25))
    disp = nt.nodes.new("ShaderNodeDisplacement")
    disp.inputs["Midlevel"].default_value = 0.6
    disp.inputs["Scale"].default_value = 0.0045
    nt.links.new(height, disp.inputs["Height"])
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    nt.links.new(disp.outputs["Displacement"], out.inputs["Displacement"])
    m.displacement_method = "BOTH"
    m.diffuse_color = _lin("#6B5636")
    _MATS[name] = m
    return m


def image_floor(name, texdir, tint="#8C8F94", tile=3.0):
    """Painted concrete from the Poly Haven set (diff/nor_gl/arm), tiled in object space every
    `tile` metres. Falls back to a procedural concrete when the media pack is missing."""
    if name in _MATS:
        return _MATS[name]
    m = _new_material(name)
    nt = m.node_tree
    p = _principled(nt)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1 / tile)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    files = {k: None for k in ("diff", "nor_gl", "arm")}
    if texdir and os.path.isdir(texdir):
        for f in os.listdir(texdir):
            for k in files:
                if f"_{k}_" in f:
                    files[k] = os.path.join(texdir, f)
    tint_mix = nt.nodes.new("ShaderNodeMix")
    tint_mix.data_type = "RGBA"
    tint_mix.blend_type = "MIX"                      # scan adds variation; the paint colour dominates
    tint_mix.inputs["Factor"].default_value = 0.86
    tint_mix.inputs["B"].default_value = _lin(tint)
    if all(files.values()):
        def img(path, colour):
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = bpy.data.images.load(path, check_existing=True)
            n.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
            nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
            return n
        d, nor, arm = img(files["diff"], True), img(files["nor_gl"], False), img(files["arm"], False)
        nt.links.new(d.outputs["Color"], tint_mix.inputs["A"])
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.3
        nt.links.new(nor.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(arm.outputs["Color"], sep.inputs["Color"])
        # sealed/painted hall floor: a touch glossier than the raw scan
        nt.links.new(_math(nt, "ADD", _math(nt, "MULTIPLY", sep.outputs["Green"], 0.25), 0.32), p.inputs["Roughness"])
    else:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 8.0
        nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Color"], tint_mix.inputs["A"])
        p.inputs["Roughness"].default_value = 0.35
    nt.links.new(tint_mix.outputs["Result"], p.inputs["Base Color"])
    _MATS[name] = m
    return m


def material(name):
    """Named material from the shared palette (see PALETTE)."""
    if name in _MATS:
        return _MATS[name]
    if name.startswith("hex:"):                      # ad-hoc cable/tie colours, e.g. hex:#00A7B5
        return plain(name, name[4:], rough=0.45, spec=0.5)
    spec = PALETTE[name]
    return spec[0](name, *spec[1:]) if callable(spec[0]) else plain(name, *spec)


# name -> args for plain(name, colour, metallic, rough, emission, strength, alpha, coat)
PALETTE = {
    "rack_black": ("#1B1B1D", 0.2, 0.55),
    "blank": ("#141416", 0.1, 0.6),
    "rail_zinc": ("#9A9DA0", 0.9, 0.35),
    "dgx_champagne": ("#B5A58A", 0.85, 0.32),
    "dgx_pad": ("#BCAE93", 0.75, 0.42),
    "dgx_chassis": ("#7C7F84", 0.85, 0.42),
    "dgx_dark": ("#1C1C1E", 0.5, 0.5),
    "screw": ("#C9CBCE", 1.0, 0.25),
    "perf_silver": (perforated, "#D4D6D8", "#0B0B0C", 0.0062, 0.40, 0.85, 0.33),
    "perf_silver_fine": (perforated, "#C8CACD", "#0B0B0C", 0.0035, 0.36, 0.85, 0.35),
    "perf_black": (perforated, "#17191C", "#030303", 0.0034, 0.38, 0.4, 0.45),
    "perf_black_honey": (perforated, "#202226", "#030303", 0.005, 0.42, 0.5, 0.4),
    "amber_mesh": (perforated, "#C98A1E", "#1A0E02", 0.0028, 0.34, 0.8, 0.35),
    "cage": ("#A7ABAF", 0.9, 0.3),
    "cage_dark": ("#3A3F44", 0.8, 0.35),
    "osfp_body": ("#B9BCC0", 0.9, 0.28),
    "osfp_fin": ("#6D7278", 0.9, 0.35),
    "mpo_green": ("#3DAE2B", 0.0, 0.4),
    "plug_black": ("#0E0E0F", 0.0, 0.55),
    "plug_grey": ("#B9BDC2", 0.0, 0.35),
    "tab_yg": ("#B5D335", 0.0, 0.45),
    "switch_black": ("#1A1A1A", 0.3, 0.45),
    "switch_grey": ("#2B2F33", 0.35, 0.45),
    "steel": ("#8C8F93", 0.9, 0.35),
    "ddn_gloss": ("#0A0A0A", 0.0, 0.22, None, 0.0, 1.0, 0.45, 0.35),
    "vast_fan": ("#555A5F", 0.4, 0.45),
    "vast_bay": ("#0B0B0B", 0.1, 0.55),
    "vast_ear": ("#9A9A9A", 0.8, 0.4),
    "salmon": ("#E8A8A0", 0.0, 0.5),
    "blue_latch": ("#2B44C8", 0.0, 0.45),
    "tan_label": ("#C8A400", 0.0, 0.5),
    "pdu_black": ("#141414", 0.2, 0.5),
    "lcd": ("#0A1C2E", 0.0, 0.15, "#2F7BFF", 1.5),
    "led_green": ("#1B5E20", 0.0, 0.3, "#39FF4A", 22.0),
    "led_blue": ("#0D2A6B", 0.0, 0.3, "#3A7BFF", 18.0),
    "led_amber": ("#6B4A0D", 0.0, 0.3, "#FFB020", 18.0),
    "led_amber_off": ("#3A2A0A", 0.0, 0.3),
    "led_yellow": ("#6B660D", 0.0, 0.3, "#FFE600", 14.0),
    "led_off": ("#1A1D20", 0.0, 0.2),
    "floor_paint": (image_floor, None),
    "dgx_foam": (metal_foam,),
    "wall": ("#D3D6D9", 0.0, 0.8),
    "ceiling": ("#8E9296", 0.0, 0.85),
    "skirting": ("#3A3C3F", 0.0, 0.6),
    "acrylic": ("#DFE6EA", 0.0, 0.06, None, 0.0, 0.3),
    "busway": ("#B8BCC0", 0.95, 0.32),
    "raceway": ("#F2C200", 0.0, 0.4),
    "ladder": ("#1B1B1D", 0.3, 0.5),
    "crah_body": ("#D9DBDD", 0.2, 0.45),
    "crah_fan": ("#1A1B1D", 0.2, 0.5),
    "led_panel": ("#FFFFFF", 0.0, 0.5, "#F2F5FF", 30.0),
    "led_panel_dim": ("#FFFFFF", 0.0, 0.5, "#F2F5FF", 8.0),
    "fixture": ("#C8CACC", 0.9, 0.3),
    "brush": ("#0B0B0B", 0.0, 0.8),
    "rod": ("#7D8084", 0.9, 0.4),
    "logo_white": ("#F4F4F4", 0.0, 0.3),
    "logo_emboss": ("#A89A7F", 0.85, 0.35),
    "cardboard_label": ("#EDEDE8", 0.0, 0.6),
    # mixed pod: GB300 kit (reference/compute-dgx-gb300, colours est) and cooling kit
    "gb_champagne": ("#85765C", 0.7, 0.4),
    "gb_champagne_dark": ("#625443", 0.6, 0.45),
    "gb_silver": ("#D4D6D8", 0.85, 0.4),
    "shelf_black": ("#2E2E2E", 0.3, 0.5),
    "busbar_clip": ("#2A2A2C", 0.4, 0.5),
    "busbar_cover": ("#2A2A2C", 0.3, 0.55),
    "cartridge": ("#C9C9C4", 0.0, 0.7),
    "perf_black_sq": (perforated, "#17191C", "#030303", 0.0036, 0.34, 0.4, 0.45, "XZ", True),
    "perf_black_fine": (perforated, "#1E2024", "#6B5D48", 0.0030, 0.44, 0.3, 0.5),   # door mesh: coil fins show through the holes
    "qd_metal": ("#C9CCD0", 0.9, 0.3),
    "qd_hot": ("#D32F2F", 0.0, 0.45),
    "qd_cold": ("#1E63D6", 0.0, 0.45),
    "led_red": ("#5E0A0A", 0.0, 0.3, "#FF2020", 16.0),
    "led_teal": ("#0A4A4A", 0.0, 0.3, "#20E0D0", 14.0),
    "led_blue_strip": ("#0D2A6B", 0.0, 0.4, "#2A7FFF", 6.0),
    "led_blue_dim": ("#0D2A6B", 0.0, 0.4, "#2A7FFF", 3.0),
    "door_black": ("#151517", 0.2, 0.5),
    "door_badge": ("#C8102E", 0.0, 0.45),
    "stainless": ("#B9BCC0", 0.95, 0.3),
    "coil_fin": ("#9A8A70", 0.8, 0.5),
    "cdu_black": ("#0D0D10", 0.2, 0.45),
    "crah_white": ("#F4F4F0", 0.0, 0.45),
    "crah_panel": ("#E8E8E4", 0.0, 0.5),
    "plant_grey": ("#D6D6D2", 0.1, 0.55),
    "pipe_insul": ("#D9D9D6", 0.0, 0.6),
    "hose_black": ("#111111", 0.0, 0.55),
    "valve_red": ("#C8102E", 0.0, 0.45),
    "drip_tray": ("#B8BCC0", 0.8, 0.4),
    "leak_rope": ("#F59E0B", 0.0, 0.5),
    "concrete_pad": ("#9A9A96", 0.0, 0.85),
    "sleeve": ("#7D8084", 0.9, 0.4),
    "fan_blade": ("#2A2C30", 0.6, 0.45),
    "fan_cowl": ("#1A1A1A", 0.3, 0.5),
    "coil_dark": ("#3A3A3C", 0.7, 0.6),
    "asphalt": ("#55575A", 0.0, 0.9),
}


def tie_material(hexcol):
    return plain(f"tie_{hexcol.lstrip('#')}", hexcol, 0.0, 0.5)


def bundle_material(hexcol, strands=16):
    """Cable-bundle jacket: many parallel strands suggested by a wave bump around the tube
    (curve UV: V runs around the circumference), grooves slightly darker."""
    name = f"bundle_{hexcol.lstrip('#')}"
    if name in _MATS:
        return _MATS[name]
    m = _new_material(name)
    nt = m.node_tree
    p = _principled(nt)
    uv = nt.nodes.new("ShaderNodeUVMap")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction, wave.wave_profile = "BANDS", "Y", "SIN"
    wave.inputs["Scale"].default_value = strands
    wave.inputs["Distortion"].default_value = 1.5
    wave.inputs["Detail"].default_value = 1.0
    nt.links.new(uv.outputs["UV"], wave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    bump.inputs["Distance"].default_value = 0.0015
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = tuple(v * 0.55 for v in _lin(hexcol)[:3]) + (1.0,)
    mix.inputs["B"].default_value = _lin(hexcol)
    nt.links.new(wave.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.45
    m.diffuse_color = _lin(hexcol)
    _MATS[name] = m
    return m


def jacket_material(hexcol):
    dark = sum(layout.hex_rgb(hexcol)) < 0.3          # black DAC/cat6: matt PVC, no coat sheen
    return plain(f"jacket_{hexcol.lstrip('#')}", hexcol, 0.0, 0.6 if dark else 0.42, spec=0.4 if dark else 0.5,
                 coat=0.0 if dark else 0.15)


# ---------------------------------------------------------------- collections ---------------
def collection(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def instance(name, coll_src, loc, yaw, parent, props=None):
    """Collection instance (an empty) of an asset collection."""
    e = bpy.data.objects.new(name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = coll_src
    e.location = loc
    e.rotation_euler = (0.0, 0.0, yaw)
    e.empty_display_size = 0.05
    for k, v in (props or {}).items():
        e[k] = v
    parent.objects.link(e)
    return e


# ---------------------------------------------------------------- mesh builder --------------
def _basis(axis):
    ax = axis
    n = math.sqrt(sum(a * a for a in ax))
    ax = tuple(a / n for a in ax)
    helper = (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = (ax[1] * helper[2] - ax[2] * helper[1], ax[2] * helper[0] - ax[0] * helper[2], ax[0] * helper[1] - ax[1] * helper[0])
    un = math.sqrt(sum(a * a for a in u))
    u = tuple(a / un for a in u)
    v = (ax[1] * u[2] - ax[2] * u[1], ax[2] * u[0] - ax[0] * u[2], ax[0] * u[1] - ax[1] * u[0])
    return ax, u, v


class MeshBuilder:
    """Accumulates primitives (with a material name each) and writes one mesh object.
    All faces are wound outward by construction (verified in tests via Newell normals)."""

    def __init__(self):
        self.verts, self.faces, self.fmat, self.mats = [], [], [], []

    def _m(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _face(self, idx, mi):
        self.faces.append(tuple(idx))
        self.fmat.append(mi)

    def box(self, x0, y0, z0, x1, y1, z1, mat):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        b = len(self.verts)
        for k in (z0, z1):
            for j in (y0, y1):
                for i in (x0, x1):
                    self.verts.append((i, j, k))
        mi = self._m(mat)
        for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
            self._face([b + i for i in f], mi)

    def cyl(self, centre, axis, r, length, mat, seg=12, caps=True):
        ax, u, v = _basis(axis)
        b = len(self.verts)
        for s in (-0.5, 0.5):
            for i in range(seg):
                t = 2 * math.pi * i / seg
                c, sn = math.cos(t) * r, math.sin(t) * r
                self.verts.append(tuple(centre[k] + ax[k] * s * length + u[k] * c + v[k] * sn for k in range(3)))
        mi = self._m(mat)
        for i in range(seg):
            j = (i + 1) % seg
            self._face((b + i, b + j, b + seg + j, b + seg + i), mi)
        if caps:
            self._face([b + seg + i for i in range(seg)], mi)
            self._face([b + i for i in reversed(range(seg))], mi)

    def prism(self, outline, y0, y1, mat):
        """Extrude a CCW-in-(x,z) outline between y0 and y1 (y0 < y1)."""
        n = len(outline)
        area = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
        if area < 0:
            outline = list(reversed(outline))
        b = len(self.verts)
        for y in (y0, y1):
            for x, z in outline:
                self.verts.append((x, y, z))
        mi = self._m(mat)
        # CCW in (x,z) seen from +Y is clockwise; +Y face therefore takes the reversed order
        self._face([b + n + i for i in reversed(range(n))], mi)
        self._face([b + i for i in range(n)], mi)
        for i in range(n):
            j = (i + 1) % n
            self._face((b + i, b + n + i, b + n + j, b + j), mi)

    def prism_xy(self, outline, z0, z1, mat):
        """Extrude an (x, y) outline between z0 and z1 (z0 < z1), outward-wound."""
        n = len(outline)
        area = sum(outline[i][0] * outline[(i + 1) % n][1] - outline[(i + 1) % n][0] * outline[i][1] for i in range(n))
        if area < 0:
            outline = list(reversed(outline))
        b = len(self.verts)
        for z in (z0, z1):
            for x, y in outline:
                self.verts.append((x, y, z))
        mi = self._m(mat)
        self._face([b + i for i in reversed(range(n))], mi)          # bottom (-Z)
        self._face([b + n + i for i in range(n)], mi)                # top (+Z)
        for i in range(n):
            j = (i + 1) % n
            self._face((b + i, b + j, b + n + j, b + n + i), mi)

    def rrect(self, x0, z0, x1, z1, y0, y1, rad, mat, seg=5):
        rad = min(rad, abs(x1 - x0) / 2 - 1e-5, abs(z1 - z0) / 2 - 1e-5)
        x0, x1 = min(x0, x1), max(x0, x1)
        z0, z1 = min(z0, z1), max(z0, z1)
        pts = []
        for cx, cz, a0 in ((x1 - rad, z0 + rad, -90), (x1 - rad, z1 - rad, 0), (x0 + rad, z1 - rad, 90), (x0 + rad, z0 + rad, 180)):
            for k in range(seg + 1):
                a = math.radians(a0 + 90 * k / seg)
                pts.append((cx + rad * math.cos(a), cz + rad * math.sin(a)))
        self.prism(pts, min(y0, y1), max(y0, y1), mat)

    def ellipse(self, cx, cz, a, b, y0, y1, mat, seg=32, tilt=0.0):
        """Elliptic prism along Y; `tilt` (degrees) leans the long axis up to the right as
        seen from the FRONT (+Y viewer, whose right is -X)."""
        t0 = math.radians(tilt)
        ux, uz = -math.cos(t0), math.sin(t0)
        vx, vz = math.sin(t0), math.cos(t0)
        pts = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            ca, sb = a * math.cos(t), b * math.sin(t)
            pts.append((cx + ca * ux + sb * vx, cz + ca * uz + sb * vz))
        self.prism(pts, min(y0, y1), max(y0, y1), mat)

    def grid(self, x0, z0, x1, z1, y, nx, nz, mat):
        """Subdivided plane facing +Y (for true displacement)."""
        b = len(self.verts)
        for k in range(nz + 1):
            z = z0 + (z1 - z0) * k / nz
            for i in range(nx + 1):
                self.verts.append((x0 + (x1 - x0) * i / nx, y, z))
        mi = self._m(mat)
        w = nx + 1
        for k in range(nz):
            for i in range(nx):
                a = b + k * w + i
                # normal +Y: (x+ then z+) gives -Y, so go z+ first
                self._face((a, a + w, a + w + 1, a + 1), mi)

    def ring(self, centre, axis, r, width, mat, seg=12):
        self.cyl(centre, axis, r, width, mat, seg=seg, caps=False)

    def extend(self, other):
        off = len(self.verts)
        self.verts.extend(other.verts)
        for f, mi in zip(other.faces, other.fmat):
            self._face([i + off for i in f], self._m(other.mats[mi]))

    def build(self, name, coll, bevel=0.0, segments=2, smooth=False):
        if not self.faces:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        me.polygons.foreach_set("material_index", self.fmat)
        for mname in self.mats:
            me.materials.append(material(mname) if isinstance(mname, str) else mname)
        if smooth:
            me.shade_smooth()
        me.update()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        if bevel > 0:
            mod = ob.modifiers.new("bevel", "BEVEL")
            mod.width = bevel
            mod.segments = segments
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(40)
            mod.use_clamp_overlap = True
        return ob


# ---------------------------------------------------------------- curves --------------------
def curve(name, points, radius, mat, coll, props=None, resolution=2):
    """One swept tube as its own object (so it can carry tracing props and be highlighted)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = 1.0
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    cu.twist_mode = "MINIMUM"
    cu.materials.append(material(mat) if isinstance(mat, str) else mat)
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    flat = []
    for p in points:
        flat.extend((p[0], p[1], p[2], 1.0))
    sp.points.foreach_set("co", flat)
    sp.points.foreach_set("radius", [radius] * len(points))
    ob = bpy.data.objects.new(name, cu)
    for k, v in (props or {}).items():
        ob[k] = v
    coll.objects.link(ob)
    return ob


class CurveBatch:
    """Many poly splines in one curve object; per-spline radius and material."""

    def __init__(self, name, resolution=2):
        self.name, self.resolution, self.splines, self.mats = name, resolution, [], []

    def add(self, points, radius, mat):
        if len(points) < 2:
            return
        if mat not in self.mats:
            self.mats.append(mat)
        self.splines.append((points, radius, self.mats.index(mat)))

    def build(self, coll):
        if not self.splines:
            return None
        cu = bpy.data.curves.new(self.name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_mode = "ROUND"
        cu.bevel_depth = 1.0
        cu.bevel_resolution = self.resolution
        cu.use_fill_caps = True
        cu.twist_mode = "MINIMUM"
        # slots first: material_index is clamped to the existing slot count when assigned
        for m in self.mats:
            cu.materials.append(material(m) if isinstance(m, str) else m)
        for pts, r, mi in self.splines:
            sp = cu.splines.new("POLY")
            sp.points.add(len(pts) - 1)
            flat = []
            for p in pts:
                flat.extend((p[0], p[1], p[2], 1.0))
            sp.points.foreach_set("co", flat)
            sp.points.foreach_set("radius", [r] * len(pts))
            sp.material_index = mi
        ob = bpy.data.objects.new(self.name, cu)
        coll.objects.link(ob)
        return ob
