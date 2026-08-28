"""
scripts/portrait_anim.py

Generates a looping "living portrait" GIF from a single static photo:
- Subtle Ken Burns zoom+pan on the real source photo (slow scale/pan of existing pixels).
- A pulsing/rotating radial glow behind the subject in the accent color (#A855F7).
- Circular crop matching the header treatment.
- Theme-aware background (dark: #0d1117, light: #ffffff).

Usage:
    python scripts/portrait_anim.py
Outputs:
    assets/portrait-anim-dark.gif
    assets/portrait-anim-light.gif
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
SRC = WORKSPACE_DIR / "assets" / "portrait-source.png"
if not SRC.exists():
    SRC = WORKSPACE_DIR / "LinkedIn Profile.jpeg"

OUT_DIR = WORKSPACE_DIR / "assets"
ACCENT = (168, 85, 247)       # #A855F7
ACCENT_SOFT = (192, 132, 252) # lighter purple for glow highlight

CANVAS = 460          # output square canvas size
CIRCLE_D = 280        # visible circle diameter within canvas
FRAMES = 30           # frames per loop
DURATION_MS = 80      # ms per frame (~2.4s per full loop)


def load_subject():
    img = Image.open(SRC).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = int(h * 0.02)
    top = max(0, min(top, h - side))
    img = img.crop((left, top, left + side, top + min(side, h - top)))
    img = img.resize((CANVAS, CANVAS), Image.LANCZOS)
    return img


def make_glow_frame(t, bg_color):
    """t in [0,1): animation phase for pulsing + slow rotation of the glow."""
    canvas = Image.new("RGB", (CANVAS, CANVAS), bg_color)
    glow = Image.new("RGB", (CANVAS, CANVAS), bg_color)
    draw = ImageDraw.Draw(glow)

    pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi)  # 0..1
    base_r = CANVAS * 0.40
    r = base_r + pulse * (CANVAS * 0.10)

    angle = t * 2 * math.pi
    cx = CANVAS / 2 + math.cos(angle) * 20
    cy = CANVAS / 2 + math.sin(angle) * 14

    steps = 50
    for i in range(steps, 0, -1):
        frac = i / steps
        rad = r * frac
        blend = (1 - frac) ** 1.4
        color = tuple(
            int(bg_color[c] + (ACCENT_SOFT[c] - bg_color[c]) * blend * (0.75 + 0.35 * pulse))
            for c in range(3)
        )
        bbox = [cx - rad, cy - rad, cx + rad, cy + rad]
        draw.ellipse(bbox, fill=color)

    glow = glow.filter(ImageFilter.GaussianBlur(CANVAS * 0.035))
    return glow


def ken_burns_transform(img, t):
    """Slow zoom 1.0 -> 1.10 and gentle pan, ping-ponging via cosine so loop is seamless."""
    zoom_phase = (1 - math.cos(t * 2 * math.pi)) / 2  # 0..1..0 smooth
    scale = 1.0 + 0.10 * zoom_phase
    pan_x = math.sin(t * 2 * math.pi) * CANVAS * 0.015
    pan_y = math.cos(t * 2 * math.pi) * CANVAS * 0.008

    new_size = int(CANVAS * scale)
    resized = img.resize((new_size, new_size), Image.LANCZOS)
    left = (new_size - CANVAS) // 2 + int(pan_x)
    top = (new_size - CANVAS) // 2 + int(pan_y)
    left = max(0, min(left, new_size - CANVAS))
    top = max(0, min(top, new_size - CANVAS))
    return resized.crop((left, top, left + CANVAS, top + CANVAS))


def circle_mask(size, d):
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    off = (size - d) // 2
    draw.ellipse([off, off, off + d, off + d], fill=255)
    return mask


def ring_overlay(size, d, color, width=6):
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ring)
    off = (size - d) // 2
    draw.ellipse([off, off, off + d, off + d], outline=color + (255,), width=width)
    return ring


def build(bg_color, out_path):
    subject = load_subject()
    mask = circle_mask(CANVAS, CIRCLE_D)
    ring = ring_overlay(CANVAS, CIRCLE_D, ACCENT, width=7)

    frames = []
    for i in range(FRAMES):
        t = i / FRAMES
        glow = make_glow_frame(t, bg_color)
        subj_t = ken_burns_transform(subject, t)

        frame = glow.convert("RGBA")
        frame.paste(subj_t, (0, 0), mask)
        frame = Image.alpha_composite(frame, ring)
        frame = frame.convert("RGB")
        frames.append(frame)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION_MS,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {out_path} ({len(frames)} frames)")


if __name__ == "__main__":
    build((13, 17, 23), OUT_DIR / "portrait-anim-dark.gif")     # #0d1117
    build((255, 255, 255), OUT_DIR / "portrait-anim-light.gif")  # #ffffff
