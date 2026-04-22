"""
Run once to generate assets/icon.png:
    python3 generate_icon.py
Requires Pillow.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SIZE = 64
OUT  = Path("assets/icon.png")
OUT.parent.mkdir(exist_ok=True)

img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded rectangle background — blue brand colour
R = 12
draw.rounded_rectangle([2, 2, SIZE - 2, SIZE - 2], radius=R, fill="#2563eb")

# "LF" in white — use default font, scale to fit
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
except Exception:
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        font = ImageFont.load_default()

text = "LF"
bbox = draw.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
x = (SIZE - tw) / 2 - bbox[0]
y = (SIZE - th) / 2 - bbox[1]
draw.text((x, y), text, fill="white", font=font)

# Also save a 32×32 for Windows / smaller displays
img.save(OUT)
img.resize((32, 32), Image.LANCZOS).save(OUT.parent / "icon_32.png")
img.resize((16, 16), Image.LANCZOS).save(OUT.parent / "icon_16.png")

print(f"Saved {OUT}")
