"""Hani & Mako 3D -- picnic set, props and look-dev.

Run (headless, ~20 s):
    blender -b --python scripts/build_set.py
Produces assets/set.blend.  Renders are done by scripts/render_set.py.

World conventions (docs/phase0-brief.md): metres, Z up, camera looks toward +Y,
screen-left = -X.  Blanket top surface sits at Z = BLANKET_TOP.

Everything is procedural (bmesh / nodes / metaballs); no external data.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix, Euler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_BLEND = os.path.join(ROOT, "assets", "set.blend")

# ----------------------------------------------------------------------------
# Layout constants (exported to docs/set_layout.md, also stored on the scene)
# ----------------------------------------------------------------------------
BLANKET_TOP = 0.004            # top surface of the blanket (blanket mesh spans Z 0..0.004)
BLANKET_CENTER = (0.0, 0.16)
BLANKET_SIZE = (1.70, 1.36)    # X, Y

PLATE_R = 0.13                 # plate diameter 0.26
PLATE_FLOOR = 0.0045           # inner floor height above plate base
PLATE_H = (-0.185, 0.0)        # Hani's plate centre (screen-left)
PLATE_M = (0.185, 0.0)         # Mako's plate centre (screen-right)
SLOT_Z = BLANKET_TOP + PLATE_FLOOR
SLOT_DX_H = [-0.09, -0.03, 0.03, 0.09]     # 4 slots on Hani's plate
SLOT_DX_M = [-0.06, 0.0, 0.06]             # 3 slots on Mako's plate

BOWL_POS = (0.135, 0.33)
BASKET_POS = (0.62, 0.56)
HANI_SPOT = (-0.185, 0.30, BLANKET_TOP)    # kneeling/sitting pivot (pelvis on heels), faces -Y (camera)

USE_GRASS_TUFTS = False        # blade tufts read as noisy weeds; soft ground looks calmer
BERRY_W = 0.055
BERRY_H = 0.065

random.seed(7)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def hexcol(h, a=1.0):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    # sRGB -> linear
    lin = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]
    return (lin[0], lin[1], lin[2], a)


def link_obj(obj, coll):
    coll.objects.link(obj)
    return obj


def new_coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def mesh_from_bm(name, bm, coll, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


class NB:
    """Tiny node-tree builder for materials."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, **inputs):
        node = self.nt.nodes.new(kind)
        node.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            if k.startswith('_'):
                setattr(node, k[1:], v)
            else:
                self.set(node, k, v)
        return node

    def set(self, node, key, v):
        sock = node.inputs[key]
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def link(self, a, b):
        self.nt.links.new(a, b)


def principled(name, color, rough=0.5, spec=0.5, coat=0.0, coat_rough=0.1,
               sss=0.0, sss_radius=(0.1, 0.05, 0.03), sheen=0.0):
    mat = bpy.data.materials.new(name)
    b = NB(mat)
    bsdf = b.n('ShaderNodeBsdfPrincipled')
    b.set(bsdf, 'Base Color', color)
    b.set(bsdf, 'Roughness', rough)
    b.set(bsdf, 'Specular IOR Level', spec)
    b.set(bsdf, 'Coat Weight', coat)
    b.set(bsdf, 'Coat Roughness', coat_rough)
    b.set(bsdf, 'Subsurface Weight', sss)
    b.set(bsdf, 'Subsurface Radius', sss_radius)
    b.set(bsdf, 'Sheen Weight', sheen)
    out = b.n('ShaderNodeOutputMaterial')
    b.link(bsdf.outputs[0], out.inputs[0])
    mat['bsdf'] = bsdf.name
    return mat


def catmull(points, n):
    """Catmull-Rom resample of a list of tuples -> n points (inclusive ends)."""
    pts = [points[0]] + list(points) + [points[-1]]
    segs = len(points) - 1
    out = []
    for i in range(n):
        u = i / (n - 1) * segs
        k = min(int(u), segs - 1)
        t = u - k
        p0, p1, p2, p3 = pts[k], pts[k + 1], pts[k + 2], pts[k + 3]
        t2, t3 = t * t, t * t * t
        out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t +
                                (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)
                        for j in range(len(p1))))
    return out


def lathe(bm, profile, segs, mat_fn=None, close_bottom=True, close_top=True):
    """Revolve a list of (r, z) points around Z. Poles where r == 0 are merged.
    mat_fn(r, z) -> material index for each quad (evaluated at quad centre)."""
    rings = []
    for (r, z) in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segs),
                                        r * math.sin(2 * math.pi * i / segs), z))
                          for i in range(segs)])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                vs = (a[0], b[j], b[i]) if True else None
                vs = (a[0], b[i], b[j])
            elif len(b) == 1:
                vs = (a[i], b[0], a[j])
                vs = (a[i], a[j], b[0])
            else:
                vs = (a[i], a[j], b[j], b[i])
            f = bm.faces.new(vs)
            if mat_fn:
                c = f.calc_center_median()
                f.material_index = mat_fn(math.hypot(c.x, c.y), c.z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return rings


# ----------------------------------------------------------------------------
# scene reset
# ----------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "SET_picnic"

C_SET = new_coll("SET")
C_GROUND = new_coll("SET_ground", C_SET)
C_PROPS = new_coll("SET_props", C_SET)
C_BERRIES = new_coll("STRAWBERRIES")
C_SLOTS = new_coll("SLOTS")
C_BG = new_coll("SET_background", C_SET)
C_LIGHTS = new_coll("LIGHTS")
C_CAMS = new_coll("CAMERAS")
C_GUIDES = new_coll("GUIDES")

# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
def make_grass_mat():
    mat = bpy.data.materials.new("M_grass")
    b = NB(mat)
    tc = b.n('ShaderNodeTexCoord')
    noise = b.n('ShaderNodeTexNoise', Scale=0.35, Detail=3.0, Roughness=0.5)
    b.link(tc.outputs['Object'], noise.inputs['Vector'])
    noise2 = b.n('ShaderNodeTexNoise', Scale=2.2, Detail=2.0)
    b.link(tc.outputs['Object'], noise2.inputs['Vector'])
    ramp = b.n('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position = 0.35
    cr.elements[0].color = hexcol('#5FA844')
    cr.elements[1].position = 0.68
    cr.elements[1].color = hexcol('#93C95A')
    b.link(noise.outputs['Fac'], ramp.inputs['Fac'])
    mix = b.n('ShaderNodeMix', _data_type='RGBA', _blend_type='OVERLAY')
    b.set(mix, 0, 0.25)
    b.link(ramp.outputs[0], mix.inputs[6])
    b.link(noise2.outputs['Color'], mix.inputs[7])
    bsdf = b.n('ShaderNodeBsdfPrincipled', Roughness=0.85)
    b.set(bsdf, 'Specular IOR Level', 0.2)
    b.set(bsdf, 'Sheen Weight', 0.4)
    b.set(bsdf, 'Sheen Tint', hexcol('#E8FFC0'))
    b.link(mix.outputs[2], bsdf.inputs['Base Color'])
    gb = b.n('ShaderNodeTexNoise', Scale=60.0, Detail=2.0)
    b.link(tc.outputs['Object'], gb.inputs['Vector'])
    bump = b.n('ShaderNodeBump', Strength=0.25, Distance=0.002)
    b.link(gb.outputs['Fac'], bump.inputs['Height'])
    b.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    out = b.n('ShaderNodeOutputMaterial')
    b.link(bsdf.outputs[0], out.inputs[0])
    return mat


def make_blade_mat():
    """Grass blades: colour from vertex attribute 'col' (per-blade variation)."""
    mat = bpy.data.materials.new("M_grass_blade")
    b = NB(mat)
    attr = b.n('ShaderNodeAttribute', _attribute_name='col')
    bsdf = b.n('ShaderNodeBsdfPrincipled', Roughness=0.7)
    b.set(bsdf, 'Specular IOR Level', 0.25)
    b.set(bsdf, 'Subsurface Weight', 0.0)
    b.set(bsdf, 'Sheen Weight', 0.3)
    b.link(attr.outputs['Color'], bsdf.inputs['Base Color'])
    out = b.n('ShaderNodeOutputMaterial')
    b.link(bsdf.outputs[0], out.inputs[0])
    return mat


def make_gingham_mat():
    mat = bpy.data.materials.new("M_blanket_gingham")
    b = NB(mat)
    tc = b.n('ShaderNodeTexCoord')
    sep = b.n('ShaderNodeSeparateXYZ')
    b.link(tc.outputs['Object'], sep.inputs[0])
    # tiny weave wobble so stripe edges feel woven rather than vector-perfect
    wob = b.n('ShaderNodeTexNoise', Scale=140.0, Detail=1.0)
    b.link(tc.outputs['Object'], wob.inputs['Vector'])
    period = 0.085

    def stripe(axis_out, offset):
        m1 = b.n('ShaderNodeMath', _operation='MULTIPLY_ADD')
        b.link(wob.outputs['Fac'], m1.inputs[0])
        m1.inputs[1].default_value = 0.004
        b.link(axis_out, m1.inputs[2])
        d = b.n('ShaderNodeMath', _operation='DIVIDE')
        b.link(m1.outputs[0], d.inputs[0])
        d.inputs[1].default_value = period
        a = b.n('ShaderNodeMath', _operation='ADD')
        b.link(d.outputs[0], a.inputs[0])
        a.inputs[1].default_value = offset
        fr = b.n('ShaderNodeMath', _operation='FRACT')
        b.link(a.outputs[0], fr.inputs[0])
        sb = b.n('ShaderNodeMath', _operation='SUBTRACT')
        b.link(fr.outputs[0], sb.inputs[0])
        sb.inputs[1].default_value = 0.5
        ab = b.n('ShaderNodeMath', _operation='ABSOLUTE')
        b.link(sb.outputs[0], ab.inputs[0])
        mr = b.n('ShaderNodeMapRange', _interpolation_type='SMOOTHSTEP')
        b.link(ab.outputs[0], mr.inputs['Value'])
        mr.inputs['From Min'].default_value = 0.235
        mr.inputs['From Max'].default_value = 0.265
        mr.inputs['To Min'].default_value = 1.0
        mr.inputs['To Max'].default_value = 0.0
        return mr.outputs['Result']

    # stripes centred so that a dark square sits on the blanket centre
    sx = stripe(sep.outputs['X'], 0.5)
    sy = stripe(sep.outputs['Y'], 0.5 - BLANKET_CENTER[1] / period)
    cream = hexcol('#FFF4E0')
    mid = hexcol('#F8BC8C')
    dark = hexcol('#EE9960')
    m_a = b.n('ShaderNodeMix', _data_type='RGBA')
    b.link(sx, m_a.inputs[0])
    m_a.inputs[6].default_value = cream
    m_a.inputs[7].default_value = mid
    m_b = b.n('ShaderNodeMix', _data_type='RGBA')
    b.link(sy, m_b.inputs[0])
    b.link(m_a.outputs[2], m_b.inputs[6])
    m_b.inputs[7].default_value = mid
    both = b.n('ShaderNodeMath', _operation='MULTIPLY')
    b.link(sx, both.inputs[0])
    b.link(sy, both.inputs[1])
    m_c = b.n('ShaderNodeMix', _data_type='RGBA')
    b.link(both.outputs[0], m_c.inputs[0])
    b.link(m_b.outputs[2], m_c.inputs[6])
    m_c.inputs[7].default_value = dark
    # hem border (attribute 'edge' = distance to blanket outline in metres)
    ed = b.n('ShaderNodeAttribute', _attribute_name='edge')
    hm = b.n('ShaderNodeMapRange', _interpolation_type='SMOOTHSTEP')
    b.link(ed.outputs['Fac'], hm.inputs['Value'])
    hm.inputs['From Min'].default_value = 0.026
    hm.inputs['From Max'].default_value = 0.032
    hm.inputs['To Min'].default_value = 1.0
    hm.inputs['To Max'].default_value = 0.0
    m_d = b.n('ShaderNodeMix', _data_type='RGBA')
    b.link(hm.outputs['Result'], m_d.inputs[0])
    b.link(m_c.outputs[2], m_d.inputs[6])
    m_d.inputs[7].default_value = hexcol('#EE9C66')
    # fabric bump (fine weave)
    wave1 = b.n('ShaderNodeTexWave', _wave_type='BANDS', _bands_direction='X', Scale=420.0)
    b.link(tc.outputs['Object'], wave1.inputs['Vector'])
    wave2 = b.n('ShaderNodeTexWave', _wave_type='BANDS', _bands_direction='Y', Scale=420.0)
    b.link(tc.outputs['Object'], wave2.inputs['Vector'])
    wm = b.n('ShaderNodeMath', _operation='MULTIPLY')
    b.link(wave1.outputs['Fac'], wm.inputs[0])
    b.link(wave2.outputs['Fac'], wm.inputs[1])
    bump = b.n('ShaderNodeBump', Strength=0.12, Distance=0.0005)
    b.link(wm.outputs[0], bump.inputs['Height'])
    bsdf = b.n('ShaderNodeBsdfPrincipled', Roughness=0.9)
    b.set(bsdf, 'Specular IOR Level', 0.15)
    b.set(bsdf, 'Sheen Weight', 0.6)
    b.set(bsdf, 'Sheen Roughness', 0.5)
    b.set(bsdf, 'Sheen Tint', hexcol('#FFF0DD'))
    b.set(bsdf, 'Subsurface Weight', 0.05)
    b.link(m_d.outputs[2], bsdf.inputs['Base Color'])
    b.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    out = b.n('ShaderNodeOutputMaterial')
    b.link(bsdf.outputs[0], out.inputs[0])
    return mat


def make_berry_mat():
    """Glossy coral-red with a gentle warm gradient (lighter shoulders)."""
    mat = bpy.data.materials.new("M_strawberry")
    b = NB(mat)
    tc = b.n('ShaderNodeTexCoord')
    sep = b.n('ShaderNodeSeparateXYZ')
    b.link(tc.outputs['Object'], sep.inputs[0])
    mr = b.n('ShaderNodeMapRange')
    b.link(sep.outputs['Z'], mr.inputs['Value'])
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = BERRY_H
    ramp = b.n('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = hexcol('#D3303F')
    cr.elements[1].position = 0.55
    cr.elements[1].color = hexcol('#E2404C')
    e = cr.elements.new(0.92)
    e.color = hexcol('#EC5A55')
    b.link(mr.outputs['Result'], ramp.inputs['Fac'])
    bsdf = b.n('ShaderNodeBsdfPrincipled', Roughness=0.32)
    b.set(bsdf, 'Specular IOR Level', 0.6)
    b.set(bsdf, 'Coat Weight', 0.3)
    b.set(bsdf, 'Coat Roughness', 0.08)
    b.set(bsdf, 'Subsurface Weight', 0.12)
    b.set(bsdf, 'Subsurface Radius', (0.6, 0.2, 0.15))
    b.set(bsdf, 'Subsurface Scale', 0.01)
    b.link(ramp.outputs[0], bsdf.inputs['Base Color'])
    out = b.n('ShaderNodeOutputMaterial')
    b.link(bsdf.outputs[0], out.inputs[0])
    return mat


def make_plate_mat(name, rim_hex):
    """Ceramic plate: cream body, coloured rim (material index 1), glossy glaze."""
    body = principled(name + "_body", hexcol('#FBF1E2'), rough=0.3, spec=0.4,
                      coat=0.25, coat_rough=0.1, sss=0.05)
    rim = principled(name + "_rim", hexcol(rim_hex), rough=0.22, spec=0.5,
                     coat=0.4, coat_rough=0.08)
    return body, rim


M_GRASS = make_grass_mat()
M_BLADE = make_blade_mat()
M_GINGHAM = make_gingham_mat()
M_BERRY = make_berry_mat()
M_SEED = principled("M_strawberry_seed", hexcol('#FFEDB0'), rough=0.4, sss=0.1)
M_LEAF = principled("M_strawberry_leaf", hexcol('#4FB244'), rough=0.45, spec=0.4,
                    sss=0.15, sss_radius=(0.1, 0.3, 0.05), sheen=0.3)
M_STEM = principled("M_strawberry_stem", hexcol('#6FA03C'), rough=0.6)
M_PLATE_H_BODY, M_PLATE_H_RIM = make_plate_mat("M_plate_hani", '#6EC3F2')
M_PLATE_M_BODY, M_PLATE_M_RIM = make_plate_mat("M_plate_mako", '#23B3A4')
M_BOWL = principled("M_bowl_cream", hexcol('#FFF3DF'), rough=0.25, coat=0.35, sss=0.05)
M_BOWL_BAND = principled("M_bowl_apricot", hexcol('#F7A464'), rough=0.25, coat=0.35)
M_TRUNK = principled("M_tree_trunk", hexcol('#A27752'), rough=0.8)


# ----------------------------------------------------------------------------
# ground
# ----------------------------------------------------------------------------
def ground_z(x, y):
    """Flat picnic lawn; gentle rolling hills only far behind (y > 5)."""
    far = max(0.0, min(1.0, (y - 5.0) / 10.0))
    h = (0.5 + 0.5 * math.sin(x * 0.30 + 1.3)) * 0.6 + (0.5 + 0.5 * math.sin(x * 0.13 - 0.4)) * 0.8
    return h * far * 0.45 - 0.002


def build_ground():
    bm = bmesh.new()
    size, n = 60.0, 120
    bmesh.ops.create_grid(bm, x_segments=n, y_segments=n, size=size / 2)
    for v in bm.verts:
        x, y = v.co.x, v.co.y
        # gentle rolling hills only far behind the picnic
        v.co.z = ground_z(x, y)
    ob = mesh_from_bm("GROUND_grass", bm, C_GROUND)
    ob.data.materials.append(M_GRASS)
    return ob


def blanket_outline_dist(x, y):
    hx, hy = BLANKET_SIZE[0] / 2, BLANKET_SIZE[1] / 2
    lx, ly = x - BLANKET_CENTER[0], y - BLANKET_CENTER[1]
    return min(hx - abs(lx), hy - abs(ly))


def build_grass_blades():
    """Soft stylized grass tufts around (not under) the blanket."""
    bm = bmesh.new()
    col_layer = bm.loops.layers.color.new('col')
    greens = ['#62AA45', '#6FB34B', '#80BE52', '#5AA141', '#8BC458']
    rnd = random.Random(11)
    hx, hy = BLANKET_SIZE[0] / 2 + 0.03, BLANKET_SIZE[1] / 2 + 0.03
    count = 0
    tries = 0
    while count < 1100 and tries < 60000:
        tries += 1
        # denser near the camera side and around blanket, sparse far away
        x = rnd.uniform(-1.6, 1.6)
        y = rnd.uniform(-1.0, 1.5)
        lx, ly = x - BLANKET_CENTER[0], y - BLANKET_CENTER[1]
        if abs(lx) < hx and abs(ly) < hy:
            continue
        # a soft fringe hugging the blanket (contact), thinning out quickly
        ring = max(abs(lx) - hx, abs(ly) - hy)
        if rnd.random() > math.exp(-ring / 0.12):
            continue
        dist = math.hypot(x, y + 1.2)
        count += 1
        nb = rnd.randint(4, 7)
        tuft_h = rnd.uniform(0.028, 0.05) * (1.0 + 0.1 * min(dist, 4))
        base_col = Vector(hexcol(rnd.choice(greens))[:3])
        for k in range(nb):
            ang = rnd.uniform(0, 2 * math.pi)
            lean = rnd.uniform(0.15, 0.45)
            h = tuft_h * rnd.uniform(0.7, 1.15)
            w = h * rnd.uniform(0.32, 0.42)
            ox, oy = x + rnd.uniform(-0.012, 0.012), y + rnd.uniform(-0.012, 0.012)
            d = Vector((math.cos(ang), math.sin(ang), 0))
            perp = Vector((-d.y, d.x, 0))
            pts = []
            segs = 3
            for s in range(segs + 1):
                t = s / segs
                ww = w * (1 - t) ** 0.8 * 0.5
                c = Vector((ox, oy, 0)) + d * (lean * h * t * t) + Vector((0, 0, h * t * (1 - 0.25 * t * lean)))
                if s < segs:
                    pts.append((c - perp * ww, c + perp * ww))
                else:
                    pts.append((c,))
            verts = []
            for row in pts:
                verts.append([bm.verts.new(p) for p in row])
            for s in range(segs):
                a, bb = verts[s], verts[s + 1]
                if len(bb) == 1:
                    f = bm.faces.new((a[0], a[1], bb[0]))
                else:
                    f = bm.faces.new((a[0], a[1], bb[1], bb[0]))
                for loop in f.loops:
                    t = loop.vert.co.z / max(h, 1e-4)
                    c = base_col * (0.80 + 0.35 * t)
                    loop[col_layer] = (c.x, c.y, c.z, 1.0)
    ob = mesh_from_bm("GROUND_grass_tufts", bm, C_GROUND)
    ob.data.materials.append(M_BLADE)
    return ob


# ----------------------------------------------------------------------------
# blanket
# ----------------------------------------------------------------------------
def build_blanket():
    hx, hy = BLANKET_SIZE[0] / 2, BLANKET_SIZE[1] / 2
    nx, ny = 136, 110
    corner_r = 0.06
    bm = bmesh.new()
    edge_layer = bm.verts.layers.float.new('edge')
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            x = (u - 0.5) * 2 * hx
            y = (v - 0.5) * 2 * hy
            # rounded corners: map the corner square onto a quarter disc
            cx, cy = hx - corner_r, hy - corner_r
            if abs(x) > cx and abs(y) > cy:
                dx, dy = abs(x) - cx, abs(y) - cy
                m = max(dx, dy)
                ln = math.hypot(dx, dy)
                if ln > 1e-9:
                    dx, dy = dx / ln * m, dy / ln * m
                x = math.copysign(cx + dx, x)
                y = math.copysign(cy + dy, y)
            # hand-made, slightly irregular outline
            d_edge = min(hx - abs(x), hy - abs(y))
            k = max(0.0, 1.0 - d_edge / 0.12)
            x += k * 0.006 * math.sin(y * 9.0 + 1.0)
            y += k * 0.006 * math.sin(x * 7.0 + 2.0)
            # height: flat interior; soft rolled hem + lazy folds near the edges
            z = BLANKET_TOP
            hem = max(0.0, 1.0 - d_edge / 0.035)
            z += 0.0035 * math.sin(hem * math.pi * 0.5) ** 2
            fold = max(0.0, 1.0 - d_edge / 0.22) ** 2
            along = x if (hy - abs(y)) < (hx - abs(x)) else y
            z += fold * 0.010 * (0.5 + 0.5 * math.sin(along * 11.0 + 0.7)) * (0.6 + 0.4 * math.sin(along * 3.1))
            # edges sink a touch into the grass so the cloth hugs the ground
            z -= max(0.0, 1.0 - d_edge / 0.02) * 0.004
            # a couple of soft interior ripples away from plates/Hani/bowl
            for (wx, wy, wr, wa) in ((0.62, -0.35, 0.18, 0.008), (-0.62, -0.30, 0.20, 0.007),
                                     (0.62, 0.62, 0.2, 0.009), (-0.60, 0.66, 0.2, 0.006)):
                dd = math.hypot(x - wx + BLANKET_CENTER[0], y - (wy + BLANKET_CENTER[1]) + BLANKET_CENTER[1])
                if dd < wr:
                    z += wa * (0.5 + 0.5 * math.cos(math.pi * dd / wr)) * (0.5 + 0.5 * math.sin((x + y) * 26))
            vtx = bm.verts.new((x + BLANKET_CENTER[0], y + BLANKET_CENTER[1], z))
            vtx[edge_layer] = d_edge
            row.append(vtx)
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    ob = mesh_from_bm("SET_blanket", bm, C_PROPS)
    ob.data.materials.append(M_GINGHAM)
    sol = ob.modifiers.new("thickness", 'SOLIDIFY')
    sol.thickness = 0.004
    sol.offset = -1.0
    sol.use_even_offset = True
    return ob


# ----------------------------------------------------------------------------
# plates & bowl
# ----------------------------------------------------------------------------
def build_plate(name, center, body_mat, rim_mat):
    R = PLATE_R
    prof = [
        (0.0, PLATE_FLOOR), (0.060, PLATE_FLOOR), (0.088, PLATE_FLOOR + 0.0004),
        (0.100, PLATE_FLOOR + 0.0030), (0.112, 0.0115), (0.122, 0.0165),
        (0.1285, 0.0188), (R, 0.0172), (0.1295, 0.0150), (0.124, 0.0128),
        (0.108, 0.0080), (0.090, 0.0030), (0.080, 0.0008), (0.072, 0.0),
        (0.066, 0.0012), (0.0, 0.0012),
    ]

    def matfn(r, z):
        return 1 if (r > 0.1035 and z > 0.0070) else 0

    bm = bmesh.new()
    lathe(bm, prof, 72, matfn)
    ob = mesh_from_bm(name, bm, C_PROPS)
    ob.data.materials.append(body_mat)
    ob.data.materials.append(rim_mat)
    ob.location = (center[0], center[1], BLANKET_TOP)
    sub = ob.modifiers.new("smooth", 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 2
    return ob


def build_bowl():
    Rb, H, t = 0.085, 0.078, 0.0055
    outer = [(0.0, 0.0), (0.040, 0.0), (0.046, 0.002), (0.050, 0.006), (0.064, 0.016),
             (0.076, 0.032), (0.083, 0.050), (0.0855, 0.066), (0.0855, H - 0.002)]
    inner = [(0.0825, H - 0.002), (0.0798, 0.064), (0.0772, 0.049), (0.069, 0.032),
             (0.056, 0.019), (0.040, 0.0125), (0.0, 0.0105)]
    lip = [(0.0848, H)]
    prof = outer + lip + inner

    def matfn(r, z):
        # apricot band on the outer wall
        return 1 if (0.040 < z < 0.062 and r > 0.0805) else 0

    bm = bmesh.new()
    lathe(bm, prof, 64, matfn)
    ob = mesh_from_bm("SET_bowl", bm, C_PROPS)
    ob.data.materials.append(M_BOWL)
    ob.data.materials.append(M_BOWL_BAND)
    ob.location = (BOWL_POS[0], BOWL_POS[1], BLANKET_TOP)
    sub = ob.modifiers.new("smooth", 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 2
    return ob


# ----------------------------------------------------------------------------
# strawberry
# ----------------------------------------------------------------------------
BERRY_PROFILE = [  # (t, r/R, z/H)   r normalised to half-width, z to height
    (0.00, 0.00, 0.000),
    (0.05, 0.16, 0.006),
    (0.12, 0.30, 0.040),
    (0.25, 0.48, 0.160),
    (0.42, 0.74, 0.370),
    (0.58, 0.93, 0.580),
    (0.70, 1.00, 0.740),
    (0.80, 0.97, 0.860),
    (0.89, 0.80, 0.948),
    (0.95, 0.48, 0.988),
    (0.985, 0.15, 0.975),
    (1.00, 0.00, 0.955),
]


def berry_profile_samples(n=44):
    pts = catmull([(p[1], p[2]) for p in BERRY_PROFILE], n)
    pts[0] = (0.0, 0.0)
    pts[-1] = (0.0, BERRY_PROFILE[-1][2])
    return pts


def build_strawberry(name, rnd):
    R, H = BERRY_W / 2, BERRY_H
    prof = berry_profile_samples(44)
    segs = 40
    lobe_phase = rnd.uniform(0, 2 * math.pi)
    lobe_amp = rnd.uniform(0.018, 0.032)

    def radius_mod(theta, zn):
        return 1.0 + lobe_amp * math.cos(3 * theta + lobe_phase) * math.sin(math.pi * min(1, zn))

    bm = bmesh.new()
    rings = []
    for (rn, zn) in prof:
        if rn < 1e-6:
            rings.append([bm.verts.new((0, 0, zn * H))])
        else:
            ring = []
            for i in range(segs):
                th = 2 * math.pi * i / segs
                r = rn * R * radius_mod(th, zn)
                ring.append(bm.verts.new((r * math.cos(th), r * math.sin(th), zn * H)))
            rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            if len(a) == 1:
                bm.faces.new((a[0], b[j], b[i]))
            elif len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
        f.material_index = 0

    # analytic surface (for seeds and leaves)
    prof_dense = catmull([(p[1], p[2]) for p in BERRY_PROFILE], 400)

    def surf(tn, th):
        idx = tn * (len(prof_dense) - 1)
        k = min(int(idx), len(prof_dense) - 2)
        f = idx - k
        rn = prof_dense[k][0] * (1 - f) + prof_dense[k + 1][0] * f
        zn = prof_dense[k][1] * (1 - f) + prof_dense[k + 1][1] * f
        r = rn * R * radius_mod(th, zn)
        return Vector((r * math.cos(th), r * math.sin(th), zn * H))

    def frame(tn, th):
        p = surf(tn, th)
        dt = (surf(min(1, tn + 0.002), th) - surf(max(0, tn - 0.002), th)).normalized()
        dth = (surf(tn, th + 0.002) - surf(tn, th - 0.002)).normalized()
        n = dth.cross(dt).normalized()
        if n.dot(Vector((p.x, p.y, 0))) < 0:
            n = -n
        return p, n, dt, dth

    # --- seeds: staggered rows, pale, slightly sunk into little dimples
    seed_rows = [0.16, 0.25, 0.34, 0.43, 0.52, 0.61, 0.70]
    for ri, tn in enumerate(seed_rows):
        p0, _, _, _ = frame(tn, 0)
        circ = 2 * math.pi * math.hypot(p0.x, p0.y)
        n_seeds = max(5, int(circ / 0.0105))
        off = (ri % 2) * 0.5 + rnd.uniform(-0.1, 0.1)
        for s in range(n_seeds):
            th = 2 * math.pi * (s + off) / n_seeds + rnd.uniform(-0.05, 0.05)
            tt = tn + rnd.uniform(-0.012, 0.012)
            p, n, dt, dth = frame(tt, th)
            sc = rnd.uniform(0.9, 1.1)
            mat = Matrix((dth * 0.0013 * sc, dt * 0.0021 * sc, n * 0.0009)).transposed()
            res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            for v in res['verts']:
                v.co = p + n * 0.00025 + mat @ v.co
            for f in {f for v in res['verts'] for f in v.link_faces}:
                f.material_index = 1
                f.smooth = True

    # --- leafy cap: 6 pointed leaves draped over the shoulders
    top_z = BERRY_PROFILE[-1][2] * H
    # radial distance -> shoulder height (upper half of profile)
    upper = [(p[0] * R, p[1] * H) for p in prof_dense if p[1] > 0.7]
    upper.sort()

    def shoulder_z(d):
        for (r0, z0), (r1, z1) in zip(upper[:-1], upper[1:]):
            if r0 <= d <= r1:
                f = (d - r0) / max(r1 - r0, 1e-9)
                return z0 * (1 - f) + z1 * f
        return upper[-1][1] if d > upper[-1][0] else upper[0][1]

    n_leaves = 6
    rot0 = rnd.uniform(0, 2 * math.pi)
    for k in range(n_leaves):
        ang = rot0 + 2 * math.pi * k / n_leaves + rnd.uniform(-0.15, 0.15)
        L = rnd.uniform(0.0175, 0.0215)
        W = rnd.uniform(0.0058, 0.0072)
        dirv = Vector((math.cos(ang), math.sin(ang), 0))
        perp = Vector((-dirv.y, dirv.x, 0))
        ns, nw = 10, 6
        grid = []
        for i in range(ns + 1):
            s = i / ns
            hw = W * (math.sin(math.pi * min(1.0, s ** 0.8)) ** 0.85) * (1 - s ** 6) + 0.0004
            row = []
            for j in range(nw + 1):
                w = (j / nw) * 2 - 1
                d = 0.0015 + s * L
                base = dirv * d + perp * (w * hw)
                dd = math.hypot(base.x, base.y)
                z = shoulder_z(min(dd, R * 0.99)) + 0.0010
                z += 0.0011 * (1 - w * w)          # cupped leaf, raised midrib
                z += 0.0030 * s ** 3               # tips lift a touch (cute curl)
                if s < 0.2:
                    z = max(z, top_z + 0.0012 * (1 - s / 0.2))
                row.append(bm.verts.new((base.x, base.y, z)))
            grid.append(row)
        for i in range(ns):
            for j in range(nw):
                f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
                f.material_index = 2
                f.smooth = True

    # small calyx dome covering the leaf roots
    res = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    for v in res['verts']:
        v.co = Vector((v.co.x * 0.0052, v.co.y * 0.0052, max(v.co.z, -0.2) * 0.0026 + top_z + 0.0008))
    for f in {f for v in res['verts'] for f in v.link_faces}:
        f.material_index = 2
        f.smooth = True
    # stem: short curved tube
    lean = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized()
    stem_rings = []
    for i in range(6):
        s = i / 5
        c = Vector((0, 0, top_z + 0.0015 + s * 0.0085)) + lean * (0.0025 * s * s)
        r = 0.0014 * (1 - 0.25 * s)
        stem_rings.append([bm.verts.new(c + Vector((r * math.cos(a), r * math.sin(a), 0)))
                           for a in [2 * math.pi * q / 8 for q in range(8)]])
    for a, b in zip(stem_rings[:-1], stem_rings[1:]):
        for i in range(8):
            j = (i + 1) % 8
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.material_index = 3
            f.smooth = True
    capv = bm.faces.new(stem_rings[-1])
    capv.material_index = 3
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.material_index == 3])

    ob = mesh_from_bm(name, bm, C_BERRIES, smooth=False)
    for m in (M_BERRY, M_SEED, M_LEAF, M_STEM):
        ob.data.materials.append(m)
    return ob


# ----------------------------------------------------------------------------
# background: rounded metaball trees and bushes, soft sky
# ----------------------------------------------------------------------------
HAZE = hexcol('#DDEBE0')


def tree_mat(name, hexc, haze=0.0):
    c = hexcol(hexc)
    c = tuple(c[i] * (1 - haze) + HAZE[i] * haze for i in range(3)) + (1.0,)
    return principled(name, c, rough=0.75, spec=0.25, sss=0.08,
                      sss_radius=(0.2, 0.4, 0.1), sheen=0.12)


def haze_for(y):
    # gentle aerial perspective: further things drift toward a warm pale haze
    return max(0.0, min(0.35, (y - 2.0) / 24.0))


def metaball_blob(name, balls, mat, coll, resolution=0.08):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = resolution
    mb.render_resolution = resolution * 0.6
    mb.threshold = 0.6
    for (p, r) in balls:
        e = mb.elements.new()
        e.co = p
        e.radius = r
    ob = bpy.data.objects.new(name, mb)
    coll.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def build_background():
    rnd = random.Random(3)
    greens = ['#6EC255', '#8ED05E', '#5DB35A', '#9BD468', '#72C474']
    bush_greens = ['#66AE52', '#80C060', '#5A9F50']
    trees = [  # x, y, canopy radius, height
        # near layer: frames the shot at the sides (canopies cropped by the frame)
        (-3.0, 6.0, 1.15, 2.0), (3.4, 6.6, 1.2, 2.1), (-5.6, 8.6, 1.4, 2.3), (6.4, 8.4, 1.4, 2.3),
        # far layer: small, hazy, round lollipop tops fully visible above the bushes
        (-1.7, 16.0, 1.2, 1.55), (1.3, 18.5, 1.35, 1.7), (3.9, 15.5, 1.15, 1.5),
        (-4.3, 18.0, 1.35, 1.7), (-0.1, 22.0, 1.5, 1.9), (6.6, 19.0, 1.4, 1.8),
        (-7.2, 15.0, 1.3, 1.6), (9.5, 14.0, 1.3, 1.7)
    ]
    for idx, (x, y, cr, h) in enumerate(trees):
        z0 = ground_z(x, y) - 0.05
        # trunk
        bm = bmesh.new()
        prof = [(0.0, 0.0), (0.16, 0.0), (0.11, 0.25), (0.085, h * 0.55), (0.06, h * 0.8), (0.0, h * 0.8)]
        lathe(bm, prof, 12)
        tr = mesh_from_bm("BG_tree_trunk_%02d" % idx, bm, C_BG)
        tc_ = hexcol('#B08562')
        hz = haze_for(y)
        tr.data.materials.append(principled("M_trunk_%02d" % idx, tuple(tc_[i] * (1 - hz) + HAZE[i] * hz for i in range(3)) + (1,), rough=0.8))
        tr.location = (x, y, z0)
        # canopy (metaball clusters -> soft cloud-like silhouettes)
        balls = [((0, 0, 0), cr)]
        for k in range(6):
            a = rnd.uniform(0, 2 * math.pi)
            d = cr * rnd.uniform(0.45, 0.75)
            balls.append(((math.cos(a) * d, math.sin(a) * d * 0.6, rnd.uniform(-0.25, 0.45) * cr),
                          cr * rnd.uniform(0.55, 0.8)))
        balls.append(((0, 0, cr * 0.6), cr * 0.7))
        cn = metaball_blob("BGcanopy%02d" % idx, balls,
                           tree_mat("M_foliage_%02d" % idx, greens[idx % len(greens)], haze_for(y)),
                           C_BG, resolution=0.12)
        cn.location = (x, y, z0 + h)
    bushes = [  # x, y, size
        (-2.2, 2.9, 0.55), (-1.3, 3.3, 0.45), (-0.2, 3.8, 0.5), (1.2, 3.2, 0.5),
        (2.1, 2.8, 0.6), (3.2, 3.6, 0.5), (-3.3, 3.4, 0.6), (0.6, 4.4, 0.45),
    ]
    for idx, (x, y, s) in enumerate(bushes):
        balls = [((0, 0, s * 0.25), s)]
        for k in range(4):
            a = rnd.uniform(0, 2 * math.pi)
            balls.append(((math.cos(a) * s * 0.8, math.sin(a) * s * 0.35, rnd.uniform(0.0, 0.3) * s),
                          s * rnd.uniform(0.55, 0.8)))
        metaball_blob("BGbush%02d" % idx, balls, tree_mat("M_bush_%02d" % idx, bush_greens[idx % 3], haze_for(y) * 0.7),
                      C_BG, resolution=0.06).location = (x, y, ground_z(x, y))


def build_flowers():
    """A few small white daisies with butter-yellow centres (nothing red/berry-like)."""
    petal = principled("M_daisy_petal", hexcol('#FFFDF6'), rough=0.5, sss=0.2, sheen=0.3)
    centre = principled("M_daisy_centre", hexcol('#FFC94A'), rough=0.6)
    stemm = principled("M_daisy_stem", hexcol('#6FAE4C'), rough=0.6)
    rnd = random.Random(5)
    bm = bmesh.new()
    spots = []
    hx, hy = BLANKET_SIZE[0] / 2 + 0.08, BLANKET_SIZE[1] / 2 + 0.08
    clumps = [(-1.0, -0.62), (1.05, -0.65), (-1.15, 0.95), (1.1, 1.05), (-0.55, 1.15),
              (0.45, 1.25), (-1.7, 1.7), (1.5, 0.25), (-1.4, 0.2), (-0.9, 2.1), (0.8, 2.2),
              (1.9, 1.9), (-2.1, 1.0), (0.1, 2.6), (-0.3, 1.6), (1.3, 1.6)]
    for (cx, cy) in clumps:
        # leafy rosette at the base of each clump
        for k in range(7):
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(0.02, 0.07)
            lx, ly = cx + math.cos(a) * d, cy + math.sin(a) * d
            if abs(lx - BLANKET_CENTER[0]) < hx and abs(ly - BLANKET_CENTER[1]) < hy:
                continue
            res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0)
            rotz = Matrix.Rotation(a, 3, 'Z')
            for v in res['verts']:
                v.co = Vector((lx, ly, 0.0)) + rotz @ Vector((v.co.x * 0.032, v.co.y * 0.014, max(v.co.z, -0.3) * 0.006))
            for f in {f for v in res['verts'] for f in v.link_faces}:
                f.material_index = 3
                f.smooth = True
        for k in range(rnd.randint(3, 5)):
            x, y = cx + rnd.uniform(-0.09, 0.09), cy + rnd.uniform(-0.09, 0.09)
            if abs(x - BLANKET_CENTER[0]) < hx and abs(y - BLANKET_CENTER[1]) < hy:
                continue
            spots.append((x, y))
    for (x, y) in spots:
        h = rnd.uniform(0.035, 0.07)
        tilt = Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 1)).normalized()
        top = Vector((x, y, 0)) + tilt * h
        # stem
        rings = []
        for i in range(4):
            c = Vector((x, y, 0)).lerp(top, i / 3)
            rings.append([bm.verts.new(c + Vector((0.0022 * math.cos(a), 0.0022 * math.sin(a), 0)))
                          for a in [2 * math.pi * q / 6 for q in range(6)]])
        for a, b in zip(rings[:-1], rings[1:]):
            for i in range(6):
                f = bm.faces.new((a[i], a[(i + 1) % 6], b[(i + 1) % 6], b[i]))
                f.material_index = 2
        # petals
        np_ = 10
        rad = rnd.uniform(0.024, 0.032)
        rot = Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z')
        up = tilt
        q = Vector((0, 0, 1)).rotation_difference(up).to_matrix()
        for k in range(np_):
            a = 2 * math.pi * k / np_
            d = rot @ Vector((math.cos(a), math.sin(a), 0))
            pp = rot @ Vector((-math.sin(a), math.cos(a), 0))
            vs = []
            for (s, w) in ((0.15, 0.0), (0.4, 0.42), (0.8, 0.46), (1.0, 0.0), (0.8, -0.46), (0.4, -0.42)):
                loc = d * (rad * s) + pp * (rad * 0.32 * w) + Vector((0, 0, 0.004 * s * s * -1 + 0.002))
                vs.append(bm.verts.new(top + q @ loc))
            f = bm.faces.new(vs)
            f.material_index = 0
        res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0)
        for v in res['verts']:
            v.co = top + q @ Vector((v.co.x * 0.0065, v.co.y * 0.0065, v.co.z * 0.0035 + 0.002))
        for f in {f for v in res['verts'] for f in v.link_faces}:
            f.material_index = 1
    ob = mesh_from_bm("SET_daisies", bm, C_GROUND)
    leafm = principled("M_daisy_leaf", hexcol('#4F9A3C'), rough=0.6, sheen=0.3)
    for m in (petal, centre, stemm, leafm):
        ob.data.materials.append(m)


def build_basket(pos):
    """Small wicker picnic basket with a lid and an arched handle (warm tan)."""
    mat = bpy.data.materials.new("M_basket_wicker")
    b = NB(mat)
    tc = b.n('ShaderNodeTexCoord')
    w1 = b.n('ShaderNodeTexWave', _wave_type='BANDS', _bands_direction='Z', Scale=38.0, Distortion=0.6)
    b.link(tc.outputs['Object'], w1.inputs['Vector'])
    w2 = b.n('ShaderNodeTexWave', _wave_type='RINGS', _rings_direction='Z', Scale=60.0)
    b.link(tc.outputs['Object'], w2.inputs['Vector'])
    m = b.n('ShaderNodeMath', _operation='MULTIPLY')
    b.link(w1.outputs['Fac'], m.inputs[0])
    b.link(w2.outputs['Fac'], m.inputs[1])
    ramp = b.n('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = hexcol('#B07A43')
    ramp.color_ramp.elements[1].color = hexcol('#E6B878')
    b.link(m.outputs[0], ramp.inputs['Fac'])
    bump = b.n('ShaderNodeBump', Strength=0.5, Distance=0.002)
    b.link(m.outputs[0], bump.inputs['Height'])
    bsdf = b.n('ShaderNodeBsdfPrincipled', Roughness=0.7)
    b.set(bsdf, 'Sheen Weight', 0.3)
    b.link(ramp.outputs[0], bsdf.inputs['Base Color'])
    b.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    out = b.n('ShaderNodeOutputMaterial')
    b.link(bsdf.outputs[0], out.inputs[0])
    lidm = principled("M_basket_lid_cloth", hexcol('#9FD3E8'), rough=0.85, sheen=0.6)
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.105, 0.0), (0.118, 0.01), (0.13, 0.06), (0.138, 0.112), (0.142, 0.118),
            (0.132, 0.12), (0.0, 0.12)]
    lathe(bm, prof, 48)
    # soft cloth lid (pale sky-blue napkin) bulging on top
    lid = [(0.0, 0.152), (0.07, 0.146), (0.12, 0.135), (0.148, 0.122), (0.150, 0.114), (0.0, 0.114)]
    n0 = len(bm.faces)
    lathe(bm, lid, 48)
    for f in list(bm.faces)[n0:]:
        f.material_index = 1
    # handle: half torus arch over the lid
    res = bmesh.ops.create_circle(bm, cap_ends=False, segments=10, radius=0.008)
    ring = res['verts']
    arc = []
    for i in range(25):
        a = math.pi * i / 24
        c = Vector((math.cos(a) * 0.128, 0.0, 0.12 + math.sin(a) * 0.12))
        tang = Vector((-math.sin(a), 0.0, math.cos(a)))
        q = Vector((0, 0, 1)).rotation_difference(tang).to_matrix()
        arc.append([bm.verts.new(c + q @ v.co) for v in ring])
    for v in ring:
        bm.verts.remove(v)
    for a_, b_ in zip(arc[:-1], arc[1:]):
        for i in range(10):
            bm.faces.new((a_[i], a_[(i + 1) % 10], b_[(i + 1) % 10], b_[i]))
    ob = mesh_from_bm("SET_basket", bm, C_PROPS)
    ob.data.materials.append(mat)
    ob.data.materials.append(lidm)
    ob.location = (pos[0], pos[1], BLANKET_TOP)
    ob.rotation_euler = (0, 0, math.radians(-25))
    sub = ob.modifiers.new("smooth", 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 2
    return ob


# ----------------------------------------------------------------------------
# world / lights / camera / render settings
# ----------------------------------------------------------------------------
def build_world():
    world = bpy.data.worlds.new("W_soft_sky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = hexcol('#F6EBD2')     # below horizon: warm ground bounce
    cr.elements[1].position = 0.5
    cr.elements[1].color = hexcol('#FFF2DA')     # horizon: warm cream glow
    e = cr.elements.new(0.535)
    e.color = hexcol('#F4F1E2')
    e = cr.elements.new(0.585)
    e.color = hexcol('#ADDAF6')                  # soft sky blue already low in the frame
    e = cr.elements.new(1.0)
    e.color = hexcol('#69B2EA')                  # zenith
    mr = nt.nodes.new('ShaderNodeMapRange')
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mr.inputs['From Min'].default_value = -1.0
    mr.inputs['From Max'].default_value = 1.0
    nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
    bg = nt.nodes.new('ShaderNodeBackground')          # what lights the scene
    bg.inputs['Strength'].default_value = 0.32
    nt.links.new(ramp.outputs[0], bg.inputs['Color'])
    bgc = nt.nodes.new('ShaderNodeBackground')         # what the camera sees (brighter, airy)
    bgc.inputs['Strength'].default_value = 2.3
    nt.links.new(ramp.outputs[0], bgc.inputs['Color'])
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(bgc.outputs[0], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(mix.outputs[0], out.inputs[0])
    world['sky_strength_node'] = bg.name


def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def build_lights():
    # KEY: warm late-morning sun from front-left, soft angular size -> soft shadows
    sun_d = bpy.data.lights.new("KEY_sun", 'SUN')
    sun_d.energy = 5.2
    sun_d.color = (1.0, 0.84, 0.66)
    sun_d.angle = math.radians(9.0)
    sun_d.use_shadow = True
    sun_d.use_shadow_jitter = True       # true soft penumbra (accumulated over TAA samples)
    sun_d.shadow_jitter_overblur = 10.0
    sun = bpy.data.objects.new("KEY_sun", sun_d)
    C_LIGHTS.objects.link(sun)
    sun.location = (-2.6, -2.0, 2.6)
    aim(sun, (0.0, 0.2, 0.0))
    # FILL: big soft area from camera-right, slightly cooler, low intensity
    fill_d = bpy.data.lights.new("FILL_area", 'AREA')
    fill_d.shape = 'DISK'
    fill_d.size = 2.6
    fill_d.energy = 14.0
    fill_d.color = (0.93, 0.96, 1.0)
    fill_d.use_shadow = True
    fill_d.specular_factor = 0.4
    fill = bpy.data.objects.new("FILL_area", fill_d)
    C_LIGHTS.objects.link(fill)
    fill.location = (1.9, -1.7, 1.1)
    aim(fill, (0.0, 0.15, 0.2))
    # RIM: warm peach back light (catches hair bun / berry tops / plate rims)
    rim_d = bpy.data.lights.new("RIM_area", 'AREA')
    rim_d.shape = 'DISK'
    rim_d.size = 1.4
    rim_d.energy = 55.0
    rim_d.color = (1.0, 0.80, 0.62)
    rim = bpy.data.objects.new("RIM_area", rim_d)
    C_LIGHTS.objects.link(rim)
    rim.location = (1.1, 1.9, 1.3)
    aim(rim, (-0.15, 0.3, 0.35))
    # BOUNCE: low warm area under camera simulating light reflected off the blanket
    b_d = bpy.data.lights.new("BOUNCE_area", 'AREA')
    b_d.size = 1.2
    b_d.energy = 8.0
    b_d.color = (1.0, 0.88, 0.76)
    b_d.use_shadow = False
    b_d.specular_factor = 0.0
    bo = bpy.data.objects.new("BOUNCE_area", b_d)
    C_LIGHTS.objects.link(bo)
    bo.location = (-0.1, -0.6, 0.08)
    aim(bo, (-0.18, 0.33, 0.45))
    # KICKER: specular-only small light near camera-left -> crisp glossy highlights
    # on strawberries/plates (and catch-lights in Hani's eyes)
    k_d = bpy.data.lights.new("SPEC_kicker", 'AREA')
    k_d.size = 0.25
    k_d.energy = 30.0
    k_d.color = (1.0, 0.95, 0.88)
    k_d.diffuse_factor = 0.0
    k_d.specular_factor = 1.0
    k_d.use_shadow = False
    ki = bpy.data.objects.new("SPEC_kicker", k_d)
    C_LIGHTS.objects.link(ki)
    ki.location = (-0.55, -1.0, 0.9)
    aim(ki, (0.0, 0.0, 0.03))


def make_camera(name, loc, target, lens, focus_obj=None, fstop=2.8):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start = 0.02
    cd.clip_end = 200.0
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cam = bpy.data.objects.new(name, cd)
    C_CAMS.objects.link(cam)
    cam.location = loc
    aim(cam, target)
    if focus_obj:
        cd.dof.focus_object = focus_obj
    return cam


def setup_render():
    r = scene.render
    r.engine = 'BLENDER_EEVEE_NEXT'
    r.resolution_x, r.resolution_y = 1920, 1080
    r.resolution_percentage = 100
    r.fps = 30
    r.film_transparent = False
    r.filter_size = 1.5
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    e = scene.eevee
    e.taa_render_samples = 32
    e.taa_samples = 8
    e.use_shadows = True
    e.shadow_ray_count = 1
    e.shadow_step_count = 8
    e.use_raytracing = True
    e.ray_tracing_method = 'SCREEN'
    e.use_fast_gi = True
    e.fast_gi_method = 'GLOBAL_ILLUMINATION'
    e.fast_gi_distance = 0.6
    e.fast_gi_quality = 0.5
    e.use_gtao = True
    e.use_bokeh_jittered = True      # accumulate DOF over TAA samples: no halos around canopies
    e.bokeh_overblur = 2.0
    e.gtao_distance = 0.25
    e.gtao_quality = 0.5
    try:
        e.ray_tracing_options.resolution_scale = '2'
    except Exception:
        pass
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    for look in ('AgX - Punchy', 'AgX - Medium High Contrast', 'None'):  # punchy keeps berry red saturated
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = -0.45
    vs.gamma = 1.0
    # slightly warm grade: tell the view the scene's white is a bit bluer than D65
    vs.use_white_balance = True
    vs.white_balance_temperature = 7600.0
    vs.white_balance_tint = 4.0
    scene.display_settings.display_device = 'sRGB'
    scene.sequencer_colorspace_settings.name = 'sRGB'


def setup_compositor():
    """Gentle bloom + soft vignette for the warm storybook feel."""
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    glare = nt.nodes.new('CompositorNodeGlare')
    glare.glare_type = 'BLOOM' if 'BLOOM' in [i.identifier for i in glare.bl_rna.properties['glare_type'].enum_items] else 'FOG_GLOW'
    glare.quality = 'MEDIUM'
    try:
        glare.threshold = 0.85
        glare.mix = -0.82
        glare.size = 8
    except Exception:
        pass
    for key, val in (('Threshold', 3.0), ('Strength', 0.15), ('Size', 0.5)):  # only specular glints bloom (not the sky)
        if key in glare.inputs:
            glare.inputs[key].default_value = val
    nt.links.new(rl.outputs['Image'], glare.inputs['Image'])
    # vignette
    ell = nt.nodes.new('CompositorNodeEllipseMask')
    ell.width, ell.height = 1.25, 1.15
    blur = nt.nodes.new('CompositorNodeBlur')
    blur.filter_type = 'FAST_GAUSS'
    blur.use_relative = True
    blur.factor_x = blur.factor_y = 25.0
    try:
        blur.size_x = blur.size_y = 300
    except Exception:
        pass
    nt.links.new(ell.outputs['Mask'], blur.inputs['Image'])
    mr = nt.nodes.new('CompositorNodeMapRange')
    nt.links.new(blur.outputs['Image'], mr.inputs['Value'])
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 0.32     # corners: gentle warm darkening
    mr.inputs['To Max'].default_value = 0.0      # centre: untouched
    mul = nt.nodes.new('CompositorNodeMixRGB')
    mul.blend_type = 'MULTIPLY'
    nt.links.new(mr.outputs['Value'], mul.inputs['Fac'])
    nt.links.new(glare.outputs['Image'], mul.inputs[1])
    mul.inputs[2].default_value = hexcol('#D9B08C')
    hs = nt.nodes.new('CompositorNodeHueSat')        # a touch more colour for the preschool palette
    nt.links.new(mul.outputs['Image'], hs.inputs['Image'])
    hs.inputs['Saturation'].default_value = 1.1
    comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(hs.outputs['Image'], comp.inputs['Image'])
    vw = nt.nodes.new('CompositorNodeViewer')
    nt.links.new(hs.outputs['Image'], vw.inputs['Image'])
    scene['vignette_node'] = mul.name


# ----------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------
build_ground()
if USE_GRASS_TUFTS:
    build_grass_blades()
build_blanket()
build_flowers()
plate_h = build_plate("PLATE_hani", PLATE_H, M_PLATE_H_BODY, M_PLATE_H_RIM)
plate_m = build_plate("PLATE_mako", PLATE_M, M_PLATE_M_BODY, M_PLATE_M_RIM)
build_bowl()
build_basket(BASKET_POS)
build_background()

# slots (empties, world space, parented to plates so they travel with them)
slots = {}
for i, dx in enumerate(SLOT_DX_H):
    slots["slot_H%d" % i] = (PLATE_H[0] + dx, PLATE_H[1], SLOT_Z)
for i, dx in enumerate(SLOT_DX_M):
    slots["slot_M%d" % i] = (PLATE_M[0] + dx, PLATE_M[1], SLOT_Z)
for name, loc in slots.items():
    em = bpy.data.objects.new(name, None)
    em.empty_display_type = 'SINGLE_ARROW'
    em.empty_display_size = 0.03
    C_SLOTS.objects.link(em)
    plate = plate_h if name.startswith("slot_H") else plate_m
    em.parent = plate                       # identity parent-inverse: location is plate-local
    em.location = (loc[0] - plate.location.x, loc[1] - plate.location.y, loc[2] - plate.location.z)

# strawberries in the start state: Hani S1..S4 on H0..H3, Mako S5,S6 on M1,M2
start_state = {"S1": "slot_H0", "S2": "slot_H1", "S3": "slot_H2", "S4": "slot_H3",
               "S5": "slot_M1", "S6": "slot_M2"}
rnd = random.Random(42)
for sname, slot in start_state.items():
    ob = build_strawberry(sname, rnd)
    ob.location = slots[slot]
    # tiny organic variation: yaw + forward/back tilt only (never sideways -> no overlap)
    ob.rotation_euler = Euler((math.radians(rnd.uniform(-5, 5)), 0.0, rnd.uniform(0, 2 * math.pi)), 'XYZ')
    s = rnd.uniform(0.97, 1.0)
    ob.scale = (s, s, s)
    ob["start_slot"] = slot

# Hani placement guide (empty only; the character is built elsewhere)
hs = bpy.data.objects.new("HANI_spot", None)
hs.empty_display_type = 'ARROWS'
hs.empty_display_size = 0.15
hs.location = HANI_SPOT
hs.rotation_euler = (0, 0, 0)    # character faces -Y (toward camera)
C_GUIDES.objects.link(hs)
look = bpy.data.objects.new("LOOK_plates", None)
look.empty_display_type = 'SPHERE'
look.empty_display_size = 0.02
look.location = (0.0, 0.0, 0.03)
C_GUIDES.objects.link(look)

build_world()
build_lights()
focus = bpy.data.objects.new("FOCUS_main", None)
focus.location = (-0.10, 0.17, 0.20)   # between plates and Hani's face: both stay crisp
C_GUIDES.objects.link(focus)
cam = make_camera("CAM_main", (0.03, -1.30, 0.50), (0.0, 0.20, 0.30), 32.0, focus, fstop=2.8)
scene.camera = cam
focus_d = bpy.data.objects.new("FOCUS_detail", None)
focus_d.location = (0.0, 0.0, 0.03)
C_GUIDES.objects.link(focus_d)
make_camera("CAM_detail", (0.0, -0.66, 0.40), (0.0, 0.035, 0.02), 40.0, focus_d, fstop=4.0)

setup_render()
setup_compositor()

# record the layout on the scene for downstream scripts
scene["slots"] = {k: list(v) for k, v in slots.items()}
scene["hani_spot"] = list(HANI_SPOT)
scene["blanket_top"] = BLANKET_TOP
scene.frame_start, scene.frame_end = 1, 1

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
print("SAVED", OUT_BLEND)
for k, v in slots.items():
    print("SLOT", k, tuple(round(c, 4) for c in v))
