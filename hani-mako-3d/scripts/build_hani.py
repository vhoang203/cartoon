"""
build_hani.py -- procedural build of HANI (Hani & Mako, Phase 0).

Run (headless, ~1-2 min):
    blender -b --python /home/user/cartoon/hani-mako-3d/scripts/build_hani.py
Produces:
    /home/user/cartoon/hani-mako-3d/assets/hani.blend

Everything is generated here from code: meshes, metaball-derived limbs, curl geometry,
materials, armature `Hani_rig`, face shape keys and the pose actions. No external assets.
Units metres, Z up, Hani faces -Y (towards a camera that looks along +Y). Character's
left (.L) is +X (screen right in a front view).
See docs/hani_rig.md for the animator-facing interface.
"""
import bpy, bmesh, math, random, os, time
import numpy as np
from mathutils import Vector, Matrix, Quaternion, noise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "hani.blend")
T0 = time.time()


def log(*a):
    print(f"[hani {time.time()-T0:6.1f}s]", *a, flush=True)


# ----------------------------------------------------------------------------- utils
def V(*a):
    return Vector(a)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0)) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3 - 2 * t)


def srgb(r, g, b, a=1.0):
    def c(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c(r), c(g), c(b), a)


def orthonormal(t):
    t = t.normalized()
    a = V(0, 0, 1) if abs(t.z) < 0.9 else V(1, 0, 0)
    n = (a - t * a.dot(t)).normalized()
    return n, t.cross(n)


class Geo:
    """Accumulates a multi-part mesh with material indices, weights and float attrs."""

    def __init__(self):
        self.v, self.f, self.fm = [], [], []
        self.wconst = []   # (start, end, {bone: w})
        self.wvar = {}     # vid -> {bone: w}
        self.fattr = {}    # name -> {vid: value}

    def add(self, verts, faces, mat=0, weights=None, attrs=None):
        o = len(self.v)
        self.v.extend(verts)
        self.f.extend([tuple(i + o for i in f) for f in faces])
        self.fm.extend([mat] * len(faces))
        if isinstance(weights, dict):
            self.wconst.append((o, o + len(verts), weights))
        elif isinstance(weights, list):
            for i, w in enumerate(weights):
                self.wvar[o + i] = w
        if attrs:
            for k, val in attrs.items():
                d = self.fattr.setdefault(k, {})
                if isinstance(val, (list, tuple)):
                    for i, x in enumerate(val):
                        d[o + i] = x
                else:
                    for i in range(len(verts)):
                        d[o + i] = val
        return o


def make_object(name, geo, mats, coll, smooth=True, subsurf=0, subsurf_render=None, crease=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in geo.v], [], geo.f)
    me.validate(clean_customdata=False)
    me.update()
    for m in mats:
        me.materials.append(m)
    if geo.fm and len(geo.fm) == len(me.polygons):
        me.polygons.foreach_set("material_index", geo.fm)
    if smooth:
        me.shade_smooth()
    for k, d in geo.fattr.items():
        at = me.attributes.new(k, 'FLOAT', 'POINT')
        vals = [0.0] * len(me.vertices)
        for i, x in d.items():
            vals[i] = x
        at.data.foreach_set('value', vals)
    if crease:
        ca = me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
        cs = set(frozenset(e) for e in crease)
        vals = [0.0] * len(me.edges)
        for e in me.edges:
            if frozenset(e.vertices) in cs:
                vals[e.index] = 0.9
        ca.data.foreach_set('value', vals)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    # vertex groups
    groups = {}

    def grp(b):
        if b not in groups:
            groups[b] = ob.vertex_groups.new(name=b)
        return groups[b]
    for (s, e, wd) in geo.wconst:
        for b, w in wd.items():
            grp(b).add(list(range(s, e)), w, 'REPLACE')
    byb = {}
    for vid, wd in geo.wvar.items():
        tot = sum(wd.values()) or 1.0
        for b, w in wd.items():
            if w / tot > 1e-4:
                byb.setdefault(b, {}).setdefault(round(w / tot, 3), []).append(vid)
    for b, dd in byb.items():
        g = grp(b)
        for w, ids in dd.items():
            g.add(ids, w, 'REPLACE')
    if subsurf:
        m = ob.modifiers.new("Subsurf", 'SUBSURF')
        m.levels = subsurf
        m.render_levels = subsurf_render if subsurf_render is not None else subsurf
    return ob


def tube(pts, radii, ring=8, cap_end=True, cap_start=False, cap_rings=3):
    """Tube along polyline with parallel-transport frames; returns verts, faces, per-vertex param."""
    n = len(pts)
    T = []
    for i in range(n):
        d = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        T.append(d.normalized() if d.length > 1e-9 else V(0, 0, 1))
    N, _ = orthonormal(T[0])
    frames = []
    for i in range(n):
        if i > 0:
            ax = T[i - 1].cross(T[i])
            if ax.length > 1e-9:
                ang = T[i - 1].angle(T[i])
                N = Matrix.Rotation(ang, 3, ax.normalized()) @ N
            N = (N - T[i] * N.dot(T[i])).normalized()
        frames.append((N, T[i].cross(N)))
    rings = []  # (center, radius, N, B, param)
    if cap_start:
        for k in range(cap_rings, 0, -1):
            a = k / (cap_rings + 1) * math.pi / 2
            rings.append((pts[0] - T[0] * radii[0] * math.sin(a), radii[0] * math.cos(a), frames[0][0], frames[0][1], 0.0))
    for i in range(n):
        rings.append((pts[i], radii[i], frames[i][0], frames[i][1], i / max(1, n - 1)))
    if cap_end:
        for k in range(1, cap_rings + 1):
            a = k / (cap_rings + 1) * math.pi / 2
            rings.append((pts[-1] + T[-1] * radii[-1] * math.sin(a), radii[-1] * math.cos(a), frames[-1][0], frames[-1][1], 1.0))
    verts, faces, param = [], [], []
    cs = [(math.cos(2 * math.pi * j / ring), math.sin(2 * math.pi * j / ring)) for j in range(ring)]
    for (c, r, Nn, Bn, pr) in rings:
        for (ca, sa) in cs:
            verts.append(c + (Nn * ca + Bn * sa) * r)
            param.append(pr)
    nr = len(rings)
    for i in range(nr - 1):
        for j in range(ring):
            j2 = (j + 1) % ring
            faces.append((i * ring + j, i * ring + j2, (i + 1) * ring + j2, (i + 1) * ring + j))
    if cap_end:
        tip = len(verts)
        verts.append(pts[-1] + T[-1] * radii[-1])
        param.append(1.0)
        b = (nr - 1) * ring
        for j in range(ring):
            faces.append((b + j, b + (j + 1) % ring, tip))
    if cap_start:
        tip = len(verts)
        verts.append(pts[0] - T[0] * radii[0])
        param.append(0.0)
        for j in range(ring):
            faces.append(((j + 1) % ring, j, tip))
    return verts, faces, param


def path_frames(pts):
    n = len(pts)
    T = []
    for i in range(n):
        d = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        T.append(d.normalized() if d.length > 1e-9 else V(0, 0, 1))
    N, _ = orthonormal(T[0])
    out = []
    for i in range(n):
        if i > 0:
            ax = T[i - 1].cross(T[i])
            if ax.length > 1e-9:
                N = Matrix.Rotation(T[i - 1].angle(T[i]), 3, ax.normalized()) @ N
            N = (N - T[i] * N.dot(T[i])).normalized()
        out.append((T[i], N, T[i].cross(N)))
    return out


def strands(pts, radii, nstr=3, twist=1.5, ring=5, phase=0.0):
    """Replace one fat tube by a twisted bundle of thinner strands (reads as hair, not pasta)."""
    fr = path_frames(pts)
    res = []
    n = len(pts)
    for k in range(nstr):
        sp, sr = [], []
        for i in range(n):
            s = i / max(1, n - 1)
            a = phase + 2 * math.pi * (k / nstr + twist * s)
            T, N, B = fr[i]
            o = radii[i] * 0.56
            sp.append(pts[i] + (N * math.cos(a) + B * math.sin(a)) * o)
            sr.append(radii[i] * (0.60 if k else 0.64))
        res.append(tube(sp, sr, ring=ring, cap_end=True, cap_start=True, cap_rings=1))
    return res


def uv_sphere(center, radii, seg=24, rings=14, rot=None):
    verts, faces = [], []
    rot = rot or Matrix.Identity(3)
    verts.append(center + rot @ V(0, 0, -radii[2]))
    for i in range(1, rings):
        th = math.pi * i / rings - math.pi / 2
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            verts.append(center + rot @ V(radii[0] * math.cos(th) * math.cos(ph), radii[1] * math.cos(th) * math.sin(ph), radii[2] * math.sin(th)))
    verts.append(center + rot @ V(0, 0, radii[2]))
    top = len(verts) - 1
    for j in range(seg):
        faces.append((0, 1 + (j + 1) % seg, 1 + j))
    for i in range(rings - 2):
        for j in range(seg):
            a = 1 + i * seg + j
            b = 1 + i * seg + (j + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    base = 1 + (rings - 2) * seg
    for j in range(seg):
        faces.append((base + j, base + (j + 1) % seg, top))
    return verts, faces


def lathe(rings, nseg, fold=None, close_bottom=False, close_top=False):
    """rings: list of (z, rx, ry, cy). theta=0 is front (-Y). fold(theta, k) -> radial mult, or (mult, dz)."""
    verts, faces = [], []
    for k, (z, rx, ry, cy) in enumerate(rings):
        for j in range(nseg):
            th = 2 * math.pi * j / nseg
            m, dz = 1.0, 0.0
            if fold:
                r = fold(th, k)
                m, dz = (r if isinstance(r, tuple) else (r, 0.0))
            verts.append(V(rx * m * math.sin(th), cy - ry * m * math.cos(th), z + dz))
    for k in range(len(rings) - 1):
        for j in range(nseg):
            j2 = (j + 1) % nseg
            a, b = k * nseg + j, k * nseg + j2
            faces.append((a, a + nseg, b + nseg, b))
    if close_bottom:
        c = len(verts)
        z, rx, ry, cy = rings[0]
        verts.append(V(0, cy, z))
        for j in range(nseg):
            faces.append((j, (j + 1) % nseg, c))
    if close_top:
        c = len(verts)
        z, rx, ry, cy = rings[-1]
        verts.append(V(0, cy, z))
        b = (len(rings) - 1) * nseg
        for j in range(nseg):
            faces.append((b + (j + 1) % nseg, b + j, c))
    return verts, faces


def fix_winding_outward(verts, faces, center_fn):
    out = []
    for f in faces:
        a, b, c = verts[f[0]], verts[f[1]], verts[f[2]]
        n = (b - a).cross(c - a)
        cen = sum((verts[i] for i in f), Vector()) / len(f)
        if n.dot(cen - center_fn(cen)) < 0:
            f = tuple(reversed(f))
        out.append(f)
    return out


# ----------------------------------------------------------------------------- materials
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    return m, nt, out


def bsdf(nt, **kw):
    n = nt.nodes.new('ShaderNodeBsdfPrincipled')
    for k, v in kw.items():
        n.inputs[k.replace('_', ' ')].default_value = v
    return n


def mixrgb(nt, fac, a, b, blend='MIX'):
    m = nt.nodes.new('ShaderNodeMix')
    m.data_type = 'RGBA'
    m.blend_type = blend
    m.clamp_factor = True
    if isinstance(fac, (int, float)):
        m.inputs[0].default_value = fac
    else:
        nt.links.new(fac, m.inputs[0])
    for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = val
        else:
            nt.links.new(val, sock)
    return m.outputs[2]


def math_node(nt, op, a, b=None, clamp_=False):
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = op
    m.use_clamp = clamp_
    for sock, val in ((m.inputs[0], a), (m.inputs[1], b)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            sock.default_value = val
        else:
            nt.links.new(val, sock)
    return m.outputs[0]


def maprange(nt, val, a, b, c=0.0, d=1.0, interp='LINEAR'):
    m = nt.nodes.new('ShaderNodeMapRange')
    m.interpolation_type = interp
    m.clamp = True
    nt.links.new(val, m.inputs['Value'])
    m.inputs['From Min'].default_value = a
    m.inputs['From Max'].default_value = b
    m.inputs['To Min'].default_value = c
    m.inputs['To Max'].default_value = d
    return m.outputs['Result']


def sparkle(nt, scale, density, size=0.08):
    """returns mask socket of tiny sparse dots (object space)."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = scale
    nt.links.new(tc.outputs['Object'], vor.inputs['Vector'])
    dots = maprange(nt, vor.outputs['Distance'], size, size * 0.3, 0.0, 1.0)
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(vor.outputs['Color'], sep.inputs[0])
    sel = maprange(nt, sep.outputs[0], 1.0 - density - 0.02, 1.0 - density, 0.0, 1.0)
    return math_node(nt, 'MULTIPLY', dots, sel)


SKIN = srgb(226, 166, 128)
BLUSH = srgb(236, 112, 102)
LIP = srgb(204, 96, 96)


def build_materials():
    M = {}
    # --- skin
    m, nt, out = new_mat("Hani_skin")
    b = bsdf(nt, Base_Color=SKIN, Roughness=0.5, Subsurface_Weight=0.12, Subsurface_Radius=(1.0, 0.42, 0.25),
             Subsurface_Scale=0.006, Specular_IOR_Level=0.32, Sheen_Weight=0.25, Sheen_Roughness=0.45,
             Sheen_Tint=(1.0, 0.85, 0.8, 1.0))
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'face_paint'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(at.outputs['Color'], sep.inputs[0])
    c1 = mixrgb(nt, math_node(nt, 'MULTIPLY', sep.outputs[0], 0.55), SKIN, BLUSH)
    c2 = mixrgb(nt, math_node(nt, 'MULTIPLY', sep.outputs[1], 0.75), c1, LIP)
    c3 = mixrgb(nt, math_node(nt, 'MULTIPLY', sep.outputs[2], 0.35), c2, BLUSH)
    nt.links.new(c3, b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0])
    M['skin'] = m
    # --- lashes / brows / mouth
    m, nt, out = new_mat("Hani_lash")
    nt.links.new(bsdf(nt, Base_Color=srgb(28, 16, 12), Roughness=0.55).outputs[0], out.inputs[0])
    M['lash'] = m
    m, nt, out = new_mat("Hani_brow")
    nt.links.new(bsdf(nt, Base_Color=srgb(70, 44, 32), Roughness=0.8, Specular_IOR_Level=0.2).outputs[0], out.inputs[0])
    M['brow'] = m
    m, nt, out = new_mat("Hani_mouth_inner")
    nt.links.new(bsdf(nt, Base_Color=srgb(96, 30, 34), Roughness=0.6, Specular_IOR_Level=0.2).outputs[0], out.inputs[0])
    M['mouth'] = m
    m, nt, out = new_mat("Hani_tongue")
    nt.links.new(bsdf(nt, Base_Color=srgb(222, 110, 112), Roughness=0.45, Subsurface_Weight=0.2,
                      Subsurface_Scale=0.004).outputs[0], out.inputs[0])
    M['tongue'] = m
    # --- eyeball (iris drawn procedurally from object-space angle to local -Y)
    m, nt, out = new_mat("Hani_eye")
    b = bsdf(nt, Roughness=0.06, Specular_IOR_Level=0.7, Coat_Weight=0.6, Coat_Roughness=0.02)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nrm = nt.nodes.new('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Object'], nrm.inputs[0])
    sx = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(nrm.outputs[0], sx.inputs[0])
    ang = math_node(nt, 'ARCCOSINE', math_node(nt, 'MULTIPLY', sx.outputs['Y'], -1.0))
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(maprange(nt, ang, 0.0, 1.6), ramp.inputs[0])
    K_ = 0.875
    st = [(0.0, srgb(8, 4, 3)), (0.30 * K_, srgb(10, 5, 4)), (0.33 * K_, srgb(34, 17, 9)),
          (0.48 * K_, srgb(58, 31, 15)), (0.60 * K_, srgb(40, 21, 11)), (0.665 * K_, srgb(24, 12, 7)),
          (0.70 * K_, srgb(16, 8, 5)), (0.73 * K_, srgb(232, 226, 222)), (1.0, srgb(200, 190, 186))]
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = st[0][0] / 1.6, st[0][1]
    el[1].position, el[1].color = st[-1][0], st[-1][1]
    for p, c in st[1:-1]:
        e = el.new(p / 1.6)
        e.color = c
    # warm glow in the lower iris
    low = maprange(nt, sx.outputs['Z'], 0.05, -0.45, 0.0, 1.0)
    irism = maprange(nt, ang, 0.595, 0.525, 0.0, 1.0)
    pup = maprange(nt, ang, 0.27, 0.305, 0.0, 1.0)
    glow = math_node(nt, 'MULTIPLY', math_node(nt, 'MULTIPLY', low, irism), pup)
    # radial streaks
    ns = nt.nodes.new('ShaderNodeTexNoise')
    ns.inputs['Scale'].default_value = 55.0
    ns.inputs['Detail'].default_value = 2.0
    nt.links.new(nrm.outputs[0], ns.inputs['Vector'])
    col = mixrgb(nt, math_node(nt, 'MULTIPLY', glow, 0.6), ramp.outputs[0], srgb(104, 56, 26))
    col = mixrgb(nt, math_node(nt, 'MULTIPLY', math_node(nt, 'MULTIPLY', irism, pup), 0.25), col,
                 ns.outputs['Color'], blend='OVERLAY')
    nt.links.new(col, b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0])
    M['eye'] = m
    # --- eye highlight (two soft spots, emission, alpha masked)
    m, nt, out = new_mat("Hani_eye_highlight")
    m.surface_render_method = 'BLENDED'
    m.use_transparent_shadow = True
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nrm = nt.nodes.new('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Object'], nrm.inputs[0])
    masks = []
    for dvec, size in ((V(-0.22, -0.94, 0.17), 0.13), (V(0.21, -0.94, -0.20), 0.07)):
        dv = nt.nodes.new('ShaderNodeVectorMath')
        dv.operation = 'DOT_PRODUCT'
        nt.links.new(nrm.outputs[0], dv.inputs[0])
        dv.inputs[1].default_value = dvec.normalized()
        masks.append(maprange(nt, dv.outputs['Value'], math.cos(size), math.cos(size * 0.55), 0.0, 1.0))
        dv.name = "hl_dir_%d" % len(masks)
    mask = math_node(nt, 'MAXIMUM', masks[0], math_node(nt, 'MULTIPLY', masks[1], 0.9))
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.98, 0.95, 1)
    em.inputs['Strength'].default_value = 2.2
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(mask, mx.inputs[0])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    M['eye_hl'] = m
    # --- hair
    m, nt, out = new_mat("Hani_hair")
    b = bsdf(nt, Roughness=0.55, Specular_IOR_Level=0.3, Sheen_Weight=0.25, Sheen_Roughness=0.4,
             Sheen_Tint=srgb(120, 84, 64), Coat_Weight=0.1, Coat_Roughness=0.35)
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'hair_var'
    col = mixrgb(nt, at.outputs['Fac'], srgb(22, 14, 11), srgb(58, 36, 25))
    nt.links.new(col, b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0])
    M['hair'] = m
    m, nt, out = new_mat("Hani_hair_tie")
    nt.links.new(bsdf(nt, Base_Color=srgb(36, 98, 214), Roughness=0.32, Sheen_Weight=0.4,
                      Coat_Weight=0.3).outputs[0], out.inputs[0])
    M['tie'] = m
    # --- dress
    def dress_mat(name, base, alpha=1.0, spark=0.0, spark_scale=260.0, sheen=0.5):
        m, nt, out = new_mat(name)
        b = bsdf(nt, Base_Color=base, Roughness=0.55, Sheen_Weight=sheen, Sheen_Roughness=0.3,
                 Sheen_Tint=(1, 1, 1, 1), Specular_IOR_Level=0.3, Alpha=alpha)
        if spark > 0:
            sm = sparkle(nt, spark_scale, spark)
            nt.links.new(mixrgb(nt, 0.0, (1, 1, 1, 1), (1, 1, 1, 1)), b.inputs['Emission Color'])
            nt.links.new(math_node(nt, 'MULTIPLY', sm, 5.0), b.inputs['Emission Strength'])
            if alpha < 1.0:
                nt.links.new(math_node(nt, 'MAXIMUM', sm, alpha), b.inputs['Alpha'])
        if alpha < 1.0:
            m.surface_render_method = 'DITHERED'
            m.use_transparent_shadow = True
        nt.links.new(b.outputs[0], out.inputs[0])
        return m
    M['bodice'] = dress_mat("Hani_dress_bodice", srgb(86, 156, 232), spark=0.05, spark_scale=330)
    M['skirt_under'] = dress_mat("Hani_dress_underskirt", srgb(80, 148, 228), sheen=0.6)
    M['tulle1'] = dress_mat("Hani_dress_tulle_a", srgb(120, 180, 240), alpha=0.55, spark=0.03, spark_scale=240)
    M['tulle2'] = dress_mat("Hani_dress_tulle_b", srgb(140, 192, 244), alpha=0.42, spark=0.05, spark_scale=300)
    M['sleeve'] = dress_mat("Hani_dress_sleeve", srgb(132, 186, 242), spark=0.04, spark_scale=300, sheen=0.8)
    m, nt, out = new_mat("Hani_white_satin")
    nt.links.new(bsdf(nt, Base_Color=srgb(246, 246, 250), Roughness=0.35, Sheen_Weight=0.6,
                      Specular_IOR_Level=0.4).outputs[0], out.inputs[0])
    M['white'] = m
    m, nt, out = new_mat("Hani_pearl")
    nt.links.new(bsdf(nt, Base_Color=srgb(250, 247, 242), Roughness=0.18, Coat_Weight=1.0,
                      Coat_Roughness=0.05, Thin_Film_Thickness=350.0, Specular_IOR_Level=0.6).outputs[0], out.inputs[0])
    M['pearl'] = m
    m, nt, out = new_mat("Hani_star_gold")
    nt.links.new(bsdf(nt, Base_Color=srgb(255, 205, 110), Metallic=1.0, Roughness=0.22).outputs[0], out.inputs[0])
    M['gold'] = m
    m, nt, out = new_mat("Hani_shoe_pink")
    b = bsdf(nt, Base_Color=srgb(242, 150, 178), Roughness=0.28, Coat_Weight=0.6, Coat_Roughness=0.08,
             Specular_IOR_Level=0.5)
    sm = sparkle(nt, 420, 0.08, 0.1)
    nt.links.new(mixrgb(nt, 0.0, (1, 0.9, 0.95, 1), (1, 1, 1, 1)), b.inputs['Emission Color'])
    nt.links.new(math_node(nt, 'MULTIPLY', sm, 2.0), b.inputs['Emission Strength'])
    nt.links.new(b.outputs[0], out.inputs[0])
    M['shoe'] = m
    m, nt, out = new_mat("Hani_shoe_sole")
    nt.links.new(bsdf(nt, Base_Color=srgb(222, 118, 148), Roughness=0.5).outputs[0], out.inputs[0])
    M['sole'] = m
    return M


# ----------------------------------------------------------------------------- proportions
HC = V(0.0, 0.0, 0.684)      # cranium centre
HR = 0.125                    # cranium radius (head chin->crown ~0.26 + hair -> ~0.30)
R_E = 0.038                   # eyeball radius
EYE_AZ, EYE_EL = 24.0, -6.0   # eye direction from head centre (deg)
EYE_PROT = 0.0075
EYE_FLAT = 0.86              # eyes/lids flattened along their forward axis (less goggle)             # eyeball protrusion beyond the base surface
EYE_NBLEND = 0.38             # eye forward: blend of surface normal vs -Y
LID = dict(W=0.74, Hu=0.56, Hl=0.45, ci=-0.06, co=0.07, close=-0.30)
NOSE_EL = -24.0


def head_surface(d):
    """Base (unprocessed) head surface point for unit direction d."""
    x, y, z = d
    zf = lerp(1.02, 0.80, smoothstep(-0.12, -0.92, z))   # short toddler chin (soft transition)
    p = V(x * 1.0, y * 0.965, z * zf) * HR
    for s in (-1, 1):  # soft, full toddler cheeks
        c = V(0.62 * s, -0.58, -0.50).normalized()
        g = math.exp(-(d - c).length_squared / (2 * 0.34 ** 2))
        p += d * (0.021 * g)
    c = V(0, -0.45, -0.89).normalized()  # small round chin
    p += d * 0.004 * math.exp(-(d - c).length_squared / (2 * 0.22 ** 2))
    c = V(0, -0.72, 0.69).normalized()  # forehead
    p += d * 0.005 * math.exp(-(d - c).length_squared / (2 * 0.35 ** 2))
    c = V(0, 0.75, 0.35).normalized()  # round back of head
    p += d * 0.008 * math.exp(-(d - c).length_squared / (2 * 0.45 ** 2))
    if z < -0.55:  # flatter under-chin -> neck
        p.z += (-0.55 - z) * 0.022
    if y < -0.55:  # slightly flatter face plane (eyes sit in it)
        p.y += (-0.55 - y) * 0.010 * smoothstep(-0.7, -0.1, z) * (1 - smoothstep(0.35, 0.8, z))
    # button nose
    nz = math.sin(math.radians(NOSE_EL))
    if y < 0:
        g = math.exp(-((x / 0.052) ** 2 + ((z - nz) / 0.050) ** 2) / 2.0)
        g2 = math.exp(-((x / 0.05) ** 2 + ((z - nz + 0.035) / 0.04) ** 2) / 2.0)
        p += V(0, -1, 0) * (0.0105 * g) + V(0, 0, 0.0018) * g2
    return HC + p


def eye_frame(side):
    az, el = math.radians(EYE_AZ), math.radians(EYE_EL)
    d = V(side * math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))
    S = head_surface(d)
    n = d
    E = S - n * (R_E - EYE_PROT)
    f = (n * EYE_NBLEND + V(0, -1, 0) * (1 - EYE_NBLEND)).normalized()
    up = V(0, 0, 1)
    Xl = up.cross(f).normalized() * side       # points outward (temple side)
    Zl = (up - f * up.dot(f)).normalized()
    Yl = -f
    M = Matrix((Xl, Yl, Zl)).transposed()      # columns = local axes (may be mirrored for R)
    Mrot = Matrix((Xl * side, Yl, Zl)).transposed()  # proper rotation for objects
    return dict(side=side, E=E, f=f, M=M, Mi=M.transposed(), Mrot=Mrot)


def lid_curves(xn):
    W, Hu, Hl, ci, co = LID['W'], LID['Hu'], LID['Hl'], LID['ci'], LID['co']
    t = clamp(xn / W, -1, 1)
    b = lerp(ci, co, (t + 1) / 2)
    prof = max(0.0, 1 - t * t)
    hu = b + Hu * prof ** 0.55
    hl = b - Hl * prof ** 0.8
    hc = b + LID['close'] * Hl * prof ** 0.8
    rho = math.sqrt(max(1e-6, 1 - xn * xn))

    def th(h):
        return math.asin(clamp(h / rho, -0.995, 0.995))
    return th(hu), th(hl), th(hc), prof


def flat(q):
    return V(q.x, q.y * EYE_FLAT if q.y < 0 else q.y, q.z)


def rot_local(q, dth):
    """rotate local point about local X (lid rotation); +dth moves the front upward."""
    rho = math.hypot(q.y, q.z)
    th = math.atan2(q.z, -q.y) + dth
    return V(q.x, -rho * math.cos(th), rho * math.sin(th))


# ----------------------------------------------------------------------------- HEAD
def build_head(M, coll):
    log("head: lattice")
    n = 48
    h = n // 2
    MR, MW = -h + 5, 6
    lat = {}
    dirs, keys = [], []
    tt = math.pi / 4 / h

    def vid(a, b, c, side=None):
        sp = side if (b == -h and c == MR and -MW < a < MW) else None
        k = (a, b, c, sp)
        if k not in lat:
            lat[k] = len(dirs)
            dirs.append(V(math.tan(a * tt), math.tan(b * tt), math.tan(c * tt)).normalized())
            keys.append(k)
        return lat[k]
    faces = []
    for axis in range(3):
        oth = [k for k in range(3) if k != axis]
        for sgn in (-1, 1):
            for i in range(-h, h):
                for j in range(-h, h):
                    side = None
                    if axis == 1 and sgn == -1 and -MW <= i < MW:
                        if j == MR:
                            side = 'U'
                        elif j == MR - 1:
                            side = 'L'
                    ids = []
                    for (u, v) in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        co = [0, 0, 0]
                        co[axis] = sgn * h
                        co[oth[0]], co[oth[1]] = u, v
                        ids.append(vid(*co, side=side))
                    faces.append(tuple(ids))
    pos = [head_surface(d) for d in dirs]
    faces = fix_winding_outward(pos, faces, lambda c: HC)
    nskin = len(pos)
    # slit bookkeeping
    U = {k[0]: i for i, k in enumerate(keys) if k[3] == 'U'}
    L = {k[0]: i for i, k in enumerate(keys) if k[3] == 'L'}
    CL, CR = lat[(-MW, -h, MR, None)], lat[(MW, -h, MR, None)]
    Mc = (pos[U[0]] + pos[L[0]]) / 2
    mw = (pos[CR].x - pos[CL].x) / 2
    lower_set = set(L.values())
    upper_set = set(U.values())
    # rest mouth: gentle smile curve and a hairline gap
    for i in range(nskin):
        p = pos[i]
        dx, dz = p.x - Mc.x, p.z - Mc.z
        if abs(dz) < 0.012 and abs(dx) < mw * 1.6 and p.y < Mc.y + 0.02:
            u = clamp(dx / mw, -1, 1)
            fall = math.exp(-(dz / 0.006) ** 2) * (1 - smoothstep(1.0, 1.6, abs(dx) / mw))
            p.z += 0.0030 * u ** 4 * fall + 0.0008 * u * u * fall
            p.y += 0.0012 * u * u * fall
    for a, i in U.items():
        u = a / MW
        pos[i].z += 0.00012 * (1 - u * u)
    for a, i in L.items():
        u = a / MW
        pos[i].z -= 0.00012 * (1 - u * u)
    # eyes: sockets
    eyes = {s: eye_frame(s) for s in (1, -1)}
    for s, e in eyes.items():
        E, Mi = e['E'], e['Mi']
        for i in range(nskin):
            q = Mi @ (pos[i] - E)
            d = q.length
            if d > R_E * 1.9 or -q.y <= 0:
                continue
            xn = q.x / d
            th = math.atan2(q.z, -q.y)
            tu, tl, tc, _ = lid_curves(clamp(xn, -0.97, 0.97))
            m = 0.13
            if abs(xn) < LID['W'] + 0.06 and tl - m < th < tu + m:
                pos[i] = E + e['M'] @ flat(q.normalized() * R_E * 0.84)
            elif d < R_E * 1.07:
                pos[i] = E + e['M'] @ (q.normalized() * min(d, R_E * 1.05))
    # mouth tunnel
    loop = [CL] + [U[a] for a in range(-MW + 1, MW)] + [CR] + [L[a] for a in range(MW - 1, -MW, -1)]
    directed = set()
    for f in faces:
        for k in range(len(f)):
            directed.add((f[k], f[(k + 1) % len(f)]))
    src = {}
    r1, r2 = {}, {}
    for vi in loop:
        p = pos[vi]
        w = (HC + V(0, 0.03, -0.01) - p).normalized()
        r1[vi] = len(pos)
        pos.append(p + w * 0.0022)
        src[r1[vi]] = vi
        r2[vi] = len(pos)
        pos.append(p + w * 0.0075)
        src[r2[vi]] = vi
    tun_faces, tun_mats = [], []
    for k in range(len(loop)):
        a, b = loop[k], loop[(k + 1) % len(loop)]
        if (a, b) in directed:
            a, b = b, a
        tun_faces.append((a, b, r1[b], r1[a]))
        tun_mats.append(0)
        tun_faces.append((r1[a], r1[b], r2[b], r2[a]))
        tun_mats.append(3)
    nskin_t = len(pos)
    G = Geo()
    G.add(pos, faces + tun_faces, 0)
    G.fm = [0] * len(faces) + tun_mats
    # ---- lids
    log("head: lids/brows/mouth")
    lidinfo = {}  # vid -> (side, 'u'/'l', xn, local q)
    ncol = 31
    xs = [math.sin(-1.33 + 2.66 * k / (ncol - 1)) / math.sin(1.33) * 0.975 for k in range(ncol)]
    # far rows sink onto the eyeball (r ~ 0.99) so the shells never graze the cheek/temple skin
    rows_u = [(-0.035, 0.985), (0.0, 1.03), (0.04, 1.075), (0.10, 1.075), (0.18, 1.075), (0.28, 1.075)] + \
        [(0.28 + 0.16 * k, lerp(1.075, 0.99, smoothstep(0.95, 1.45, 0.28 + 0.16 * k))) for k in range(1, 14)]
    rows_l = [(0.03, 0.985), (0.0, 1.025), (-0.035, 1.062), (-0.09, 1.062), (-0.17, 1.062), (-0.27, 1.062)] + \
        [(-0.27 - 0.16 * k, lerp(1.062, 0.99, smoothstep(0.45, 0.85, 0.27 + 0.16 * k))) for k in range(1, 13)]
    for s, e in eyes.items():
        for lid, rows in (('u', rows_u), ('l', rows_l)):
            verts, info = [], []
            for xn in xs:
                tu, tl, tc, prof = lid_curves(xn)
                th0 = tu if lid == 'u' else tl
                for (dth, rr) in rows:
                    r = R_E * rr
                    q = V(xn * r, -r * math.sqrt(1 - xn * xn) * math.cos(th0 + dth), r * math.sqrt(1 - xn * xn) * math.sin(th0 + dth))
                    verts.append(e['E'] + e['M'] @ flat(q))
                    info.append((s, lid, xn, q))
            nr = len(rows)
            fl, mats = [], []
            for c in range(ncol - 1):
                for r in range(nr - 1):
                    a = c * nr + r
                    fl.append((a, a + 1, a + nr + 1, a + nr))
                    lash = lid == 'u' and r < 3 and abs(xs[c]) < LID['W'] + 0.05
                    mats.append(1 if lash else 0)
            E0 = e['E']
            fl = fix_winding_outward(verts, fl, lambda c, E0=E0: E0)
            o = G.add(verts, fl, 0)
            G.fm[-len(fl):] = mats
            for i, inf in enumerate(info):
                lidinfo[o + i] = inf
        # lash flicks at the outer upper lid
        for k, xn in enumerate((0.22, 0.42, 0.58, 0.70, 0.79)):
            tu, tl, tc, prof = lid_curves(xn)
            r = R_E * 1.07
            q0 = V(xn * r, -r * math.sqrt(1 - xn * xn) * math.cos(tu + 0.02), r * math.sqrt(1 - xn * xn) * math.sin(tu + 0.02))
            radial = q0.normalized()
            ln = 0.0035 + 0.0035 * k / 4
            d0 = (radial * 0.7 + V(0.25 + 0.6 * k / 4, 0, 0.35)).normalized()
            pts, rad = [], []
            for j in range(6):
                t = j / 5
                d = (d0 + V(0.25 * t * t, 0, 0.9 * t * t)).normalized()
                pts.append((pts[-1] + d * ln / 5) if pts else q0 - radial * 0.0006)
                rad.append(lerp(0.00062, 0.00012, t))
            vv, ff, _ = tube(pts, rad, ring=5, cap_end=True, cap_rings=1)
            o = G.add([e['E'] + e['M'] @ flat(p) for p in vv], ff, 1)
            for i, p in enumerate(vv):
                lidinfo[o + i] = (s, 'u', xn, p)
    # ---- brows
    browinfo = {}

    def brow_verts(e, raise_=0.0, inner=0.0, outer=0.0):
        R = 0.0345
        out = []
        K = 15
        cen, nrm = [], []
        for k in range(K):
            s = k / (K - 1)
            x = lerp(-0.62, 0.98, s) * R
            z = R * 1.30 + R * 0.20 * math.sin(math.pi * (0.08 + 0.84 * s)) - R * 0.10 * s
            z += raise_ + inner * (1 - s) ** 2 + outer * s * s
            P = e['E'] + e['M'] @ V(x, -R * 0.75, z + (R_E - R) * 0.6)
            d = (P - HC).normalized()
            C = head_surface(d)
            cen.append(C)
            nrm.append((C - HC).normalized())
        for k in range(K):
            s = k / (K - 1)
            t = (cen[min(k + 1, K - 1)] - cen[max(k - 1, 0)]).normalized()
            b = nrm[k].cross(t).normalized()
            w = 0.0046 * (1 - 0.55 * s) * (min(1, s / 0.10) ** 0.5) * (1 - 0.6 * smoothstep(0.75, 1.0, s)) + 0.0006
            for (bb, hh) in ((0.5, 0.0011), (-0.5, 0.0011), (-0.5, -0.0009), (0.5, -0.0009)):
                out.append(cen[k] + b * (w * bb) + nrm[k] * hh)
        return out
    bf = []
    K = 15
    for k in range(K - 1):
        for j in range(4):
            j2 = (j + 1) % 4
            bf.append((k * 4 + j, k * 4 + j2, (k + 1) * 4 + j2, (k + 1) * 4 + j))
    bf.append((3, 2, 1, 0))
    l4 = (K - 1) * 4
    bf.append((l4, l4 + 1, l4 + 2, l4 + 3))
    for s, e in eyes.items():
        vv = brow_verts(e)
        vv_ = vv
        bff = fix_winding_outward(vv_, bf, lambda c, vv_=vv_: sum(vv_, Vector()) / len(vv_))
        o = G.add(vv, bff, 2)
        browinfo[s] = (o, e)
    # ---- mouth bag + tongue
    inward = V(0, 1, 0.15).normalized()
    bagc = Mc + inward * 0.0175 + V(0, 0, -0.003)
    vv, ff = uv_sphere(bagc, (0.0165, 0.0095, 0.0125), 20, 12)
    skin_np = np.array([tuple(p) for p in pos[:nskin]])
    near = skin_np[np.linalg.norm(skin_np - np.array(tuple(Mc)), axis=1) < 0.05]

    def keep_inside(p, gap):
        # pull a point back (+Y, towards the head) until it is `gap` behind the nearest skin sample
        for _ in range(12):
            dd = np.linalg.norm(near - np.array(tuple(p)), axis=1)
            k = int(np.argmin(dd))
            q = Vector(near[k])
            if dd[k] > gap or p.y > q.y + gap:
                break
            p = p + V(0, 0.0012, 0)
        return p
    vv = [keep_inside(p, 0.0035) for p in vv]
    bag_o = G.add(vv, ff, 3)
    tc_ = Mc + inward * 0.0145 + V(0, 0, -0.0075)
    vv, ff = uv_sphere(tc_, (0.0100, 0.0075, 0.0033), 16, 10)
    vv = [keep_inside(p, 0.0035) for p in vv]
    tongue_o = G.add(vv, ff, 4)
    tongue_ids = list(range(tongue_o, tongue_o + len(vv)))
    G.wconst.append((0, len(G.v), {'head': 1.0}))
    nall = len(G.v)
    base = np.array([tuple(p) for p in G.v])
    # ---- face paint (R blush, G lips, B nose)
    paint = np.zeros((nall, 4))
    paint[:, 3] = 1
    nzp = head_surface(V(0, -math.cos(math.radians(NOSE_EL)), math.sin(math.radians(NOSE_EL))))
    for i in range(nskin):
        p = pos[i]
        bl = 0.0
        for s in (-1, 1):
            cc = V(0.058 * s, 0, Mc.z + 0.022)
            dd = ((p.x - cc.x) / 0.022) ** 2 + ((p.z - cc.z) / 0.016) ** 2
            if p.y < HC.y - 0.04:
                bl = max(bl, math.exp(-dd / 2))
        dx, dz = p.x - Mc.x, p.z - Mc.z
        sx = max(0.0, abs(dx) - mw * 0.75)
        lipw = 0.0
        if p.y < Mc.y + 0.015:
            sig = 0.0026 if dz > 0 else 0.0034
            lipw = math.exp(-((dz - 0.0003) / sig) ** 2 - (sx / 0.0035) ** 2) * (1 - smoothstep(0.9, 1.25, abs(dx) / mw))
        nose = math.exp(-((p - nzp).length / 0.0065) ** 2)
        paint[i, 0], paint[i, 1], paint[i, 2] = bl, lipw * 0.55, nose
    for vi, si in src.items():
        paint[vi, 1] = 0.6
    # ---- shape keys (displacement fields)
    log("head: shape keys")
    adj = [set() for _ in range(nskin_t)]
    for f in faces + tun_faces:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            adj[a].add(b)
            adj[b].add(a)
    maxd = max(len(a) for a in adj)
    nb = np.full((nskin_t, maxd), nskin_t, dtype=np.int64)
    deg = np.zeros(nskin_t)
    for i, a in enumerate(adj):
        nb[i, :len(a)] = list(a)
        deg[i] = len(a)
    deg[deg == 0] = 1

    def harmonic(fixed, region_mask, iters=400):
        disp = np.zeros((nskin_t + 1, 3))
        fid = np.array(list(fixed.keys()), dtype=np.int64)
        fval = np.array([tuple(v) for v in fixed.values()])
        free = region_mask.copy()
        free[fid] = False
        disp[fid] = fval
        for _ in range(iters):
            avg = disp[nb].sum(axis=1) / deg[:, None]
            disp[:nskin_t][free] = avg[free]
            disp[nskin_t] = 0
        return disp[:nskin_t]
    skin = base[:nskin_t]
    rel = skin - np.array(tuple(Mc))
    front = skin[:, 1] < HC.y - 0.02

    def region(rx, rz, cz=0.0):
        return (((rel[:, 0] / rx) ** 2 + ((rel[:, 2] - cz) / rz) ** 2) < 1.0) & front

    def jaw_rot(p, ang):
        P = Mc + V(0, 0.045, 0.012)
        q = p - P
        c, s_ = math.cos(ang), math.sin(ang)
        return P + V(q.x, q.y * c - q.z * s_, q.y * s_ + q.z * c) - p
    slit = {CL: 'C', CR: 'C'}
    for i in upper_set:
        slit[i] = 'U'
    for i in lower_set:
        slit[i] = 'L'
    keys_disp = {}
    # mouth_open
    reg = region(0.050, 0.052, -0.012)
    fx = {}
    ja = math.radians(15)
    for i, t in slit.items():
        p = pos[i]
        u = clamp((p.x - Mc.x) / mw, -1, 1)
        if t == 'U':
            fx[i] = V(0, -0.0004, 0.0013 * (1 - u * u) + 0.0004)
        elif t == 'L':
            fx[i] = jaw_rot(p, ja) + V(0, 0, -0.0035 * (1 - u * u) ** 0.7)
        else:
            fx[i] = jaw_rot(p, ja) * 0.45 + V(-0.0012 * math.copysign(1, u), 0.0008, 0)
    for i in np.nonzero(reg & (rel[:, 2] < -0.022))[0]:
        fx[int(i)] = jaw_rot(pos[i], ja)
    keys_disp['mouth_open'] = (harmonic(fx, reg), {k: jaw_rot(G.v[k], ja) for k in tongue_ids})
    # mouth_smile
    reg = region(0.062, 0.050, 0.008)
    fx = {}
    for i, t in slit.items():
        p = pos[i]
        u = clamp((p.x - Mc.x) / mw, -1, 1)
        dv = V(0.0018 * u, 0.0016 * u * u, 0.0034 * u * u)
        if t == 'L':
            dv += V(0, 0, -0.0007 * (1 - u * u))
        fx[i] = dv
    for s in (-1, 1):
        cc = np.array((Mc.x + 0.05 * s, 0, Mc.z + 0.026))
        dd = np.sqrt((skin[:, 0] - cc[0]) ** 2 + (skin[:, 2] - cc[2]) ** 2)
        for i in np.nonzero((dd < 0.007) & front)[0]:
            fx[int(i)] = V(0.0006 * s, -0.0018, 0.0026)
    keys_disp['mouth_smile'] = (harmonic(fx, reg), {})
    # mouth_O
    reg = region(0.045, 0.045, -0.006)
    fx = {}
    for i, t in slit.items():
        p = pos[i]
        u = clamp((p.x - Mc.x) / mw, -1, 1)
        tx = Mc.x + (p.x - Mc.x) * 0.48
        hz = math.sqrt(max(0.0, 1 - u * u))
        if t == 'U':
            tz = Mc.z + 0.0050 * hz + 0.0006
        elif t == 'L':
            tz = Mc.z - 0.0068 * hz - 0.0008
        else:
            tz = Mc.z - 0.0003
        fx[i] = V(tx - p.x, -0.0026 * (1 - 0.4 * u * u), tz - p.z)
    for i in np.nonzero(reg & (rel[:, 2] < -0.024))[0]:
        fx[int(i)] = jaw_rot(pos[i], math.radians(5))
    keys_disp['mouth_O'] = (harmonic(fx, reg), {k: jaw_rot(G.v[k], math.radians(7)) for k in tongue_ids})
    # assemble
    def full(key):
        arr = base.copy()
        if key in keys_disp:
            d, extra = keys_disp[key]
            arr[:nskin_t] += d
            for vi, si in src.items():
                arr[vi] = base[vi] + d[si]
            for k, v in extra.items():
                arr[k] += np.array(tuple(v))
        return arr
    shapes = {k: full(k) for k in ('mouth_open', 'mouth_smile', 'mouth_O', 'blink_L', 'blink_R', 'brow_up', 'brow_worry')}

    def lid_apply(arr, side, fn):
        for vi, (s, lid, xn, q) in lidinfo.items():
            if s != side:
                continue
            dth = fn(lid, xn)
            if dth:
                e = eyes[s]
                arr[vi] = tuple(e['E'] + e['M'] @ flat(rot_local(q, dth)))
    for side, key in ((1, 'blink_L'), (-1, 'blink_R')):
        def fb(lid, xn):
            tu, tl, tc, prof = lid_curves(xn)
            return -(tu - tc) - 0.02 if lid == 'u' else 0.62 * (tc - tl)
        lid_apply(shapes[key], side, fb)
    for side in (1, -1):
        def fs(lid, xn):
            tu, tl, tc, prof = lid_curves(xn)
            return -0.05 * prof if lid == 'u' else 0.20 * (tu - tl) * prof ** 0.5
        lid_apply(shapes['mouth_smile'], side, fs)

        def fu(lid, xn):
            return 0.08 * lid_curves(xn)[3] if lid == 'u' else -0.03 * lid_curves(xn)[3]
        lid_apply(shapes['brow_up'], side, fu)

        def fw(lid, xn):
            pr = lid_curves(xn)[3]
            return (0.07 * pr * smoothstep(0.3, -0.5, xn) - 0.05 * pr * smoothstep(0.0, 0.7, xn)) if lid == 'u' else 0.0
        lid_apply(shapes['brow_worry'], side, fw)
    for s, (o, e) in browinfo.items():
        up = brow_verts(e, raise_=0.0065, inner=0.0010, outer=0.0)
        wo = brow_verts(e, raise_=0.0015, inner=0.0105, outer=-0.0030)
        for k in range(len(up)):
            shapes['brow_up'][o + k] = tuple(up[k])
            shapes['brow_worry'][o + k] = tuple(wo[k])
    mats = [M['skin'], M['lash'], M['brow'], M['mouth'], M['tongue']]
    lip_edges = [(loop[k], loop[(k + 1) % len(loop)]) for k in range(len(loop))]
    ob = make_object("Hani_head", G, mats, coll, subsurf=1, subsurf_render=1, crease=lip_edges)
    ca = ob.data.color_attributes.new('face_paint', 'FLOAT_COLOR', 'POINT')
    ca.data.foreach_set('color', paint.flatten().tolist())
    ob.shape_key_add(name='Basis', from_mix=False)
    for k, arr in shapes.items():
        kb = ob.shape_key_add(name=k, from_mix=False)
        kb.data.foreach_set('co', arr.flatten().tolist())
        kb.slider_min, kb.slider_max = 0.0, 1.0
    info = dict(eyes=eyes, mouth=Mc, mw=mw)
    return ob, info


def build_eyes(M, coll, info):
    obs = {}
    for s, e in info['eyes'].items():
        sfx = 'L' if s > 0 else 'R'
        G = Geo()
        vv, ff = uv_sphere(V(0, 0, 0), (R_E, R_E, R_E), 48, 32)
        G.add(vv, ff, 0)
        ob = make_object("Hani_eye." + sfx, G, [M['eye']], coll)
        ob.matrix_world = Matrix.Translation(e['E']) @ e['Mrot'].to_4x4() @ Matrix.Diagonal((1, EYE_FLAT, 1, 1))
        obs['eye.' + sfx] = ob
        G = Geo()
        r = R_E * 1.004
        verts, faces = [], []
        nr, ns = 24, 48
        for i in range(nr + 1):
            a = 0.75 * i / nr
            for j in range(ns):
                ph = 2 * math.pi * j / ns
                verts.append(V(r * math.sin(a) * math.cos(ph), -r * math.cos(a), r * math.sin(a) * math.sin(ph)))
        for i in range(nr):
            for j in range(ns):
                j2 = (j + 1) % ns
                faces.append((i * ns + j, i * ns + j2, (i + 1) * ns + j2, (i + 1) * ns + j))
        faces = fix_winding_outward(verts, faces, lambda c: V(0, 0, 0))
        G.add(verts, faces, 0)
        hl = make_object("Hani_eye_highlight." + sfx, G, [M['eye_hl']], coll)
        hl.matrix_world = Matrix.Translation(e['E']) @ e['Mrot'].to_4x4() @ Matrix.Diagonal((1, EYE_FLAT, 1, 1))
        hl.visible_shadow = False
        obs['hl.' + sfx] = hl
        # highlight directions are defined in world-ish terms -> convert into this object's local space
    return obs


def build_ears(M, coll):
    G = Geo()
    for s in (1, -1):
        d = V(s * math.cos(math.radians(-7)), 0.04, math.sin(math.radians(-7))).normalized()
        P = head_surface(d)
        rot = Matrix.Rotation(math.radians(-30 * s), 3, 'Z') @ Matrix.Rotation(math.radians(-8), 3, 'X')
        vv, ff = uv_sphere(V(0, 0, 0), (0.0062, 0.0135, 0.0195), 20, 14)
        out = []
        for p in vv:
            q = V(p.x, p.y, p.z)
            if q.x > 0:  # concha dent on the outer face
                dd = (q.y / 0.012) ** 2 + ((q.z + 0.002) / 0.017) ** 2
                q.x -= 0.0068 * math.exp(-dd * 1.5)
            q.x *= s
            out.append(P + V(s * 0.0055, 0.011, 0) + rot @ q)
        G.add(out, ff, 0)
    G.wconst.append((0, len(G.v), {'head': 1.0}))
    return make_object("Hani_ears", G, [M['skin']], coll, subsurf=1)


# ----------------------------------------------------------------------------- HAIR
BUN_C = HC + V(0, 0.022, 0.192)
BUN_R = V(0.066, 0.062, 0.057)
TIE_C = HC + V(0, 0.010, 0.137)
TIE_AX = V(0, 0.18, 1).normalized()


def hairline_el(phi):
    tab = [(0, 31), (20, 28), (40, 14), (55, 3), (68, -6), (78, -8), (86, 6), (96, 10), (104, 2), (114, -24),
           (135, -40), (180, -50)]
    for k in range(len(tab) - 1):
        a, b = tab[k], tab[k + 1]
        if a[0] <= phi <= b[0]:
            t = smoothstep(0, 1, (phi - a[0]) / (b[0] - a[0]))
            return lerp(a[1], b[1], t)
    return tab[-1][1]


def hair_mask(d):
    phi = math.degrees(math.atan2(abs(d.x), -d.y))
    el = math.degrees(math.asin(clamp(d.z, -1, 1)))
    return smoothstep(-2, 14, el - hairline_el(phi))


def cap_thick(d):
    m = hair_mask(d)
    side = smoothstep(0.3, 0.85, abs(d.x)) * smoothstep(-0.55, 0.15, d.z)
    back = smoothstep(-0.2, 0.7, d.y) * smoothstep(-0.8, -0.2, d.z)
    top = smoothstep(0.55, 0.95, d.z)
    vol = 0.006 + 0.011 * side + 0.008 * back - 0.002 * top
    nz = noise.noise(d * 6.0) * 0.003
    mm = smoothstep(0.3, 1.0, m)
    return -0.0022 + (mm ** 1.7) * (vol + nz + 0.0022)


def cap_point(d):
    return head_surface(d) + d * cap_thick(d)


def coil(center, axis, nrm, radius, turns, length, tube_r, seg=13, phase=0.0, ring=6):
    a = axis.normalized()
    n = (nrm - a * nrm.dot(a)).normalized()
    b = a.cross(n)
    npts = max(6, int(turns * seg) + 1)
    pts, rad = [], []
    for i in range(npts):
        s = i / (npts - 1)
        ph = phase + 2 * math.pi * turns * s
        rr = radius * (1 - 0.25 * s)
        pts.append(center + a * (length * (s - 0.5)) + (n * math.cos(ph) + b * math.sin(ph)) * rr)
        rad.append(tube_r * (0.55 + 0.45 * math.sin(math.pi * min(1, s * 1.15 + 0.05)) ** 0.5))
    if ring <= 0:
        return tube(pts, rad, ring=6, cap_end=True, cap_start=True, cap_rings=2)
    return strands(pts, rad, nstr=3, twist=turns * 0.6, ring=max(4, ring), phase=phase)


def build_hair(M, coll, rng):
    log("hair: cap")
    G = Geo()
    # --- cap
    n = 40
    h = n // 2
    tt = math.pi / 4 / h
    lat, dirs = {}, []

    def vid(co):
        k = tuple(co)
        if k not in lat:
            lat[k] = len(dirs)
            dirs.append(V(*(math.tan(c * tt) for c in co)).normalized())
        return lat[k]
    faces = []
    for axis in range(3):
        oth = [k for k in range(3) if k != axis]
        for sgn in (-1, 1):
            for i in range(-h, h):
                for j in range(-h, h):
                    ids = []
                    for (u, v) in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        co = [0, 0, 0]
                        co[axis] = sgn * h
                        co[oth[0]], co[oth[1]] = u, v
                        ids.append(vid(co))
                    faces.append(tuple(ids))
    masks = [hair_mask(d) for d in dirs]
    keep = [f for f in faces if max(masks[i] for i in f) > 0.02]
    used = sorted({i for f in keep for i in f})
    remap = {o: k for k, o in enumerate(used)}
    cv = [cap_point(dirs[i]) for i in used]
    cf = [tuple(remap[i] for i in f) for f in keep]
    cf = fix_winding_outward(cv, cf, lambda c: HC)
    G.add(cv, cf, 0, {'head': 1.0}, attrs={'hair_var': 0.15})
    capG = G
    cap = make_object("Hani_hair_cap", capG, [M['hair']], coll, subsurf=0)
    # --- curls
    log("hair: scalp curls")
    G = Geo()
    N = 1250
    ga = math.pi * (3 - math.sqrt(5))
    count = 0
    for i in range(N):
        z = 1 - 2 * (i + 0.5) / N
        r = math.sqrt(1 - z * z)
        d = V(r * math.cos(ga * i), r * math.sin(ga * i), z)
        d = (d + V(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)) * 0.012).normalized()
        m = hair_mask(d)
        if m < 0.22 or (m < 0.4 and rng.random() < 0.45):
            continue
        P = cap_point(d)
        # skip under bun core / around tie
        q = P - BUN_C
        if (q.x / BUN_R.x) ** 2 + (q.y / BUN_R.y) ** 2 + (q.z / BUN_R.z) ** 2 < 0.9:
            continue
        tq = P - TIE_C
        if abs(tq.dot(TIE_AX)) < 0.012 and (tq - TIE_AX * tq.dot(TIE_AX)).length < 0.036:
            continue
        nrm = (P - HC).normalized()
        flow = (TIE_C - P)
        flow = (flow - nrm * flow.dot(nrm))
        if flow.length < 1e-4:
            flow = V(1, 0, 0)
        flow.normalize()
        ax = Matrix.Rotation(rng.uniform(-0.6, 0.6), 3, nrm) @ flow
        edge = smoothstep(0.35, 0.95, m)
        cr = rng.uniform(0.0078, 0.0108) * (0.5 + 0.5 * edge)
        tr = rng.uniform(0.0034, 0.0043) * (0.55 + 0.45 * edge)
        turns = rng.uniform(1.1, 1.8)
        ln = cr * 1.25 * turns
        cen = P + nrm * (cr * 0.05 + (0.0026 + cr * 0.55 + tr) * (1 - edge))
        hv = rng.uniform(0.0, 0.6)
        for vv, ff, _ in coil(cen, ax, nrm, cr, turns, ln, tr, seg=11, phase=rng.uniform(0, 6.28), ring=4):
            G.add(vv, ff, 0, {'head': 1.0}, attrs={'hair_var': hv + rng.uniform(-0.1, 0.1)})
        count += 1
    log("  scalp curls", count)
    # --- bun core + curls
    log("hair: bun")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    bv = []
    for v in bm.verts:
        d = v.co.normalized()
        rr = 1.0 + noise.noise(d * 3.0) * 0.08
        bv.append(BUN_C + V(d.x * BUN_R.x, d.y * BUN_R.y, d.z * BUN_R.z) * rr)
    bfaces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    bfaces = fix_winding_outward(bv, bfaces, lambda c: BUN_C)
    G.add(bv, bfaces, 0, {'bun': 1.0}, attrs={'hair_var': 0.1})
    NB = 240
    for i in range(NB):
        z = 1 - 2 * (i + 0.5) / NB
        r = math.sqrt(1 - z * z)
        d = V(r * math.cos(ga * i), r * math.sin(ga * i), z)
        if d.z < -0.62:
            continue
        P = BUN_C + V(d.x * BUN_R.x, d.y * BUN_R.y, d.z * BUN_R.z) * (1.0 + noise.noise(d * 3.0) * 0.08)
        nrm = V(d.x / BUN_R.x, d.y / BUN_R.y, d.z / BUN_R.z).normalized()
        t, _ = orthonormal(nrm)
        ax = Matrix.Rotation(rng.uniform(0, 6.28), 3, nrm) @ t
        cr = rng.uniform(0.0100, 0.0140)
        tr = rng.uniform(0.0041, 0.0050)
        turns = rng.uniform(1.2, 2.0)
        cen = P + nrm * (cr * 0.15)
        hv = rng.uniform(0.0, 0.65)
        for vv, ff, _ in coil(cen, ax, nrm, cr, turns, cr * 1.45 * turns, tr, seg=12, phase=rng.uniform(0, 6.28), ring=4):
            G.add(vv, ff, 0, {'bun': 1.0}, attrs={'hair_var': hv + rng.uniform(-0.1, 0.1)})
    for i in range(46):  # messy outer loops for a lively silhouette
        d = V(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.25, 1)).normalized()
        P = BUN_C + V(d.x * BUN_R.x, d.y * BUN_R.y, d.z * BUN_R.z) * 1.04
        nrm = d
        t, _ = orthonormal(nrm)
        ax = Matrix.Rotation(rng.uniform(0, 6.28), 3, nrm) @ t
        cr = rng.uniform(0.012, 0.0165)
        tr = rng.uniform(0.0040, 0.0047)
        turns = rng.uniform(1.0, 1.7)
        cen = P + nrm * (cr * 0.55)
        hv = rng.uniform(0.1, 0.7)
        for vv, ff, _ in coil(cen, ax, nrm, cr, turns, cr * 1.2 * turns, tr, seg=13, phase=rng.uniform(0, 6.28), ring=4):
            G.add(vv, ff, 0, {'bun': 1.0}, attrs={'hair_var': hv + rng.uniform(-0.1, 0.1)})
    # --- ringlets framing the face
    log("hair: ringlets")
    rdefs = [  # name, phi, el offset above hairline, length, coil r, pitch factor, tube r
        ('fore', 15, 2.0, 0.026, 0.0060, 2.9, 0.0032),
        ('temple', 44, 2.0, 0.100, 0.0074, 2.15, 0.0049),
        ('side', 64, 3.0, 0.085, 0.0070, 2.15, 0.0046),
        ('ear', 100, 3.0, 0.115, 0.0078, 2.15, 0.0050),
        ('back', 128, 4.0, 0.105, 0.0078, 2.15, 0.0050),
        ('nape', 160, 4.0, 0.080, 0.0074, 2.15, 0.0048),
    ]
    bones = []
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        for (nm, phi, elo, ln, cr, pf, tr) in rdefs:
            turns = ln / (pf * tr * 1.05)
            phi_ = phi + rng.uniform(-3, 3)
            el = hairline_el(phi_) + elo + 6
            d = V(s * math.sin(math.radians(phi_)) * math.cos(math.radians(el)),
                  -math.cos(math.radians(phi_)) * math.cos(math.radians(el)), math.sin(math.radians(el)))
            A = cap_point(d) - d * 0.002
            nrm = d
            t0 = V(0, 0, -1) - nrm * (-nrm.z)
            t0 = t0.normalized() if t0.length > 1e-4 else V(0, 0, -1)
            ph0 = rng.uniform(0, 6.28)
            spine = [A]
            K = 14
            ln_ = ln * rng.uniform(0.92, 1.08)
            for k in range(1, K):
                sk = k / (K - 1)
                wig = V(noise.noise(V(sk * 3, ph0, 1.0)), noise.noise(V(sk * 3, ph0, 2.0)), 0) * 0.35
                dirv = (t0 * (1 - smoothstep(0, 0.5, sk)) + V(0, 0, -1) * smoothstep(0, 0.5, sk) +
                        V(d.x, d.y * 0.5, 0) * 0.25 + wig).normalized()
                p = spine[-1] + dirv * (ln_ / (K - 1))
                # keep clear of the head / cheeks / neck / shoulders
                for _ in range(3):
                    q = p - HC
                    dd = q.normalized()
                    lim = (head_surface(dd) - HC).length + cap_thick(dd) * 0.5 + cr + tr + (0.010 if nm in ('temple', 'side') else 0.003)
                    if q.length < lim:
                        p = HC + dd * lim
                    rq = V(p.x, p.y - 0.004, 0)
                    if p.z < 0.66 and rq.length < 0.045 + cr:
                        p = V(0, 0.004, p.z) + rq.normalized() * (0.045 + cr)
                    if p.z < 0.565 + cr:
                        p.z = 0.565 + cr
                spine.append(p)
            # helix around the spine
            npts = int(turns * 14) + 1
            Ts = []
            pts, rad, prm = [], [], []
            Nn, _ = orthonormal(spine[1] - spine[0])
            for i in range(npts):
                sk = i / (npts - 1)
                fk = sk * (K - 1)
                k0 = min(int(fk), K - 2)
                c = spine[k0].lerp(spine[k0 + 1], fk - k0)
                tg = (spine[k0 + 1] - spine[k0]).normalized()
                Nn = (Nn - tg * Nn.dot(tg)).normalized()
                Bn = tg.cross(Nn)
                ph = ph0 + 2 * math.pi * turns * sk
                rr = cr * lerp(0.45, 1.0, smoothstep(0, 0.12, sk)) * lerp(1.0, 0.65, sk) * (1 + 0.22 * noise.noise(V(sk * 6.0, ph0, 0.3)))
                pts.append(c + (Nn * math.cos(ph) + Bn * math.sin(ph)) * rr)
                rad.append(tr * lerp(1.0, 0.7, sk))
                prm.append(sk)
            bundle = strands(pts, rad, nstr=4, twist=turns * 0.35, ring=5, phase=ph0)
            b1, b2 = f"curl_{nm}.{sfx}.01", f"curl_{nm}.{sfx}.02"
            mid = spine[K // 2]
            bones.append((b1, spine[1], mid))
            bones.append((b2, mid, spine[-1]))
            hv = rng.uniform(0.15, 0.6)
            for vv, ff, pp in bundle:
              wl = []
              for sp in pp:
                if sp < 0.12:
                    w = {'head': 1 - smoothstep(0.0, 0.12, sp), b1: smoothstep(0.0, 0.12, sp)}
                elif sp < 0.6:
                    a_ = smoothstep(0.4, 0.6, sp)
                    w = {b1: 1 - a_, b2: a_}
                else:
                    w = {b2: 1.0}
                wl.append(w)
              G.add(vv, ff, 0, wl, attrs={'hair_var': hv + rng.uniform(-0.12, 0.12)})
    curls = make_object("Hani_hair_curls", G, [M['hair']], coll)
    # --- hair tie
    G = Geo()
    nT, nt_ = 40, 10
    Rt, rt = 0.0265, 0.0058
    n1, n2 = orthonormal(TIE_AX)
    tv, tf = [], []
    for i in range(nT):
        a = 2 * math.pi * i / nT
        c = TIE_C + (n1 * math.cos(a) + n2 * math.sin(a)) * Rt
        rad = (n1 * math.cos(a) + n2 * math.sin(a))
        for j in range(nt_):
            b = 2 * math.pi * j / nt_
            tv.append(c + (rad * math.cos(b) + TIE_AX * math.sin(b) * 1.25) * rt)
    for i in range(nT):
        for j in range(nt_):
            i2, j2 = (i + 1) % nT, (j + 1) % nt_
            tf.append((i * nt_ + j, i2 * nt_ + j, i2 * nt_ + j2, i * nt_ + j2))
    tf = fix_winding_outward(tv, tf, lambda c: TIE_C + ((c - TIE_C) - TIE_AX * (c - TIE_C).dot(TIE_AX)).normalized() * Rt)
    G.add(tv, tf, 0, {'head': 1.0})
    tie = make_object("Hani_hair_tie", G, [M['tie']], coll, subsurf=1)
    return [cap, curls, tie], bones


# ----------------------------------------------------------------------------- BODY
SH = {1: V(0.090, 0.004, 0.522), -1: V(-0.090, 0.004, 0.522)}
ARM_DOWN = 45.0
L_UP, L_LO = 0.110, 0.100
HIPJ = {1: V(0.048, 0.0, 0.300), -1: V(-0.048, 0.0, 0.300)}
KNEE = {1: V(0.050, -0.006, 0.168), -1: V(-0.050, -0.006, 0.168)}
ANK = {1: V(0.051, 0.006, 0.052), -1: V(-0.051, 0.006, 0.052)}
TOE = {1: V(0.053, -0.060, 0.016), -1: V(-0.053, -0.060, 0.016)}


def arm_points(s):
    S = SH[s]
    a1 = V(s * math.sin(math.radians(ARM_DOWN)), 0.0, -math.cos(math.radians(ARM_DOWN)))
    E = S + a1 * L_UP
    a2 = (Matrix.Rotation(math.radians(8), 3, V(0, 0, 1) if s > 0 else V(0, 0, -1)) @ a1)
    a2 = (a2 + V(0, -0.12, 0)).normalized()
    W = E + a2 * L_LO
    a3 = a2
    pn = V(-s * math.cos(math.radians(ARM_DOWN)), 0, -math.sin(math.radians(ARM_DOWN)))
    pn = (pn - a3 * pn.dot(a3)).normalized()      # palm normal (towards the body)
    th = a3.cross(pn).normalized() * (-s)          # thumb side (roughly forward)
    if th.y > 0:
        th = -th
    return S, E, W, a1, a2, a3, pn, th


def metaball_mesh(name, elems, res=0.0022, thresh=0.6):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = res
    mb.render_resolution = res
    mb.threshold = thresh
    ob = bpy.data.objects.new(name, mb)
    bpy.context.scene.collection.objects.link(ob)
    for (kind, p0, p1, r, stiff) in elems:
        el = mb.elements.new()
        el.stiffness = stiff
        vis = (1 - (thresh / stiff) ** (1 / 3)) ** 0.5
        el.radius = r / vis
        if kind == 'ball':
            el.type = 'BALL'
            el.co = p0
        else:
            el.type = 'CAPSULE'
            el.co = (p0 + p1) / 2
            d = p1 - p0
            el.size_x = d.length / 2
            el.rotation = V(1, 0, 0).rotation_difference(d.normalized())
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.metaballs.remove(mb)
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    bpy.data.meshes.remove(me)
    return verts, faces


def seg_param(p, a, b):
    ab = b - a
    t = clamp((p - a).dot(ab) / ab.length_squared)
    return t, (a + ab * t - p).length


def build_body(M, coll):
    log("body: arms")
    G = Geo()
    hand_frames = {}
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        S, E, W, a1, a2, a3, pn, th = arm_points(s)
        side = a3.cross(pn).normalized()
        if side.dot(th) < 0:
            side = -side
        el = [('cap', S + a1 * 0.016, E, 0.0222, 2.0),
              ('cap', E, E + a2 * 0.05, 0.0205, 2.0),
              ('cap', E + a2 * 0.05, W - a3 * 0.004, 0.0178, 2.0),
              ('ball', W + a3 * 0.004, None, 0.0148, 2.0)]
        # hand (palm + fingers + thumb), toddler-chubby
        pc = W + a3 * 0.019 + pn * 0.001
        el += [('cap', W + a3 * 0.010 + side * 0.004, W + a3 * 0.026 - side * 0.002, 0.0118, 2.0),
               ('cap', W + a3 * 0.012 - side * 0.007, W + a3 * 0.026 - side * 0.007, 0.0098, 2.0)]
        K = W + a3 * 0.030
        offs = [0.0080, 0.0027, -0.0027, -0.0078]
        lens = [0.0180, 0.0205, 0.0195, 0.0160]
        for k in range(4):
            b0 = K + side * offs[k] - a3 * 0.004
            d1 = (a3 + pn * 0.25 + side * (offs[k] * 6)).normalized()
            b1 = b0 + d1 * lens[k] * 0.55
            d2 = (a3 + pn * 0.65 + side * (offs[k] * 6)).normalized()
            b2 = b1 + d2 * lens[k] * 0.45
            rr = 0.0044 if k < 3 else 0.0039
            el += [('cap', b0, b1, rr, 3.2), ('cap', b1, b2, rr * 0.92, 3.2)]
        t0 = W + a3 * 0.010 + side * 0.010 + pn * 0.003
        td = (a3 * 0.6 + side * 0.55 + pn * 0.35).normalized()
        t1 = t0 + td * 0.013
        t2 = t1 + (a3 * 0.8 + side * 0.15 + pn * 0.45).normalized() * 0.010
        el += [('cap', t0, t1, 0.0058, 3.0), ('cap', t1, t2, 0.0050, 3.0)]
        vv, ff = metaball_mesh("MBarm" + sfx, el, res=0.0016)
        hand_frames[s] = dict(W=W, K=K, a3=a3, pn=pn, side=side, t0=t0, t2=t2, S=S, E=E)
        wl = []
        for p in vv:
            w = {}
            hp = (p - W).dot(a3)
            tt, dist_t = seg_param(p, t0 - td * 0.004, t2)
            if hp < -0.002:
                tu, du = seg_param(p, S, E)
                tl, dl = seg_param(p, E, W)
                if du < dl or tu < 1 and (p - S).dot(a1) < L_UP - 0.012:
                    a_ = smoothstep(L_UP - 0.016, L_UP + 0.006, (p - S).dot(a1))
                    w = {'upper_arm.' + sfx: 1 - a_, 'lower_arm.' + sfx: a_}
                else:
                    w = {'lower_arm.' + sfx: 1.0}
                if (p - S).dot(a1) < 0.012:
                    w = {k: v * 0.8 for k, v in w.items()}
                    w['shoulder.' + sfx] = 0.2
                hw = smoothstep(-0.012, -0.002, hp)
                if hw > 0:
                    w = {k: v * (1 - hw) for k, v in w.items()}
                    w['hand.' + sfx] = hw
            else:
                fw = smoothstep(0.023, 0.032, hp)
                thw = 1 - smoothstep(0.0055, 0.009, dist_t) if tt > 0.15 else 0.0
                thw *= (1 - fw)
                w = {'hand.' + sfx: max(0.0, 1 - fw - thw), 'fingers.' + sfx: fw, 'thumb.' + sfx: thw}
                lw = 1 - smoothstep(-0.002, 0.006, hp)
                if lw > 0:
                    w = {k: v * (1 - lw) for k, v in w.items()}
                    w['lower_arm.' + sfx] = lw
            wl.append(w)
        G.add(vv, ff, 0, wl)
    log("body: legs")
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        Hj, Kn, An, To = HIPJ[s], KNEE[s], ANK[s], TOE[s]
        el = [('cap', Hj + V(0, 0, 0.03), Kn, 0.0335, 2.0),
              ('cap', Kn, Kn + (An - Kn) * 0.45, 0.0275, 2.0),
              ('cap', Kn + (An - Kn) * 0.45, An, 0.0200, 2.0),
              ('cap', An + V(0, 0.012, -0.022), An + (To - An) * 0.70 + V(0, 0, 0.003), 0.0160, 2.0)]
        vv, ff = metaball_mesh("MBleg" + sfx, el, res=0.0025)
        wl = []
        for p in vv:
            t1, d1 = seg_param(p, Hj, Kn)
            t2, d2 = seg_param(p, Kn, An)
            if p.z > An.z + 0.012 or (p - An).length > 0.03:
                if p.z > Kn.z + 0.012:
                    a_ = smoothstep(Hj.z + 0.0, Hj.z + 0.04, p.z)
                    w = {'thigh.' + sfx: 1 - a_ * 0.5, 'hips': a_ * 0.5}
                    kb = smoothstep(Kn.z + 0.028, Kn.z + 0.008, p.z)
                    if kb > 0:
                        w = {k: v * (1 - kb) for k, v in w.items()}
                        w['shin.' + sfx] = kb * 0.5
                        w['thigh.' + sfx] = w.get('thigh.' + sfx, 0) + kb * 0.5
                else:
                    kb = smoothstep(Kn.z + 0.012, Kn.z - 0.012, p.z)
                    w = {'thigh.' + sfx: 1 - kb, 'shin.' + sfx: kb}
                    if p.z < An.z + 0.03:
                        fb = smoothstep(An.z + 0.03, An.z + 0.005, p.z) * 0.5
                        w = {k: v * (1 - fb) for k, v in w.items()}
                        w['foot.' + sfx] = fb
            else:
                fb = smoothstep(0.0, 0.02, (p - An).dot((To - An).normalized()) + 0.012)
                w = {'shin.' + sfx: 1 - fb, 'foot.' + sfx: fb}
            wl.append(w)
        G.add(vv, ff, 0, wl)
    # neck
    rings = [(0.528, 0.038, 0.035, 0.004), (0.555, 0.0385, 0.035, 0.004), (0.58, 0.039, 0.036, 0.006),
             (0.60, 0.040, 0.037, 0.008), (0.63, 0.039, 0.036, 0.010)]
    vv, ff = lathe(rings, 24)
    wl = []
    for p in vv:
        a_ = smoothstep(0.56, 0.60, p.z)
        b_ = smoothstep(0.528, 0.552, p.z)
        wl.append({'chest': 1 - b_, 'neck': b_ * (1 - a_), 'head': a_ * b_ + a_ * (1 - b_)})
    G.add(vv, ff, 0, wl)
    ob = make_object("Hani_body", G, [M['skin']], coll)
    return ob, hand_frames


def star_mesh(center, R, r, depth, rot):
    verts = [center + rot @ V(0, -depth, 0), center + rot @ V(0, depth * 0.3, 0)]
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = R if k % 2 == 0 else r
        verts.append(center + rot @ V(rr * math.cos(a), 0, rr * math.sin(a)))
    faces = []
    for k in range(10):
        a, b = 2 + k, 2 + (k + 1) % 10
        faces.append((0, b, a))
        faces.append((1, a, b))
    return verts, faces


def skirt_layer_def(layer):
    # (waist z, waist r, hem z, hem r, folds, amp, phase, ring count)
    return [dict(z0=0.418, r0=0.097, z1=0.186, r1=0.196, k=13, amp=0.010, ph=0.3, hem=0.003),
            dict(z0=0.420, r0=0.101, z1=0.172, r1=0.207, k=16, amp=0.014, ph=1.7, hem=0.004),
            dict(z0=0.422, r0=0.105, z1=0.163, r1=0.216, k=19, amp=0.016, ph=0.9, hem=0.005)][layer]


SKIRT_NSEG, SKIRT_NR = 120, 16


def skirt_profile(L, t):
    z = lerp(L['z0'], L['z1'], t)
    r = L['r0'] + (L['r1'] - L['r0']) * (1 - (1 - t) ** 1.7)
    return z, r


def skirt_fold(L, th, t):
    m = 1 + (L['amp'] * (0.15 + 0.85 * t) / 0.2) * math.sin(L['k'] * th + L['ph'] + 0.6 * math.sin(3 * th))
    dz = L['hem'] * math.sin(L['k'] * 0.5 * th + L['ph'] * 2) * t ** 3
    return m, dz


def build_dress(M, coll):
    log("dress")
    obs = []
    # bodice
    rings = [(0.398, 0.096, 0.083, 0.004), (0.425, 0.100, 0.087, 0.002), (0.455, 0.101, 0.086, 0.0),
             (0.485, 0.099, 0.081, 0.002), (0.508, 0.095, 0.075, 0.004), (0.527, 0.087, 0.067, 0.006),
             (0.542, 0.073, 0.057, 0.006), (0.551, 0.056, 0.047, 0.006), (0.557, 0.040, 0.037, 0.006)]
    vv, ff = lathe(rings, 64)
    G = Geo()
    wl = []
    for p in vv:
        a_ = smoothstep(0.42, 0.47, p.z)
        b_ = smoothstep(0.47, 0.52, p.z)
        w = {'hips': 1 - a_, 'spine': a_ * (1 - b_), 'chest': b_}
        sh = smoothstep(0.06, 0.09, abs(p.x)) * smoothstep(0.49, 0.53, p.z)
        if sh > 0:
            w = {k: v * (1 - sh * 0.5) for k, v in w.items()}
            w['shoulder.' + ('L' if p.x > 0 else 'R')] = sh * 0.5
        wl.append(w)
    G.add(vv, ff, 0, wl)
    obs.append(make_object("Hani_dress_bodice", G, [M['bodice']], coll, subsurf=1, subsurf_render=2))
    # waistband
    rings = [(0.402, 0.0985, 0.0855, 0.004), (0.405, 0.1025, 0.0895, 0.003), (0.417, 0.1035, 0.0905, 0.003),
             (0.425, 0.1015, 0.0885, 0.002), (0.427, 0.0995, 0.0865, 0.002)]
    vv, ff = lathe(rings, 72)
    G = Geo()
    G.add(vv, ff, 0, {'hips': 1.0})
    obs.append(make_object("Hani_dress_waistband", G, [M['white']], coll, subsurf=1))
    # skirt layers
    skirts = []
    for layer, (nm, mat) in enumerate((("Hani_skirt_under", 'skirt_under'), ("Hani_skirt_tulle_a", 'tulle1'),
                                        ("Hani_skirt_tulle_b", 'tulle2'))):
        L = skirt_layer_def(layer)
        verts, faces = [], []
        for k in range(SKIRT_NR):
            t = k / (SKIRT_NR - 1)
            z, r = skirt_profile(L, t)
            for j in range(SKIRT_NSEG):
                th = 2 * math.pi * j / SKIRT_NSEG
                m, dz = skirt_fold(L, th, t)
                verts.append(V(r * m * math.sin(th), 0.002 - r * m * 0.93 * math.cos(th), z + dz))
        for k in range(SKIRT_NR - 1):
            for j in range(SKIRT_NSEG):
                j2 = (j + 1) % SKIRT_NSEG
                a, b = k * SKIRT_NSEG + j, k * SKIRT_NSEG + j2
                faces.append((a, a + SKIRT_NSEG, b + SKIRT_NSEG, b))
        G = Geo()
        G.add(verts, faces, 0, {'hips': 1.0})
        ob = make_object(nm, G, [M[mat]], coll, subsurf=1)
        ob["skirt_layer"] = layer
        skirts.append(ob)
        obs.append(ob)
    # sleeves (puff) + cuffs
    G = Geo()
    Gc = Geo()
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        S, E, W, a1, a2, a3, pn, th = arm_points(s)
        n1, n2 = orthonormal(a1)
        prof = [(-0.020, 0.022), (-0.010, 0.033), (0.002, 0.041), (0.016, 0.043), (0.030, 0.039),
                (0.041, 0.031), (0.047, 0.0255), (0.049, 0.0235)]
        vv, ff = [], []
        ns = 40
        for k, (u, r) in enumerate(prof):
            t = k / (len(prof) - 1)
            for j in range(ns):
                a = 2 * math.pi * j / ns
                m = 1 + 0.07 * math.sin(10 * a) * math.sin(math.pi * t) + 0.04 * math.sin(20 * a) * t ** 3
                c = S + a1 * (0.012 + u) + V(0, 0, 0.004) + V(-s * 0.004, 0, 0)
                vv.append(c + (n1 * math.cos(a) + n2 * math.sin(a)) * r * m)
        for k in range(len(prof) - 1):
            for j in range(ns):
                j2 = (j + 1) % ns
                ff.append((k * ns + j, k * ns + j2, (k + 1) * ns + j2, (k + 1) * ns + j))
        cc = S + a1 * 0.03
        ff = fix_winding_outward(vv, ff, lambda c, S=S, a1=a1: S + a1 * (c - S).dot(a1))
        wl = []
        for p in vv:
            u = (p - S).dot(a1)
            a_ = smoothstep(0.0, 0.035, u)
            wl.append({'shoulder.' + sfx: 1 - a_, 'upper_arm.' + sfx: a_})
        G.add(vv, ff, 0, wl)
        # cuff band
        cv, cf = [], []
        nT, nt_ = 40, 8
        cc = S + a1 * (0.012 + 0.049) + V(0, 0, 0.004) + V(-s * 0.004, 0, 0)
        for i in range(nT):
            a = 2 * math.pi * i / nT
            rad = n1 * math.cos(a) + n2 * math.sin(a)
            c = cc + rad * 0.0232
            for j in range(nt_):
                b = 2 * math.pi * j / nt_
                cv.append(c + (rad * math.cos(b) + a1 * math.sin(b) * 1.3) * 0.0030)
        for i in range(nT):
            for j in range(nt_):
                i2, j2 = (i + 1) % nT, (j + 1) % nt_
                cf.append((i * nt_ + j, i2 * nt_ + j, i2 * nt_ + j2, i * nt_ + j2))
        cf = fix_winding_outward(cv, cf, lambda c, cc=cc, a1=a1: cc + ((c - cc) - a1 * (c - cc).dot(a1)).normalized() * 0.0232)
        Gc.add(cv, cf, 0, {'upper_arm.' + sfx: 1.0})
    obs.append(make_object("Hani_dress_sleeves", G, [M['sleeve']], coll, subsurf=1))
    obs.append(make_object("Hani_dress_cuffs", Gc, [M['white']], coll, subsurf=1))
    # collar band + pearls
    G = Geo()
    rings = [(0.5435, 0.068, 0.058, 0.006), (0.5490, 0.0585, 0.0495, 0.006), (0.5545, 0.0490, 0.0425, 0.006),
             (0.5585, 0.0420, 0.0375, 0.006), (0.5600, 0.0395, 0.0355, 0.006)]
    vv, ff = lathe(rings, 64)
    for i, p in enumerate(vv):
        vv[i] = p + (p - V(0, 0.006, p.z)).normalized() * 0.0012 + V(0, 0, 0.0012)
    G.add(vv, ff, 0, {'chest': 1.0})
    obs.append(make_object("Hani_dress_collar", G, [M['white']], coll, subsurf=1))
    G = Geo()
    NP = 26
    for k in range(NP):
        th = 2 * math.pi * (k + 0.5) / NP
        p = V(0.0585 * math.sin(th), 0.006 - 0.0505 * math.cos(th), 0.5515)
        nrm = (p - V(0, 0.006, 0.53)).normalized()
        vv, ff = uv_sphere(p + nrm * 0.0022, (0.0029, 0.0029, 0.0029), 12, 8)
        G.add(vv, ff, 0, {'chest': 1.0})
    obs.append(make_object("Hani_dress_pearls", G, [M['pearl']], coll))
    # star brooch (five-point)
    G = Geo()
    rot = Matrix.Rotation(math.radians(-14), 3, 'X')
    vv, ff = star_mesh(V(0, -0.0822, 0.493), 0.0185, 0.0080, 0.0055, rot)
    G.add(vv, ff, 0, {'chest': 1.0})
    st = make_object("Hani_dress_star", G, [M['gold']], coll, smooth=False)
    bv = st.modifiers.new("Bevel", 'BEVEL')
    bv.width = 0.0006
    bv.segments = 2
    obs.append(st)
    return obs, skirts


def build_shoes(M, coll):
    log("shoes")
    G = Geo()
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        An, To = ANK[s], TOE[s]
        fwd = (To - An)
        fwd.z = 0
        fwd.normalize()
        rgt = fwd.cross(V(0, 0, 1)).normalized()
        c = An + fwd * 0.016
        c.z = 0.0026
        SC = 1.17

        def sc(lst, c=c, SC=SC):
            return [c + (p - c) * SC for p in lst]
        verts, faces = [], []
        nu, nv = 40, 20
        keepv = []
        for i in range(nv + 1):
            el = -math.pi / 2 + math.pi * i / nv
            for j in range(nu):
                az = 2 * math.pi * j / nu
                dx, dy, dz = math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)
                # dy>0 forward(toe)
                L_ = 0.047 if dy > 0 else 0.038
                Wd = 0.0245 + 0.004 * max(0, dy)
                Ht = 0.021 + 0.006 * max(0, dy) ** 2 if dz > 0 else 0.010
                p = V(dx * Wd, dy * L_, dz * Ht)
                if dz < -0.3:
                    p.z = -0.0095 + dz * 0.0015
                verts.append(c + rgt * (p.x * s) + fwd * p.y + V(0, 0, p.z + 0.010))
                keepv.append((dz, dy))
        for i in range(nv):
            for j in range(nu):
                j2 = (j + 1) % nu
                a, b = i * nu + j, i * nu + j2
                dz, dy = keepv[a]
                dz2, dy2 = keepv[(i + 1) * nu + j]
                # opening for the foot (instep/heel region on top)
                if dz2 > 0.42 and -0.72 < dy < 0.12:
                    continue
                faces.append((a, b, b + nu, a + nu))
        faces = fix_winding_outward(verts, faces, lambda q, c=c: c + V(0, 0, 0.010))
        o = G.add(sc(verts), faces, 0, {'foot.' + sfx: 1.0})
        # sole: flat slab following the shoe outline
        sv, sf = [], []
        nsl = 40
        for zz in (-0.0022, 0.0032):
            for j in range(nsl):
                th_ = 2 * math.pi * j / nsl
                fy = math.cos(th_) * (0.0485 if math.cos(th_) > 0 else 0.0395)
                fx = math.sin(th_) * 0.0262 * (1.0 if math.cos(th_) > 0 else 0.93)
                sv.append(c + rgt * fx + fwd * fy + V(0, 0, zz))
        for j in range(nsl):
            j2 = (j + 1) % nsl
            sf.append((j, j2, nsl + j2, nsl + j))
        sv.append(c + V(0, 0, -0.0022))
        sv.append(c + V(0, 0, 0.0032))
        for j in range(nsl):
            j2 = (j + 1) % nsl
            sf.append((j2, j, 2 * nsl))
            sf.append((nsl + j, nsl + j2, 2 * nsl + 1))
        sf = fix_winding_outward(sv, sf, lambda q, c=c: c)
        G.add(sc(sv), sf, 1, {'foot.' + sfx: 1.0})
        # strap over the instep + button
        sv, sfc = [], []
        n_s = 18
        pts = []
        for k in range(n_s):
            a = math.pi * k / (n_s - 1)
            pts.append(c + fwd * 0.004 + rgt * (math.cos(a) * 0.0262) + V(0, 0, 0.010 + math.sin(a) * 0.0205 + 0.002))
        vv, ff, _ = tube(pts, [0.0026] * n_s, ring=8, cap_end=True, cap_start=True, cap_rings=1)
        G.add(sc(vv), ff, 0, {'foot.' + sfx: 1.0})
        bp = c + fwd * 0.004 + rgt * (s * 0.0262) + V(0, 0, 0.012)
        vv, ff = uv_sphere(bp + rgt * s * 0.002, (0.0035, 0.0035, 0.0035), 12, 8)
        G.add(sc(vv), ff, 2, {'foot.' + sfx: 1.0})
    ob = make_object("Hani_shoes", G, [M['shoe'], M['sole'], M['pearl']], coll, subsurf=1)
    so = ob.modifiers.new("Solidify", 'SOLIDIFY')
    so.thickness = 0.0018
    so.offset = -1
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    return ob


# ----------------------------------------------------------------------------- RIG
def build_rig(coll, info, hair_bones, hand_frames):
    log("rig")
    arm = bpy.data.armatures.new("Hani_rig")
    rig = bpy.data.objects.new("Hani_rig", arm)
    coll.objects.link(rig)
    arm.display_type = 'STICK'
    rig.show_in_front = True
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones

    def B(name, head, tail, parent=None, deform=True, roll_z=None, connect=False):
        b = eb.new(name)
        b.head, b.tail = head, tail
        if roll_z is not None:
            b.align_roll(roll_z)
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        b.use_deform = deform
        return b
    B('root', V(0, 0, 0), V(0, 0.18, 0), deform=False, roll_z=V(0, 0, 1))
    B('hips', V(0, 0, 0.32), V(0, 0, 0.41), 'root', roll_z=V(0, -1, 0))
    B('spine', V(0, 0, 0.41), V(0, 0, 0.47), 'hips', roll_z=V(0, -1, 0), connect=True)
    B('chest', V(0, 0, 0.47), V(0, 0.002, 0.545), 'spine', roll_z=V(0, -1, 0), connect=True)
    B('neck', V(0, 0.002, 0.545), V(0, 0.004, HC.z - 0.112), 'chest', roll_z=V(0, -1, 0), connect=True)
    B('head', V(0, 0.004, HC.z - 0.112), V(0, 0.004, HC.z + 0.14), 'neck', roll_z=V(0, -1, 0), connect=True)
    B('bun', BUN_C + V(0, 0, -0.045), BUN_C + V(0, 0.006, 0.06), 'head', roll_z=V(0, -1, 0))
    for s, e in info['eyes'].items():
        sfx = 'L' if s > 0 else 'R'
        B('eye.' + sfx, e['E'], e['E'] + e['f'] * 0.025, 'head', roll_z=V(0, 0, 1))
    et = (info['eyes'][1]['E'] + info['eyes'][-1]['E']) / 2 + V(0, -0.70, 0)
    B('eye_target', et, et + V(0, 0, 0.04), 'root', deform=False, roll_z=V(0, -1, 0))
    for s, e in info['eyes'].items():
        sfx = 'L' if s > 0 else 'R'
        p = e['E'] + e['f'] * (0.70 / max(0.2, -e['f'].y))
        p.z = et.z
        B('eye_target.' + sfx, p, p + V(0, 0, 0.02), 'eye_target', deform=False, roll_z=V(0, -1, 0))
    for (nm, a, b) in hair_bones:
        B(nm, a, b, 'head', roll_z=V(0, -1, 0))
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        hf = hand_frames[s]
        S, E, W, K = hf['S'], hf['E'], hf['W'], hf['K']
        a3, pn, side = hf['a3'], hf['pn'], hf['side']
        B('shoulder.' + sfx, V(s * 0.018, 0.002, 0.535), S, 'chest', roll_z=V(0, -1, 0))
        B('upper_arm.' + sfx, S, E, 'shoulder.' + sfx, roll_z=V(0, -1, 0), connect=True)
        B('lower_arm.' + sfx, E, W, 'upper_arm.' + sfx, roll_z=V(0, -1, 0), connect=True)
        B('hand.' + sfx, W, K, 'lower_arm.' + sfx, roll_z=pn, connect=True)
        B('fingers.' + sfx, K, K + a3 * 0.022, 'hand.' + sfx, roll_z=pn)
        B('thumb.' + sfx, hf['t0'], hf['t2'], 'hand.' + sfx, roll_z=pn)
        B('hand_ik.' + sfx, W, K, 'root', deform=False, roll_z=pn)
        B('arm_pole.' + sfx, E + V(s * 0.05, 0.30, 0.0), E + V(s * 0.05, 0.33, 0.0), 'root', deform=False)
        B('thigh.' + sfx, HIPJ[s], KNEE[s], 'hips', roll_z=V(0, -1, 0))
        B('shin.' + sfx, KNEE[s], ANK[s], 'thigh.' + sfx, roll_z=V(0, -1, 0), connect=True)
        B('foot.' + sfx, ANK[s], TOE[s], 'shin.' + sfx, roll_z=V(0, 0, 1), connect=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    # custom props + constraints
    pr = rig.pose.bones['root']
    pr["sit"] = 0.0
    pr.id_properties_ui("sit").update(min=0.0, max=1.0, description="Seated skirt drape (0 standing .. 1 seated)")
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        c = rig.pose.bones['eye.' + sfx].constraints.new('DAMPED_TRACK')
        c.target, c.subtarget, c.track_axis = rig, 'eye_target.' + sfx, 'TRACK_Y'
        ik = rig.pose.bones['lower_arm.' + sfx].constraints.new('IK')
        ik.target, ik.subtarget = rig, 'hand_ik.' + sfx
        ik.pole_target, ik.pole_subtarget = rig, 'arm_pole.' + sfx
        ik.chain_count = 2
        cr = rig.pose.bones['hand.' + sfx].constraints.new('COPY_ROTATION')
        cr.target, cr.subtarget = rig, 'hand_ik.' + sfx
    # pick pole angles that keep the rest pose exact
    bpy.context.view_layer.update()
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        ik = rig.pose.bones['lower_arm.' + sfx].constraints['IK']
        best = None
        for deg in range(-180, 180, 1):
            ik.pole_angle = math.radians(deg)
            bpy.context.view_layer.update()
            pb = rig.pose.bones['upper_arm.' + sfx]
            err = (pb.matrix.to_3x3() - pb.bone.matrix_local.to_3x3())
            e = sum(abs(err[i][j]) for i in range(3) for j in range(3))
            if best is None or e < best[0]:
                best = (e, deg)
        ik.pole_angle = math.radians(best[1])
        log("  pole angle", sfx, best)
    # bone collections for clarity
    cols = {}
    for nm in ('Body', 'Face', 'Hair', 'Controls'):
        cols[nm] = arm.collections.new(nm)
    for b in arm.bones:
        n = b.name
        if n.startswith(('curl_', 'bun')):
            cols['Hair'].assign(b)
        elif n.startswith(('eye',)):
            cols['Face'].assign(b)
        elif n.startswith(('hand_ik', 'arm_pole', 'root', 'eye_target')):
            cols['Controls'].assign(b)
        else:
            cols['Body'].assign(b)
    return rig


def bind(rig, ob):
    ob.parent = rig
    m = ob.modifiers.new("Armature", 'ARMATURE')
    m.object = rig
    m.use_deform_preserve_volume = ob.name in ("Hani_body",)
    ob.modifiers.move(ob.modifiers.find(m.name), 0)   # armature before subsurf/solidify


def parent_bone(ob, rig, bone):
    mw = ob.matrix_world.copy()
    ob.parent = rig
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    b = rig.data.bones[bone]
    ob.matrix_parent_inverse = (rig.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
    ob.matrix_world = mw


# ----------------------------------------------------------------------------- POSES
def set_bone_world(rig, name, M4):
    pb = rig.pose.bones[name]
    pb.matrix = rig.matrix_world.inverted() @ M4
    bpy.context.view_layer.update()


def bone_rest_world(rig, name):
    return rig.matrix_world @ rig.data.bones[name].matrix_local


def rotate_about(M4, pivot, R3):
    return Matrix.Translation(pivot) @ R3.to_4x4() @ Matrix.Translation(-pivot) @ M4


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    rig.pose.bones['root']["sit"] = 0.0
    bpy.context.view_layer.update()


def frame_between(a, b):
    """rotation taking frame a=(dir, normal) to frame b."""
    def F(d, n):
        d = d.normalized()
        n = (n - d * n.dot(d)).normalized()
        return Matrix((d, n, d.cross(n))).transposed()
    return F(*b) @ F(*a).transposed()


POSE_CONTROL_BONES = None


def pose_stand(rig, hf):
    reset_pose(rig)
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        S, W = hf[s]['S'], hf[s]['W']
        a_rest = (W - S).normalized()
        tgt = V(s * math.sin(math.radians(31)), 0.06, -math.cos(math.radians(31))).normalized()
        R = a_rest.rotation_difference(tgt).to_matrix()
        M = rotate_about(bone_rest_world(rig, 'hand_ik.' + sfx), S, R)
        # relax wrist: palm towards the skirt
        M = rotate_about(M, M.translation, Matrix.Rotation(math.radians(-6 * s), 3, 'Y'))
        set_bone_world(rig, 'hand_ik.' + sfx, M)
        pb = rig.pose.bones['fingers.' + sfx]
        pb.rotation_quaternion = Quaternion((1, 0, 0), math.radians(12))
    rig.pose.bones['head'].rotation_quaternion = Quaternion((0, 1, 0), math.radians(-3)) @ Quaternion((1, 0, 0), math.radians(3))
    bpy.context.view_layer.update()


SEAT_DROP = 0.222
SEAT_LEGS = {  # cross-legged ("criss-cross") sit, world directions per side (+1 = character left)
    'thigh': lambda s: V(s * 0.66, -0.70, 0.17),
    'shin': lambda s: V(-s * 0.80, -0.42 - 0.10 * s, -0.36),
    'foot': lambda s: V(-s * 0.75, -0.35, -0.30),
    'foot_up': lambda s: V(s * 0.1, -0.75, 0.65),
}


def pose_seated(rig, hf, hand_z=None):
    reset_pose(rig)
    set_bone_world(rig, 'root', Matrix.Translation(V(0, 0, -SEAT_DROP)) @ bone_rest_world(rig, 'root'))
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        Hj = HIPJ[s] + V(0, 0, -SEAT_DROP)
        chain = (('thigh', HIPJ[s], KNEE[s]), ('shin', KNEE[s], ANK[s]))
        start = Hj
        for nm, a_, b_ in chain:
            dvec = SEAT_LEGS[nm](s).normalized()
            Mrest = bone_rest_world(rig, nm + '.' + sfx)
            R = frame_between(((b_ - a_), V(0, -1, 0)), (dvec, V(0, -0.2, 1.0) if nm == 'thigh' else V(0, 0, 1)))
            M = R.to_4x4() @ Matrix.Translation(-Mrest.translation) @ Mrest
            M.translation = start
            set_bone_world(rig, nm + '.' + sfx, M)
            start = start + dvec * (b_ - a_).length
        Mrest = bone_rest_world(rig, 'foot.' + sfx)
        R = frame_between(((TOE[s] - ANK[s]), V(0, 0, 1)), (SEAT_LEGS['foot'](s), SEAT_LEGS['foot_up'](s)))
        M = R.to_4x4() @ Matrix.Translation(-Mrest.translation) @ Mrest
        M.translation = start
        set_bone_world(rig, 'foot.' + sfx, M)
    # torso: small forward lean, cute head tilt
    for nm, ang in (('spine', 5), ('chest', 3), ('neck', -2)):
        rig.pose.bones[nm].rotation_quaternion = Quaternion((1, 0, 0), math.radians(ang))
    rig.pose.bones['head'].rotation_quaternion = Quaternion((0, 1, 0), math.radians(-6)) @ Quaternion((1, 0, 0), math.radians(8))
    bpy.context.view_layer.update()
    # hands resting on the knees/lap
    for s in (1, -1):
        sfx = 'L' if s > 0 else 'R'
        Mr = bone_rest_world(rig, 'hand_ik.' + sfx)
        hfs = hf[s]
        R = frame_between((hfs['a3'], hfs['pn']), (V(-s * 0.45, -1.0, -0.35), V(s * 0.15, 0.1, -1.0)))
        M = R.to_4x4() @ Matrix.Translation(-Mr.translation) @ Mr
        M.translation = V(s * 0.105, -0.095, hand_z[s] if hand_z else 0.16)
        set_bone_world(rig, 'hand_ik.' + sfx, M)
        rig.pose.bones['fingers.' + sfx].rotation_quaternion = Quaternion((1, 0, 0), math.radians(18))
        pole = rig.pose.bones['arm_pole.' + sfx]
        Mp = bone_rest_world(rig, 'arm_pole.' + sfx)
        Mp.translation = V(s * 0.35, 0.15, 0.25)
        set_bone_world(rig, 'arm_pole.' + sfx, Mp)
    Mt = bone_rest_world(rig, 'eye_target')
    Mt.translation = V(0, -0.70, 0.40)
    set_bone_world(rig, 'eye_target', Mt)
    rig.pose.bones['root']["sit"] = 1.0
    bpy.context.view_layer.update()


def key_pose(rig, name):
    rig.animation_data_create()
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.keyframe_insert('location', frame=1, group=pb.name)
        pb.keyframe_insert('rotation_quaternion', frame=1, group=pb.name)
    rig.pose.bones['root'].keyframe_insert('["sit"]', frame=1, group='root')
    act = rig.animation_data.action
    act.name = name
    act.use_fake_user = True
    rig.animation_data.action = None
    return act


# ----------------------------------------------------------------------------- SKIRT DRAPE
def drape_skirts(rig, skirts, legs_ob, shoes_ob, leg_vid_ranges):
    """Bake a 'skirt_sit' shape key per layer, computed against the posed legs (rest/hips space)."""
    log("skirt drape")
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob, ranges in ((legs_ob, leg_vid_ranges), (shoes_ob, None)):
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        n = len(me.vertices)
        for i, v in enumerate(me.vertices):
            if ranges and not any(a <= i < b for a, b in ranges):
                continue
            pts.append(mw @ v.co)
        ev.to_mesh_clear()
    pb = rig.pose.bones['hips']
    Mh = rig.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted()
    Mhi = Mh.inverted()
    rp = [Mhi @ p for p in pts]
    # heightfield
    res, ext = 0.006, 0.5
    nG = int(2 * ext / res) + 1
    Hf = np.full((nG, nG), -1.0)
    for p in rp:
        ix, iy = int((p.x + ext) / res), int((p.y + ext) / res)
        if 0 <= ix < nG and 0 <= iy < nG:
            Hf[ix, iy] = max(Hf[ix, iy], p.z)
    # dilate + blur
    for _ in range(2):
        H2 = Hf.copy()
        H2[1:, :] = np.maximum(H2[1:, :], Hf[:-1, :])
        H2[:-1, :] = np.maximum(H2[:-1, :], Hf[1:, :])
        H2[:, 1:] = np.maximum(H2[:, 1:], Hf[:, :-1])
        H2[:, :-1] = np.maximum(H2[:, :-1], Hf[:, 1:])
        Hf = H2
    gz = (Mhi @ V(0, 0, 0.0)).z
    Hf = np.maximum(Hf, gz)
    for _ in range(3):
        Hp = np.pad(Hf, 1, mode='edge')
        Hf = np.maximum(Hf * 0.0 + (Hp[:-2, 1:-1] + Hp[2:, 1:-1] + Hp[1:-1, :-2] + Hp[1:-1, 2:] + Hf * 2) / 6, gz)

    def H(x, y):
        fx, fy = (x + ext) / res, (y + ext) / res
        ix, iy = int(math.floor(fx)), int(math.floor(fy))
        if ix < 0 or iy < 0 or ix >= nG - 1 or iy >= nG - 1:
            return gz
        tx, ty = fx - ix, fy - iy
        return (Hf[ix, iy] * (1 - tx) * (1 - ty) + Hf[ix + 1, iy] * tx * (1 - ty) +
                Hf[ix, iy + 1] * (1 - tx) * ty + Hf[ix + 1, iy + 1] * tx * ty)
    for ob in skirts:
        layer = ob["skirt_layer"]
        L = skirt_layer_def(layer)
        clear = 0.006 + 0.0045 * layer
        prof = [skirt_profile(L, k / (SKIRT_NR - 1)) for k in range(SKIRT_NR)]
        sk_co = [None] * (SKIRT_NR * SKIRT_NSEG)
        for j in range(SKIRT_NSEG):
            th = 2 * math.pi * j / SKIRT_NSEG
            sn, cs = math.sin(th), math.cos(th)
            rr, zz = prof[0][1], prof[0][0]
            path = [(rr, zz)]
            for k in range(1, SKIRT_NR):
                dr = prof[k][1] - prof[k - 1][1]
                dzz = prof[k][0] - prof[k - 1][0]
                ds = math.hypot(dr, dzz)
                dirv = V(dr, dzz).normalized()
                dirv = (dirv + V(0.0, -0.95)).normalized()
                rem = ds
                for _ in range(4):
                    nr_, nz_ = rr + dirv.x * rem, zz + dirv.y * rem
                    hh = H(nr_ * sn, 0.002 - nr_ * 0.93 * cs) + clear
                    if nz_ < hh:
                        nz_ = hh
                    step = math.hypot(nr_ - rr, nz_ - zz)
                    rr, zz = nr_, nz_
                    rem -= step
                    if rem < 1e-4:
                        break
                    dirv = V(1.0, 0.0)
                path.append((rr, zz))
            for k in range(SKIRT_NR):
                t = k / (SKIRT_NR - 1)
                m, dz = skirt_fold(L, th, t)
                rr, zz = path[k]
                flat = smoothstep(0.012, 0.0, zz - (gz + clear))
                mm = 1 + (m - 1) * (1 - 0.5 * flat)
                sk_co[k * SKIRT_NSEG + j] = (rr * mm * sn, 0.002 - rr * mm * 0.93 * cs, zz + dz * (1 - flat) + abs(m - 1) * 0.25 * flat * 0.02)
        if not ob.data.shape_keys:
            ob.shape_key_add(name='Basis', from_mix=False)
        kb = ob.shape_key_add(name='skirt_sit', from_mix=False)
        kb.data.foreach_set('co', [c for p in sk_co for c in p])
        fc = kb.driver_add('value')
        drv = fc.driver
        drv.type = 'SUM'
        var = drv.variables.new()
        var.name = 'sit'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = rig
        var.targets[0].data_path = 'pose.bones["root"]["sit"]'
    return H


# ----------------------------------------------------------------------------- MAIN
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.unit_settings.system = 'METRIC'
    scn.render.engine = 'BLENDER_EEVEE_NEXT'
    rng = random.Random(7)
    coll = bpy.data.collections.new("Hani")
    scn.collection.children.link(coll)
    M = build_materials()
    head, info = build_head(M, coll)
    eyes = build_eyes(M, coll, info)
    ears = build_ears(M, coll)
    hair_obs, hair_bones = build_hair(M, coll, rng)
    body, hand_frames = build_body(M, coll)
    dress_obs, skirts = build_dress(M, coll)
    shoes = build_shoes(M, coll)
    rig = build_rig(coll, info, hair_bones, hand_frames)
    for ob in [head, ears, body, shoes] + hair_obs + dress_obs:
        bind(rig, ob)
    for s in ('L', 'R'):
        parent_bone(eyes['eye.' + s], rig, 'eye.' + s)
        parent_bone(eyes['hl.' + s], rig, 'head')
    # leg vertex ranges in Hani_body (arms were added first): find by bone groups
    leg_ranges = []
    me = body.data
    gi = {g.name: g.index for g in body.vertex_groups}
    legset = {gi[n] for n in gi if n.startswith(('thigh', 'shin', 'foot'))}
    ids = [v.index for v in me.vertices if any(g.group in legset and g.weight > 0.3 for g in v.groups)]
    leg_ranges = [(min(ids), max(ids) + 1)]
    # poses
    pose_seated(rig, hand_frames)
    drape_skirts(rig, skirts, body, shoes, leg_ranges)
    # put hands on top of the draped skirt
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    top = skirts[-1]
    ev = top.evaluated_get(dg)
    me2 = ev.to_mesh()
    hz = {}
    for s in (1, -1):
        hx, hy = s * 0.105, -0.095
        zs = [v.co.z for v in me2.vertices if abs(v.co.x - hx) < 0.012 and abs(v.co.y - hy) < 0.012]
        hz[s] = (max(zs) if zs else 0.15) + 0.016
    ev.to_mesh_clear()
    log("  skirt top under hands", hz)
    pose_seated(rig, hand_frames, hand_z=hz)
    seated = key_pose(rig, "Hani_seated")
    pose_stand(rig, hand_frames)
    stand = key_pose(rig, "Hani_stand")
    pose_stand(rig, hand_frames)   # leave the file in the standing pose (no action assigned)
    rig["hani_info"] = "See docs/hani_rig.md. Actions: Hani_stand, Hani_seated. Face keys on Hani_head."
    scn.frame_start, scn.frame_end = 1, 1
    for ob in coll.objects:
        ob.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    log("saved", OUT)
    # stats
    tot = sum(len(o.data.vertices) for o in coll.objects if o.type == 'MESH')
    log("mesh verts total", tot)


main()
