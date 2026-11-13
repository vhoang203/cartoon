"""
render_shot.py -- render shots/test_shot.blend in bounded chunks.

  blender -b shots/test_shot.blend --python shots/render_shot.py -- --preset preview \
          --frames 1-24 --out renders/shot/preview/f_####.png
  blender -b shots/test_shot.blend --python shots/render_shot.py -- --preset final \
          --frames 1,111 --out renders/shot/key_{name}.png --names start,anticipation
  --preset  preview : 960x540, 6 TAA samples, no ray tracing, sharper sun (fast, for motion review)
            final   : 1920x1080, 32 TAA samples (file look-dev settings)
            check   : 640x360, 3 samples (blocking checks)
  --cam CAM_detail|CHECK_close   alternative camera (CHECK_close = close-up of hands/plates)
"""
import bpy, sys, os, time
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d


preset = arg('--preset', 'preview')
out = arg('--out', '/tmp/shot_####.png')
names = arg('--names', '')
names = names.split(',') if names else []
spec = arg('--frames', '1')
frames = []
for part in spec.split(','):
    if '-' in part:
        a, b = part.split('-')
        step = 1
        if ':' in b:
            b, step = b.split(':')
        frames += list(range(int(a), int(b) + 1, int(step)))
    else:
        frames.append(int(part))

scn = bpy.context.scene
r = scn.render
ee = scn.eevee
if preset == 'final':
    r.resolution_x, r.resolution_y = 1920, 1080
    ee.taa_render_samples = int(arg('--samples', '32'))
elif preset == 'preview':
    r.resolution_x, r.resolution_y = 960, 540
    ee.taa_render_samples = int(arg('--samples', '6'))
    ee.use_raytracing = False
    bpy.data.objects['KEY_sun'].data.angle = 0.035
    bpy.data.objects['Hani_head'].modifiers['Subdivision'].render_levels = 1
else:
    r.resolution_x, r.resolution_y = 640, 360
    ee.taa_render_samples = int(arg('--samples', '3'))
    ee.use_raytracing = False
    bpy.data.objects['KEY_sun'].data.angle = 0.035
if preset != 'final' or '--fastshadow' in argv:
    # transparent tulle shadows cost ~70 % of the frame on this CPU; opaque shadows for previews
    for n in ('Hani_skirt_tulle_a', 'Hani_skirt_tulle_b', 'Hani_skirt_under'):
        for m in bpy.data.objects[n].data.materials:
            m.use_transparent_shadow = False
r.resolution_percentage = int(arg('--pct', '100'))
r.image_settings.file_format = 'PNG'

cam = arg('--cam')
if cam == 'CHECK_close':
    cd = bpy.data.cameras.new('CHECK_close')
    co = bpy.data.objects.new('CHECK_close', cd)
    scn.collection.objects.link(co)
    loc = Vector([float(x) for x in arg('--camloc', '0.0,-0.75,0.32').split(',')])
    tgt = Vector([float(x) for x in arg('--camtgt', '0.0,0.08,0.10').split(',')])
    co.location = loc
    co.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
    cd.lens = float(arg('--lens', '40'))
    scn.camera = co
elif cam:
    scn.camera = bpy.data.objects[cam]

for i, f in enumerate(frames):
    t = time.time()
    scn.frame_set(f)
    p = out
    if '{name}' in p:
        p = p.replace('{name}', names[i] if i < len(names) else str(f))
    if '#' in p:
        n = p.count('#')
        p = p.replace('#' * n, str(f).zfill(n))
    r.filepath = os.path.abspath(p)
    bpy.ops.render.render(write_still=True)
    print('RENDERED', f, r.filepath, '%.1fs' % (time.time() - t), flush=True)
