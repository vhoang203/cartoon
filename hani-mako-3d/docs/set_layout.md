# Picnic set — layout, slots, look-dev (Phase 0)

Source of truth: `scripts/build_set.py` → `assets/set.blend` (about 3 s to build, fully procedural, no external data).

```
blender -b --python scripts/build_set.py                                   # rebuild assets/set.blend
blender -b assets/set.blend --python scripts/check_set.py                  # sanity check: names, slots, no overlap
blender -b assets/set.blend --python scripts/render_set.py -- \
        --cam CAM_main --out renders/set/style_frame_CAM_main.png [--pct 50] [--samples 64] [--proxy]
```
`--proxy` adds a grey kneeling-toddler stand-in at `HANI_spot` for layout checks only. It is never saved into the .blend.

Conventions follow `docs/phase0-brief.md`: metres, Z up, camera looks toward +Y, screen-left = −X.

## Renders
| file | what |
|---|---|
| `renders/set/style_frame_CAM_main.png` | 1920×1080, EEVEE, 64 TAA samples, from `CAM_main` (empty spot where Hani goes) |
| `renders/set/detail_plates_CAM_detail.png` | 1920×1080 close detail of both plates, from `CAM_detail` |
| `renders/set/layout_check_hani_proxy.png` | 960×540 framing check with the grey Hani stand-in |

Timing on this machine: about 5–6.5 min for a 1080p still at 64 samples (with other jobs running), and about 75 s at 50 % / 24 samples. The first frame of each process also pays roughly 70 s of shader compile.

## Collections and object names
| collection | objects |
|---|---|
| `SET_props` | `SET_blanket` (gingham, Solidify 4 mm), `PLATE_hani`, `PLATE_mako`, `SET_bowl`, `SET_basket` |
| `STRAWBERRIES` | `S1` … `S6` (one mesh each: body + seeds + leafy cap + stem, 4 materials) |
| `SLOTS` | empties `slot_H0..H3`, `slot_M0..M2` (children of their plate) |
| `SET_ground` | `GROUND_grass` (60 m lawn, gentle hills only beyond y > 5), `SET_daisies` (white/yellow, not red) |
| `SET_background` | `BG_tree_trunk_NN`, `BGcanopyNN` (metaball canopies), `BGbushNN` (metaball bushes) |
| `LIGHTS` | `KEY_sun`, `FILL_area`, `RIM_area`, `BOUNCE_area`, `SPEC_kicker` |
| `CAMERAS` | `CAM_main` (scene camera), `CAM_detail` |
| `GUIDES` | `HANI_spot`, `LOOK_plates`, `FOCUS_main`, `FOCUS_detail` (empties, not rendered) |

Layout values are also stored on the scene as custom props: `scene["slots"]`, `scene["hani_spot"]`, `scene["blanket_top"]`.

## Key heights
- Blanket top surface: **Z = 0.004** (blanket spans 1.70 × 1.36 m, centred at (0, 0.16)). Its edges carry soft folds and a rolled apricot hem. The central area around the plates, Hani and the bowl is flat.
- Plates: Ø 0.26 m, base at Z = 0.004, inner floor at **Z = 0.0085**, rim top ≈ Z = 0.023.

## Plates and slots (world coordinates, metres)
| object | position | notes |
|---|---|---|
| `PLATE_hani` | (−0.185, 0.000, 0.004) | screen-left, sky-blue rim `#6EC3F2` |
| `PLATE_mako` | ( 0.185, 0.000, 0.004) | screen-right, teal rim `#23B3A4` |

| slot | world XYZ | start state |
|---|---|---|
| `slot_H0` | (−0.275, 0.000, 0.0085) | S1 |
| `slot_H1` | (−0.215, 0.000, 0.0085) | S2 |
| `slot_H2` | (−0.155, 0.000, 0.0085) | S3 |
| `slot_H3` | (−0.095, 0.000, 0.0085) | **S4** (moves) |
| `slot_M0` | ( 0.125, 0.000, 0.0085) | **free → S4's target** |
| `slot_M1` | ( 0.185, 0.000, 0.0085) | S5 |
| `slot_M2` | ( 0.245, 0.000, 0.0085) | S6 |

Slot pitch is 0.06 m and a berry is at most 0.057 m wide, so there are at least 3 mm of clear gap. `check_set.py` verifies this with world-space vertex bounds.
The slot empties are parented to their plate with an identity parent-inverse, so their local location is the offset from the plate. Read the world position with `bpy.data.objects["slot_M0"].matrix_world.translation`.

### Strawberries
- Origin = **bottom contact point** (tip of the berry) and Z points up toward the cap. Putting the origin on a slot seats the berry on the plate floor. Example: `S4.matrix_world.translation = slot_M0.matrix_world.translation`, or keyframe `S4.location` to (0.125, 0, 0.0085) since the berries are unparented.
- Size: 0.055 wide × 0.065 tall (body), about 0.071 including the stem. Each berry has a slight random scale between 0.97 and 1.0, a random yaw, and a forward/back tilt of up to ±5° (never sideways, so no overlap). Custom prop `start_slot` on each berry.
- A good grab point for the hand is about 0.035 above the origin, at the widest part. The cap is at Z ≈ 0.062.
- Materials: `M_strawberry` (glossy coral-red gradient with clear-coat and a little SSS), `M_strawberry_seed` (pale cream), `M_strawberry_leaf`, `M_strawberry_stem`.

### Bowl and basket
- `SET_bowl`: cream bowl with an apricot band, empty, Ø 0.17 × 0.078 m, at (0.135, 0.33, 0.004). It sits behind and between the plates, to Hani's left (screen-right of her).
- `SET_basket`: wicker basket with a pale-blue cloth lid, at (0.62, 0.56, 0.004), back right. It balances Hani on the left of frame.

## Hani spot
- Empty **`HANI_spot` at (−0.185, 0.30, 0.004), rotation (0, 0, 0)**. Put Hani's root/pelvis pivot here, **facing −Y (toward camera)**, kneeling and sitting back on her heels, centred behind her plate.
- Clearances: keep the front of the knees and skirt at y ≥ 0.14 (the plate's back edge is at y = 0.13). Keep the skirt within x ≤ 0.04 so it clears the bowl (bowl spans x 0.05…0.22, y 0.245…0.415).
- Reach: from a shoulder at about (−0.10, 0.28, 0.33), S4 (slot_H3) is ≈ 0.40 m away and slot_M0 is ≈ 0.46 m away. Picking up from her own plate needs a small forward hinge from the hips. Placing on Mako's leftmost slot needs a clear lean to screen-right with her left hand (hand path stays in front of the bowl, y < 0.2).
- Expected head centre ≈ (−0.185, 0.30, 0.44), with the bun top ≈ 0.70 m. In `CAM_main` the head sits in the upper-left third with headroom above the bun. See `layout_check_hani_proxy.png`.
- `LOOK_plates` (0, 0, 0.03) is a handy eye target for "looks at the plates".

## Cameras
| camera | location | aims at | lens | DOF |
|---|---|---|---|---|
| `CAM_main` (scene camera) | (0.03, −1.30, 0.50) | (0.0, 0.20, 0.30) → rot ≈ (82.4°, 0°, 1.15°) | 32 mm, 36 mm sensor | f/2.8, focus `FOCUS_main` (−0.10, 0.17, 0.20) |
| `CAM_detail` | (0.00, −0.66, 0.40) | (0.0, 0.035, 0.02) | 40 mm | f/4, focus `FOCUS_detail` (0, 0, 0.03) |

`CAM_main` is at toddler eye level with a slight downward look. Both plates are readable and the horizon and garden sit in the top third. A slow push-in toward the plates works (dolly +Y about 0.2 m, or lens 32 → 38 mm). If you push in, move `FOCUS_main` too.

## Look-dev / render settings (set in `setup_render()`)
- Engine `BLENDER_EEVEE_NEXT`, 1920×1080 at 100 %, 30 fps, filter 1.5 px. **TAA render samples 32** in the file (64 used for the style stills).
- Shadows: ray count 1, step count 8. `KEY_sun` uses **jittered soft shadows** (angle 9°), which accumulate over TAA samples, so keep ≥ 24 samples or the penumbra gets grainy.
- Ray tracing on (screen space), fast GI on (global illumination, distance 0.6) and AO (`use_gtao`, distance 0.25). Jittered DOF (`use_bokeh_jittered`) avoids halos around the tree canopies.
- Colour management: **AgX, look "AgX - Punchy", exposure −0.45**, white balance 7600 K / tint +4. The scene's white is treated as slightly blue, so the grade comes out warm.
- Compositor: Glare/Bloom (threshold 3.0, so only specular glints bloom), a soft warm vignette (multiply `#D9B08C`, up to 32 % in the corners, 0 in the centre), and Hue/Sat at saturation 1.1.
- World `W_soft_sky`: a gradient (warm cream horizon → sky blue). Lighting strength is 0.32. The camera sees the sky at 2.3 through a Light Path "Is Camera Ray" mix, which gives a bright airy sky without flattening the light.

### Lights
| light | type | energy | where | role |
|---|---|---|---|---|
| `KEY_sun` | Sun, angle 9°, jittered shadows | 5.2 | from front-left-high (−2.6, −2.0, 2.6) | warm key (1.0, 0.84, 0.66) |
| `FILL_area` | Disk 2.6 m | 14 W | camera-right (1.9, −1.7, 1.1) | cool soft fill |
| `RIM_area` | Disk 1.4 m | 55 W | back-right (1.1, 1.9, 1.3), aimed at Hani's head/bun | warm peach rim |
| `BOUNCE_area` | Square 1.2 m, no shadow, no spec | 8 W | low in front (−0.1, −0.6, 0.08), aimed up at Hani | warm blanket bounce under chin |
| `SPEC_kicker` | Area 0.25 m, **specular only** | 30 W | camera-left-high (−0.55, −1.0, 0.9) | glossy highlights on berries/plates; catch-lights in eyes |

Tips for the shot and character agents:
- Append or link the collections from `assets/set.blend`. Keep `LIGHTS`, the world and the render settings, or copy them via `setup_render()` / `setup_compositor()`.
- Skin reads best with the existing key from front-left. If Hani's face looks flat, raise `RIM_area` rather than the fill.
