"""
portrait.py

CLI tool to convert source photograph into theme-aware glowing developer portraits.
Composites the subject photo with a soft radial accent glow in #A855F7 (Neon Purple),
producing crisp 2x resolution PNG assets tuned for GitHub Dark Mode (#0d1117) and
GitHub Light Mode (#ffffff), along with SVG wrapper assets.

Usage:
    python scripts/portrait.py [INPUT] [options]

Examples:
    python scripts/portrait.py assets/portrait-source.png --accent "#A855F7"
"""

import argparse
import base64
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
except ImportError:
    print("Error: Pillow library is required. Install it using 'pip install Pillow'.", file=sys.stderr)
    sys.exit(1)


def hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def generate_glowing_portrait(
    source_path: Path,
    output_png_path: Path,
    output_svg_path: Path = None,
    is_dark: bool = True,
    canvas_size: int = 600,
    accent_hex: str = "#A855F7"
):
    """
    Generates a photo-based portrait composited with a soft radial accent glow behind the subject.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    r_accent, g_accent, b_accent = hex_to_rgb(accent_hex)
    bg_color = (13, 17, 23, 255) if is_dark else (255, 255, 255, 255)

    # 1. Base Canvas
    canvas = Image.new("RGBA", (canvas_size, canvas_size), bg_color)

    # 2. Soft Radial Accent Glow Layer Behind Subject
    glow_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    center_x, center_y = canvas_size // 2, canvas_size // 2
    max_radius = int(canvas_size * 0.46)

    # Multi-pass radial distribution for butter-smooth glow falloff
    for r in range(max_radius, 0, -2):
        factor = 1.0 - (r / max_radius)
        alpha = int(255 * (factor ** 1.75))
        if is_dark:
            color = (r_accent, g_accent, b_accent, min(255, int(alpha * 0.85)))
        else:
            color = (r_accent, g_accent, b_accent, min(255, int(alpha * 0.50)))

        glow_draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=color
        )

    # Gaussian blur to eliminate any discrete step artifacts
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=28))
    canvas.paste(glow_layer, (0, 0), glow_layer)

    # 3. Load & Process Source Photo
    src_img = Image.open(source_path).convert("RGBA")

    # Enhance photo contrast and sharpness
    enhancer_c = ImageEnhance.Contrast(src_img)
    src_img = enhancer_c.enhance(1.15)

    enhancer_s = ImageEnhance.Sharpness(src_img)
    src_img = enhancer_s.enhance(1.25)

    # Avatar circle sizing
    avatar_size = int(canvas_size * 0.65)

    # Center crop photo to square
    w, h = src_img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    src_cropped = src_img.crop((left, top, left + min_dim, top + min_dim))
    src_resized = src_cropped.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    # Create circular mask with antialiased edge
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.2))

    # Paste circular portrait onto canvas over glow
    avatar_pos = ((canvas_size - avatar_size) // 2, (canvas_size - avatar_size) // 2)
    canvas.paste(src_resized, avatar_pos, mask)

    # 4. Cyber Accent Ring Border & Subtle Outer Glow
    ring_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring_layer)

    r_outer = avatar_size // 2
    ring_color = (r_accent, g_accent, b_accent, 255) if is_dark else (126, 34, 206, 255)

    ring_draw.ellipse(
        [center_x - r_outer, center_y - r_outer, center_x + r_outer, center_y + r_outer],
        outline=ring_color,
        width=4
    )

    ring_glow = ring_layer.filter(ImageFilter.GaussianBlur(radius=4))
    canvas.paste(ring_glow, (0, 0), ring_glow)
    canvas.paste(ring_layer, (0, 0), ring_layer)

    # Save output PNG
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_png_path, "PNG")
    print(f"Generated photo-glow portrait asset: {output_png_path}")

    # Generate corresponding SVG asset if requested
    if output_svg_path:
        with open(output_png_path, "rb") as f:
            b64_png = base64.b64encode(f.read()).decode("utf-8")

        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_size} {canvas_size}" width="100%" height="{canvas_size}">
  <image href="data:image/png;base64,{b64_png}" width="{canvas_size}" height="{canvas_size}" />
</svg>'''
        output_svg_path.write_text(svg_content, encoding="utf-8")
        print(f"Generated SVG wrapper asset: {output_svg_path}")


def main():
    parser = argparse.ArgumentParser(description="Photo-based radial glow portrait generator")
    parser.add_argument("input", nargs="?", default="assets/portrait-source.png", help="Path to input photograph")
    parser.add_argument("--accent", default="#A855F7", help="Primary accent color (default: #A855F7)")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    src_file = Path(args.input)
    if not src_file.is_absolute():
        src_file = base_dir / src_file

    if not src_file.exists():
        src_file = base_dir / "LinkedIn Profile.jpeg"

    dark_png = base_dir / "assets" / "portrait-dark.png"
    light_png = base_dir / "assets" / "portrait-light.png"
    dark_svg = base_dir / "assets" / "portrait-dark.svg"
    light_svg = base_dir / "assets" / "portrait-light.svg"

    generate_glowing_portrait(src_file, dark_png, dark_svg, is_dark=True, accent_hex=args.accent)
    generate_glowing_portrait(src_file, light_png, light_svg, is_dark=False, accent_hex=args.accent)


if __name__ == "__main__":
    main()
