"""
dotify.py

CLI tool and module to convert raster images (photographs, portraits) into
futuristic dot-matrix SVG vector visuals.

Usage:
    python scripts/dotify.py INPUT -o OUTPUT [options]

Examples:
    python scripts/dotify.py assets/portrait-source.png -o assets/portrait-dark.svg --cols 88 --equalize --detail 0.5 --mode dark
    python scripts/dotify.py assets/portrait-source.png -o assets/portrait-light.svg --cols 88 --equalize --detail 0.5 --mode light
    python scripts/dotify.py assets/portrait-source.png -o assets/portrait-color.svg --cols 88 --equalize --detail 0.5 --color
"""

import argparse
import math
import sys
from pathlib import Path
from typing import Tuple, List, Optional

try:
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
except ImportError:
    print("Error: Pillow library is required. Install it using 'pip install Pillow'.", file=sys.stderr)
    sys.exit(1)


def enhance_image(
    image: Image.Image,
    equalize: bool = False,
    detail: float = 0.5
) -> Image.Image:
    """
    Applies histogram equalization and detail/sharpness enhancement to the source image.
    """
    img = image.convert("RGB")

    if equalize:
        # Perform histogram equalization on luminance channel
        img_l = img.convert("L")
        img_l_eq = ImageOps.equalize(img_l)
        hsv = img.convert("HSV")
        h, s, _ = hsv.split()
        img = Image.merge("HSV", (h, s, img_l_eq)).convert("RGB")

    if detail > 0:
        # Sharpness and edge detail enhancement
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.0 + detail * 1.5)

        # Contrast enhancement for crisp facial structures
        contrast_enhancer = ImageEnhance.Contrast(img)
        img = contrast_enhancer.enhance(1.0 + detail * 0.4)

        # Apply subtle unsharp mask for sharp edge contours
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=int(detail * 100), threshold=3))

    return img


def calculate_luminance(r: int, g: int, b: int) -> float:
    """
    Calculates normalized ITU-R BT.601 luminance (0.0 to 1.0) from RGB components.
    """
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def fmt_num(val: float) -> str:
    """Formats float compactly for light SVG output."""
    res = f"{val:.1f}"
    if res.endswith(".0"):
        return res[:-2]
    return res


def generate_dot_matrix_svg(
    image_path: Path,
    cols: int = 88,
    equalize: bool = True,
    detail: float = 0.5,
    use_color: bool = False,
    accent: str = "#A855F7",
    circle_mask: bool = False,
    invert: bool = False,
    reveal: bool = False,
    reveal_time: float = 1.5,
    reveal_fade: float = 0.4,
    min_radius_ratio: float = 0.10,
    max_radius_ratio: float = 0.48,
    min_opacity: float = 0.15,
    max_opacity: float = 1.0,
    mode: str = "dark"
) -> str:
    """
    Generates an optimized dot-matrix SVG string from an input image path.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    with Image.open(image_path) as orig_img:
        has_alpha = orig_img.mode in ("RGBA", "LA") or (orig_img.mode == "P" and "transparency" in orig_img.info)
        if has_alpha:
            orig_rgba = orig_img.convert("RGBA")
            r, g, b, a = orig_rgba.split()
            rgb_img = Image.merge("RGB", (r, g, b))
        else:
            orig_rgba = None
            rgb_img = orig_img.convert("RGB")

        orig_w, orig_h = rgb_img.size

        aspect_ratio = orig_h / orig_w
        rows = max(1, round(cols * aspect_ratio))

        processed_img = enhance_image(rgb_img, equalize=equalize, detail=detail)
        resized_img = processed_img.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = resized_img.load()

        if orig_rgba is not None:
            resized_alpha = a.resize((cols, rows), Image.Resampling.LANCZOS)
            alpha_pixels = resized_alpha.load()
        else:
            alpha_pixels = None

    cell_size = 10.0
    svg_width = cols * cell_size
    svg_height = rows * cell_size

    center_x = svg_width / 2.0
    center_y = svg_height / 2.0
    max_dist = math.hypot(center_x, center_y)

    svg_lines = []
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt_num(svg_width)} {fmt_num(svg_height)}" width="100%" height="100%">'
    )

    if reveal:
        svg_lines.append("  <style>")
        svg_lines.append("    @keyframes dotReveal {")
        svg_lines.append("      0% { opacity: 0; transform: scale(0); }")
        svg_lines.append("      70% { opacity: 0.8; transform: scale(1.15); }")
        svg_lines.append("      100% { opacity: 1; transform: scale(1); }")
        svg_lines.append("    }")
        svg_lines.append("    .dot-node {")
        svg_lines.append("      transform-box: fill-box;")
        svg_lines.append("      transform-origin: center;")
        svg_lines.append("      animation: dotReveal var(--duration, 1s) ease-out forwards;")
        svg_lines.append("    }")
        svg_lines.append("  </style>")

    # For monochrome mode, set default fill on group to avoid repeating attribute
    group_fill_attr = "" if use_color else f' fill="{accent}"'
    svg_lines.append(f'  <g class="dot-matrix-group"{group_fill_attr}>')

    for r_idx in range(rows):
        row_delay = (r_idx / max(1, rows - 1)) * (reveal_time - reveal_fade)
        for c_idx in range(cols):
            if alpha_pixels is not None and alpha_pixels[c_idx, r_idx] < 64:
                continue

            r, g, b = pixels[c_idx, r_idx]
            lum = calculate_luminance(r, g, b)

            # In light mode, if invert is auto/true, invert luminance so dark features (hair, eyes, beard)
            # are rendered as dense purple dots against the light background.
            effective_invert = invert or (mode == "light" and not use_color)
            if effective_invert:
                lum = 1.0 - lum

            x_pos = (c_idx + 0.5) * cell_size
            y_pos = (r_idx + 0.5) * cell_size

            if circle_mask:
                dist = math.hypot(x_pos - center_x, y_pos - center_y)
                norm_dist = dist / max_dist
                if norm_dist > 0.85:
                    fade = max(0.0, (1.0 - norm_dist) / 0.15)
                    lum *= fade

            # Skip tiny background noise dots
            if lum < 0.04:
                continue

            # Non-linear power curve for crisp facial features
            gamma_lum = math.pow(lum, 1.15)
            radius = cell_size * (min_radius_ratio + (max_radius_ratio - min_radius_ratio) * gamma_lum)
            opacity = min_opacity + (max_opacity - min_opacity) * math.pow(lum, 0.75)

            fill_attr = f' fill="rgb({r},{g},{b})"' if use_color else ""

            if mode == "light" and not use_color:
                # Slightly enhance opacity for light mode on white background
                opacity = min(1.0, opacity * 1.1)

            anim_attr = ""
            if reveal:
                anim_attr = f' class="dot-node" style="animation-delay: {fmt_num(row_delay)}s;"'

            opacity_str = f' opacity="{fmt_num(opacity)}"' if abs(opacity - 1.0) > 0.02 else ""

            svg_lines.append(
                f'    <circle cx="{fmt_num(x_pos)}" cy="{fmt_num(y_pos)}" r="{fmt_num(radius)}"{fill_attr}{opacity_str}{anim_attr}/>'
            )

    svg_lines.append("  </g>")
    svg_lines.append("</svg>")

    return "\n".join(svg_lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert photographic images into futuristic dot-matrix SVG visuals."
    )
    parser.add_argument("input", type=str, help="Path to input source image")
    parser.add_argument("-o", "--output", type=str, required=True, help="Path to output SVG file or base path")
    parser.add_argument("--cols", type=int, default=88, help="Number of dot columns (default: 88)")
    parser.add_argument("--equalize", action="store_true", help="Enable histogram tonal equalization")
    parser.add_argument("--detail", type=float, default=0.5, help="Local detail enhancement factor (default: 0.5)")
    parser.add_argument("--color", action="store_true", help="Use source image RGB colors instead of monochrome accent")
    parser.add_argument("--accent", type=str, default="#A855F7", help="Monochrome accent hex color (default: #A855F7)")
    parser.add_argument("--circle", action="store_true", help="Apply circular subject fade mask")
    parser.add_argument("--invert", action="store_true", help="Invert luminance mapping")
    parser.add_argument("--reveal", action="store_true", help="Add load/reveal CSS animation")
    parser.add_argument("--reveal-time", type=float, default=1.5, help="Reveal animation duration in seconds")
    parser.add_argument("--reveal-fade", type=float, default=0.4, help="Individual row fade duration in seconds")
    parser.add_argument("--mode", type=str, choices=["dark", "light"], default="dark", help="Target theme mode (dark or light)")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_arg = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    output_arg.parent.mkdir(parents=True, exist_ok=True)

    targets = []
    if output_arg.suffix.lower() == ".svg":
        targets.append((output_arg, args.mode))
    else:
        # Produce both -dark.svg and -light.svg when base name given
        dark_file = output_arg.with_name(f"{output_arg.name}-dark.svg")
        light_file = output_arg.with_name(f"{output_arg.name}-light.svg")
        targets.append((dark_file, "dark"))
        targets.append((light_file, "light"))

    for out_path, mode in targets:
        try:
            svg_content = generate_dot_matrix_svg(
                image_path=input_path,
                cols=args.cols,
                equalize=args.equalize,
                detail=args.detail,
                use_color=args.color,
                accent=args.accent,
                circle_mask=args.circle,
                invert=args.invert,
                reveal=args.reveal,
                reveal_time=args.reveal_time,
                reveal_fade=args.reveal_fade,
                mode=mode
            )

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(svg_content)

            file_size_kb = out_path.stat().st_size / 1024.0
            print(f"Successfully generated dot-matrix SVG ({mode}): {out_path} ({file_size_kb:.1f} KB, cols={args.cols})")

        except Exception as e:
            print(f"Error generating dot-matrix SVG for {out_path}: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
