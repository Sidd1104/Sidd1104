"""
radar.py

CLI tool to generate futuristic, theme-aware SVG radar charts for:
1. Self-rated skills configuration (`assets/skills.json`).
2. GitHub language reality statistics derived directly from GitHub REST API.

Usage:
    python scripts/radar.py --data assets/skills.json -o assets/radar
    python scripts/radar.py --github Sidd1104 -o assets/radar-langs --limit 7 --values --curve 0.4 --exclude "shell,makefile,dockerfile,batchfile,procfile"
"""

import argparse
import json
import math
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Tuple


def fmt_num(val: float) -> str:
    """Formats floating point numbers cleanly for compact SVG strings."""
    res = f"{val:.1f}"
    if res.endswith(".0"):
        return res[:-2]
    return res


def bytes_to_human(n_bytes: int) -> str:
    """Converts raw byte count into human-readable string (B, KB, MB)."""
    if n_bytes >= 1_048_576:
        return f"{n_bytes / 1_048_576:.2f} MB"
    if n_bytes >= 1024:
        return f"{n_bytes / 1024:.1f} KB"
    return f"{n_bytes} B"


def fetch_github_language_data(
    username: str,
    limit: int = 7,
    curve: float = 0.4,
    exclude: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Queries public GitHub repositories for `username`, aggregates language byte counts,
    applies category exclusions, applies curve transformation for geometric radar scaling,
    and returns sorted axis definitions.
    """
    if exclude is None:
        exclude = ["shell", "makefile", "dockerfile", "batchfile", "procfile"]
    exclude_set = {e.strip().lower() for e in exclude if e.strip()}

    headers = {"User-Agent": "Mozilla/5.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repos_url = f"https://api.github.com/users/{urllib.parse.quote(username)}/repos?per_page=100&type=owner"
    req = urllib.request.Request(repos_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            repos_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching repositories for '{username}' from GitHub API: {e}", file=sys.stderr)
        return []

    lang_totals: Dict[str, int] = {}

    for repo in repos_data:
        if repo.get("fork", False):
            continue
        lang_url = repo.get("languages_url")
        if not lang_url:
            continue

        try:
            l_req = urllib.request.Request(lang_url, headers=headers)
            with urllib.request.urlopen(l_req, timeout=10) as l_resp:
                langs = json.loads(l_resp.read().decode("utf-8"))
                for lang_name, byte_count in langs.items():
                    if lang_name.lower() in exclude_set:
                        continue
                    lang_totals[lang_name] = lang_totals.get(lang_name, 0) + byte_count
        except Exception:
            continue

    if not lang_totals:
        print(f"Warning: No language statistics retrieved for GitHub user '{username}'.", file=sys.stderr)
        return []

    # Sort descending by byte count
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    total_bytes = sum(b for _, b in sorted_langs)
    max_bytes = max(b for _, b in sorted_langs) if sorted_langs else 1

    axes = []
    for lang_name, byte_count in sorted_langs:
        # Curve transformation: normalized_fraction ^ curve
        # Curve = 0.4 compresses large magnitude differences so smaller languages remain visible on radar geometry
        fraction = byte_count / max_bytes
        transformed_val = math.pow(fraction, curve) * 100.0
        pct = (byte_count / total_bytes * 100.0) if total_bytes > 0 else 0.0

        axes.append({
            "label": lang_name,
            "value": round(transformed_val, 1),
            "display_val": f"{bytes_to_human(byte_count)} ({pct:.1f}%)",
            "raw_bytes": byte_count
        })

    return axes


def render_radar_svg(
    axes: List[Dict[str, Any]],
    title: str = "Skill Radar",
    theme: str = "dark",
    accent: str = "#A855F7",
    show_values: bool = True
) -> str:
    """
    Renders an SVG string representing an n-sided radar chart with grid rings,
    polygon overlay, labels, and numeric indicators.
    """
    n_axes = len(axes)
    if n_axes < 3:
        raise ValueError("Radar chart requires at least 3 axes to form a valid polygon.")

    width = 540
    height = 460
    center_x = width / 2.0
    center_y = height / 2.0 + 10
    radius = 135.0

    # Theme colors
    if theme == "dark":
        text_color = "#e6edf3"
        subtext_color = accent
        grid_stroke = "#30363d"
        grid_opacity = "0.6"
        polygon_fill = accent
        polygon_fill_opacity = "0.28"
        polygon_stroke = accent
        ring_label_color = "#8b949e"
    else:
        text_color = "#1f2328"
        subtext_color = "#7e22ce"
        grid_stroke = "#d0d7de"
        grid_opacity = "0.8"
        polygon_fill = accent
        polygon_fill_opacity = "0.22"
        polygon_stroke = accent
        ring_label_color = "#6e7681"

    angles = [-math.pi / 2.0 + (2.0 * math.pi * i / n_axes) for i in range(n_axes)]

    svg_lines = []
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">'
    )

    # Styling block
    svg_lines.append("  <style>")
    svg_lines.append(f"    .radar-title {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 700; fill: {text_color}; text-anchor: middle; letter-spacing: 1px; }}")
    svg_lines.append(f"    .radar-label {{ font-family: 'JetBrains Mono', monospace, sans-serif; font-size: 12px; font-weight: 600; fill: {text_color}; }}")
    svg_lines.append(f"    .radar-value {{ font-family: 'JetBrains Mono', monospace, sans-serif; font-size: 11px; font-weight: 500; fill: {subtext_color}; }}")
    svg_lines.append(f"    .grid-label {{ font-family: monospace; font-size: 9px; fill: {ring_label_color}; text-anchor: middle; }}")
    svg_lines.append("  </style>")

    svg_lines.append(f'  <g class="radar-container">')

    # Title
    svg_lines.append(f'    <text x="{fmt_num(center_x)}" y="32" class="radar-title">{title.upper()}</text>')

    # Concentric Grid Rings (20%, 40%, 60%, 80%, 100%)
    rings = [0.2, 0.4, 0.6, 0.8, 1.0]
    for r_ratio in rings:
        r_dist = radius * r_ratio
        ring_points = []
        for a in angles:
            rx = center_x + r_dist * math.cos(a)
            ry = center_y + r_dist * math.sin(a)
            ring_points.append(f"{fmt_num(rx)},{fmt_num(ry)}")
        pts_str = " ".join(ring_points)
        svg_lines.append(
            f'    <polygon points="{pts_str}" fill="none" stroke="{grid_stroke}" stroke-opacity="{grid_opacity}" stroke-width="1" />'
        )
        # Ring value scale marker
        val_marker = int(r_ratio * 100)
        svg_lines.append(
            f'    <text x="{fmt_num(center_x)}" y="{fmt_num(center_y - r_dist - 3)}" class="grid-label">{val_marker}</text>'
        )

    # Spoke lines
    for a in angles:
        sx = center_x + radius * math.cos(a)
        sy = center_y + radius * math.sin(a)
        svg_lines.append(
            f'    <line x1="{fmt_num(center_x)}" y1="{fmt_num(center_y)}" x2="{fmt_num(sx)}" y2="{fmt_num(sy)}" stroke="{grid_stroke}" stroke-opacity="{grid_opacity}" stroke-width="1" />'
        )

    # Radar Data Polygon
    poly_points = []
    node_coords = []

    for i, item in enumerate(axes):
        val = max(0.0, min(100.0, float(item["value"])))
        r_dist = radius * (val / 100.0)
        a = angles[i]
        px = center_x + r_dist * math.cos(a)
        py = center_y + r_dist * math.sin(a)
        poly_points.append(f"{fmt_num(px)},{fmt_num(py)}")
        node_coords.append((px, py))

    pts_str = " ".join(poly_points)
    svg_lines.append(
        f'    <polygon points="{pts_str}" fill="{polygon_fill}" fill-opacity="{polygon_fill_opacity}" stroke="{polygon_stroke}" stroke-width="2.5" stroke-linejoin="round" />'
    )

    # Data Nodes
    for nx, ny in node_coords:
        svg_lines.append(
            f'    <circle cx="{fmt_num(nx)}" cy="{fmt_num(ny)}" r="4.5" fill="{accent}" />'
        )
        svg_lines.append(
            f'    <circle cx="{fmt_num(nx)}" cy="{fmt_num(ny)}" r="2" fill="#ffffff" />'
        )

    # Axis Labels
    label_margin = 24.0
    for i, item in enumerate(axes):
        a = angles[i]
        lx = center_x + (radius + label_margin) * math.cos(a)
        ly = center_y + (radius + label_margin) * math.sin(a)

        cos_a = math.cos(a)
        if cos_a > 0.15:
            anchor = "start"
        elif cos_a < -0.15:
            anchor = "end"
        else:
            anchor = "middle"

        label_text = item["label"]
        disp_val = item.get("display_val") or str(item["value"])

        if show_values:
            svg_lines.append(f'    <text x="{fmt_num(lx)}" y="{fmt_num(ly - 4)}" text-anchor="{anchor}" class="radar-label">{label_text}</text>')
            svg_lines.append(f'    <text x="{fmt_num(lx)}" y="{fmt_num(ly + 11)}" text-anchor="{anchor}" class="radar-value">{disp_val}</text>')
        else:
            svg_lines.append(f'    <text x="{fmt_num(lx)}" y="{fmt_num(ly + 4)}" text-anchor="{anchor}" class="radar-label">{label_text}</text>')

    svg_lines.append("  </g>")
    svg_lines.append("</svg>")

    return "\n".join(svg_lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate futuristic SVG radar charts for skills and GitHub language data."
    )
    parser.add_argument("--data", type=str, help="Path to input skills JSON file (e.g. assets/skills.json)")
    parser.add_argument("--github", type=str, help="GitHub username to query language data for (e.g. Sidd1104)")
    parser.add_argument("-o", "--output", type=str, required=True, help="Base path for output SVG files (e.g. assets/radar)")
    parser.add_argument("--limit", type=int, default=7, help="Maximum number of radar axes (default: 7)")
    parser.add_argument("--values", action="store_true", help="Display numeric values/percentages alongside labels")
    parser.add_argument("--curve", type=float, default=0.4, help="Curve exponent for non-linear radar scaling (default: 0.4)")
    parser.add_argument("--exclude", type=str, default="shell,makefile,dockerfile,batchfile,procfile", help="Comma-separated category exclusions")
    parser.add_argument("--accent", type=str, default="#A855F7", help="Monochrome accent hex color (default: #A855F7)")

    args = parser.parse_args()

    out_base = Path(args.output)
    out_dir = out_base.parent
    base_name = out_base.name
    out_dir.mkdir(parents=True, exist_ok=True)

    out_dark_path = out_dir / f"{base_name}-dark.svg"
    out_light_path = out_dir / f"{base_name}-light.svg"

    axes_data = []
    chart_title = "Skill Radar"

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"Error: Data file '{data_path}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        chart_title = raw_data.get("title", "Skill Radar")
        axes_data = raw_data.get("axes", [])[:args.limit]

    elif args.github:
        chart_title = "GitHub Language Reality"
        exclude_list = [e.strip() for e in args.exclude.split(",") if e.strip()]
        axes_data = fetch_github_language_data(
            username=args.github,
            limit=args.limit,
            curve=args.curve,
            exclude=exclude_list
        )

    else:
        print("Error: Specify either --data or --github.", file=sys.stderr)
        sys.exit(1)

    if not axes_data:
        print(f"Error: No radar data available for rendering.", file=sys.stderr)
        sys.exit(1)

    try:
        # Render Dark Mode SVG
        dark_svg = render_radar_svg(
            axes=axes_data,
            title=chart_title,
            theme="dark",
            accent=args.accent,
            show_values=args.values or bool(args.data)
        )
        with open(out_dark_path, "w", encoding="utf-8") as f:
            f.write(dark_svg)

        # Render Light Mode SVG
        light_svg = render_radar_svg(
            axes=axes_data,
            title=chart_title,
            theme="light",
            accent=args.accent,
            show_values=args.values or bool(args.data)
        )
        with open(out_light_path, "w", encoding="utf-8") as f:
            f.write(light_svg)

        size_dark = out_dark_path.stat().st_size / 1024.0
        size_light = out_light_path.stat().st_size / 1024.0

        print(f"Successfully generated radar SVGs:")
        print(f"  - {out_dark_path} ({size_dark:.1f} KB)")
        print(f"  - {out_light_path} ({size_light:.1f} KB)")

    except Exception as e:
        print(f"Error generating radar SVGs: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
