"""Sanity checks for assets/set.blend (run: blender -b assets/set.blend --python scripts/check_set.py).
Prints strawberry world bounds, verifies no two strawberries overlap, every berry sits on its slot,
and every required object exists."""
import bpy
from mathutils import Vector

req = ["CAM_main", "CAM_detail", "PLATE_hani", "PLATE_mako", "SET_bowl", "SET_blanket", "HANI_spot",
       "KEY_sun", "FILL_area", "RIM_area"] + ["S%d" % i for i in range(1, 7)] + \
      ["slot_H%d" % i for i in range(4)] + ["slot_M%d" % i for i in range(3)]
missing = [n for n in req if n not in bpy.data.objects]
print("MISSING:", missing or "none")
dg = bpy.context.evaluated_depsgraph_get()
boxes = {}
for i in range(1, 7):
    ob = bpy.data.objects["S%d" % i]
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]   # true world-space vertex extents
    mn = Vector([min(p[k] for p in pts) for k in range(3)])
    mx = Vector([max(p[k] for p in pts) for k in range(3)])
    boxes[ob.name] = (mn, mx)
    slot = bpy.data.objects[ob["start_slot"]]
    d = (ob.matrix_world.translation - slot.matrix_world.translation).length
    print("%s on %s  loc=(%.4f, %.4f, %.4f)  size=(%.4f x %.4f x %.4f)  slot_dist=%.5f" % (
        ob.name, ob["start_slot"], *ob.matrix_world.translation, *(mx - mn), d))
ok = True
names = sorted(boxes)
for a in range(len(names)):
    for b in range(a + 1, len(names)):
        A, B = boxes[names[a]], boxes[names[b]]
        if all(A[0][k] < B[1][k] and B[0][k] < A[1][k] for k in range(3)):
            ok = False
            print("OVERLAP (bbox)", names[a], names[b])
print("NO_OVERLAP" if ok else "OVERLAP_FOUND")
