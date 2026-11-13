"""Render a still of the picnic set.

    blender -b assets/set.blend --python scripts/render_set.py -- \
        --cam CAM_main --out renders/set/style_frame.png [--pct 100] [--samples 64] [--proxy]

--proxy adds a grey stand-in for a kneeling toddler at HANI_spot (layout check only;
it is NOT saved into set.blend).
"""
import bpy
import sys
import os
import argparse

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--cam", default="CAM_main")
ap.add_argument("--out", required=True)
ap.add_argument("--pct", type=int, default=100)
ap.add_argument("--samples", type=int, default=0)
ap.add_argument("--proxy", action="store_true")
ap.add_argument("--nocomp", action="store_true")
a = ap.parse_args(argv)

scene = bpy.context.scene
scene.camera = bpy.data.objects[a.cam]
scene.render.resolution_percentage = a.pct
if a.samples:
    scene.eevee.taa_render_samples = a.samples
if a.nocomp:
    scene.use_nodes = False

if a.proxy:
    from mathutils import Vector
    spot = bpy.data.objects["HANI_spot"].location
    mat = bpy.data.materials.new("M_proxy")
    mat.diffuse_color = (0.75, 0.6, 0.55, 1)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.62, 0.52, 1)

    def blob(name, loc, scale):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=spot + Vector(loc))
        o = bpy.context.active_object
        o.name = name
        o.scale = scale
        o.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        return o
    blob("px_skirt", (0, 0.0, 0.06), (0.21, 0.19, 0.07))      # tulle skirt pooled while kneeling
    blob("px_torso", (0, 0.01, 0.20), (0.105, 0.085, 0.12))
    blob("px_head", (0, 0.0, 0.44), (0.145, 0.135, 0.15))     # head ~0.30 m tall
    blob("px_bun", (0, 0.03, 0.62), (0.09, 0.09, 0.08))
    blob("px_handR", (-0.08, -0.22, 0.08), (0.03, 0.03, 0.03))
    blob("px_handL", (0.07, -0.20, 0.09), (0.03, 0.03, 0.03))

out = os.path.abspath(a.out)
os.makedirs(os.path.dirname(out), exist_ok=True)
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("WROTE", out)
