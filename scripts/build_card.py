"""Render the code-editor profile card: assets/dark_mode.svg and assets/light_mode.svg.

The GitHub Action runs this every day, so the uptime, the stats and the sync date stay
current. It only needs the standard library and a token that can read public data (the
Action's GITHUB_TOKEN is enough):

    GITHUB_TOKEN=... python scripts/build_card.py

To preview without a token, pass the numbers yourself:

    python scripts/build_card.py --stats stats.json

where stats.json holds created_at, repos, stars, followers, following,
contributions_year and contributions_all.

The card is an editor window in Catppuccin (Mocha for dark, Latte for light) with
about.ts open. The code in it lives in code_lines() below. When the page loads the code
types itself in behind the cursor, which then keeps blinking on the last line. Without
SMIL every element simply rests at its final state.
"""

import argparse
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOGIN = "Dthariq347"
WIB = dt.timezone(dt.timedelta(hours=7))

# Code: 15px monospace (9px per character), 20px per line, COLS characters wide.
FONT, LINE, CH, COLS = 15, 20, 9.0, 60
UI = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"

MARGIN = 20  # transparent room around the window for the glow
TITLE, TABS, CRUMB, STATUS = 36, 35, 24, 24  # heights of the bars, top to bottom
ACTIVITY, SIDEBAR, GUTTER, MINIMAP = 48, 176, 56, 56  # widths of the columns, left to right

# Catppuccin flavours: https://catppuccin.com/palette
FLAVOURS = {
    "dark": {  # Mocha
        "base": "#1e1e2e", "mantle": "#181825", "crust": "#11111b",
        "surface0": "#313244", "surface1": "#45475a", "surface2": "#585b70",
        "overlay0": "#6c7086", "overlay1": "#7f849c", "overlay2": "#9399b2",
        "subtext0": "#a6adc8", "text": "#cdd6f4", "lavender": "#b4befe",
        "mauve": "#cba6f7", "blue": "#89b4fa", "sky": "#89dceb", "green": "#a6e3a1",
        "peach": "#fab387", "yellow": "#f9e2af", "pink": "#f5c2e7", "rosewater": "#f5e0dc",
        "pill": "#313244", "halo": "#cba6f7", "halo_opacity": 0.22, "halo_dy": 0, "border_opacity": 0.75,
    },
    "light": {  # Latte
        "base": "#eff1f5", "mantle": "#e6e9ef", "crust": "#dce0e8",
        "surface0": "#ccd0da", "surface1": "#bcc0cc", "surface2": "#acb0be",
        "overlay0": "#9ca0b0", "overlay1": "#8c8fa1", "overlay2": "#7c7f93",
        "subtext0": "#6c6f85", "text": "#4c4f69", "lavender": "#7287fd",
        "mauve": "#8839ef", "blue": "#1e66f5", "sky": "#04a5e5", "green": "#40a02b",
        "peach": "#fe640b", "yellow": "#df8e1d", "pink": "#ea76cb", "rosewater": "#dc8a78",
        "pill": "#eff1f5", "halo": "#4c4f69", "halo_opacity": 0.16, "halo_dy": 6, "border_opacity": 0.55,
    },
}

# Syntax roles -> flavour colours. b0..b2 colour brackets by nesting depth.
SYNTAX = {
    "kw": "mauve", "str": "green", "num": "peach", "prop": "blue", "type": "yellow",
    "var": "text", "punct": "overlay2", "op": "sky", "comment": "overlay1",
    "b0": "yellow", "b1": "mauve", "b2": "sky",
}


def code_lines(s):
    synced = dt.datetime.now(WIB).date().isoformat()
    return [
        'import type { Developer } from "./types";',
        "",
        "export const dzaky: Developer = {",
        '  role: "Full-Stack Developer",',
        '  host: "Markaz Digital Payment",',
        f'  uptime: "{uptime(s["created_at"])}",',
        '  os: ["Windows 11", "Linux (Docker)"],',
        '  ide: ["VS Code", "Claude Code"],',
        "",
        "  languages: {",
        '    programming: ["Go", "PHP", "JavaScript", "TypeScript"],',
        '    computer: ["HTML", "CSS", "SQL", "YAML"],',
        '    spoken: ["Indonesian", "English"],',
        "  },",
        "  stack: {",
        '    backend: ["Go", "Laravel", "PostgreSQL"],',
        '    frontend: ["React", "Vue", "Tailwind CSS"],',
        '    tools: ["Docker", "Git", "GitHub Actions", "Figma"],',
        "  },",
        "",
        "  github: {",
        f"    repos: {s['repos']}, stars: {s['stars']}, followers: {s['followers']}, following: {s['following']},",
        f"    contributions: {{ pastYear: {s['contributions_year']:_}, allTime: {s['contributions_all']:_} }},",
        "  },",
        "};",
        "",
        f"// synced daily by GitHub Actions · {synced}",
    ]


TOKEN = re.compile(
    r'(?P<comment>//.*)|(?P<str>"[^"]*")|(?P<num>\d[\d_]*)|(?P<word>[A-Za-z_$][\w$]*)'
    r"|(?P<space>\s+)|(?P<op>=)|(?P<bracket>[{}\[\]()])|(?P<punct>.)"
)
KEYWORDS = {"import", "type", "from", "export", "const"}


def highlight(line, depth):
    """Split one line into (role, text) tokens. depth carries bracket nesting across lines."""
    tokens, prev_word = [], None
    for m in TOKEN.finditer(line):
        role, text = m.lastgroup, m.group()
        if role == "word":
            if text in KEYWORDS:
                role = "kw"
            elif prev_word == "const":
                role = "var"
            elif line[m.end():].lstrip().startswith(":"):
                role = "prop"
            else:
                role = "type" if text[0].isupper() else "var"
            prev_word = text
        elif role == "bracket":
            if text in "}])":
                depth -= 1
            role = f"b{depth % 3}"
            if text in "{[(":
                depth += 1
        tokens.append((role, text))
    return tokens, depth


def uptime(created_at):
    since = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(WIB).date()
    today = dt.datetime.now(WIB).date()
    years, months, days = today.year - since.year, today.month - since.month, today.day - since.day
    if days < 0:
        months -= 1
        days += (today.replace(day=1) - dt.timedelta(days=1)).day
    if months < 0:
        years -= 1
        months += 12
    plural = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")
    return ", ".join([plural(years, "year"), plural(months, "month"), plural(days, "day")])


USER_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    following { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection { contributionCalendar { totalContributions } }
  }
}
"""


def graphql(token, query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": LOGIN + "-profile-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch_stats(token):
    user = graphql(token, USER_QUERY, {"login": LOGIN})["user"]
    # A contributionsCollection spans at most one year, so ask for each year since joining.
    first_year = int(user["createdAt"][:4])
    years = range(first_year, dt.datetime.now(WIB).year + 1)
    fields = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z")'
        " { contributionCalendar { totalContributions } }"
        for y in years
    )
    per_year = graphql(token, f"query($login: String!) {{ user(login: $login) {{ {fields} }} }}", {"login": LOGIN})["user"]
    return {
        "created_at": user["createdAt"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in user["repositories"]["nodes"]),
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "contributions_year": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "contributions_all": sum(c["contributionCalendar"]["totalContributions"] for c in per_year.values()),
    }


def tspans(tokens):
    """Coloured tspans for one line. No whitespace between them: white-space: pre would draw it."""
    return "".join(
        f"<tspan>{escape(text)}</tspan>" if role == "space" else f'<tspan class="{role}">{escape(text)}</tspan>'
        for role, text in tokens
    )


def hold(until):
    """Keep an element hidden until `until` seconds, then let it rest at its own (visible) state."""
    return f'<set attributeName="opacity" to="0" dur="{until:.3f}s"/>'


def keyed(attr, values, times, total, discrete=False):
    key_times = ";".join(f"{t / total:.5f}" for t in times)
    mode = ' calcMode="discrete"' if discrete else ""
    return (f'<animate attributeName="{attr}" values="{";".join(f"{v:.1f}" for v in values)}"'
            f' keyTimes="{key_times}" dur="{total:.3f}s"{mode} fill="freeze"/>')


# Activity bar icons, 24px boxes centred on (x, y); stroked, not filled.
ICONS = {
    "files": "M{l} {t}h9l5 5v15h-14z M{m2} {t}v5h5",
    "search": "M{x} {y}m-8 -2a6 6 0 1 0 12 0a6 6 0 1 0 -12 0 M{x} {y}m2.3 2.3l5.7 5.7",
    "git": "M{x} {y}m-5 -5.5v11 M{x} {y}m6 -3c0 5 -11 3 -11 8.5"
           " M{x} {y}m-7.5 -8a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0 -5 0"
           " M{x} {y}m-7.5 8a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0 -5 0"
           " M{x} {y}m3.5 -5.5a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0 -5 0",
    "run": "M{x} {y}m-5 -8l12 8l-12 8z",
    "extensions": "M{x} {y}m-8 -1h7v7h-7z M{x} {y}m-1 -1h7v7h-7z M{x} {y}m-8 -8h7v7h-7z M{x} {y}m2 -10l5 0l0 5l-5 0z",
    "account": "M{x} {y}m-3.5 -4a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0 M{x} {y}m-7 9c0 -5 3 -6.5 7 -6.5s7 1.5 7 6.5",
}


def icon(name, x, y, color, width=1.5):
    d = ICONS[name].format(x=x, y=y, l=x - 7, t=y - 10, m2=x + 2)
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"'
            ' stroke-linejoin="round" stroke-linecap="round"/>')


def file_badge(kind, x, y, c):
    """The little file-type mark in the explorer, tabs and breadcrumbs, left edge at x."""
    label, color, size = {"ts": ("TS", c["blue"], 8.5), "json": ("{}", c["yellow"], 10.5),
                          "md": ("M↓", c["sky"], 8.5)}[kind]
    return f'<text class="ui" x="{x}" y="{y - 0.5}" font-size="{size}" font-weight="700" fill="{color}">{escape(label)}</text>'


def chevron(x, y, open_, color):
    d = f"M{x - 4} {y - 2}l4 4l4 -4" if open_ else f"M{x - 2} {y - 4}l4 4l-4 4"
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>'


def render(theme, lines):
    c = FLAVOURS[theme]
    side_x = MARGIN + ACTIVITY
    ed_x = side_x + SIDEBAR
    code_x = ed_x + GUTTER
    mm_x = code_x + COLS * CH + 18
    win_w = round(mm_x + MINIMAP + 12 - MARGIN)
    win_r = MARGIN + win_w
    body_y = MARGIN + TITLE
    crumb_y = body_y + TABS
    code_top = crumb_y + CRUMB + 8
    top = lambda i: code_top + i * LINE  # top edge of code line i
    status_y = code_top + len(lines) * LINE + 12
    win_h = status_y + STATUS - MARGIN
    width, height = win_w + 2 * MARGIN, win_h + 2 * MARGIN

    for i, line in enumerate(lines):
        if len(line) > COLS:
            print(f"warning: line {i + 1} is {len(line)} characters, wider than {COLS}")

    # Typing timeline, in seconds: each line takes a beat plus a little per character.
    t, starts, ends = 0.6, [], []
    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        starts.append(t)
        t += 0.04 + 0.0035 * (len(line) - indent)
        ends.append(t)
        t += 0.02
    done = ends[-1]

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"'
        f' font-family="ConsolasFallback,Consolas,Menlo,monospace" font-size="{FONT}px">',
        "<title>Dzaky Abiyyu Thariq - profile card</title>",
        "<defs>",
        f'<clipPath id="win"><rect x="{MARGIN}" y="{MARGIN}" width="{win_w}" height="{win_h}" rx="12"/></clipPath>',
        f'<linearGradient id="border" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["mauve"]}"/>'
        f'<stop offset="0.5" stop-color="{c["blue"]}"/><stop offset="1" stop-color="{c["pink"]}"/></linearGradient>',
        f'<radialGradient id="glow" cx="1" cy="0" r="0.9"><stop offset="0" stop-color="{c["mauve"]}" stop-opacity="0.07"/>'
        f'<stop offset="1" stop-color="{c["mauve"]}" stop-opacity="0"/></radialGradient>',
        '<filter id="blur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="10"/></filter>',
    ]
    # Each code line is revealed by widening its clip rectangle from the indent to the end.
    for i, line in enumerate(lines):
        if not line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        w = (len(line) - indent) * CH + 4
        a = starts[i] / ends[i]
        out.append(
            f'<clipPath id="l{i}"><rect x="{code_x + indent * CH - 1:.1f}" y="{top(i)}" width="{w:.1f}" height="{LINE}">'
            f'<animate attributeName="width" values="0;0;{w:.1f}" keyTimes="0;{a:.4f};1" dur="{ends[i]:.3f}s"/></rect></clipPath>'
        )
    out += [
        "</defs>",
        "<style>",
        "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback';"
        " font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
        "text { white-space: pre; }",
        f".ui {{ font-family: {UI}; }}",
        *(f".{role} {{ fill: {c[name]}; }}" for role, name in SYNTAX.items()),
        ".comment { font-style: italic; }",
        "</style>",
        # Glow (dark) or soft shadow (light) behind the window.
        f'<rect x="{MARGIN + 8}" y="{MARGIN + 8 + c["halo_dy"]}" width="{win_w - 16}" height="{win_h - 16}" rx="14"'
        f' fill="{c["halo"]}" opacity="{c["halo_opacity"]}" filter="url(#blur)"/>',
        '<g clip-path="url(#win)">',
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{win_w}" height="{win_h}" fill="{c["base"]}"/>',
        f'<rect x="{ed_x}" y="{crumb_y}" width="{win_r - ed_x}" height="{status_y - crumb_y}" fill="url(#glow)"/>',
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{win_w}" height="{TITLE}" fill="{c["crust"]}"/>',
        f'<rect x="{MARGIN}" y="{body_y}" width="{ACTIVITY}" height="{status_y - body_y}" fill="{c["crust"]}"/>',
        f'<rect x="{side_x}" y="{body_y}" width="{SIDEBAR}" height="{status_y - body_y}" fill="{c["mantle"]}"/>',
        f'<rect x="{ed_x}" y="{body_y}" width="{win_r - ed_x}" height="{TABS}" fill="{c["crust"]}"/>',
        f'<rect x="{MARGIN}" y="{status_y}" width="{win_w}" height="{STATUS}" fill="{c["crust"]}"/>',
        f'<line x1="{ed_x - 0.5}" y1="{body_y}" x2="{ed_x - 0.5}" y2="{status_y}" stroke="{c["crust"]}"/>',
        "</g>",
    ]

    # Title bar: traffic lights, the command centre pill, layout toggles.
    mid_y = MARGIN + TITLE / 2
    out += [f'<circle cx="{MARGIN + 20 + i * 20}" cy="{mid_y}" r="6" fill="{color}"/>'
            for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840"))]
    pill_w, pill_x = 300, MARGIN + win_w / 2 - 150
    out += [
        f'<rect x="{pill_x}" y="{mid_y - 11}" width="{pill_w}" height="22" rx="6" fill="{c["pill"]}"'
        f' fill-opacity="0.7" stroke="{c["surface1"]}" stroke-opacity="0.6"/>',
        f'<path d="M{pill_x + pill_w / 2 - 52} {mid_y - 1}m-4.5 0a4.5 4.5 0 1 0 9 0a4.5 4.5 0 1 0 -9 0m7.7 3.2l3 3"'
        f' fill="none" stroke="{c["overlay1"]}" stroke-width="1.3" stroke-linecap="round"/>',
        f'<text class="ui" x="{pill_x + pill_w / 2 + 6}" y="{mid_y + 4}" text-anchor="middle" font-size="12" fill="{c["subtext0"]}">dzaky-thariq</text>',
    ]
    # Toggle sidebar, panel and secondary sidebar: an outlined box with the filled part inside.
    for j, (dx, dy, w, h) in enumerate(((0, 0, 4.5, 10), (0, 6, 14, 4), (9.5, 0, 4.5, 10))):
        x = win_r - 78 + j * 22
        out.append(f'<rect x="{x}" y="{mid_y - 5}" width="14" height="10" rx="1.5" fill="none" stroke="{c["overlay1"]}"/>'
                   f'<rect x="{x + dx}" y="{mid_y - 5 + dy}" width="{w}" height="{h}" fill="{c["overlay1"]}"/>')

    # Activity bar: Explorer is the active view.
    ax = MARGIN + ACTIVITY / 2
    for k, name in enumerate(("files", "search", "git", "run", "extensions")):
        y = body_y + 26 + k * 46
        out.append(icon(name, ax, y, c["text"] if k == 0 else c["overlay1"]))
    out.append(f'<rect x="{MARGIN}" y="{body_y + 12}" width="2" height="28" fill="{c["mauve"]}"/>')
    out.append(icon("account", ax, status_y - 62, c["overlay1"]))
    gear_y = status_y - 24
    out.append(f'<circle cx="{ax}" cy="{gear_y}" r="6.5" fill="none" stroke="{c["overlay1"]}" stroke-width="3" stroke-dasharray="2.6 2.5"/>'
               f'<circle cx="{ax}" cy="{gear_y}" r="4.6" fill="none" stroke="{c["overlay1"]}" stroke-width="1.5"/>')

    # Explorer.
    out.append(f'<text class="ui" x="{side_x + 20}" y="{body_y + 22}" font-size="11" letter-spacing="0.8" fill="{c["subtext0"]}">EXPLORER</text>')
    out += [f'<circle cx="{side_x + SIDEBAR - 30 + k * 5}" cy="{body_y + 18}" r="1.1" fill="{c["subtext0"]}"/>' for k in range(3)]
    tree = [
        (0, "open", "DZAKY-THARIQ"),
        (1, "dir", ".github"),
        (1, "dir", "assets"),
        (1, "open", "src"),
        (2, "ts", "about.ts"),
        (2, "ts", "stack.ts"),
        (2, "json", "github.json"),
        (1, "md", "README.md"),
    ]
    row_top = lambda r: body_y + 32 + r * 22
    for r, (level, kind, name) in enumerate(tree):
        y = row_top(r) + 15
        x = side_x + 10 + level * 10
        if name == "about.ts":
            out.append(f'<rect x="{side_x}" y="{row_top(r)}" width="{SIDEBAR}" height="22" fill="{c["surface0"]}" fill-opacity="0.75"/>')
        if level == 0:
            out.append(chevron(x, y - 4, True, c["text"]))
            out.append(f'<text class="ui" x="{x + 9}" y="{y - 0.5}" font-size="11" font-weight="700" fill="{c["text"]}">{name}</text>')
        elif kind in ("dir", "open"):
            out.append(chevron(x, y - 4, kind == "open", c["subtext0"]))
            out.append(f'<text class="ui" x="{x + 9}" y="{y}" font-size="13" fill="{c["text"]}">{name}</text>')
        else:
            out.append(file_badge(kind, x + 9, y, c))
            out.append(f'<text class="ui" x="{x + 27}" y="{y}" font-size="13" fill="{c["text"]}">{name}</text>')
    src = next(r for r, row in enumerate(tree) if row[2] == "src")
    guide_x = side_x + 20.5
    out.append(f'<line x1="{guide_x}" y1="{row_top(src + 1)}" x2="{guide_x}" y2="{row_top(src + 4)}" stroke="{c["surface1"]}"/>')
    for k, name in enumerate(("OUTLINE", "TIMELINE")):
        y = status_y - 44 + k * 22
        out.append(f'<line x1="{side_x}" y1="{y}" x2="{ed_x}" y2="{y}" stroke="{c["surface0"]}"/>')
        out.append(chevron(side_x + 12, y + 11, False, c["text"]))
        out.append(f'<text class="ui" x="{side_x + 21}" y="{y + 15}" font-size="11" font-weight="700" fill="{c["text"]}">{name}</text>')

    # Tabs: about.ts is open, two more sit behind it.
    x = ed_x
    for kind, name, w in (("ts", "about.ts", 128), ("json", "github.json", 132), ("md", "README.md", 130)):
        active = name == "about.ts"
        out.append(f'<rect x="{x}" y="{body_y}" width="{w}" height="{TABS}" fill="{c["base"] if active else c["mantle"]}"/>')
        if active:
            out.append(f'<rect x="{x}" y="{body_y}" width="{w}" height="2" fill="{c["mauve"]}"/>')
            cx, cy = x + w - 18, body_y + TABS / 2
            out.append(f'<path d="M{cx - 4} {cy - 4}l8 8M{cx + 4} {cy - 4}l-8 8" stroke="{c["subtext0"]}" stroke-width="1.3" stroke-linecap="round"/>')
        out.append(file_badge(kind, x + 12, body_y + 22, c))
        out.append(f'<text class="ui" x="{x + 31}" y="{body_y + 22}" font-size="13" fill="{c["text"] if active else c["overlay1"]}">{name}</text>')
        out.append(f'<line x1="{x + w - 0.5}" y1="{body_y}" x2="{x + w - 0.5}" y2="{body_y + TABS}" stroke="{c["crust"]}"/>')
        x += w
    out += [f'<circle cx="{win_r - 30 + k * 5}" cy="{body_y + TABS / 2}" r="1.1" fill="{c["subtext0"]}"/>' for k in range(3)]

    # Breadcrumbs.
    sep = f'<tspan fill="{c["overlay0"]}">  ›  </tspan>'
    out.append(
        f'<text class="ui" x="{ed_x + 18}" y="{crumb_y + 16}" font-size="12" fill="{c["subtext0"]}">src{sep}'
        f'<tspan font-size="8.5" font-weight="700" fill="{c["blue"]}">TS</tspan> about.ts{sep}'
        f'<tspan fill="{c["mauve"]}">◆</tspan> dzaky</text>'
    )

    # Cursor path: along each line while it types, then down to the next.
    times, xs, ys = [0.0], [code_x], [top(0)]
    for i, line in enumerate(lines):
        indent = len(line) - len(line.lstrip(" "))
        times += [starts[i], ends[i]]
        xs += [code_x + indent * CH, code_x + len(line) * CH]
        ys += [top(i), top(i)]
    last = len(lines) - 1

    # Current line highlight follows the cursor.
    out.append(
        f'<rect x="{ed_x}" y="{top(last)}" width="{mm_x - ed_x - 6}" height="{LINE}" fill="{c["surface0"]}" fill-opacity="0.45">'
        f'{keyed("y", ys, times, done, discrete=True)}</rect>'
    )

    # Per line: number, indent guides and minimap strokes appear when the line starts typing.
    depth = 0
    indents = [len(l) - len(l.lstrip(" ")) if l else None for l in lines]
    for i, line in enumerate(lines):
        tokens, depth = highlight(line, depth)
        if indents[i] is None:  # blank lines keep the guides of the block around them
            near = [n for n in (indents[i - 1] if i else None, indents[i + 1] if i < last else None) if n is not None]
            levels = min(near) // 2 if near else 0
        else:
            levels = indents[i] // 2
        parts = [f'<text x="{code_x - 18}" y="{top(i) + 15}" text-anchor="end" font-size="13"'
                 f' fill="{c["lavender"] if i == last else c["surface2"]}">{i + 1}</text>']
        parts += [f'<line x1="{code_x + k * 2 * CH + 0.5:.1f}" y1="{top(i)}" x2="{code_x + k * 2 * CH + 0.5:.1f}"'
                  f' y2="{top(i) + LINE}" stroke="{c["surface1"]}" stroke-opacity="0.7"/>' for k in range(levels)]
        col = 0
        for role, text in tokens:
            if role != "space":
                parts.append(f'<rect x="{mm_x + col * 0.9:.1f}" y="{code_top + i * 3.6:.1f}" width="{len(text) * 0.9:.1f}"'
                             f' height="2" fill="{c[SYNTAX[role]]}" fill-opacity="0.7"/>')
            col += len(text)
        out.append(f"<g>{hold(starts[i])}{''.join(parts)}</g>")
        if line:
            out.append(f'<text x="{code_x}" y="{top(i) + 15}" clip-path="url(#l{i})">{tspans(tokens)}</text>')
    out.append(f'<rect x="{mm_x - 3}" y="{code_top - 3}" width="{MINIMAP + 6}" height="{len(lines) * 3.6 + 5:.1f}"'
               f' rx="2" fill="{c["overlay0"]}" fill-opacity="0.08"/>')

    # The cursor: solid while typing, blinking once it rests at the end of the last line.
    out.append(
        f'<rect x="{xs[-1]:.1f}" y="{top(last) + 2}" width="2" height="16" fill="{c["rosewater"]}">'
        f'{keyed("x", xs, times, done)}{keyed("y", [y + 2 for y in ys], times, done, discrete=True)}'
        f'<animate attributeName="opacity" values="1;0" calcMode="discrete" dur="1.1s" begin="{done:.3f}s" repeatCount="indefinite"/></rect>'
    )

    # Status bar.
    sy = status_y + STATUS / 2
    out += [
        f'<rect x="{MARGIN}" y="{status_y}" width="32" height="{STATUS}" fill="{c["mauve"]}"/>',
        f'<path d="M{MARGIN + 13} {sy - 4}l-4 4l4 4M{MARGIN + 19} {sy - 4}l4 4l-4 4" fill="none" stroke="{c["crust"]}"'
        ' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    bx = MARGIN + 46
    out.append(
        f'<g fill="none" stroke="{c["subtext0"]}" stroke-width="1.2"><circle cx="{bx}" cy="{sy + 4.5}" r="1.7"/>'
        f'<circle cx="{bx}" cy="{sy - 4.5}" r="1.7"/><circle cx="{bx + 6}" cy="{sy - 2.5}" r="1.7"/>'
        f'<path d="M{bx} {sy - 2.8}v5.6M{bx + 6} {sy - 0.8}c0 3 -6 2 -6 3.6"/></g>'
    )
    ex, wx = MARGIN + 108, MARGIN + 140
    out += [
        f'<text class="ui" x="{bx + 13}" y="{sy + 4}" font-size="12" fill="{c["subtext0"]}">main</text>',
        f'<g fill="none" stroke="{c["subtext0"]}" stroke-width="1.2" stroke-linecap="round"><circle cx="{ex}" cy="{sy}" r="5"/>'
        f'<path d="M{ex - 2} {sy - 2}l4 4M{ex + 2} {sy - 2}l-4 4M{wx} {sy - 5}l5.5 9.5h-11z M{wx} {sy - 1.5}v2.5"/></g>',
        f'<text class="ui" x="{ex + 9}" y="{sy + 4}" font-size="12" fill="{c["subtext0"]}">0</text>',
        f'<text class="ui" x="{wx + 10}" y="{sy + 4}" font-size="12" fill="{c["subtext0"]}">0</text>',
        f'<text class="ui" x="{win_r - 14}" y="{sy + 4}" text-anchor="end" font-size="12" fill="{c["subtext0"]}">'
        f"Ln {last + 1}, Col {len(lines[-1]) + 1}    Spaces: 2    UTF-8    LF    "
        f'<tspan fill="{c["yellow"]}">{{}}</tspan> TypeScript</text>',
        f'<rect x="{MARGIN + 0.6}" y="{MARGIN + 0.6}" width="{win_w - 1.2}" height="{win_h - 1.2}" rx="11.5"'
        f' fill="none" stroke="url(#border)" stroke-opacity="{c["border_opacity"]}" stroke-width="1.2"/>',
        "</svg>",
    ]
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats", type=Path, help="JSON file with the numbers, instead of asking GitHub")
    args = parser.parse_args()

    if args.stats:
        stats = json.loads(args.stats.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("set GITHUB_TOKEN, or pass --stats FILE")
        stats = fetch_stats(token)
    print(json.dumps(stats))

    lines = code_lines(stats)
    for theme in ("dark", "light"):
        (ASSETS / f"{theme}_mode.svg").write_text(render(theme, lines), encoding="utf-8")
    print(f"wrote {ASSETS / 'dark_mode.svg'} and {ASSETS / 'light_mode.svg'}")


if __name__ == "__main__":
    main()
