# Hani & Mako — Episode 01: "Bữa picnic của Hani và Mako"

Original 2D cutout educational episode (Vietnamese, ages 4–6, ~140 s, 1920×1080, 30 fps)
built with Remotion + React + TypeScript. Learning objective: **share six whole strawberries
between two friends so that each has three**.

> **Status: DRAFT with temporary synthetic voices.** Picture, timing, music, effects, captions
> and checks are complete. The voices are local Piper TTS placeholders whose commercial-use
> rights are unresolved (see `docs/provenance.md`). Replace them with cleared voices before
> publishing — the pipeline is built for that (one command, below).

## Deliverables (`out/`)

| File | What |
|---|---|
| `hani-mako-ep01-DRAFT-tempvoice.mp4` | Full episode, H.264 High / AAC 48 kHz, −16 LUFS, ≤ −1.5 dBTP |
| `hani-mako-ep01.vi.srt` | Vietnamese subtitles aligned to the actual clips (not burned in) |
| `hani-mako-ep01-thumbnail.png` | 1280×720 thumbnail (real frame from the episode) |
| `hani-mako-ep01-contact-sheet.png` | 16 key frames from the exported MP4, incl. 4/2 and 3/3 |
| `continuity-report.md` | Strawberry inventory / counting / lesson checks (auto-generated) |

Docs: `docs/script-storyboard.md` (script + storyboard), `docs/timing.md` (generated timing sheet),
`docs/recording-script.md` (lines for voice actors), `docs/provenance.md`, `docs/publication-draft.md`.

## Setup

Requires Node 22+, Python 3.11+, FFmpeg/ffprobe, and a Chromium/headless shell.

```bash
npm ci
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.lock.txt
# temporary TTS voice (only needed to regenerate synthetic lines; ~63 MB)
mkdir -p tools/voices && cd tools/voices && for f in vi_VN-vais1000-medium.onnx vi_VN-vais1000-medium.onnx.json; do \
  curl -L -o $f https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/$f; done; cd ../..
```

`remotion.config.ts` points Remotion at a local headless Chromium. Set `REMOTION_BROWSER` to use another one.

## Preview, edit, render

```bash
npm run studio          # Remotion Studio preview (needs public/audio/mix.wav -> run `npm run mix` once)
npm run build           # full pipeline: TTS/overrides -> timeline + checks + SRT -> mix -> render -> master -> thumbnail -> contact sheet
npm run render:test     # ~12 s representative test clip (speech + acting + strawberry transfers)
```

`npm run build` steps (each can be run alone):

1. `build:audio` — dialogue clips → `public/audio/dialogue/*.wav` + `src/generated/audio-manifest.json`
   (durations and per-frame mouth envelopes). Clips are cached by content hash; only changed lines regenerate.
2. `export` — builds the timeline from `src/episode01/cues.ts` + measured audio; writes `build/timeline.json`,
   the SRT, `docs/timing.md`, and runs the continuity checks (non-zero exit on failure).
3. `mix` — original music, ambience and SFX placed from the timeline; dialogue ducking; `public/audio/mix.wav`.
4. `render:raw` → `master` — Remotion render, then two-pass loudness normalisation and a YouTube-friendly encode.

### Typical edits

- **Change a line**: edit `src/episode01/dialogue.json` → `npm run build`. Timing follows the new audio.
- **Change acting / duration / camera**: edit the cue in `src/episode01/cues.ts` (`pad`, `dur`, `lead`,
  `shot`, character `pose`/`expr`/`look`/`hand`) → `npm run build`.
- **Reuse characters**: `src/lib/` holds everything episode-independent (rigs, poses, expressions,
  props, garden). A new episode is a new folder like `src/episode01/` with its own dialogue, cues and layout.

## Replacing the voices (required before publishing)

1. Record the lines in `docs/recording-script.md` (one WAV per line ID; `L27` is sung by both characters →
   `L27_hani.wav` and `L27_mako.wav`).
2. Put the files in `audio-src/overrides/` (e.g. `audio-src/overrides/L06.wav`). Any line without an
   override keeps its current clip, so you can replace lines gradually.
3. Run `OUT_NAME=hani-mako-ep01-final npm run build`.
   Clips are trimmed and levelled automatically; the timeline, mouth movement, captions and mix are rebuilt
   from the real recordings, and the continuity checks run again.
4. Watch the result. `out/continuity-report.md` must be all PASS.

An already-licensed commercial TTS can be used the same way: export its WAVs into `audio-src/overrides/`.

## Project layout

```
src/lib/                reusable series assets (palette, rig, Hani [girl], Mako [boy], props, garden, fonts)
src/episode01/          dialogue.json, cues.ts (storyboard), layout.ts, timeline.ts, evaluate.ts, Episode.tsx, Thumbnail.tsx
src/generated/          audio manifest (generated)
public/                 fonts (Nunito, OFL), dialogue clips, sfx (generated)
audio-src/overrides/    drop-in recorded voice lines
tools/                  build_audio.py, export.ts (timeline/SRT/checks), stills.mjs, contact_sheet.py, recording_script.py
docs/                   script/storyboard, timing, recording script, provenance, publication draft
```

## Assumptions made

- Character designs follow the owner's reference sheets (supplied after the first draft): **Hani** is the girl
  (curly bun, blue hair tie, sky-blue tulle dress, pink shoes) and **Mako** is the boy (curly hair, mint henley,
  navy suspenders, cream shorts, blue clogs). They were redrawn as flat 2D cutout rigs. At the owner's request the
  dress was made original (pearl collar, small star brooch, puff sleeves, no gloves) instead of the Frozen/Elsa-like
  details of the sheet. The boy's toy camera was left out of this episode to keep the scene free of extra objects.
- The rabbit "ear flop" beat became Hani's loose curl falling over her eye. Plates follow the outfits:
  Hani's plate (left) has a sky-blue rim, Mako's plate (right) a teal rim.
- The reference photos and sheets are not stored in the repository (they show a real child).
- Dialogue uses "mình" / "bạn" and the names, so no gendered pronouns were needed.
- The bowl count at the start ("một… sáu") was added because it directly supports the objective
  (six whole strawberries) and gave the opening a natural reason for Hani to be at the bowl.
- Runtime is 139.8 s (inside 135–165 s); it was reached with story beats, not padding.
- Piper TTS is stochastic: the committed clips in `public/audio/dialogue/` are the reference takes.
  Bump `TTS_VERSION` in `tools/build_audio.py` to force fresh takes.
