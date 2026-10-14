"""Render the neofetch-style profile card: assets/dark_mode.svg and assets/light_mode.svg.

The GitHub Action runs this every day, so Uptime and the stats stay current.
It only needs the standard library and a token that can read public data
(the Action's GITHUB_TOKEN is enough):

    GITHUB_TOKEN=... python scripts/build_card.py

To preview without a token, pass the numbers yourself:

    python scripts/build_card.py --stats stats.json

where stats.json holds created_at, repos, stars, followers, following,
contributions_year and contributions_all.

The text on the card lives in info_lines() below. The portrait comes from
assets/ascii_dark.txt and assets/ascii_light.txt (see ascii_art.py).

The card is a terminal window that "boots" when the page loads: `neofetch` is
typed, the portrait scans in, the info lines follow, then a gold glint sweeps
across the portrait every few seconds. Everything is visible without the
animation too (reduced motion, or a viewer that ignores it).
"""

import argparse
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOGIN = "Dthariq347"
WIB = dt.timezone(dt.timedelta(hours=7))

# Info column: 16px monospace (9.6px per character), 20px per line, WIDTH characters wide.
INFO_FONT, INFO_LINE, INFO_CHAR, WIDTH = 16, 20, 9.6, 60
# Portrait: 12px monospace (7.2px per character), 14.2px per line. Keep in step with ascii_art.py.
ART_FONT, ART_LINE, ART_CHAR, ART_COLS = 12, 14.2, 7.2, 52

MARGIN = 20  # transparent room around the window for the glow
BAR = 36  # title bar height
PAD = 20  # inner padding of the window
GAP = 22  # between the portrait and the info column
PROMPT_Y = MARGIN + BAR + 32  # baseline of the "$ neofetch" line
INFO_TOP = PROMPT_Y + 38  # baseline of the first info line

PALETTES = {
    "dark": {
        "bg": ("#17151d", "#09090c"), "bar": "#111016", "rule": "#2b2517",
        "border": ("#f5d77a", "#6e5419", "#e3b341"), "halo": "#e3b341", "halo_opacity": 0.30, "halo_dy": 0,
        "title": "#857857", "text": "#cfc6b0", "key": "#e3b341", "value": "#efe6d2", "cc": "#4f432a",
        "user": "#f5d77a", "host": "#efe6d2",
        "art": ("#fbe7a1", "#e3b341", "#a8761c"), "shine": "#fff6d8", "shine_opacity": 0.95,
        "blocks": (
            ("#3a2a0c", "#5c4314", "#7d5c1a", "#9e7621", "#bf9029", "#d9a935", "#e9c25b", "#f5d77a"),
            ("#3f3829", "#655b45", "#8f8468", "#b9ad92", "#d8cfba", "#efe6d2", "#fbeec4", "#f8e3a0"),
        ),
    },
    "light": {
        "bg": ("#fffdf8", "#f3ecdc"), "bar": "#f1e9d6", "rule": "#e2d5b4",
        "border": ("#c9a227", "#efdca4", "#9c741b"), "halo": "#6b4e16", "halo_opacity": 0.20, "halo_dy": 5,
        "title": "#8f7d58", "text": "#5a4a30", "key": "#8a5a00", "value": "#3b2f1c", "cc": "#d6c69c",
        "user": "#8a5a00", "host": "#3b2f1c",
        "art": ("#a87a1c", "#7a5410", "#3f2b08"), "shine": "#f7d774", "shine_opacity": 0.9,
        "blocks": (
            ("#4a330a", "#6b4a10", "#8a5f14", "#a8781c", "#c29a2e", "#d4b04a", "#e2c573", "#eed89c"),
            ("#2b2418", "#3b2f1c", "#5a4a30", "#7a6a4f", "#9a8b6e", "#b9ab8e", "#d3c8ae", "#e6dcc6"),
        ),
    },
}


def info_lines(s):
    return [
        title("dzaky", "thariq"),
        kv("OS", "Windows 11, Linux (Docker)"),
        kv("Uptime", uptime(s["created_at"])),
        kv("Host", "Markaz Digital Payment"),
        kv("Kernel", "Full-Stack Developer"),
        kv("IDE", "VS Code, Claude Code"),
        [],
        kv("Languages.Programming", "Go, PHP, JavaScript, TypeScript"),
        kv("Languages.Computer", "HTML, CSS, SQL, YAML"),
        kv("Languages.Real", "Indonesian, English"),
        [],
        kv("Stack.Backend", "Go, Laravel, PostgreSQL"),
        kv("Stack.Frontend", "React, Vue, Tailwind CSS"),
        kv("Stack.Tools", "Docker, Git, GitHub Actions, Figma"),
        [],
        section("GitHub Stats"),
        pair(("Repos", s["repos"]), ("Stars", s["stars"])),
        pair(("Followers", s["followers"]), ("Following", s["following"])),
        kv("Contributions.PastYear", f"{s['contributions_year']:,}"),
        kv("Contributions.AllTime", f"{s['contributions_all']:,}"),
        [],
        [("blocks", 0)],
        [("blocks", 1)],
    ]


# A line is a list of (css class, text) segments; "" means the plain text colour.

def title(user, host):
    used = len(user) + 1 + len(host) + 1
    return [("user", user), ("", "@"), ("host", host), ("cc", " " + "─" * (WIDTH - used))]


def section(name):
    used = 2 + len(name) + 1
    return [("cc", "─ "), ("", name), ("cc", " " + "─" * (WIDTH - used))]


def kv_body(key, value, width):
    value = str(value)
    dots = max(1, width - len(key) - 1 - 2 - len(value))
    return [("key", key), ("", ":"), ("cc", " " + "." * dots + " "), ("value", value)]


def kv(key, value):
    return [("cc", ". ")] + kv_body(key, value, WIDTH - 2)


def pair(left, right):
    left_width = 29
    return ([("cc", ". ")] + kv_body(*left, left_width) + [("", " | ")]
            + kv_body(*right, WIDTH - 2 - left_width - 3))


def prompt(user, host):
    return [("user", user), ("", "@"), ("host", host), ("", ":"), ("value", "~"), ("key", "$ ")]


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


def tspans(segments):
    """Coloured tspans for one line. No whitespace between them: white-space: pre would draw it."""
    return "".join(
        f'<tspan class="{cls}">{escape(text)}</tspan>' if cls else f"<tspan>{escape(text)}</tspan>"
        for cls, text in segments
    )


def render(theme, art, lines):
    p = PALETTES[theme]
    left = MARGIN + PAD
    info_x = left + ART_COLS * ART_CHAR + GAP
    win_w = round(info_x + WIDTH * INFO_CHAR + PAD - MARGIN)
    last_info = INFO_TOP + (len(lines) - 1) * INFO_LINE

    # Centre the portrait on the info column, but never let it climb into the prompt line;
    # when it is the taller column the window grows to fit it.
    art_h = len(art) * ART_LINE
    art_top = max((INFO_TOP - INFO_FONT + last_info) / 2 - art_h / 2, INFO_TOP - INFO_FONT)
    art_base = art_top + ART_FONT * 0.8
    final_y = round(max(last_info + 40, art_top + art_h + 24))
    win_h = round(final_y + 24 - MARGIN)
    width, height = win_w + 2 * MARGIN, win_h + 2 * MARGIN
    art_w = ART_COLS * ART_CHAR
    # The glint is a band across a gradient running right and slightly down, so it leans like
    # a reflection; sweep far enough that the leaning band clears the portrait at both ends.
    shine_dy = art_w / 2
    sweep = round(art_w + art_h * shine_dy / art_w + 120)

    # Boot timeline, in seconds.
    type_at, type_step = 0.35, 0.07
    boot = type_at + len("neofetch") * type_step + 0.25
    row_step, line_step = 0.025, 0.05
    done = boot + max(len(art) * row_step, len(lines) * line_step) + 0.3

    stop = lambda off, color, op=1: f'<stop offset="{off}" stop-color="{color}" stop-opacity="{op}"/>'
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"'
        f' font-family="ConsolasFallback,Consolas,monospace" font-size="{INFO_FONT}px">',
        "<title>Dzaky Abiyyu Thariq - profile card</title>",
        "<defs>",
        f'<radialGradient id="bg" cx="0.12" cy="0" r="1.2">{stop(0, p["bg"][0])}{stop(1, p["bg"][1])}</radialGradient>',
        f'<linearGradient id="border" x1="0" y1="0" x2="1" y2="1">'
        f'{stop(0, p["border"][0])}{stop(0.5, p["border"][1])}{stop(1, p["border"][2])}</linearGradient>',
        f'<linearGradient id="gold" gradientUnits="userSpaceOnUse" x1="0" y1="{art_top:.0f}" x2="0" y2="{art_top + art_h:.0f}">'
        f'{stop(0, p["art"][0])}{stop(0.45, p["art"][1])}{stop(1, p["art"][2])}</linearGradient>',
        f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="{left}" y1="{art_top:.0f}"'
        f' x2="{left + art_w:.0f}" y2="{art_top + shine_dy:.0f}" gradientTransform="translate(-{sweep} 0)">'
        f'{stop(0.38, p["shine"], 0)}{stop(0.5, p["shine"], p["shine_opacity"])}{stop(0.62, p["shine"], 0)}'
        # Sweep across in the first 30% of each cycle, then rest off to the side.
        f'<animateTransform attributeName="gradientTransform" type="translate" values="-{sweep} 0;{sweep} 0;{sweep} 0"'
        f' keyTimes="0;0.3;1" dur="7s" begin="{done:.2f}s" repeatCount="indefinite"/></linearGradient>',
        '<filter id="blur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9"/></filter>',
        "</defs>",
        "<style>",
        "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback';"
        " font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
        "text { white-space: pre; }",
        f".row, .glint {{ font-size: {ART_FONT}px; }}",
        f".t {{ fill: {p['text']}; }}",
        *(f".{c} {{ fill: {p[c]}; }}" for c in ("key", "value", "cc", "user", "host")),
        f".bar {{ font: 13px 'Segoe UI', -apple-system, Helvetica, Arial, sans-serif; fill: {p['title']}; }}",
        "@keyframes show { from { opacity: 0; } to { opacity: 1; } }",
        "@keyframes slide { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: none; } }",
        "@keyframes type { from { fill-opacity: 0; } to { fill-opacity: 1; } }",
        "@keyframes blink { 50% { opacity: 0; } }",
        ".row { animation: show .4s ease-out both; }",
        ".ln { animation: slide .45s cubic-bezier(.2,.7,.2,1) both; }",
        ".ch { animation: type .01s linear both; }",
        ".cursor { animation: blink 1.1s step-end infinite; }",
        "@media (prefers-reduced-motion: reduce) { .row, .ln, .ch, .cursor { animation: none; } }",
        "</style>",
        # Glow (dark) or soft shadow (light) behind the window.
        f'<rect x="{MARGIN + 6}" y="{MARGIN + 6 + p["halo_dy"]}" width="{win_w - 12}" height="{win_h - 12}" rx="16"'
        f' fill="{p["halo"]}" opacity="{p["halo_opacity"]}" filter="url(#blur)"/>',
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{win_w}" height="{win_h}" rx="14" fill="url(#bg)"/>',
        # Title bar: square bottom corners, rounded top ones (clipped by the outline drawn last).
        f'<path d="M{MARGIN} {MARGIN + 14}a14 14 0 0 1 14 -14h{win_w - 28}a14 14 0 0 1 14 14v{BAR - 14}h-{win_w}z" fill="{p["bar"]}"/>',
        f'<line x1="{MARGIN}" y1="{MARGIN + BAR}" x2="{MARGIN + win_w}" y2="{MARGIN + BAR}" stroke="{p["rule"]}"/>',
        *(f'<circle cx="{MARGIN + 22 + i * 20}" cy="{MARGIN + BAR / 2}" r="6" fill="{c}"/>'
          for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840"))),
        f'<text class="bar" x="{MARGIN + win_w / 2}" y="{MARGIN + BAR / 2 + 4.5}" text-anchor="middle">dzaky@thariq: ~ — neofetch</text>',
        f'<rect x="{MARGIN + 0.6}" y="{MARGIN + 0.6}" width="{win_w - 1.2}" height="{win_h - 1.2}" rx="13.5"'
        f' fill="none" stroke="url(#border)" stroke-width="1.2"/>',
    ]

    # "$ neofetch", typed one character at a time.
    typed = "".join(
        f'<tspan class="value ch" style="animation-delay:{type_at + i * type_step:.2f}s">{escape(c)}</tspan>'
        for i, c in enumerate("neofetch")
    )
    out.append(f'<text class="t" x="{left}" y="{PROMPT_Y}">{tspans(prompt("dzaky", "thariq"))}{typed}</text>')

    # Portrait: gold gradient rows that scan in, then the same rows again carrying the glint.
    # Drawn twice rather than through <use>, whose clones animate unevenly across browsers.
    row_y = lambda i: f"{art_base + i * ART_LINE:.1f}"
    out.append('<g fill="url(#gold)">' + "".join(
        f'<text class="row" style="animation-delay:{boot + i * row_step:.3f}s" x="{left}" y="{row_y(i)}">{escape(row)}</text>'
        for i, row in enumerate(art)
    ) + "</g>")
    out.append('<g fill="url(#shine)" aria-hidden="true">' + "".join(
        f'<text class="glint" x="{left}" y="{row_y(i)}">{escape(row)}</text>' for i, row in enumerate(art)
    ) + "</g>")

    for i, segments in enumerate(lines):
        y = INFO_TOP + i * INFO_LINE
        delay = f'style="animation-delay:{boot + i * line_step:.2f}s"'
        if segments and segments[0][0] == "blocks":
            colors = p["blocks"][segments[0][1]]
            out.append(f'<g class="ln" {delay}>' + "".join(
                f'<rect x="{info_x + j * 3 * INFO_CHAR:.1f}" y="{y - 14}" width="{3 * INFO_CHAR - 3:.1f}" height="17" rx="2.5" fill="{c}"/>'
                for j, c in enumerate(colors)
            ) + "</g>")
            continue
        if not segments:
            continue
        cols = sum(len(text) for _, text in segments)
        if cols > WIDTH:
            print(f"warning: line {i + 1} is {cols} characters, wider than {WIDTH}")
        out.append(f'<text class="t ln" {delay} x="{info_x}" y="{y}">{tspans(segments)}</text>')

    # Back at the prompt, with a blinking cursor.
    final = prompt("dzaky", "thariq")
    cursor_x = left + sum(len(text) for _, text in final) * INFO_CHAR
    out.append(
        f'<g class="ln" style="animation-delay:{done:.2f}s"><text class="t" x="{left}" y="{final_y}">{tspans(final)}</text>'
        f'<rect class="cursor" x="{cursor_x:.1f}" y="{final_y - INFO_FONT + 2}" width="{INFO_CHAR}" height="{INFO_FONT + 2}"'
        f' fill="{p["user"]}"/></g>'
    )
    out.append("</svg>")
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

    lines = info_lines(stats)
    for theme in ("dark", "light"):
        art = (ASSETS / f"ascii_{theme}.txt").read_text(encoding="utf-8").rstrip("\n").split("\n")
        (ASSETS / f"{theme}_mode.svg").write_text(render(theme, art, lines), encoding="utf-8")
    print(f"wrote {ASSETS / 'dark_mode.svg'} and {ASSETS / 'light_mode.svg'}")


if __name__ == "__main__":
    main()
