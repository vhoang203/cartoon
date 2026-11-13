#!/usr/bin/env python3
"""Contact sheet of key frames pulled from the exported MP4 (not from source).
usage: contact_sheet.py <video.mp4> <out.png>"""
import json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
video, out = sys.argv[1], sys.argv[2]
tl = json.loads((ROOT / "build/timeline.json").read_text())
cue = {c["id"]: c for c in tl["cues"]}
PICKS = [  # (cue, offset frames, label)
    ("open", 70, "1 · Title / garden"),
    ("enter", 60, "1 · Hani brings the bowl (6)"),
    ("countH0", 150, "1 · Counting the bowl: 6"),
    ("L03", 30, "1 · Curl over the eye (personality)"),
    ("L07", 50, "1 · Hani's plate L / Mako's plate R"),
    ("share", 100, "2 · Quick sharing (arcs)"),
    ("L09", 20, "2 · After sharing: 4 / 2, bowl empty"),
    ("countH1", 90, "3 · Hani counts 1-2-3-4"),
    ("think", 75, "4 · Viewer pause, 4 vs 2"),
    ("move", 50, "5 · Hani lifts S4"),
    ("move", 70, "5 · Hand-off to Mako"),
    ("move", 112, "5 · S4 placed: 3 / 3"),
    ("countM2", 75, "5 · Mako counts 1-2-3"),
    ("L25", 45, "5 · Result: 3 = 3"),
    ("L26", 8, "6 · Celebration"),
    ("end", 45, "6 · End card, plates 3 / 3"),
]
font = ImageFont.truetype(str(ROOT / "public/fonts/Nunito.ttf"), 26)
font.set_variation_by_axes([800])
W, H = 640, 360
cols = 4
rows = (len(PICKS) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W, rows * (H + 44)), (255, 251, 242))
d = ImageDraw.Draw(sheet)
with tempfile.TemporaryDirectory() as tmp:
    for i, (cid, off, label) in enumerate(PICKS):
        f = cue[cid]["start"] + off
        png = Path(tmp) / f"{i}.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vf",
                        f"select=eq(n\\,{f}),scale={W}:{H}", "-frames:v", "1", str(png)], check=True)
        x, y = (i % cols) * W, (i // cols) * (H + 44)
        sheet.paste(Image.open(png), (x, y))
        t = f / tl["fps"]
        d.text((x + 10, y + H + 8), f"{int(t // 60)}:{t % 60:04.1f}  {label}", fill=(46, 58, 75), font=font)
sheet.save(out)
print(out)
