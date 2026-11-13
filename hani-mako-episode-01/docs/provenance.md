# Asset & audio provenance — Episode 01

Recorded 2026-11-13. No paid services were used, nothing was uploaded or published.

## Original to this project (no third-party content)

| Asset | Source |
|---|---|
| Hani and Mako designs, rigs, poses, expressions | Original SVG code: `src/lib/characters/*`, `src/lib/rig.ts` |
| Garden, blanket, bowl, plates, strawberries, badges, bubbles | Original SVG code: `src/lib/environment`, `src/lib/props` |
| Story, script, storyboard, Vietnamese dialogue | Written for this project |
| Music (I–vi–IV–V arrangement in F, plucks, marimba, bass, pad) | Synthesised procedurally in `tools/build_audio.py` (no samples, no loops) |
| Sound effects (plop, whoosh, hop, boing, chimes, sparkle, tap) and garden ambience | Synthesised procedurally in `tools/build_audio.py` |
| Thumbnail, contact sheet | Rendered from the episode itself |

## Third-party components

| Component | Licence | Notes |
|---|---|---|
| **Nunito** font (`public/fonts/Nunito.ttf`) | SIL Open Font License 1.1 (`public/fonts/OFL-Nunito.txt`) | © The Nunito Project Authors. Embedded in the rendered video; no attribution required in the video. |
| **Remotion** 4.0.543 (rendering framework) | Remotion License | Free for individuals, non-profits and for-profit organisations with **up to 3 employees**; larger companies need a paid Company License. **Owner should confirm which applies.** |
| React, TypeScript | MIT / Apache-2.0 | Build tooling. |
| FFmpeg 6.1 (system) | LGPL/GPL | Processing only; not distributed. |
| faster-whisper + Whisper "small" model | MIT | Used only for intelligibility checks; nothing from it is in the video. |
| piper-tts 1.8.0 (OHF-Voice/piper1-gpl) | GPL-3.0 (software) | Generated the **temporary** voices. |

## Voices — UNRESOLVED (blocks publication)

The dialogue in the DRAFT video is produced locally with the Piper voice **`vi_VN-vais1000-medium`**
(Hugging Face `rhasspy/piper-voices`), pitch-shifted to make two characters (Hani +3.2 st, Mako −1.6 st).

- The model card states the Vietnamese training data is **VAIS-1000**, licensed **CC BY 4.0**
  (commercial use allowed with attribution).
- But the same card states the model was **fine-tuned from the U.S. English "lessac" voice**, whose training
  data (Blizzard Challenge 2013, Lessac Technologies / Voice Factory) is distributed under a
  **Research Licence Agreement** (registration-only, research use). Whether a model derived from it
  may be used to make commercially monetised audio is **not established**.
- Other Vietnamese open models were reviewed and rejected for commercial use: VIVOS-based Piper voice
  (CC BY-NC-SA), Meta MMS-TTS (CC BY-NC), VietTTS pretrained weights (CC BY-NC), viXTTS (Coqui non-commercial).
  Some newer models advertise MIT/Apache weights, but their training-data rights were not verifiable.
- Free web voices (browser/Edge "read aloud", Google Translate TTS) were not used: their terms do not grant
  commercial redistribution.

**Therefore the draft voices must not be treated as cleared.** To publish, replace them with one of:
1. Two human voice actors under a work-for-hire / buy-out agreement (recommended for a children's series), or
2. A commercial TTS service whose terms grant commercial use of output (e.g. a paid cloud TTS account the
   owner already holds), keeping a record of the plan/terms at generation time.

Then follow "Replacing the voices" in `README.md`. If a CC BY voice were ever used, credit it in the description.

## Network downloads during production

npm and PyPI packages (lockfiles: `package-lock.json`, `tools/requirements.lock.txt`), the Piper voice files
(Hugging Face), the Nunito font (google/fonts on GitHub), and the Whisper model (Hugging Face).
No accounts, keys or paid APIs were used.
