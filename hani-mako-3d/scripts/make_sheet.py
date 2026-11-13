"""make_sheet.py -- compose labelled contact sheets with Pillow.
usage: python make_sheet.py OUT COLS TILE_W "label=path" ..."""
import sys
from PIL import Image, ImageDraw, ImageFont
out, cols, tw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
items = [a.split("=", 1) for a in sys.argv[4:]]
ims = []
for lab, p in items:
    im = Image.open(p).convert("RGB")
    im = im.resize((tw, int(im.height * tw / im.width)), Image.LANCZOS)
    ims.append((lab, im))
th = max(im.height for _, im in ims)
rows = (len(ims) + cols - 1) // cols
pad, lab_h = 8, 34
S = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + lab_h + pad) + pad), (236, 232, 228))
d = ImageDraw.Draw(S)
try:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
except Exception:
    f = ImageFont.load_default()
for i, (lab, im) in enumerate(ims):
    x = pad + (i % cols) * (tw + pad)
    y = pad + (i // cols) * (th + lab_h + pad)
    S.paste(im, (x, y + lab_h))
    d.text((x + 6, y + 5), lab, fill=(60, 50, 50), font=f)
S.save(out)
print("sheet", out, S.size)
