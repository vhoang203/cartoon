"""
render_hani.py -- studio renders of assets/hani.blend (turnaround, expressions, seated, control checks).

Usage:
  blender -b assets/hani.blend --python scripts/render_hani.py -- MODE [options]
MODE:
  view     --view front|q34|side|back|q34b  [--pose stand|seated] [--frame body|face|bust|seated]
  face     --keys "mouth_smile=1,brow_up=0.3" (face close-up)
Options:
  --out PATH  --res N  --samples N  --look-left/right etc via --eye "x,y,z" (eye_target offset)
"""
import bpy, sys, math, os
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "view"


def arg(name, default=None):
    if name in argv:
        return argv[argv.index(name) + 1]
    return default


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTP = arg("--out", os.path.join(ROOT, "renders", "hani", "test.png"))
RES = int(arg("--res", "1280"))
RESY = int(arg("--resy", str(RES)))
SAMPLES = int(arg("--samples", "32"))
VIEW = arg("--view", "front")
POSE = arg("--pose", "stand")
FRAME = arg("--frame", "body")
KEYS = arg("--keys", "")
EYE = arg("--eye", "")
BONES = arg("--bones", "")   # "bone:rx,ry,rz;bone2:..." degrees, local
scn = bpy.context.scene
rig = bpy.data.objects["Hani_rig"]
head = bpy.data.objects["Hani_head"]


def mat_diffuse(name, col, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.2
    return m


def sweep(name, mat):
    verts, faces = [], []
    prof = [(-4.0, 0.0), (0.6, 0.0)]
    R = 1.4
    for k in range(1, 13):
        a = math.pi / 2 * k / 12
        prof.append((0.6 + R * math.sin(a), R - R * math.cos(a)))
    prof.append((0.6 + R, 5.0))
    xs = (-5.0, 5.0)
    for (y, z) in prof:
        for x in xs:
            verts.append((x, y, z))
    for i in range(len(prof) - 1):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    scn.collection.objects.link(ob)
    return ob


def area(name, loc, target, size, power, color, parent):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.size = size
    ld.energy = power
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    scn.collection.objects.link(ob)
    ob.location = loc
    d = (Vector(target) - Vector(loc))
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    ob.parent = parent
    return ob


def setup():
    scn.render.engine = 'BLENDER_EEVEE_NEXT'
    scn.eevee.taa_render_samples = SAMPLES
    scn.eevee.use_shadows = True
    scn.eevee.shadow_ray_count = 2
    scn.eevee.shadow_step_count = 8
    scn.eevee.use_gtao = True
    scn.eevee.gtao_distance = 0.3
    scn.render.resolution_x, scn.render.resolution_y = RES, RESY
    scn.render.resolution_percentage = 100
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'AgX'
    LOOK = os.environ.get("HANI_LOOK", "AgX - Punchy")
    try:
        scn.view_settings.look = LOOK
    except Exception as ex:
        print("look options:", [l.identifier for l in scn.view_settings.bl_rna.properties['look'].enum_items])
    scn.view_settings.exposure = 0.0
    w = bpy.data.worlds.new("studio")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.36, 0.34, 0.33, 1)
    bg.inputs[1].default_value = 0.45
    scn.world = w
    rigE = bpy.data.objects.new("studio_rig", None)
    scn.collection.objects.link(rigE)
    bd = sweep("backdrop", mat_diffuse("backdrop", (0.20, 0.185, 0.175, 1)))
    bd.parent = rigE
    area("key", (-1.3, -1.7, 1.9), (0, 0, 0.62), 1.4, 210, (1.0, 0.93, 0.84), rigE)
    area("fill", (1.9, -1.3, 0.9), (0, 0, 0.55), 2.2, 75, (0.86, 0.91, 1.0), rigE)
    area("rim", (0.9, 1.5, 1.6), (0, 0, 0.72), 1.0, 160, (1.0, 0.95, 0.9), rigE)
    area("rim2", (-1.0, 1.3, 1.2), (0, 0, 0.6), 1.0, 70, (0.9, 0.93, 1.0), rigE)
    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    scn.collection.objects.link(cam)
    scn.camera = cam
    cam.parent = rigE
    return rigE, cam


def aim(cam, loc, target, lens):
    cam.data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def apply_pose():
    if POSE == "rest":
        for pb in rig.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
        return
    act = bpy.data.actions["Hani_seated" if POSE == "seated" else "Hani_stand"]
    rig.animation_data_create()
    rig.animation_data.action = act
    try:
        if act.slots:
            rig.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
    scn.frame_set(1)


def apply_keys():
    kbs = head.data.shape_keys.key_blocks
    for kv in filter(None, KEYS.split(",")):
        k, v = kv.split("=")
        kbs[k.strip()].value = float(v)


def apply_extra():
    if EYE:
        # move eye_target in root space (metres)
        x, y, z = (float(c) for c in EYE.split(","))
        pb = rig.pose.bones["eye_target"]
        M = rig.data.bones["eye_target"].matrix_local.copy()
        M.translation = Vector((x, y, z))
        pb.matrix = M
    for spec in filter(None, BONES.split(";")):
        nm, rot = spec.split(":")
        rx, ry, rz = (math.radians(float(c)) for c in rot.split(","))
        pb = rig.pose.bones[nm]
        from mathutils import Euler
        pb.rotation_quaternion = Euler((rx, ry, rz)).to_quaternion() @ pb.rotation_quaternion
    bpy.context.view_layer.update()


import json
rigE, cam = setup()
jobs = json.load(open(arg("--jobs"))) if arg("--jobs") else [dict(view=VIEW, frame=("face" if MODE == "face" else FRAME),
                                                                    pose=POSE, keys=KEYS, eye=EYE, bones=BONES, out=OUTP)]
views = {"front": 0, "q34": 40, "side": 90, "back": 180, "q34b": -40, "left": -90}
for jb in jobs:
    VIEW, FRAME, POSE = jb.get("view", "front"), jb.get("frame", "body"), jb.get("pose", "stand")
    KEYS, EYE, BONES = jb.get("keys", ""), jb.get("eye", ""), jb.get("bones", "")
    for kb in head.data.shape_keys.key_blocks[1:]:
        kb.value = 0.0
    apply_pose()
    if EYE or BONES:
        if rig.animation_data and rig.animation_data.action:
            scn.frame_set(1)
            mats = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
            sit = rig.pose.bones['root']['sit']
            rig.animation_data.action = None
            for pb in rig.pose.bones:
                pb.matrix_basis = mats[pb.name]
            rig.pose.bones['root']['sit'] = sit
        apply_extra()
    apply_keys()
    rigE.rotation_euler = (0, 0, math.radians(jb.get("yaw", views.get(VIEW, 0))))
    if FRAME == "face":
        aim(cam, (0, -0.95, 0.74), (0, 0, 0.712), 100)
    elif FRAME == "bust":
        aim(cam, (0, -1.35, 0.76), (0, 0, 0.68), 85)
    elif FRAME == "seated":
        aim(cam, (0, -1.95, 0.78), (0, -0.04, 0.33), 65)
    elif FRAME == "hands":
        aim(cam, (0.0, -0.75, 0.40), (0.13, 0.0, 0.35), 85)
    else:
        aim(cam, (0, -2.45, 0.60), (0, 0, 0.49), 70)
    if "res" in jb:
        scn.render.resolution_x = scn.render.resolution_y = jb["res"]
    out = jb["out"]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    scn.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("WROTE", out, flush=True)
