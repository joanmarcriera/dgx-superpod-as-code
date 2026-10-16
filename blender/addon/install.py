"""Install (symlink) the dgx_trace add-on into Blender's user add-ons folder and enable it.

Usage:  blender --python blender/addon/install.py          (GUI or -b)
A symlink keeps the add-on in the repo, so edits are live after "Reload Scripts".
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "dgx_trace")
dst_dir = bpy.utils.user_resource("SCRIPTS", path="addons", create=True)
dst = os.path.join(dst_dir, "dgx_trace")
if os.path.islink(dst) or os.path.exists(dst):
    if os.path.islink(dst):
        os.unlink(dst)
    else:
        print(f"refusing to replace a real directory at {dst}")
        sys.exit(1)
os.symlink(SRC, dst)
bpy.ops.preferences.addon_enable(module="dgx_trace")
bpy.ops.wm.save_userpref()
print(f"dgx_trace linked at {dst} and enabled")
