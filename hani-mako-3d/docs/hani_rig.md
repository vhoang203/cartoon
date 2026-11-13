# HANI — rig & animation guide (Phase 0)

Asset: `assets/hani.blend` · built by `scripts/build_hani.py` (headless, about 6 s) · lookdev/renders by
`scripts/render_hani.py` · sheets by `scripts/make_sheet.py`.
Rebuild: `blender -b --python scripts/build_hani.py`. Do not hand-edit `hani.blend`; change the script and rebuild.

## 1. Scale & orientation

| item | value |
|---|---|
| units / axes | metres, Z up, Hani faces **−Y** (towards a camera that looks along +Y) |
| left / right | `.L` = character's left = **+X** = screen-right in a front view |
| standing height | crown of hair ≈ **0.88 m**; top of bun ≈ **0.98 m** |
| head | chin 0.58 → skull top 0.81 (≈0.27 m with hair ≈0.30 m, about ⅓ of height) |
| key heights (rest) | shoulders 0.52, waist 0.42, skirt hem 0.16–0.19, eye centres 0.673 |
| rest pose | A-pose (arms 45° down). Use the actions below for real poses. |

Collection `Hani` contains everything; all meshes are parented to `Hani_rig` (Armature modifier first,
then Subdivision). Move/rotate Hani **only via the `root` bone** (or the `Hani_rig` object, which is at the origin).

## 2. Objects

| object | notes |
|---|---|
| `Hani_head` | head skin + eyelids + lashes + brows + mouth interior/tongue in one mesh. **All face shape keys live here.** Subsurf render 1. |
| `Hani_eye.L/.R` | eyeballs, parented to bones `eye.L/.R` (iris is procedural, follows the bone). |
| `Hani_eye_highlight.L/.R` | emissive catch-lights, parented to `head` (they stay put while eyes move; no shadow). |
| `Hani_hair_cap`, `Hani_hair_curls`, `Hani_hair_tie` | hair = mesh shell + ~700 scalp curls + ~280 bun curls + 12 ringlets, each curl a twisted 3–4 strand bundle (no particles). Blue tie. |
| `Hani_body` | arms+hands, legs, neck (metaball-derived skin mesh). |
| `Hani_ears` | small ears (mostly under the hair). |
| `Hani_dress_*` | bodice (sparkle), sleeves (puff), cuffs, collar + pearls, waistband, five-point gold star brooch. |
| `Hani_skirt_under`, `Hani_skirt_tulle_a/_b` | opaque underskirt + 2 translucent tulle layers (DITHERED transparency, sparkles). Each has shape key `skirt_sit` driven by the rig (see `sit`). |
| `Hani_shoes` | pink Mary-Janes (strap, pearl button), no logos. |

IP-safety changes from the reference sheet are built in: short puff sleeves, bare hands (no gloves), white
pearl-dot collar, white waistband, a **five-point** star brooch (no snowflake), plain sky-blue tulle.

## 3. Armature `Hani_rig`

Bone collections: **Body**, **Face**, **Hair**, **Controls**. Rotation mode is quaternion everywhere.

### Deform chain
`root` (control, at the floor) → `hips` (0.32) → `spine` → `chest` → `neck` → `head` (0.572→0.824)
- `head` children: `eye.L/.R`, `bun`, the curl bones.
- arms: `chest` → `shoulder.L` → `upper_arm.L` → `lower_arm.L` → `hand.L` → `fingers.L`, `thumb.L` (and `.R`).
- legs (FK): `hips` → `thigh.L` → `shin.L` → `foot.L` (and `.R`).

### Controls (not deforming)
| bone | parent | use |
|---|---|---|
| `root` | – | world placement of the whole character. Custom property **`sit`** (0..1) drives `skirt_sit` on the 3 skirt layers. |
| `hand_ik.L/.R` | root | **IK targets**. Location = wrist, rotation = hand orientation (`hand.*` copies its rotation). Rest = wrist (±0.238, 0.002, 0.373). |
| `arm_pole.L/.R` | root | elbow pole targets (behind/outside the elbows). Pole angles are pre-solved (−97° L / −83° R) so the rest pose is exact. |
| `eye_target` | root | where Hani looks. Its children `eye_target.L/.R` are offset sideways so the eyes keep their natural (slightly divergent) rest look; each eye bone has a Damped Track to its child. **Move only `eye_target`.** |

IK: `lower_arm.*` has IK (chain 2) → `hand_ik.*`, pole `arm_pole.*`. For FK, set the IK constraint influence to 0.

### Fingers / thumb
- `fingers.L/.R`: rotate **+X to curl into the palm** (all four fingers together). Relaxed 15–20°, holding
  a strawberry 45–60°, fist 75°.
- `thumb.L/.R`: **+X folds the thumb across the palm** (about 30–40° to pinch or hold).
- Palm axes in `hand.*` space: +Y = towards the fingertips, +Z = out of the palm. A held strawberry's centre
  is about `(0, 0.030, 0.028)` in `hand.L` space (Child Of constraint to `Hani_rig`/`hand.L`, set inverse at
  the grab frame). Treat this as a starting point and check contact in camera.

### Hair secondary motion
- `bun`: pivot at the hair tie; ±8–12° wobble about X/Y, lagging the head by 2–4 frames.
- Ringlet chains (2 bones each, `.01` root → `.02` tip; parent `head`):
  `curl_fore`, `curl_temple`, `curl_side`, `curl_ear`, `curl_back`, `curl_nape` × `.L/.R`.
  Overlap: `.01` lags the head by about 2 frames, `.02` by about 4 frames, with amplitude 1.5× the head's angular
  change (clamp to about 25°). A sine wobble after a head stop (2–3 cycles, decaying) reads well.

## 4. Face shape keys (on `Hani_head`, all 0..1)

| key | effect |
|---|---|
| `blink_L`, `blink_R` | close the character-left / character-right eye (upper lid down, lower lid up a little). |
| `mouth_open` | jaw drop + rounded lower lip, tongue visible. Main lip-sync key. |
| `mouth_smile` | corners up/out, cheeks lift, happy lower-lid squint. |
| `mouth_O` | lips gather into a small round "O", pushed forward, slight jaw. |
| `brow_up` | brows raise, upper lids open slightly (surprise/interest). |
| `brow_worry` | inner brow ends up, outer down. |

Data path: `bpy.data.objects["Hani_head"].data.shape_keys.key_blocks["mouth_open"].value`.
The keys combine linearly; tested combos: smile+brow_up, open+smile 0.2, O+brow_up, blink+smile.
The neutral face already has a soft closed smile.

**Lip sync** (`audio-manifest.json → lines.L18.env.hani`, 30 fps, 0..1):
`mouth_open = clamp(env * 0.85)`, plus `mouth_O = 0.3 * env` on rounded vowels (ô/o/u), and keep
`mouth_smile` around 0.25 during the line so she sounds friendly. Smooth the envelope over 2 frames and
let the mouth close (≤ 0.1) between words. **Blinks**: 1 frame half, 1 frame closed, 2–3 frames opening, every
2–4 s and on big eye moves. Use the same value on L and R, except for a wink.

**Eye range**: keep gaze within about ±20° of the face direction (move `eye_target` together with the head
for large turns). At about 30° the iris tucks under the lid corner and shows a lot of white.

## 5. Poses (actions, frame 1, keyed on every bone + `root["sit"]`)

### `Hani_stand` (turnaround pose)
Arms relaxed about 31° from vertical, palms towards the skirt, fingers 12° curl, head 3° tilt. The file is saved
in this pose with **no action assigned**.

### `Hani_seated` — cross-legged ("criss-cross") sit
- `root` loc (0, 0, **−0.222**) → hip joints about 0.08 m above the floor; `root["sit"] = 1` (skirt drape on).
- `spine` +5° X, `chest` +3° X, `neck` −2° X, `head` ≈ (8° X, −6° Y) tilt.
- thighs out-forward (knees about ±0.14 m wide), shins crossed in front, feet on their sides.
  Quaternions (w,x,y,z): `thigh.L` (0.6306, 0.6746, −0.1919, 0.3324), `thigh.R` (0.6306, 0.6746, 0.1919, −0.3324),
  `shin.L` (0.6308, −0.0685, 0.0842, −0.7683), `shin.R` (0.5537, −0.0591, −0.1137, 0.8228),
  `foot.L` (0.7657, −0.5320, −0.3288, 0.1503), `foot.R` (0.7854, −0.4809, 0.3132, −0.2318).
- hands rest on the knees: `hand_ik.*` world ≈ (±0.105, −0.095, 0.19), palms down; `arm_pole.*` world (±0.35, 0.15, 0.25).
- `eye_target` world (0, −0.70, 0.40): looking slightly down/forward.

Apply in a shot: assign the action, `frame_set(1)`, then copy each `pose_bone.matrix_basis` into your own action
(or append the action and keep animating on top of it with NLA). **Keep the leg bones and `sit` = 1
unchanged** while seated. The baked `skirt_sit` drape assumes these leg positions relative to `hips`.
Hips/spine may lean (the skirt follows `hips` rigidly).

**Reach envelope (measured):** the shoulders sit at about z 0.30. To touch something at plate height (z ≈ 0.075),
lean `hips` / `spine` / `chest` about **12° / 16° / 12°** (X, forward). With that the wrist gets within 3 cm of a point
0.20 m in front of the root (the palm adds about 3.5 cm), so S4 should be **no more than about 0.22 m forward and about
0.12 m sideways** of the `root` origin. The pooled skirt reaches about 0.26 m, so the plate rim may rest on the tulle edge.
To pass S4 towards Mako's plate (her left, +X), add `hips` Z twist (≤ 15°) and a sideways lean on `spine`/`chest`
(≤ 10° about Y), or slide `root` slightly. Stay inside the envelope rather than over-stretching the IK
(the arm snaps straight).

## 6. Rendering notes

- EEVEE Next. The character costs about **3.5 s per TAA sample on this CPU, independent of resolution** (geometry
  and shadow cost: ~300k faces, half of it hair). 16 samples is OK for motion; 24–32 for stills.
- Soft shadows of ringlets and tulle look speckled below about 12 samples; more samples clean it up.
- Tulle/sparkle use DITHERED transparency. Keep `Hani_skirt_tulle_*` visible to shadows (they look flat
  without them). The highlight objects do not cast shadows.
- Colour management used for lookdev: AgX + look "AgX - Punchy". The studio rig (key 210 W area, fill 75 W,
  two rims) lives only in `render_hani.py`; the asset has no lights or world.
- Speed-ups if needed: drop `Hani_head` subsurf to 0 in wide shots, or hide `Hani_hair_cap` (it sits under the curls).

## 7. Renders (all from `render_hani.py`, studio light rig, AgX Punchy)

`renders/hani/`: `hani_turnaround.png` (+ `_front/_34/_side`, 1280²), `hani_expressions.png` (+ `expr_*.png`, 640²),
`hani_seated.png` (+ `hani_seated_front/_34.png`, 1280²), `hani_controls_check.png` (one control per tile).
`renders/hani/wip/` keeps the iteration history (v1…v5, e_, f_, g_, h_, i_ sheets).
Job lists: `scripts/jobs_turnaround.json`, `jobs_expr_a/b.json`, `jobs_seated.json`, `jobs_ctl1/2.json`.

## 8. Known limitations (honest)

- Hair reads as curly, but the curls are chunkier and more regular ("spring"-like ringlets) than the soft,
  wispy hair of the sheet. The front hairline is still a slightly helmet-like edge.
- Hands are simple toddler mitts with one finger-curl bone. There are no individual finger poses.
- No skirt bones and no cloth sim: standing skirt is rigid with `hips`; seated drape is a baked shape key.
  Big hip motions on the standing pose will look stiff.
- Eyelids do not follow the eyes' up/down look. Extreme looks show a lot of white.
- Shape keys are not corrective: very large combined values (e.g. open 1 + O 1) can pinch the lip corners.
- With top/key light only, the area under the nose/around the mouth falls into shadow and reads slightly
  "smudgy" at full-body distance (worst with the seated head tilt). A soft warm fill/bounce from below-front
  (blanket bounce) fixes it in a shot. Contact shadows of the ringlets on the temples/cheeks and the head's
  shadow on the neck render a little mottled in EEVEE even at 24 samples.
- The jaw/lower face is a bit broad and boxy compared with the sheet's rounder chin. Closed eyelids read as
  slightly rounded "domes".
