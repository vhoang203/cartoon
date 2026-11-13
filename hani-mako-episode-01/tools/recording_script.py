#!/usr/bin/env python3
"""Write docs/recording-script.md from dialogue.json + the audio manifest."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "src/episode01/dialogue.json").read_text())
m = json.loads((ROOT / "src/generated/audio-manifest.json").read_text())["lines"]
DIRECTION = {
    "L01": "arriving, a little out of breath, excited", "L01b": "curious, warm",
    "L02": "welcoming", "L03": "gentle giggle, affectionate (not teasing) — about Hani's curl", "L04": "cheerful, unbothered",
    "L05": "delighted surprise", "L06": "eager, clear — this states the goal", "L07": "agreeing, pointing left then right",
    "L07b": "calm, explicit agreement", "L08": "very eager, quick", "L09": "proud, pleased",
    "L10": "thoughtful, slow", "L11": "calm statement", "L12": "curious, kind", "L13": "cheerful (not yet noticing)",
    "L14": "mild surprise, then a little sheepish", "L15": "reassuring, kind", "L16": "to the viewer, inviting, slow; leave room",
    "L16b": "to the viewer, encouraging", "L17": "sudden idea, bright", "L18": "suggesting, slightly questioning",
    "L19": "encouraging", "L20": "grateful", "L21": "to the viewer, inviting them to count",
    "L22": "satisfied", "L23": "satisfied", "L24": "clear observation", "L25": "happy conclusion",
    "L26": "celebrating", "L26b": "warm, content", "L26c": "to the viewer, grateful",
    "L27": "BOTH together, sing-song, memorable", "L28": "waving goodbye", "L29": "waving goodbye",
}
rows = []
for l in d["lines"]:
    who = {"hani": "Hani", "mako": "Mako", "both": "Hani + Mako"}[l["speaker"]]
    files = f"`{l['id']}_hani.wav` + `{l['id']}_mako.wav`" if l["speaker"] == "both" else f"`{l['id']}.wav`"
    note = "one number, slow and clear; ~0.4–0.6 s" if l.get("count") else DIRECTION.get(l["id"], "")
    rows.append(f"| {l['id']} | {who} | {l['text']} | {m[l['id']]['duration']:.2f} s | {note} | {files} |")
out = [
    "# Voice recording script — Episode 01",
    "",
    "Record each line as a separate mono WAV (44.1 or 48 kHz, 16/24-bit), dry (no music or reverb),",
    "with ~0.3 s of room tone before and after. Names are spelled **Hani** (\"Ha-ni\") and **Mako** (\"Ma-kô\").",
    "Counting words (N*) are recorded one number per file. Durations below are the temporary TTS takes —",
    "a guide only; the timeline adapts automatically to the new lengths.",
    "",
    "Hani (little girl): bright, energetic, a little quick. Mako (little boy): calm, warm, gently funny.",
    "Audience is 4–6 years old: speak clearly and a little slower than conversational speed.",
    "",
    "| ID | Character | Line (Vietnamese) | Temp length | Direction | File name |",
    "|---|---|---|---|---|---|",
    *rows,
    "",
    "Place the files in `audio-src/overrides/` and run `OUT_NAME=hani-mako-ep01-final npm run build` (see README).",
    "",
]
(ROOT / "docs/recording-script.md").write_text("\n".join(out))
print("docs/recording-script.md", len(rows), "lines")
