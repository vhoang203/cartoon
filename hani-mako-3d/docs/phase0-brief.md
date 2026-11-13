# Hani & Mako 3D — Phase 0 feasibility brief (shared by every agent)

Goal: prove whether this machine + scripted Blender can produce an **appealing, non-stiff 3D**
children's-animation look. Deliver ONE test shot (6–8 s) and a character turnaround of **Hani**.
The owner found the 2D version "stiff and ugly" — appeal, softness and lively acting matter most.

## Environment (measured)
- Blender **4.5.16 LTS** at `/usr/local/bin/blender` (headless: `blender -b ... --python script.py`).
- 4 CPU cores, no GPU, 15 GB RAM. EEVEE (`BLENDER_EEVEE_NEXT`) works via software OpenGL:
  ~25 s/frame at 1920×1080 with 16 TAA samples after the first-frame shader compile (~70 s).
  Cycles CPU: ~58 s/frame at 1080p/32 spp. **Use EEVEE.** First frame of each process is slow (shader compile).
- **Each shell command must finish in < 9 minutes.** Render in chunks (`-s`/`-e` frame ranges) or at low
  resolution for previews. Never start an unbounded render. Other agents may be rendering concurrently.
- ffmpeg/ffprobe available. Python with Pillow at `/home/user/cartoon/hani-mako-episode-01/.venv/bin/python`.
- You can view any PNG/JPG with the Read tool — **look at your renders and iterate**; do not trust code alone.

## Project layout (`/home/user/cartoon/hani-mako-3d/`)
```
scripts/     Python build scripts (source of truth; assets must be rebuildable from them)
assets/      .blend files produced by scripts (hani.blend, set.blend)
shots/       shot scripts + shot .blend (test_shot.blend)
renders/     PNG/MP4 outputs (previews, turnarounds, key frames)
docs/        this brief, rig docs, audit reports
```
Build everything procedurally with `bpy` (meshes, modifiers, shape keys, materials, armature).
No downloaded 3D models, textures, HDRIs or add-ons: all assets must be original and offline.

## References (design source — read them)
- `/home/user/refs/hani_girl_sheet.jpg` — **Hani** (girl): very curly dark hair in a high, voluminous messy bun
  with a blue hair tie, loose ringlets framing the face, big dark-brown eyes with lashes, warm light-tan skin,
  round toddler proportions (head ≈ 1/3 of height), sky-blue tulle dress, pink Mary-Jane shoes.
- `/home/user/refs/mako_boy_sheet.jpg` — **Mako** (boy) for later phases (not built in Phase 0 except as needed).
- `/home/user/refs/mood_scene_1.jpg`, `mood_scene_2.jpg` — mood: warm soft lighting, rounded shapes, glow.
- Target look: soft stylized 3D for preschoolers (rounded forms, subsurface-like skin, big expressive eyes,
  soft shadows, warm bounce light). We cannot match a photoreal film render; aim for *clean, cute, toy-like*.

### Mandatory design changes (IP safety)
The sheet's dress resembles Disney's Frozen "Elsa" costume. **Do NOT reproduce**: snowflake brooch, long
gloves, sheer long sleeves with the same pattern. Use the series' original dress: sky-blue tulle skirt with
subtle sparkle, short puff sleeves, white pearl-dot collar, small **five-point star** brooch, white waistband.
Hands are bare (needed for counting/handing strawberries). Shoes: generic pink Mary-Janes, no logos.

## World conventions
- Units: metres, Z up, camera looks toward +Y. Screen-left = −X.
- Toddler scale: Hani standing ≈ 0.90 m; head ≈ 0.30 m tall. Props slightly exaggerated for readability:
  plate Ø 0.26 m, strawberry ≈ 0.055 m wide × 0.065 m tall (clear heart/cone shape, green leafy cap,
  pale seeds, coral-red `#E9505A`-ish). Strawberries must never overlap each other.
- Picnic: blanket on grass at Z=0 (cream/pale-apricot gingham), **Hani's plate on screen-left** (sky-blue rim),
  **Mako's plate on screen-right** (teal rim), a cream bowl with an apricot band behind/between them (empty in
  this shot). Gentle garden background (soft trees/bushes, sky) — calm, nothing red or berry-like.
- Strawberry objects are named exactly `S1`…`S6`. Plate slot convention: Hani plate holds up to 4 in a row
  (left→right S1 S2 S3 S4), Mako plate up to 3.

## The Phase 0 test shot (6–8 s, 30 fps, 1920×1080)
Start state: Hani plate S1 S2 S3 S4, Mako plate S5 S6, bowl empty (the 4-vs-2 moment of Episode 01).
Mako is off-screen right (do not build Mako in Phase 0); his plate is visible.
1. Hani (sitting or kneeling on the blanket behind her plate) looks at the plates, then says the line
   **"Mình đưa một quả cho Mako nhé?"** — audio `/home/user/cartoon/hani-mako-episode-01/public/audio/dialogue/L18.wav`
   (1.64 s). Mouth must move with the audio: per-frame loudness envelope (30 fps, 0..1) is in
   `/home/user/cartoon/hani-mako-episode-01/src/generated/audio-manifest.json` → `lines.L18.env.hani`.
2. With anticipation, Hani picks up **S4** (rightmost on her plate), carries it in a visible arc and places it
   on Mako's plate (leftmost free slot). Eyes follow the strawberry. Hand must visibly contact/hold it.
3. Hani looks to camera with a happy expression and a small bounce. End state 3 vs 3.
Exactly ONE strawberry moves; total stays six; no camera cut during the move (a slow push-in is fine).
Acting must feel alive: blinks, weight shifts, overlapping motion on hair curls/bun, eased arcs, no robotic
linear interpolation, no frozen holds longer than ~1 s.

## Rig interface (character agent provides, shot agent uses) — document in `docs/hani_rig.md`
- Armature object `Hani_rig` with deform + control bones; at least: root, hips/spine/chest, neck, head,
  shoulder/upper/lower arm/hand L+R (IK targets `hand_ik.L/R` recommended), legs suitable for a sitting pose,
  bun/curl bones (or a simple way to add secondary motion).
- Face controls as shape keys on the head mesh (or bones), names: `blink_L`, `blink_R`, `mouth_open`,
  `mouth_smile`, `mouth_O`, `brow_up`, `brow_worry`; eye look via bone or empty `eye_target`.
- A seated/kneeling pose that keeps Hani's plate reachable.

## Quality bar for "Phase 0 passes"
Appealing face and silhouette that clearly reads as the girl in the sheet (bun, curls, dress colour, eyes);
soft, pleasant lighting; clean edges (no interpenetration, no black/missing materials, no flicker);
lively, readable acting; the strawberry transfer is understandable from the picture alone; mouth in sync.
