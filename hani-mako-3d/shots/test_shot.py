"""
test_shot.py -- Phase 0 test shot: Hani passes S4 to Mako's plate (4 vs 2 -> 3 vs 3).

Build (about 40 s, headless):
    blender -b --python shots/test_shot.py
Writes shots/test_shot.blend (set.blend + appended Hani + baked performance).
Render with shots/render_shot.py (see that file).

Everything is procedural and rebuildable:
  * set.blend is opened as the base scene (lights, world, grade, compositor, cameras).
  * The Hani collection + rig is appended from assets/hani.blend.
  * The performance is authored as eased "channels" (key lists, below) and baked to one
    keyframe per frame on the rig (action `Hani_shot`) and on the face shape keys (`Hani_face_shot`).
  * Hair overlap (bun + 12 ringlet chains) is a damped-spring simulation driven by the
    head's rotation and acceleration, baked per frame.
  * S4 is carried with a Child Of constraint to hand.L (influence keyed on/off); its own
    location is keyed on slot_H3 before and exactly on slot_M0 after.

LAYOUT NOTE (why Hani is not exactly at HANI_spot): with the cross-legged seated drape the
skirt dome pools ~0.24 m in front of the pelvis and stays 0.10 m high until 0.22 m, while the
toddler arm reaches ~0.22 m. To keep the skirt off the plates Hani sits at (-0.06, 0.30) and
"rocks" forward onto her crossed shins (hips pivot about a point on the shins) to reach --
the natural toddler move.  The skirt hem is re-weighted to stay on the ground while the
waist follows the hips; the hem rim that touches the plates is pressed flat under them
(geometry-nodes modifier `SkirtUnderPlates`).  The empty bowl moves back to clear the skirt.
"""
import bpy, math, json, os, sys, wave, struct
from mathutils import Vector, Matrix, Euler, Quaternion

ROOT = '/home/user/cartoon/hani-mako-3d'
SET_BLEND = ROOT + '/assets/set.blend'
HANI_BLEND = ROOT + '/assets/hani.blend'
OUT_BLEND = ROOT + '/shots/test_shot.blend'
EP = '/home/user/cartoon/hani-mako-episode-01'
MANIFEST = EP + '/src/generated/audio-manifest.json'
WAV = EP + '/public/audio/dialogue/L18.wav'

FPS = 30
F_START, F_END = 1, 225          # 7.5 s
LINE_START = 44                  # frame where L18 audio starts (documented)
HANI_ROOT = Vector((-0.06, 0.29, 0.004))
BOWL_POS = (0.25, 0.44, 0.004)

# ---- key frames of the performance (used by several channels) -------------------------
F_ANT0, F_ANT = 100, 111        # anticipation start / peak
F_APPROACH = 120
F_CONTACT = 128                 # hand reaches S4
F_GRIP = 131                    # fingers closed -> Child Of switches ON
F_LIFT0 = 134
F_LIFT = 142
F_APEX = 151
F_DESC = 157
F_PLACE = 162                   # S4 touches slot_M0
F_RELEASE = 167                 # Child Of OFF (hand static 162..167)
F_TO_CAM = 176

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def log(*a):
    print('[shot]', *a, flush=True)


# =========================================================================================
# 1. scene: open set, append Hani
# =========================================================================================
bpy.ops.wm.open_mainfile(filepath=SET_BLEND)
scn = bpy.context.scene
scn.render.fps = FPS
scn.frame_start, scn.frame_end = F_START, F_END

with bpy.data.libraries.load(HANI_BLEND, link=False) as (src, dst):
    dst.collections = ['Hani']
    dst.actions = ['Hani_seated']
hani_coll = bpy.data.collections['Hani']
scn.collection.children.link(hani_coll)
rig = bpy.data.objects['Hani_rig']
head_ob = bpy.data.objects['Hani_head']
rig.location = HANI_ROOT
RIGW = rig.matrix_world.copy()
RIGW = Matrix.Translation(HANI_ROOT)
RIGW_INV = RIGW.inverted()

bpy.data.objects['SET_bowl'].location = BOWL_POS
bpy.data.objects['HANI_spot'].location = HANI_ROOT   # keep the guide honest

# ---- base seated pose -------------------------------------------------------------------
act0 = bpy.data.actions['Hani_seated']
rig.animation_data_create()
rig.animation_data.action = act0
try:
    rig.animation_data.action_slot = act0.slots[0]
except Exception:
    pass
scn.frame_set(1)
BASE = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
SIT = rig.pose.bones['root']['sit']
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis = BASE[pb.name]
rig.pose.bones['root']['sit'] = SIT
bpy.context.view_layer.update()
POSE0 = {pb.name: pb.matrix.copy() for pb in rig.pose.bones}      # armature space
REST = {b.name: b.matrix_local.copy() for b in rig.data.bones}

# all heavy meshes off while we evaluate the rig many times
MESHES = [o for o in scn.objects if o.type in ('MESH', 'META', 'CURVE')]


def meshes_enabled(on):
    for o in MESHES:
        o.hide_viewport = not on


# =========================================================================================
# 2. skirt: hem stays on the ground, waist follows hips; flatten under plates
# =========================================================================================
def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


rig.data.bones['root'].use_deform = True      # only the skirt layers get a 'root' group
ROOT_DROP = -BASE['root'].translation.z if abs(BASE['root'].translation.z) > 0.01 else 0.222
for name in ('Hani_skirt_under', 'Hani_skirt_tulle_a', 'Hani_skirt_tulle_b'):
    ob = bpy.data.objects[name]
    me = ob.data
    kb = me.shape_keys.key_blocks['skirt_sit']
    gh = ob.vertex_groups['hips']
    gr = ob.vertex_groups.new(name='root')
    for v in me.vertices:
        h = kb.data[v.index].co.z - ROOT_DROP        # height above the floor when seated
        w = smoothstep(0.035, 0.15, h)
        gh.add([v.index], w, 'REPLACE')
        gr.add([v.index], 1.0 - w, 'REPLACE')


# ---- low picnic table: raises both plates to toddler reach (see LAYOUT NOTE) ---------------
TABLE_TOP = 0.17


def make_table():
    mat = bpy.data.materials.new('M_picnic_table')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 9.0, 1.0)
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 2.2
    wv.inputs['Distortion'].default_value = 3.0; wv.inputs['Detail'].default_value = 1.5
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.80, 0.60, 0.40, 1)
    ramp.color_ramp.elements[1].color = (0.90, 0.73, 0.53, 1)
    nt.links.new(tc.outputs['Object'], mp.inputs[0]); nt.links.new(mp.outputs[0], wv.inputs[0])
    nt.links.new(wv.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.55
    bsdf.inputs['Coat Weight'].default_value = 0.25
    coll = bpy.data.collections['SET_props'] if 'SET_props' in bpy.data.collections else scn.collection
    parts = []
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, -0.018, TABLE_TOP - 0.014))
    top = bpy.context.active_object
    top.name = 'SET_table'
    top.scale = (0.80, 0.30, 0.028)
    parts.append(top)
    for (x, y) in ((-0.355, -0.135), (0.355, -0.135), (-0.355, 0.095), (0.355, 0.095)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.021, depth=TABLE_TOP - 0.024,
                                            location=(x, y, 0.004 + (TABLE_TOP - 0.024) / 2))
        parts.append(bpy.context.active_object)
    for p in parts:
        bpy.context.view_layer.objects.active = p
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bv = p.modifiers.new('bevel', 'BEVEL'); bv.width = 0.009; bv.segments = 4; bv.limit_method = 'ANGLE'
        p.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
    for p in parts[1:]:
        p.name = 'SET_table_leg'
    for p in parts:
        for c in list(p.users_collection):
            c.objects.unlink(p)
        coll.objects.link(p)
    return top


make_table()
DZ = TABLE_TOP - 0.004
for n in ('PLATE_hani', 'PLATE_mako', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'LOOK_plates'):
    bpy.data.objects[n].location.z += DZ
bpy.context.view_layer.update()

# =========================================================================================
# 3. channel system (eased Hermite keys, evaluated in Python, baked per frame)
# =========================================================================================


def _hermite_1d(ts, vs, f):
    n = len(ts)
    if f <= ts[0]:
        return vs[0]
    if f >= ts[-1]:
        return vs[-1]
    i = max(k for k in range(n - 1) if ts[k] <= f)
    t0, t1, v0, v1 = ts[i], ts[i + 1], vs[i], vs[i + 1]
    h = t1 - t0

    def tangent(k):
        if k == 0 or k == n - 1:
            return 0.0
        d0 = (vs[k] - vs[k - 1]) / (ts[k] - ts[k - 1])
        d1 = (vs[k + 1] - vs[k]) / (ts[k + 1] - ts[k])
        if d0 * d1 <= 0:
            return 0.0
        m = (vs[k + 1] - vs[k - 1]) / (ts[k + 1] - ts[k - 1])
        lim = 3 * min(abs(d0), abs(d1))
        return max(-lim, min(lim, m))
    m0, m1 = tangent(i) * h, tangent(i + 1) * h
    s = (f - t0) / h
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * v0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * v1 + (s3 - s2) * m1


def ch(keys, f):
    """keys: list of (frame, value|tuple) sorted by frame."""
    ts = [k[0] for k in keys]
    v0 = keys[0][1]
    if isinstance(v0, (tuple, list, Vector)):
        return tuple(_hermite_1d(ts, [k[1][j] for k in keys], f) for j in range(len(v0)))
    return _hermite_1d(ts, [k[1] for k in keys], f)


def wave_(f, period, amp, phase=0.0):
    return amp * math.sin(2 * math.pi * (f / period + phase))


# ---- world targets ------------------------------------------------------------------------
S4 = bpy.data.objects['S4']
SLOT_H3 = bpy.data.objects['slot_H3'].matrix_world.translation.copy()
SLOT_M0 = bpy.data.objects['slot_M0'].matrix_world.translation.copy()
S4_START = S4.matrix_world.copy()
GRAB_H = 0.035
P_PLATE_H = Vector((-0.185, 0.0, TABLE_TOP + 0.03))
P_S4 = Vector((SLOT_H3.x, SLOT_H3.y, SLOT_H3.z + 0.03))
P_PLATE_M = Vector((0.16, 0.0, TABLE_TOP + 0.03))
P_M0 = Vector((SLOT_M0.x, SLOT_M0.y, SLOT_M0.z + 0.03))
P_MAKO = Vector((0.95, -0.35, 0.42))      # Mako, off-screen right
CAM_START = Vector((0.03, -1.30, 0.50))
P_CAM = CAM_START.copy()


def hand_quat(fdir, pdir):
    Y = Vector(fdir).normalized()
    Z = Vector(pdir)
    Z = (Z - Z.dot(Y) * Y).normalized()
    X = Y.cross(Z)
    return Matrix((X, Y, Z)).transposed().to_quaternion()


HOLD = Vector((0.0, 0.030, 0.028))       # held-object centre in hand.L space


def hand_from_hold(hold, q):
    M = q.to_matrix().to_4x4()
    M.translation = Vector(hold) - q.to_matrix() @ HOLD
    return M


# rest hands (on knees) from the seated base
REST_HAND = {}
for side in ('L', 'R'):
    M = RIGW @ POSE0['hand_ik.' + side]
    q = M.to_quaternion()
    REST_HAND[side] = (tuple(M.translation + q.to_matrix() @ HOLD), q)

Q_GRAB = hand_quat((0.15, -1, -0.55), (0.0, -0.6, -0.8))
PLACE_YAW = math.radians(15)
Q_PLACE = Quaternion((0, 0, 1), PLACE_YAW) @ Q_GRAB
Q_LIFT = hand_quat((0.3, -1, -0.35), (0.0, -0.5, -0.85))
Q_ANT = hand_quat((0.4, -0.6, 0.5), (-0.3, -0.7, -0.4))
Q_GEST = hand_quat((0.6, -0.8, 0.5), (0.2, -0.3, 0.9))     # palm up, open "for Mako" gesture
Q_CLAP_L = hand_quat((0.05, -0.55, 1.0), (-1, 0, 0))
Q_CLAP_R = hand_quat((-0.05, -0.55, 1.0), (1, 0, 0))
HOLD_GRAB = Vector((SLOT_H3.x, SLOT_H3.y, SLOT_H3.z + GRAB_H))
HOLD_PLACE = Vector((SLOT_M0.x, SLOT_M0.y, SLOT_M0.z + GRAB_H))
CLAP = Vector((-0.055, 0.175, 0.245))


def qkeys(seq):
    """make quaternion keys hemisphere-consistent"""
    out, prev = [], None
    for f, q in seq:
        q = q.copy()
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        out.append((f, tuple(q)))
        prev = q
    return out


RL_pos, RL_q = REST_HAND['L']
RR_pos, RR_q = REST_HAND['R']
RL_q, RR_q = Quaternion(RL_q), Quaternion(RR_q)

HAND_L_POS = [
    (1, RL_pos), (60, RL_pos),
    (68, (0.06, 0.18, 0.21)), (76, (0.085, 0.15, 0.235)), (84, (0.075, 0.17, 0.22)),
    (94, RL_pos), (F_ANT0, RL_pos),
    (F_ANT, (0.02, 0.22, 0.30)),
    (F_APPROACH, (-0.08, 0.05, TABLE_TOP + 0.11)),
    (F_CONTACT, tuple(HOLD_GRAB)), (F_LIFT0, tuple(HOLD_GRAB)),
    (F_LIFT, (-0.07, -0.005, TABLE_TOP + 0.095)),
    (F_APEX, (0.01, -0.035, TABLE_TOP + 0.115)),
    (F_DESC, (0.105, -0.012, TABLE_TOP + 0.075)),
    (F_PLACE, tuple(HOLD_PLACE)), (F_RELEASE, tuple(HOLD_PLACE)),
    (F_RELEASE + 6, (0.115, 0.03, TABLE_TOP + 0.10)),
    (F_RELEASE + 16, (0.05, 0.16, 0.24)),
    (192, tuple(CLAP + Vector((0.006, 0, 0)))),
    (F_END, tuple(CLAP + Vector((0.006, 0, 0)))),
]
HAND_L_Q = qkeys([
    (1, RL_q), (60, RL_q), (68, Q_GEST), (84, Q_GEST), (94, RL_q), (F_ANT0, RL_q),
    (F_ANT, Q_ANT), (F_APPROACH, Q_GRAB), (F_CONTACT, Q_GRAB), (F_LIFT0, Q_GRAB),
    (F_LIFT, Q_GRAB.slerp(Q_PLACE, 0.2)), (F_APEX, Q_GRAB.slerp(Q_PLACE, 0.6)), (F_DESC, Q_PLACE),
    (F_PLACE, Q_PLACE), (F_RELEASE, Q_PLACE), (F_RELEASE + 6, Q_LIFT),
    (F_RELEASE + 16, Q_CLAP_L.slerp(Q_LIFT, 0.4)), (192, Q_CLAP_L), (F_END, Q_CLAP_L)])
HAND_R_POS = [
    (1, RR_pos), (F_ANT0, RR_pos), (F_ANT, tuple(Vector(RR_pos) + Vector((0.0, 0.01, 0.025)))),
    (F_CONTACT, RR_pos), (F_RELEASE + 4, RR_pos),
    (F_RELEASE + 16, (-0.10, 0.17, 0.20)),
    (192, tuple(CLAP - Vector((0.006, 0, 0)))), (F_END, tuple(CLAP - Vector((0.006, 0, 0)))),
]
HAND_R_Q = qkeys([(1, RR_q), (F_RELEASE + 4, RR_q), (F_RELEASE + 16, Q_CLAP_R.slerp(RR_q, 0.4)),
                  (192, Q_CLAP_R), (F_END, Q_CLAP_R)])

FING_L = [(1, 14), (64, 14), (70, -8), (84, -8), (94, 14), (F_ANT0, 14), (F_ANT, -6), (F_APPROACH, -12),
          (F_CONTACT, -4), (F_GRIP, 52), (F_LIFT0, 50), (F_RELEASE, 50), (F_RELEASE + 4, -4),
          (F_RELEASE + 12, 14), (186, 20), (192, 8), (F_END, 10)]
THUMB_L = [(1, 8), (F_ANT0, 8), (F_ANT, -8), (F_APPROACH, -14), (F_CONTACT, -6), (F_GRIP, 34),
           (F_RELEASE, 34), (F_RELEASE + 4, -6), (F_RELEASE + 12, 8), (F_END, 8)]
FING_R = [(1, 16), (F_ANT0, 16), (F_ANT, 26), (F_CONTACT, 22), (F_RELEASE + 6, 22), (186, 18),
          (192, 8), (F_END, 10)]

# ---- body (armature-axis degrees: x = lean forward, y = lean to her left, z = turn to her left)
ROCK = [  # (frame, (forward deg, side deg))
    (1, (0, 0)), (24, (3, 0)), (40, (0, 0)), (70, (0, 2)), (92, (1, 0)),
    (F_ANT0, (0, 0)), (F_ANT, (-5, -1)),
    (F_APPROACH, (9, 0)), (F_CONTACT, (12, 0)), (F_LIFT0, (12, 0)),
    (F_LIFT, (8, 3)), (F_APEX, (7, 6)), (F_DESC, (9, 10)),
    (F_PLACE, (10, 10)), (F_RELEASE, (10, 10)),
    (F_RELEASE + 10, (3, 3)), (184, (-3, 0)), (192, (0, 0)), (F_END, (0, 0)),
]
LIFT = [(1, 0.0), (192, 0.0), (196, 0.012), (200, -0.003), (204, 0.007), (208, -0.001), (212, 0.0), (F_END, 0.0)]
SPINE = [
    (1, (3, 0, -2)), (26, (4, 1, 4)), (40, (-2, 0, 2)), (56, (2, -1, -2)), (74, (0, 2, 7)),
    (90, (-3, -2, 1)), (F_ANT0, (-1, 0, 0)), (F_ANT, (-7, -1, -3)),
    (F_APPROACH, (13, 0, -5)), (F_CONTACT, (16, 0, -5)), (F_LIFT0, (16, 0, -5)),
    (F_LIFT, (12, 3, -3)), (F_APEX, (10, 5, -2)), (F_DESC, (11, 7, -3)),
    (F_PLACE, (12, 8, -3)), (F_RELEASE, (12, 8, -3)),
    (F_RELEASE + 10, (4, 3, 0)), (184, (-4, -1, 2)), (194, (-2, 0, 0)), (210, (-3, -2, 1)), (F_END, (-2, -1, 0)),
]
CHEST = [
    (1, (3, 0, -2)), (26, (3, 0, 4)), (40, (-2, 0, 2)), (56, (2, -1, -2)), (74, (0, 2, 8)),
    (90, (-3, -2, 1)), (F_ANT0, (-1, 0, 0)), (F_ANT, (-7, -1, -3)),
    (F_APPROACH, (10, 0, -5)), (F_CONTACT, (12, 0, -5)), (F_LIFT0, (12, 0, -5)),
    (F_LIFT, (9, 3, -3)), (F_APEX, (7, 5, -2)), (F_DESC, (7, 7, -3)),
    (F_PLACE, (8, 8, -3)), (F_RELEASE, (8, 8, -3)),
    (F_RELEASE + 10, (2, 3, 0)), (184, (-4, -1, 2)), (194, (-2, 0, 0)), (210, (-3, -2, 1)), (F_END, (-2, -1, 0)),
]
# head (x = nod down, y = tilt toward her left shoulder, z = turn to her left); 65 % head / 35 % neck
HEAD = [
    (1, (8, -2, -4)), (12, (9, -3, -5)),
    (18, (8, -3, 12)), (26, (9, 3, 20)), (32, (8, 6, 18)),          # look at Mako's plate: "only two?"
    (38, (2, 2, 6)), (44, (-2, -2, 2)),                              # idea -> start talking
    (50, (0, -3, -2)), (55, (6, -4, -4)), (60, (3, -4, -4)), (63, (6, -5, -4)),   # "một quả" (to S4)
    (69, (0, 2, 20)), (74, (-3, 5, 30)), (80, (-1, 6, 31)), (84, (-3, 5, 28)),      # "cho Mako" (to Mako)
    (89, (-7, -9, 6)), (93, (-8, -12, 4)),                           # "nhé?" (to camera, tilt)
    (97, (-2, -9, 4)), (100, (-6, -8, 4)),                           # little nod: yes!
    (F_ANT, (8, -3, -3)), (F_APPROACH, (16, -2, -6)), (F_CONTACT, (17, -2, -6)), (F_LIFT0, (15, -2, -6)),
    (F_LIFT, (10, 0, 4)), (F_APEX, (8, 2, 12)), (F_DESC, (12, 2, 18)), (F_PLACE, (13, 2, 18)),
    (F_RELEASE, (16, 2, 16)), (172, (12, 2, 12)),
    (F_TO_CAM + 4, (-8, -6, 4)), (F_TO_CAM + 9, (-11, -9, 3)), (190, (-7, -8, 3)),
    (198, (-3, -10, 2)), (202, (-9, -7, 2)), (206, (-4, -9, 2)), (212, (-7, -8, 2)),
    (F_END, (-6, -10, 3)),
]
SHRUG = [(1, 0), (F_ANT0, 0), (F_ANT, 6), (F_APPROACH, 0), (186, 0), (196, 7), (200, -2), (204, 4), (210, 0), (F_END, 0)]

# ---- eyes: (start frame, target) with fast saccades; carry is tracked from the hand ----------
EYE_SAC = [
    (1, P_PLATE_H), (13, P_PLATE_M), (37, P_CAM), (52, P_S4), (66, P_MAKO), (85, P_CAM),
    (101, P_S4),
]
EYE_AFTER = [(F_RELEASE + 1, P_M0), (F_TO_CAM, P_CAM)]

# ---- face ------------------------------------------------------------------------------------
SMILE = [(1, 0.18), (14, 0.15), (24, 0.0), (34, 0.0), (40, 0.35), (44, 0.25), (86, 0.3), (91, 0.4),
         (96, 0.55), (F_ANT0, 0.45), (F_APPROACH, 0.15), (F_LIFT, 0.25), (F_PLACE, 0.4),
         (F_RELEASE + 4, 0.6), (F_TO_CAM + 6, 1.0), (200, 0.95), (210, 1.0), (F_END, 0.95)]
BROW_UP = [(1, 0.25), (12, 0.25), (24, 0.1), (36, 0.1), (40, 0.55), (46, 0.25), (84, 0.2), (90, 0.65),
           (98, 0.3), (F_ANT, 0.3), (F_APPROACH, 0.25), (F_PLACE, 0.25), (F_RELEASE + 4, 0.3),
           (F_TO_CAM + 6, 0.55), (200, 0.4), (F_END, 0.45)]
BROW_WORRY = [(1, 0.0), (16, 0.0), (26, 0.45), (34, 0.4), (40, 0.0), (F_END, 0.0)]
OPEN_EXTRA = [(1, 0.0), (F_APPROACH, 0.0), (F_CONTACT, 0.06), (F_PLACE, 0.06), (F_RELEASE + 2, 0.0),
              (F_TO_CAM + 6, 0.32), (196, 0.38), (204, 0.42), (212, 0.3), (F_END, 0.26)]
O_EXTRA = [(1, 0.0), (F_APPROACH, 0.0), (F_CONTACT, 0.18), (F_PLACE, 0.2), (F_RELEASE + 2, 0.0), (F_END, 0.0)]
BLINKS = [10, 36, 98, 113, 174, 219]


def blink_value(f):
    shape = {0: 0.45, 1: 1.0, 2: 1.0, 3: 0.65, 4: 0.3, 5: 0.08}
    v = 0.0
    for b in BLINKS:
        v = max(v, shape.get(f - b, 0.0))
    return v


# ---- lip sync from the audio manifest (+ RMS articulation from the wav) -----------------------
man = json.load(open(MANIFEST))
ENV = man['lines']['L18']['env']['hani']
wv = wave.open(WAV)
nfr, sr = wv.getnframes(), wv.getframerate()
pcm = struct.unpack('<%dh' % nfr, wv.readframes(nfr))
hop = sr // FPS
RMS = []
for i in range(len(ENV)):
    seg = pcm[i * hop:(i + 1) * hop] or [0]
    RMS.append(math.sqrt(sum(x * x for x in seg) / len(seg)) / 32768.0)
mr = max(RMS) or 1.0
RMS = [r / mr for r in RMS]
raw = []
for i, e in enumerate(ENV):
    raw.append(min(1.0, e * 0.85) * (0.45 + 0.55 * RMS[i] ** 0.6))
CLOSE = {0: 0.04, 14: 0.08, 15: 0.06, 22: 0.06, 23: 0.08, 31: 0.06, 47: 0.06, 48: 0.0}   # M / word gaps
for i, v in CLOSE.items():
    raw[i] = min(raw[i], v)
OPEN_LS = []
for i in range(len(raw)):
    a = raw[i - 1] if i > 0 else raw[i]
    b = raw[i + 1] if i + 1 < len(raw) else raw[i]
    v = 0.5 * raw[i] + 0.25 * (a + b)
    if i in CLOSE:
        v = min(v, CLOSE[i] + 0.03)
    OPEN_LS.append(v)
ROUND = set(range(9, 14)) | {16, 17} | set(range(24, 30)) | set(range(37, 42))     # một, qu-, cho, ko
O_LS = [(0.4 * ENV[i] if i in ROUND else 0.0) for i in range(len(ENV))]
LEAD = 1    # mouth shapes lead the sound by one frame


def lipsync(f):
    i = f - LINE_START + LEAD
    if 0 <= i < len(OPEN_LS):
        return OPEN_LS[i], O_LS[i]
    return 0.0, 0.0


# =========================================================================================
# 4. per-frame pose evaluation
# =========================================================================================
def axis_rot(bone, deg_xyz):
    """rotation given about ARMATURE axes (deg) -> bone-local rotation matrix"""
    R3 = REST[bone].to_3x3().normalized()
    e = Euler([math.radians(a) for a in deg_xyz], 'XYZ').to_matrix()
    return (R3.transposed() @ e @ R3).to_4x4()


def set_basis(name, M):
    rig.pose.bones[name].matrix_basis = M


EYE_SEQ = EYE_SAC + EYE_AFTER


def eye_target_at(f, hold_fn):
    # carry: track the berry with a 3-frame lead
    if F_CONTACT <= f <= F_RELEASE:
        return Vector(hold_fn(min(f + 3, F_PLACE)))
    idx = max(i for i, (fs, _) in enumerate(EYE_SEQ) if fs <= f)
    fs, cur = EYE_SEQ[idx]
    prev = EYE_SEQ[idx - 1][1] if idx > 0 else cur
    s = min(1.0, (f - fs) / 3.0)
    s = s * s * (3 - 2 * s)
    return prev.lerp(cur, s)


def hold_L(f):
    return ch(HAND_L_POS, f)


def pose_frame(f):
    meshes = None
    for pb in rig.pose.bones:
        pb.matrix_basis = BASE[pb.name]
    bpy.context.view_layer.update()
    # --- hips rock about a pivot on the crossed shins
    rf, rs = ch(ROCK, f)
    rf += wave_(f, 97, 0.6)
    rs += wave_(f, 131, 0.9, 0.3)
    piv = Vector((0.06 * min(1.0, abs(rs) / 12.0) * (1 if rs >= 0 else -1), -0.11, 0.05))
    R = Euler((math.radians(rf), math.radians(rs), 0)).to_matrix().to_4x4()
    lift = ch(LIFT, f)
    Mh = Matrix.Translation(Vector((0, 0, lift))) @ Matrix.Translation(piv) @ R @ Matrix.Translation(-piv) @ POSE0['hips']
    rig.pose.bones['hips'].matrix = Mh
    # --- spine / chest / neck / head
    sx, sy, sz = ch(SPINE, f)
    cx, cy, cz = ch(CHEST, f)
    cx += wave_(f, 78, 0.9)                        # breathing
    set_basis('spine', BASE['spine'] @ axis_rot('spine', (sx, sy, sz)))
    set_basis('chest', BASE['chest'] @ axis_rot('chest', (cx, cy, cz)))
    hx, hy, hz = ch(HEAD, f)
    # keep the face up/level while the body leans (the head counters the torso)
    hx -= 0.75 * max(0.0, rf + sx + cx)
    hy -= 0.6 * (rs + sy + cy)
    hx += wave_(f, 61, 0.7, 0.2)
    hz += wave_(f, 89, 0.8, 0.6)
    set_basis('neck', BASE['neck'] @ axis_rot('neck', (0.35 * hx, 0.35 * hy, 0.35 * hz)))
    set_basis('head', BASE['head'] @ axis_rot('head', (0.65 * hx, 0.65 * hy, 0.65 * hz)))
    sh = ch(SHRUG, f)
    set_basis('shoulder.L', BASE['shoulder.L'] @ axis_rot('shoulder.L', (0, sh, 0)))
    set_basis('shoulder.R', BASE['shoulder.R'] @ axis_rot('shoulder.R', (0, -sh, 0)))
    bpy.context.view_layer.update()
    chest_now = rig.pose.bones['chest'].matrix.copy()
    head_now = rig.pose.bones['head'].matrix.copy()
    # --- poles follow the chest so elbows keep their direction
    dchest = chest_now @ POSE0['chest'].inverted()
    for s in ('L', 'R'):
        rig.pose.bones['arm_pole.' + s].matrix = dchest @ POSE0['arm_pole.' + s]
    # --- hands (IK targets in world)
    bounce = Vector((0, 0, lift)) if f > 186 else Vector((0, 0, 0))
    for s, PK, QK in (('L', HAND_L_POS, HAND_L_Q), ('R', HAND_R_POS, HAND_R_Q)):
        hp = Vector(ch(PK, f)) + bounce
        q = Quaternion(ch(QK, f)).normalized()
        rig.pose.bones['hand_ik.' + s].matrix = RIGW_INV @ hand_from_hold(hp, q)
    # --- fingers
    set_basis('fingers.L', BASE['fingers.L'] @ Euler((math.radians(ch(FING_L, f)), 0, 0)).to_matrix().to_4x4())
    set_basis('thumb.L', BASE['thumb.L'] @ Euler((math.radians(ch(THUMB_L, f)), 0, 0)).to_matrix().to_4x4())
    set_basis('fingers.R', BASE['fingers.R'] @ Euler((math.radians(ch(FING_R, f)), 0, 0)).to_matrix().to_4x4())
    # --- eyes
    et = eye_target_at(f, hold_L)
    Me = POSE0['eye_target'].copy()
    Me.translation = RIGW_INV @ (Vector(et) + Vector((0, 0, 0.05)))
    rig.pose.bones['eye_target'].matrix = Me
    bpy.context.view_layer.update()
    return head_now


KEY_BONES = ['hips', 'spine', 'chest', 'neck', 'head', 'shoulder.L', 'shoulder.R', 'arm_pole.L', 'arm_pole.R',
             'hand_ik.L', 'hand_ik.R', 'fingers.L', 'thumb.L', 'fingers.R', 'eye_target']
HAIR_BONES = ['bun'] + [b.name for b in rig.data.bones if b.name.startswith('curl_')]

frames = list(range(F_START, F_END + 1))
meshes_enabled(False)
REC = {b: [] for b in KEY_BONES}
HEADM = []
for f in frames:
    hm = pose_frame(f)
    HEADM.append(hm)
    for b in KEY_BONES:
        REC[b].append(rig.pose.bones[b].matrix_basis.copy())
log('posed', len(frames), 'frames')

# =========================================================================================
# 5. hair overlap: damped springs driven by head rotation / acceleration
# =========================================================================================
HREST = {}
for b in HAIR_BONES:
    HREST[b] = (POSE0['head'].inverted() @ POSE0[b]).to_3x3().normalized()
PARAMS = {'bun': (0.13, 0.30, 0.45, 4.0, 11.0), '01': (0.12, 0.22, 0.65, 7.0, 22.0), '02': (0.075, 0.17, 0.85, 9.0, 25.0)}
HAIR = {b: [] for b in HAIR_BONES}
for b in HAIR_BONES:
    k, c, grot, glin, clampd = PARAMS['bun' if b == 'bun' else b[-2:]]
    th = Vector((0, 0, 0)); v = Vector((0, 0, 0))
    # bone direction in head space (for linear inertia)
    d = (POSE0['head'].inverted().to_3x3() @ (POSE0[b].to_3x3() @ Vector((0, 1, 0)))).normalized()
    root_off = POSE0['head'].inverted() @ POSE0[b].translation
    prevp = None; prevv = None
    for i, f in enumerate(frames):
        H = HEADM[i]
        p = H @ root_off
        if i == 0:
            om = Vector((0, 0, 0)); acc = Vector((0, 0, 0))
        else:
            Hp = HEADM[i - 1]
            dq = (Hp.to_3x3().transposed() @ H.to_3x3()).to_quaternion()
            ax, ang = dq.to_axis_angle()
            if ang > math.pi:
                ang -= 2 * math.pi
            om = ax * ang
            vel = p - prevp
            acc = (vel - prevv) if prevv is not None else Vector((0, 0, 0))
            acc = H.to_3x3().transposed() @ acc
            prevv = vel
        prevp = p
        th -= om * grot
        v += -k * th - c * v + d.cross(-acc) * glin
        th += v
        lim = math.radians(clampd)
        if th.length > lim:
            th = th * (lim / th.length)
        # head space -> bone local
        la = HREST[b].transposed() @ th
        ang = la.length
        Rl = Quaternion(la.normalized(), ang).to_matrix().to_4x4() if ang > 1e-6 else Matrix.Identity(4)
        HAIR[b].append(BASE[b] @ Rl)
log('hair springs baked')

# =========================================================================================
# 6. write actions
# =========================================================================================


def new_action(name, id_ob):
    act = bpy.data.actions.new(name)
    id_ob.animation_data_create()
    id_ob.animation_data.action = act
    cb = None
    try:
        slot = act.slots.new(id_type=id_ob.id_type if hasattr(id_ob, 'id_type') else 'OBJECT', name=id_ob.name)
        layer = act.layers.new('Layer')
        strip = layer.strips.new(type='KEYFRAME')
        cb = strip.channelbag(slot, ensure=True)
        id_ob.animation_data.action_slot = slot
    except Exception as ex:
        log('legacy action api', ex)
    return act, cb


def put_curve(act, cb, path, index, values, group=None, interp='LINEAR'):
    fc = (cb.fcurves.new(path, index=index) if cb is not None else act.fcurves.new(path, index=index))
    fc.keyframe_points.add(len(values))
    co = []
    for f, v in zip(frames, values):
        co += [f, v]
    fc.keyframe_points.foreach_set('co', co)
    for kp in fc.keyframe_points:
        kp.interpolation = interp
    fc.update()
    return fc


rig.animation_data.action = None
ACT, CB = new_action('Hani_shot', rig)


def key_bone_series(name, mats):
    locs, quats = [], []
    prev = None
    for M in mats:
        l, q, s = M.decompose()
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        locs.append(l); quats.append(q)
    for i in range(3):
        put_curve(ACT, CB, 'pose.bones["%s"].location' % name, i, [l[i] for l in locs])
    for i in range(4):
        put_curve(ACT, CB, 'pose.bones["%s"].rotation_quaternion' % name, i, [q[i] for q in quats])


for b in KEY_BONES:
    key_bone_series(b, REC[b])
for b in HAIR_BONES:
    key_bone_series(b, HAIR[b])
# everything else: hold the seated base (keyed once so the action is self-contained)
for pb in rig.pose.bones:
    if pb.name in KEY_BONES or pb.name in HAIR_BONES:
        continue
    l, q, s = BASE[pb.name].decompose()
    for i in range(3):
        put_curve(ACT, CB, 'pose.bones["%s"].location' % pb.name, i, [l[i]] * len(frames))
    for i in range(4):
        put_curve(ACT, CB, 'pose.bones["%s"].rotation_quaternion' % pb.name, i, [q[i]] * len(frames))
rig.pose.bones['root']['sit'] = SIT

# face
key = head_ob.data.shape_keys
FACT, FCB = new_action('Hani_face_shot', key)
vals = {n: [] for n in ('mouth_open', 'mouth_smile', 'mouth_O', 'blink_L', 'blink_R', 'brow_up', 'brow_worry')}
for f in frames:
    lo, lO = lipsync(f)
    talking = LINE_START - 1 <= f <= LINE_START + len(ENV)
    sm = ch(SMILE, f)
    if talking:
        i = f - LINE_START
        sm = 0.25 + (0.18 if i >= 42 else 0.0) + 0.05 * math.sin(f * 0.7)
    op = min(1.0, lo + ch(OPEN_EXTRA, f))
    bl = blink_value(f)
    vals['mouth_open'].append(op)
    vals['mouth_O'].append(min(1.0, lO + ch(O_EXTRA, f)))
    vals['mouth_smile'].append(min(1.0, sm * (1.0 - 0.35 * lO)))
    vals['blink_L'].append(bl)
    vals['blink_R'].append(bl)
    vals['brow_up'].append(ch(BROW_UP, f) * (1 - 0.5 * bl))
    vals['brow_worry'].append(ch(BROW_WORRY, f))
for n, vs in vals.items():
    put_curve(FACT, FCB, 'key_blocks["%s"].value' % n, 0, vs)

meshes_enabled(True)

# =========================================================================================
# 7. S4: Child Of to hand.L, influence on during the carry
# =========================================================================================
meshes_enabled(False)


def hand_world(f):
    scn.frame_set(f)
    return RIGW @ rig.pose.bones['hand.L'].matrix


Hg = hand_world(F_GRIP)
Hp = hand_world(F_RELEASE - 1)
Hp2 = hand_world(F_PLACE)
meshes_enabled(True)
carried = Hp @ Hg.inverted() @ S4_START
carried_place = Hp2 @ Hg.inverted() @ S4_START
target = carried.copy()
target.translation = SLOT_M0
err = (carried.translation - SLOT_M0).length
err_pl = (carried_place.translation - SLOT_M0).length
drift = (Hp.translation - Hp2.translation).length
log('PLACE ERROR (carried S4 vs slot_M0) = %.5f m at f%d, %.5f m at f%d; hand drift during hold %.5f' %
    (err, F_RELEASE - 1, err_pl, F_PLACE, drift))
log('grab hand', tuple(round(x, 4) for x in Hg.translation), 'hold target', tuple(round(x, 4) for x in HOLD_GRAB))

S4.animation_data_clear()
con = S4.constraints.new('CHILD_OF')
con.name = 'carry_hand'
con.target = rig
con.subtarget = 'hand.L'
con.inverse_matrix = Hg.inverted()
con.set_inverse_pending = False
for f, inf in ((F_START, 0.0), (F_GRIP - 1, 0.0), (F_GRIP, 1.0), (F_RELEASE - 1, 1.0), (F_RELEASE, 0.0)):
    con.influence = inf
    con.keyframe_insert('influence', frame=f)
# own transform: start pose until release, then exactly on slot_M0 (upright, yawed with the hand)
l0, q0, s0 = S4_START.decompose()
l1, q1, s1 = target.decompose()
S4.rotation_mode = 'QUATERNION'
for f, (l, q) in ((F_START, (l0, q0)), (F_RELEASE - 1, (l0, q0)), (F_RELEASE, (l1, q1)), (F_END, (l1, q1))):
    S4.location = l
    S4.rotation_quaternion = q
    S4.scale = s0
    S4.keyframe_insert('location', frame=f)
    S4.keyframe_insert('rotation_quaternion', frame=f)
for fc in (S4.animation_data.action.fcurves if hasattr(S4.animation_data.action, 'fcurves') else []):
    for kp in fc.keyframe_points:
        kp.interpolation = 'CONSTANT'
try:
    for layer in S4.animation_data.action.layers:
        for strip in layer.strips:
            for cbag in strip.channelbags:
                for fc in cbag.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
except Exception:
    pass
S4['moves'] = 'slot_H3 -> slot_M0, frames %d-%d' % (F_GRIP, F_PLACE)

# =========================================================================================
# 8. camera, lights, audio, render defaults
# =========================================================================================
cam = bpy.data.objects['CAM_main']
cam_rot = cam.rotation_euler.copy()
cam.animation_data_clear()
CAM_END = Vector((0.02, -1.14, 0.475))
for f, p in ((F_START, CAM_START), (F_END, CAM_END)):
    cam.location = p
    cam.keyframe_insert('location', frame=f)
cam.data.dof.aperture_fstop = 4.0
foc = bpy.data.objects['FOCUS_main']
foc.location = (-0.06, 0.14, 0.24)

rim = bpy.data.objects['RIM_area']
headpos = RIGW @ POSE0['head'].translation + Vector((0, 0, 0.1))


def aim(ob, tgt):
    ob.rotation_euler = (Vector(tgt) - ob.location).to_track_quat('-Z', 'Y').to_euler()


aim(rim, headpos)
bounce_l = bpy.data.objects['BOUNCE_area']
bounce_l.location = (HANI_ROOT.x - 0.02, -0.35, 0.06)
aim(bounce_l, (HANI_ROOT.x, HANI_ROOT.y - 0.1, 0.40))
bounce_l.data.energy = 10
# soft warm face fill from low front (fixes the smudgy mouth area), no specular
fl = bpy.data.lights.new('FACE_fill', 'AREA')
fl.shape = 'DISK'; fl.size = 0.7; fl.energy = 9.0; fl.color = (1.0, 0.86, 0.74)
try:
    fl.specular_factor = 0.0
except Exception:
    pass
flo = bpy.data.objects.new('FACE_fill', fl)
bpy.data.collections['LIGHTS'].objects.link(flo) if 'LIGHTS' in bpy.data.collections else scn.collection.objects.link(flo)
flo.location = (HANI_ROOT.x + 0.15, -0.55, 0.30)
aim(flo, (HANI_ROOT.x, HANI_ROOT.y - 0.1, 0.42))

# audio in the sequencer at the documented start frame
if not scn.sequence_editor:
    scn.sequence_editor_create()
try:
    strips = scn.sequence_editor.strips
except AttributeError:
    strips = scn.sequence_editor.sequences
snd = strips.new_sound('L18', WAV, channel=1, frame_start=LINE_START)
scn['L18_start_frame'] = LINE_START
scn['frame_range'] = '%d-%d' % (F_START, F_END)

scn.frame_set(F_START)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
log('saved', OUT_BLEND, 'line start frame', LINE_START, 'range', F_START, F_END)
