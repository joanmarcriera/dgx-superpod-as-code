"""superpod — Blender build helpers for the DGX H200 SuperPOD render.

Modules:
  layout  pure Python (no bpy): rack/device placement, port positions, cable routing,
          intersection checks. Unit-tested under the repo's normal pytest run.
  blutil  bpy helpers: materials, node groups, a batched mesh builder.
  assets  one detailed asset collection per device type (instanced into the hall).
  hall    racks, overhead infrastructure, room, lights and all cables.

Entry points live one level up: blender/build_scene.py and blender/render.py.
"""
