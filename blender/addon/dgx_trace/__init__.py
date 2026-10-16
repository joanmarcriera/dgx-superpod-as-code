"""DGX Trace — Blender add-on: select a switch, server, tray, door, CDU or rack in a hall
built by blender/build_scene.py and see every cable it owns, where each goes, its power cords
and its coolant path to the CDU and the plant.

Install:  Edit > Preferences > Add-ons > Install… > pick this folder zipped, or
          blender --python blender/addon/install.py   (symlinks it into the user add-ons dir)
Needs:    a .blend written by build_scene.py — every object carries dgx_* props and the text
          datablock `dgx_links.json` holds the links table, the cooling graph, the rack frames
          and the device library, so the file is self-contained.

Panel (3D viewport > N > DGX):
  * active-object card: name, kind, rack, role, peak kW, loop
  * Auto-trace: re-run on every selection change (msgbus on LayerObjects.active)
  * Mode: Highlight — traced objects are selected (outline in every shading mode) and
          everything else is dimmed through its object colour (Solid: Object colour mode is
          switched on; Material Preview keeps the outline only — see README "Tracing")
          Isolate — everything else is hidden in the viewport
  * Filters per fabric: compute IB, storage IB, in-band, OOB, NVLink, power, coolant supply /
    return; Depth: direct only, or follow bundles to their far-end racks and devices, and
    hoses -> branch -> header -> CDU -> FWS mains -> plant
  * Build per-port cables: individual curves from the active device's ports to its exact far
    ends (via the row trays), in a `Trace` collection, with far-end labels; Clear restores all.

The tracing rules are pure Python in trace_core.py (unit-tested by uv run pytest) so the
operator here only applies the result to the viewport.
"""
bl_info = {
    "name": "DGX Trace",
    "author": "dgx-superpod-netbox",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > DGX",
    "description": "Trace cables, power cords and coolant paths of the DGX SuperPOD hall",
    "category": "3D View",
}

import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
BLENDER_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))     # repo blender/ (for superpod.layout)
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

from . import trace_core as T  # noqa: E402

_MSGBUS_OWNER = object()
_CACHE = {"key": None, "index": None}
DIM = (0.22, 0.23, 0.25, 1.0)
KIND_COLOUR = {"rack": "#9A9DA0", "device": "#FFFFFF", "unit": "#2CA02C", "cdu": "#17BECF", "crah": "#9EDAE5",
               "plant": "#1F77B4", "leak": "#F59E0B"}


def trace_colour(idx, p):
    """Object colour for a traced object: cables / cords / pipes by fabric (the design's tie
    colours, coolant supply/return), kit by kind."""
    k = p.get("dgx_kind")
    if k in ("bundle", "cable", "power", "pipe", "hose", "trace"):
        f = p.get("dgx_fabric", "")
        if f.startswith("coolant-"):
            return T.hex_rgb(idx.data.get("cooling", {}).get("colours", {}).get(f.split("-")[1], "#888888"))
        if f == "power":
            return T.hex_rgb({"A": "#C62828", "B": "#1565C0", "C": "#2E7D32"}.get(p.get("dgx_feed", ""), "#C62828"))
        return T.hex_rgb(idx.colour_for(f))
    return T.hex_rgb(KIND_COLOUR.get(k, "#FFFFFF"))


# ------------------------------------------------------------------ data access ---------------
def index():
    """Cached trace index built from the dgx_links.json datablock (rebuilt when it changes)."""
    txt = bpy.data.texts.get("dgx_links.json")
    if txt is None:
        return None
    key = (txt.name, len(txt.as_string()))
    if _CACHE["key"] != key:
        _CACHE["index"] = T.Index(json.loads(txt.as_string()))
        _CACHE["key"] = key
    return _CACHE["index"]


def objects_by_name():
    out = {}
    for ob in bpy.data.objects:
        if "dgx_kind" in ob.keys():
            out[ob.name.split(".")[0]] = ob
    return out


def props_of(ob):
    return {k: ob[k] for k in ob.keys() if k.startswith("dgx_")}


# ------------------------------------------------------------------ settings --------------------
class DGXTraceSettings(bpy.types.PropertyGroup):
    auto: bpy.props.BoolProperty(name="Auto-trace", default=True,
                                 description="Trace whenever the active object changes")
    mode: bpy.props.EnumProperty(name="Mode", items=[("HIGHLIGHT", "Highlight", "Select + dim the rest"),
                                                     ("ISOLATE", "Isolate", "Hide everything else")],
                                 default="HIGHLIGHT")
    depth: bpy.props.EnumProperty(name="Depth", items=[("DIRECT", "Direct only", "The object's own cables / hoses"),
                                                       ("FOLLOW", "Follow", "Far ends, CDU, plant")],
                                  default="FOLLOW")
    f_compute: bpy.props.BoolProperty(name="Compute IB", default=True)
    f_storage: bpy.props.BoolProperty(name="Storage IB", default=True)
    f_inband: bpy.props.BoolProperty(name="In-band", default=True)
    f_oob: bpy.props.BoolProperty(name="OOB", default=True)
    f_nvlink: bpy.props.BoolProperty(name="NVLink", default=True)
    f_power: bpy.props.BoolProperty(name="Power", default=True)
    f_supply: bpy.props.BoolProperty(name="Coolant supply", default=True)
    f_return: bpy.props.BoolProperty(name="Coolant return", default=True)
    last: bpy.props.StringProperty(name="Last trace", default="")      # JSON list of traced object names
    subject: bpy.props.StringProperty(name="Subject", default="")

    def fabrics(self):
        on = {"compute": self.f_compute, "storage": self.f_storage, "inband": self.f_inband,
              "oob": self.f_oob, "nvlink": self.f_nvlink, "power": self.f_power,
              "coolant-supply": self.f_supply, "coolant-return": self.f_return,
              "storage-eth": self.f_storage, "mgmt": self.f_oob}
        return {k for k, v in on.items() if v}


# ------------------------------------------------------------------ viewport state --------------
def restore_all(context):
    """Undo any highlight/isolate: colours, visibility, selection, Trace collection."""
    for ob in bpy.data.objects:
        if "dgx_kind" in ob.keys():
            ob.color = (1.0, 1.0, 1.0, 1.0)
            ob.display_type = "TEXTURED"
            ob.hide_set(False)
            ob.select_set(False)
    tc = bpy.data.collections.get("Trace")
    if tc:
        for ob in list(tc.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
    for area in context.screen.areas if context.screen else []:
        if area.type == "VIEW_3D":
            for sp in area.spaces:
                if sp.type == "VIEW_3D" and sp.shading.color_type == "OBJECT":
                    sp.shading.color_type = "MATERIAL"


def apply(context, names, mode):
    objs = objects_by_name()
    idx = index()
    keep = set(names)
    for base, ob in objs.items():
        if ob.get("dgx_kind") == "decor":
            if mode == "ISOLATE":
                ob.hide_set(True)
            else:
                ob.display_type = "WIRE"
            continue
        hit = base in keep
        ob.color = (*trace_colour(idx, props_of(ob)), 1.0) if hit else DIM
        ob.display_type = "TEXTURED" if hit else "WIRE"       # dimmed objects become wireframes (every shading mode)
        if mode == "ISOLATE":
            ob.hide_set(not hit)
        else:
            ob.hide_set(False)
        ob.select_set(hit)
    if mode == "HIGHLIGHT" and context.screen:
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D" and sp.shading.type == "SOLID":
                        sp.shading.color_type = "OBJECT"


def run_trace(context, subject_ob):
    """Compute and apply the trace for `subject_ob`; returns the traced base names."""
    st = context.scene.dgx_trace
    idx = index()
    if idx is None or subject_ob is None or "dgx_kind" not in subject_ob.keys():
        return []
    objs = objects_by_name()
    all_props = {base: props_of(ob) for base, ob in objs.items()}
    names = T.trace(idx, subject_ob.name.split(".")[0], props_of(subject_ob), all_props,
                    st.fabrics(), follow=(st.depth == "FOLLOW"))
    apply(context, names, st.mode)
    st.last = json.dumps(sorted(names))
    st.subject = subject_ob.name.split(".")[0]
    context.view_layer.objects.active = subject_ob
    subject_ob.select_set(True)
    return names


# ------------------------------------------------------------------ operators -------------------
class DGX_OT_trace(bpy.types.Operator):
    bl_idname = "dgx.trace"
    bl_label = "Trace active object"
    bl_description = "Show the active object's cables, cords and coolant path"

    def execute(self, context):
        names = run_trace(context, context.view_layer.objects.active)
        self.report({"INFO"}, f"traced {len(names)} objects")
        return {"FINISHED"}


class DGX_OT_clear(bpy.types.Operator):
    bl_idname = "dgx.clear"
    bl_label = "Clear"
    bl_description = "Restore every object (colours, visibility, selection) and drop the Trace collection"

    def execute(self, context):
        restore_all(context)
        context.scene.dgx_trace.last = ""
        context.scene.dgx_trace.subject = ""
        return {"FINISHED"}


class DGX_OT_build_ports(bpy.types.Operator):
    bl_idname = "dgx.build_ports"
    bl_label = "Build per-port cables"
    bl_description = "Create one curve per link of the active device, from its port to the far-end port"

    def execute(self, context):
        from superpod import layout as L
        ob = context.view_layer.objects.active
        idx = index()
        if ob is None or idx is None or "dgx_kind" not in ob.keys():
            self.report({"WARNING"}, "select a device first")
            return {"CANCELLED"}
        dev = ob.name.split(".")[0]
        st = context.scene.dgx_trace
        tc = bpy.data.collections.get("Trace") or bpy.data.collections.new("Trace")
        if tc.name not in context.scene.collection.children:
            context.scene.collection.children.link(tc)
        for o in list(tc.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        n = 0
        for row in idx.links_of(dev):
            if row["fabric"] not in st.fabrics():
                continue
            pts = T.per_port_path(idx, row, L)
            if pts is None:
                continue
            far = row["b"] if row["a"] == dev else row["a"]
            colour = idx.colour_for(row["fabric"], row.get("rail"))
            cu = bpy.data.curves.new(f"trace_{row['label']}", "CURVE")
            cu.dimensions, cu.bevel_mode, cu.bevel_depth, cu.bevel_resolution = "3D", "ROUND", 0.0022, 2
            sp = cu.splines.new("POLY")
            sp.points.add(len(pts) - 1)
            flat = []
            for p in pts:
                flat.extend((p[0], p[1], p[2], 1.0))
            sp.points.foreach_set("co", flat)
            mat = bpy.data.materials.get(f"trace_{colour}") or bpy.data.materials.new(f"trace_{colour}")
            mat.diffuse_color = (*T.hex_rgb(colour), 1.0)
            cu.materials.append(mat)
            o = bpy.data.objects.new(f"trace_{row['label']}", cu)
            o["dgx_kind"], o["dgx_a"], o["dgx_b"], o["dgx_fabric"] = "trace", row["a"], row["b"], row["fabric"]
            o["dgx_label"] = row["label"]
            tc.objects.link(o)
            # far-end label
            fcu = bpy.data.curves.new(f"lbl_{row['label']}", "FONT")
            fcu.body, fcu.size, fcu.align_x = f"{far}:{row['b_port'] if row['a'] == dev else row['a_port']}", 0.03, "CENTER"
            lo = bpy.data.objects.new(f"lbl_{row['label']}", fcu)
            lo.location = (pts[-1][0], pts[-1][1], pts[-1][2] + 0.04)
            lo["dgx_kind"] = "trace"
            tc.objects.link(lo)
            n += 1
        self.report({"INFO"}, f"built {n} per-port cables for {dev}")
        return {"FINISHED"}


# ------------------------------------------------------------------ panel -----------------------
class DGX_PT_panel(bpy.types.Panel):
    bl_label = "DGX Trace"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DGX"

    def draw(self, context):
        st = context.scene.dgx_trace
        lay = self.layout
        ob = context.view_layer.objects.active
        box = lay.box()
        if ob is not None and "dgx_kind" in ob.keys():
            p = props_of(ob)
            box.label(text=ob.name.split(".")[0], icon="OBJECT_DATA")
            box.label(text=f"{p.get('dgx_kind', '')}  {p.get('dgx_role', '') or p.get('dgx_type', '')}")
            if p.get("dgx_rack"):
                box.label(text=f"rack {p['dgx_rack']}")
            if p.get("dgx_kw"):
                box.label(text=f"peak {p['dgx_kw']:.1f} kW")
            if p.get("dgx_loop"):
                box.label(text=f"loop {p['dgx_loop']}")
            if p.get("dgx_a") or p.get("dgx_b"):
                box.label(text=f"{p.get('dgx_a', '')} ↔ {p.get('dgx_b', '')}  {p.get('dgx_fabric', '')}")
            if p.get("dgx_labels"):
                box.label(text=f"{len(p['dgx_labels'])} cables")
        else:
            box.label(text="select a rack, device, cable or unit", icon="INFO")
        lay.prop(st, "auto")
        row = lay.row(align=True)
        row.prop(st, "mode", expand=True)
        row = lay.row(align=True)
        row.prop(st, "depth", expand=True)
        col = lay.column(align=True)
        col.label(text="Fabrics")
        for a, b in (("f_compute", "f_storage"), ("f_inband", "f_oob"), ("f_nvlink", "f_power"), ("f_supply", "f_return")):
            r = col.row(align=True)
            r.prop(st, a, toggle=True)
            r.prop(st, b, toggle=True)
        lay.operator("dgx.trace", icon="HIDE_OFF")
        lay.operator("dgx.build_ports", icon="CURVE_DATA")
        lay.operator("dgx.clear", icon="X")
        if st.subject:
            n = len(json.loads(st.last)) if st.last else 0
            lay.label(text=f"last: {st.subject} → {n} objects")


# ------------------------------------------------------------------ msgbus ----------------------
def _on_active_changed():
    try:
        ctx = bpy.context
        if not hasattr(ctx.scene, "dgx_trace") or not ctx.scene.dgx_trace.auto:
            return
        ob = ctx.view_layer.objects.active
        if ob is None or "dgx_kind" not in ob.keys():
            return
        if ob.get("dgx_kind") in ("decor", "trace"):
            return
        run_trace(ctx, ob)
    except Exception as exc:   # never let a trace break the viewport
        print("dgx_trace:", exc)


def _subscribe():
    bpy.msgbus.clear_by_owner(_MSGBUS_OWNER)
    bpy.msgbus.subscribe_rna(key=(bpy.types.LayerObjects, "active"), owner=_MSGBUS_OWNER, args=(),
                             notify=_on_active_changed)


@bpy.app.handlers.persistent
def _on_load(_dummy):
    _subscribe()


CLASSES = (DGXTraceSettings, DGX_OT_trace, DGX_OT_clear, DGX_OT_build_ports, DGX_PT_panel)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.dgx_trace = bpy.props.PointerProperty(type=DGXTraceSettings)
    _subscribe()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    bpy.msgbus.clear_by_owner(_MSGBUS_OWNER)
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    del bpy.types.Scene.dgx_trace
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
