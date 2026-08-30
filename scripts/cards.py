"""
cards.py

Fetches GitHub statistics (REST & GraphQL APIs) and generates custom futuristic
dark and light SVG stat cards matching the profile's visual design.

Usage:
    python scripts/cards.py [--username USERNAME] [-o OUTPUT_BASE]
"""

import argparse
import datetime
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


def fetch_rest_stats(username: str, token: Optional[str] = None) -> Dict[str, int]:
    """Fetches user public repo count, followers, and total stars across repos via REST API."""
    headers = {"User-Agent": "GitHub-Stat-Card-Generator"}
    if token:
        headers["Authorization"] = f"token {token}"

    user_url = f"https://api.github.com/users/{username}"
    req = urllib.request.Request(user_url, headers=headers)

    public_repos = 0
    followers = 0
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            public_repos = data.get("public_repos", 0)
            followers = data.get("followers", 0)
    except Exception as e:
        print(f"Warning: Failed to fetch REST user data for {username}: {e}", file=sys.stderr)

    total_stars = 0
    repos_url = f"https://api.github.com/users/{username}/repos?per_page=100&type=owner"
    req_repos = urllib.request.Request(repos_url, headers=headers)
    try:
        with urllib.request.urlopen(req_repos) as resp:
            repos_data = json.loads(resp.read().decode())
            if isinstance(repos_data, list):
                total_stars = sum(repo.get("stargazers_count", 0) for repo in repos_data)
    except Exception as e:
        print(f"Warning: Failed to fetch REST repos data for {username}: {e}", file=sys.stderr)

    return {
        "public_repos": public_repos,
        "followers": followers,
        "total_stars": total_stars,
    }


def fetch_graphql_stats(username: str, token: Optional[str] = None) -> Optional[Dict[str, int]]:
    """
    Fetches contribution count for the past year and calculates streaks using GraphQL API.
    Returns dict with total_contributions, current_streak, longest_streak or None if failed/no token.
    """
    if not token:
        print("Warning: GraphQL API fetch skipped: No token provided.", file=sys.stderr)
        return None

    query = """
    query($username: String!) {
      user(login: $username) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "GitHub-Stat-Card-Generator",
    }
    payload = json.dumps({"query": query, "variables": {"username": username}}).encode("utf-8")
    req = urllib.request.Request("https://api.github.com/graphql", data=payload, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode())
            if "errors" in res_data:
                err_msg = json.dumps(res_data["errors"])
                print(f"Warning: GraphQL API fetch failed: {err_msg}", file=sys.stderr)
                return None

            cal = (
                res_data.get("data", {})
                .get("user", {})
                .get("contributionsCollection", {})
                .get("contributionCalendar", {})
            )
            total_contributions = cal.get("totalContributions", 0)

            days = []
            for week in cal.get("weeks", []):
                for day in week.get("contributionDays", []):
                    days.append(day)

            days_chrono = sorted(days, key=lambda x: x["date"])
            longest_streak = 0
            curr_streak = 0
            for d in days_chrono:
                if d["contributionCount"] > 0:
                    curr_streak += 1
                    longest_streak = max(longest_streak, curr_streak)
                else:
                    curr_streak = 0

            days_rev = sorted(days, key=lambda x: x["date"], reverse=True)
            current_streak = 0
            idx = 0
            if days_rev and days_rev[0]["contributionCount"] == 0:
                idx = 1

            for i in range(idx, len(days_rev)):
                if days_rev[i]["contributionCount"] > 0:
                    current_streak += 1
                else:
                    break

            return {
                "total_contributions": total_contributions,
                "current_streak": current_streak,
                "longest_streak": longest_streak,
            }
    except Exception as e:
        print(f"Warning: GraphQL API fetch failed: {e}", file=sys.stderr)
        return None


def format_number(val: int) -> str:
    """Formats integers with thousands separators."""
    return f"{val:,}"


def render_stat_card_svg(
    metrics: List[Tuple[str, str, str]],
    mode: str = "dark",
    accent: str = "#A855F7"
) -> str:
    """
    Renders custom futuristic stat cards matching the profile theme.
    """
    is_dark = mode == "dark"
    bg_color = "#0d1117" if is_dark else "#ffffff"
    border_color = "#30363d" if is_dark else "#e1e4e8"
    card_bg = "#161b22" if is_dark else "#f6f8fa"
    text_color = "#f0f6fc" if is_dark else "#1f2328"
    label_color = "#8b949e" if is_dark else "#57606a"

    num_tiles = len(metrics)
    width = 800
    height = 140
    padding = 14
    gap = 10

    available_width = width - (padding * 2) - ((num_tiles - 1) * gap)
    tile_width = available_width / num_tiles

    val_font_size = 22 if num_tiles >= 6 else 26
    lbl_font_size = 9 if num_tiles >= 6 else 10

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">'
    )
    svg.append("  <style>")
    svg.append("    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600;700;800&amp;display=swap');")
    svg.append("    .stat-card { font-family: 'JetBrains Mono', monospace, -apple-system, sans-serif; }")
    svg.append(f"    .tile-bg {{ fill: {card_bg}; stroke: {border_color}; stroke-width: 1px; rx: 8px; ry: 8px; transition: all 0.3s ease; }}")
    svg.append(f"    .stat-val {{ font-size: {val_font_size}px; font-weight: 800; fill: {text_color}; }}")
    svg.append(f"    .stat-lbl {{ font-size: {lbl_font_size}px; font-weight: 600; fill: {label_color}; letter-spacing: 0.5px; }}")
    svg.append(f"    .stat-icon {{ fill: {accent}; }}")
    svg.append("  </style>")

    svg.append(f'  <rect width="{width}" height="{height}" fill="{bg_color}" rx="12" ry="12" stroke="{border_color}" stroke-width="1.5"/>')

    for i, (label, value, icon_svg) in enumerate(metrics):
        x = padding + i * (tile_width + gap)
        y = padding
        t_h = height - (padding * 2)

        svg.append(f'  <g class="stat-card" transform="translate({x:.1f}, {y})">')
        svg.append(f'    <rect width="{tile_width:.1f}" height="{t_h}" class="tile-bg"/>')
        # Top accent pill line
        svg.append(f'    <rect x="12" y="14" width="24" height="3" rx="1.5" fill="{accent}"/>')

        if icon_svg:
            svg.append(f'    <g transform="translate({tile_width - 28:.1f}, 12)">{icon_svg}</g>')

        svg.append(f'    <text x="12" y="58" class="stat-val">{value}</text>')
        svg.append(f'    <text x="12" y="86" class="stat-lbl">{label.upper()}</text>')
        svg.append("  </g>")

    svg.append("</svg>")
    return "\n".join(svg)


def get_icons() -> Dict[str, str]:
    """SVG icon paths for tiles."""
    return {
        "contributions": '<path class="stat-icon" d="M8 0a8 8 0 100 16A8 8 0 008 0zm0 3a5 5 0 110 10A5 5 0 018 3zm1 2.5H7v4.25l3.5 2.1.75-1.23-2.75-1.62V5.5z"/>',
        "streak": '<path class="stat-icon" d="M8 0c-.3 0-.6.1-.8.4L2.3 6.9c-.4.5-.4 1.2 0 1.7l4.9 6.5c.2.3.5.4.8.4s.6-.1.8-.4l4.9-6.5c.4-.5.4-1.2 0-1.7L8.8.4C8.6.1 8.3 0 8 0zm0 2.5l4.1 5.5L8 13.5 3.9 8 8 2.5z"/>',
        "repos": '<path class="stat-icon" d="M2 2.5A2.5 2.5 0 014.5 0h7A2.5 2.5 0 0114 2.5v11a2.5 2.5 0 01-2.5 2.5h-7A2.5 2.5 0 012 13.5v-11zM4.5 1.5a1 1 0 00-1 1v11a1 1 0 001 1h7a1 1 0 001-1v-11a1 1 0 00-1-1h-7z"/>',
        "stars": '<path class="stat-icon" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"/>',
        "followers": '<path class="stat-icon" d="M5.5 0a3.5 3.5 0 100 7 3.5 3.5 0 000-7zM7 9a6 6 0 00-6 6 .75.75 0 001.5 0 4.5 4.5 0 019 0 .75.75 0 001.5 0 6 6 0 00-6-6z"/>',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate GitHub Stat Cards in custom futuristic SVG format.")
    parser.add_argument("--username", type=str, default="Sidd1104", help="GitHub username (default: Sidd1104)")
    parser.add_argument("-o", "--output", type=str, default="assets/stats", help="Output SVG base path or file")
    parser.add_argument("--accent", type=str, default="#A855F7", help="Accent color hex (default: #A855F7)")

    args = parser.parse_args()

    token = os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("TOKEN")

    print(f"Fetching GitHub stats for user: {args.username} (Token provided: {bool(token)})")

    rest_stats = fetch_rest_stats(args.username, token=token)
    gql_stats = fetch_graphql_stats(args.username, token=token)

    icons = get_icons()

    metrics = []
    if gql_stats is not None:
        metrics.append(("Total Contributions", format_number(gql_stats["total_contributions"]), icons["contributions"]))
        metrics.append(("Current Streak", f"{gql_stats['current_streak']} Days", icons["streak"]))
        metrics.append(("Longest Streak", f"{gql_stats['longest_streak']} Days", icons["streak"]))

    metrics.append(("Repositories", format_number(rest_stats["public_repos"]), icons["repos"]))
    metrics.append(("Total Stars", format_number(rest_stats["total_stars"]), icons["stars"]))
    metrics.append(("Followers", format_number(rest_stats["followers"]), icons["followers"]))

    out_base = Path(args.output)
    out_base.parent.mkdir(parents=True, exist_ok=True)

    if out_base.suffix.lower() == ".svg":
        targets = [(out_base, "dark")]
    else:
        dark_path = out_base.with_name(f"{out_base.name}-dark.svg")
        light_path = out_base.with_name(f"{out_base.name}-light.svg")
        targets = [(dark_path, "dark"), (light_path, "light")]

    for out_path, mode in targets:
        svg_content = render_stat_card_svg(metrics, mode=mode, accent=args.accent)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        file_size_kb = out_path.stat().st_size / 1024.0
        print(f"Successfully generated stat card ({mode}): {out_path} ({file_size_kb:.1f} KB, tiles={len(metrics)})")


if __name__ == "__main__":
    main()
