#!/usr/bin/env python3
"""Draw every README card into cards/ as a self-contained animated SVG.

A GitHub README cannot run JavaScript or load CSS, and an SVG shown through
<img> is sandboxed: no scripts, no external requests. What does survive is the
SVG's own <style> block, so every card here is CSS keyframes plus fonts subset
with fontTools and inlined as base64 WOFF.

  python scripts/render_readme_cards.py            # animated
  STATIC=1 python scripts/render_readme_cards.py   # final frame, for screenshots
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import svgfont as sf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
DATA = ROOT / "data"

STATIC = os.environ.get("STATIC") == "1"

W = 880    # the width GitHub renders README content at
PAD = 36

# ------------------------------------------------------------------ palette
# Two themes, selected per run. The README serves them with <picture>, so a
# light-mode profile does not get dark blocks on a white page.

THEME = os.environ.get("THEME", "dark")

PALETTES = {
    "dark": dict(
        BG="#0b0e13", PANEL="#0f131a", LINE="#1d232d", LINE_HI="#2a323e",
        TEXT="#e8ecf1", DIM="#9aa5b3", MUTED="#636d7c", FAINT="#3c4450",
        ACCENT="#5eead4", ACCENT_DIM="#2f8d7c", BAR="#222a36", TRACK="#171d26",
        LEVELS=["#161b23", "#113c38", "#176555", "#28a187", "#5eead4"],
    ),
    "light": dict(
        BG="#ffffff", PANEL="#f8fafb", LINE="#dde3ea", LINE_HI="#c9d1da",
        TEXT="#17202a", DIM="#4e5a68", MUTED="#7b8795", FAINT="#aeb7c2",
        ACCENT="#0e8a76", ACCENT_DIM="#4cb8a4", BAR="#d7dee6", TRACK="#e8edf2",
        LEVELS=["#ebeef2", "#c3e9df", "#7fcfbc", "#36a893", "#0e8a76"],
    ),
}

_P = PALETTES[THEME]
BG = _P["BG"]
PANEL = _P["PANEL"]
LINE = _P["LINE"]
LINE_HI = _P["LINE_HI"]
TEXT = _P["TEXT"]
DIM = _P["DIM"]
MUTED = _P["MUTED"]
FAINT = _P["FAINT"]
ACCENT = _P["ACCENT"]
ACCENT_DIM = _P["ACCENT_DIM"]
BAR = _P["BAR"]
TRACK = _P["TRACK"]

# Contribution levels: empty, then four steps toward the accent.
LEVELS = _P["LEVELS"]

LANG_COLOR = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572a5",
    "Kotlin": "#a97bff",
    "Rust": "#dea584",
    "Go": "#00add8",
    "Shell": "#89e051",
    "TeX": "#3d6117",
    "HTML": "#e34c26",
    "": MUTED,
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ------------------------------------------------------------------- motion
# Animated elements start from their "before" state in ANIM_CSS and are driven
# forwards from there. REST_CSS puts everything at its end state and is what
# both STATIC=1 and prefers-reduced-motion get. Nothing loops: the cards settle
# within a couple of seconds and then hold still.

KEYFRAMES = (
    "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}"
    "@keyframes fade{from{opacity:0}to{opacity:1}}"
    "@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
    "@keyframes growy{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
    "@keyframes show{to{opacity:1}}"
    "@keyframes hide{to{opacity:0}}"
)

ANIM_CSS = (
    ".rise{opacity:0;animation:rise .55s cubic-bezier(.22,.7,.3,1) both}"
    ".fade{opacity:0;animation:fade .45s linear both}"
    ".growx{transform-box:fill-box;transform-origin:0 50%;"
    "animation:growx .6s cubic-bezier(.22,.8,.3,1) both}"
    ".growy{transform-box:fill-box;transform-origin:50% 100%;"
    "animation:growy .65s cubic-bezier(.22,.8,.3,1) both}"
    ".cnt{opacity:0}"
)

REST_CSS = (
    "*{animation:none!important}"
    ".rise,.fade,.growx,.growy{opacity:1!important;transform:none!important}"
    ".cnt{display:none!important}"
    ".cnt-end{display:inline!important;opacity:1!important}"
)


def delay(seconds: float, extra: str = "") -> str:
    return f"animation-delay:{seconds:.3f}s;{extra}"


class Card:
    """An SVG document that tracks which glyphs it actually prints."""

    def __init__(self, label: str, w: int, h: int):
        self.label = label
        self.w = w
        self.h = h
        self.defs: list[str] = []
        self.body: list[str] = []
        self.extra_css: list[str] = []
        self.used: dict[str, set] = {key: set() for key in sf.FONTS}

    # ---------------------------------------------------------- primitives
    def add(self, markup: str) -> None:
        self.body.append(markup)

    def define(self, markup: str) -> None:
        self.defs.append(markup)

    def css(self, rule: str) -> None:
        self.extra_css.append(rule)

    def rect(self, x, y, w, h, fill, *, opacity=None, cls="", style="", rx=0) -> None:
        bits = [f'x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}"']
        if rx:
            bits.append(f'rx="{rx:g}"')
        if opacity is not None:
            bits.append(f'opacity="{opacity:g}"')
        if cls:
            bits.append(f'class="{cls}"')
        if style:
            bits.append(f'style="{style}"')
        self.add(f"<rect {' '.join(bits)}/>")

    def text(self, x, y, content, *, font="sans", size=14, fill=TEXT, anchor="start",
             cls="", style="", spacing=None, opacity=None) -> None:
        content = str(content)
        self.used[font].update(content)
        bits = [
            f'x="{x:g}" y="{y:g}"',
            f'font-family="{sf.family(font)}"',
            f'font-size="{size:g}"',
            f'fill="{fill}"',
        ]
        if anchor != "start":
            bits.append(f'text-anchor="{anchor}"')
        if spacing is not None:
            bits.append(f'letter-spacing="{spacing:g}"')
        if opacity is not None:
            bits.append(f'opacity="{opacity:g}"')
        if cls:
            bits.append(f'class="{cls}"')
        if style:
            bits.append(f'style="{style}"')
        self.add(f"<text {' '.join(bits)}>{esc(content)}</text>")

    def eyebrow(self, x, y, content, *, fill=MUTED, anchor="start", cls="", style=""):
        """The small uppercase label that titles a section."""
        self.text(x, y, content.upper(), font="mono", size=11, fill=fill, anchor=anchor,
                  spacing=1.5, cls=cls, style=style)

    def width_of(self, font, content, size, spacing=0.0) -> float:
        return sf.width(font, str(content), size, spacing)

    def fit(self, font, content, size, max_width) -> str:
        return sf.fit(font, str(content), size, max_width)

    def frame(self) -> None:
        """Panel fill plus a one-pixel border. No bevels, no shadows."""
        self.rect(0, 0, self.w, self.h, LINE)
        self.rect(1, 1, self.w - 2, self.h - 2, PANEL)

    def rule(self, x, y, w, *, fill=LINE, cls="", style="") -> None:
        self.rect(x, y, w, 1, fill, cls=cls, style=style)

    # ------------------------------------------------------------- output
    def render(self) -> str:
        faces = "".join(
            sf.face(key, "".join(sorted(chars))) for key, chars in self.used.items() if chars
        )
        rules = "".join(self.extra_css)
        if STATIC:
            style = f"{faces}{rules}{REST_CSS}"
        else:
            style = (
                f"{faces}{KEYFRAMES}{ANIM_CSS}{rules}"
                f"@media (prefers-reduced-motion: reduce){{{REST_CSS}}}"
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}" role="img" aria-label="{esc(self.label)}">'
            f"<style>{style}</style>"
            f"<defs>{''.join(self.defs)}</defs>"
            f'<rect width="{self.w}" height="{self.h}" fill="{BG}"/>'
            f"{''.join(self.body)}"
            "</svg>"
        )

    def write(self, filename: str) -> None:
        out = CARDS if THEME == "dark" else CARDS / THEME
        out.mkdir(parents=True, exist_ok=True)
        path = out / filename
        path.write_text(self.render())
        print(f"  {filename:<20} {path.stat().st_size / 1024:6.1f} KB")


def count_up(card: Card, x, y, value: int, *, font="display", size=38, fill=TEXT,
             anchor="start", start=0.0, duration=.7, frames=16):
    """A number that ticks up from zero.

    CSS cannot change text, so each intermediate value is its own <text> shown
    for a few milliseconds by a pair of zero-length animations. Keeping it in
    CSS rather than SMIL is what lets prefers-reduced-motion switch it off.
    """
    if STATIC or value <= 0:
        card.text(x, y, f"{value:,}", font=font, size=size, fill=fill, anchor=anchor,
                  cls="cnt-end")
        return
    step = duration / frames
    for i in range(frames):
        shown = round(value * ((i + 1) / frames) ** 0.72)
        card.text(x, y, f"{shown:,}", font=font, size=size, fill=fill, anchor=anchor, cls="cnt",
                  style=f"animation:show 1ms linear {start + i * step:.3f}s forwards,"
                        f"hide 1ms linear {start + (i + 1) * step:.3f}s forwards")
    card.text(x, y, f"{value:,}", font=font, size=size, fill=fill, anchor=anchor,
              cls="cnt cnt-end",
              style=f"animation:show 1ms linear {start + duration:.3f}s forwards")


def wrap(font: str, text: str, size: float, max_width: float, lines: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        probe = f"{line} {word}".strip()
        if sf.width(font, probe, size) <= max_width:
            line = probe
        else:
            if line:
                out.append(line)
            line = word
            if len(out) == lines:
                break
    if line and len(out) < lines:
        out.append(line)
    if len(out) == lines:
        consumed = len(" ".join(out))
        if text[consumed:].strip():
            out[-1] = sf.fit(font, out[-1] + " " + text[consumed:].strip(), size, max_width)
    return out[:lines]


# ------------------------------------------------------------------ the data

def load_stats() -> dict:
    cal = json.loads((DATA / "contributions.json").read_text())
    stats = json.loads((DATA / "stats.json").read_text())
    days = cal["days"]

    counts = {d["date"]: d["count"] for d in days}
    levels = {d["date"]: d["level"] for d in days}
    ordered = sorted(counts)

    # Current streak: today counts if it has activity, otherwise start at
    # yesterday so an early-morning render does not read as a broken streak.
    cursor = date.fromisoformat(ordered[-1])
    if counts.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    current = 0
    while counts.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    longest = run = 0
    for iso in ordered:
        run = run + 1 if counts[iso] > 0 else 0
        longest = max(longest, run)

    last_active = max((i for i in ordered if counts[i] > 0), default=ordered[-1])
    busiest_iso = max(ordered, key=lambda i: counts[i])

    months: dict[str, int] = {}
    for iso in ordered:
        months[iso[:7]] = months.get(iso[:7], 0) + counts[iso]
    month_keys = sorted(months)[-12:]

    return {
        "cal": cal,
        "stats": stats,
        "counts": counts,
        "levels": levels,
        "ordered": ordered,
        "total": cal["total"],
        "active": sum(1 for v in counts.values() if v > 0),
        "span": len(ordered),
        "current_streak": current,
        "longest_streak": longest,
        "last_active": date.fromisoformat(last_active),
        "busiest": date.fromisoformat(busiest_iso),
        "busiest_count": counts[busiest_iso],
        "months": [(k, months[k]) for k in month_keys],
        "best_month": max(month_keys, key=lambda k: months[k]),
    }


# ----------------------------------------------------------------- the cards

NAME = "Rudraksha Singh Sengar"
ROLE = "Software Engineer · Bangalore, India"
TAGLINE = "I build for the web and contribute upstream."
CONTACT = [
    "rudraksha.tech",
    "linkedin.com/in/rudrakshasingh18",
    "rudraksharss@gmail.com",
]


def card_hero(s: dict) -> None:
    h = 178
    c = Card(f"{NAME} - {ROLE}", W, h)
    c.frame()

    c.rect(1, 1, 3, h - 2, ACCENT, opacity=.5, cls="growy", style=delay(.1))
    c.text(PAD, 78, NAME, font="display", size=42, fill=TEXT, cls="rise", style=delay(.05))
    c.text(PAD, 112, ROLE, font="mono", size=13, fill=DIM, cls="rise", style=delay(.16))
    c.text(PAD, 138, TAGLINE, font="sans", size=16, fill=MUTED, cls="rise", style=delay(.24))

    for i, line in enumerate(CONTACT):
        c.text(W - PAD, 74 + i * 22, line, font="mono", size=13,
               fill=DIM if i == 0 else MUTED, anchor="end",
               cls="rise", style=delay(.3 + i * .07))
    c.write("hero.svg")


def card_graph(s: dict) -> None:
    pitch, cell, rows = 15, 12, 7
    ordered = s["ordered"]
    first = date.fromisoformat(ordered[0])
    offset = (first.weekday() + 1) % 7  # GitHub weeks start on Sunday
    cols = (len(ordered) + offset + 6) // 7

    grid_w = cols * pitch - (pitch - cell)
    x0 = round((W - grid_w) / 2)
    top = 88
    h = top + rows * pitch + 46

    c = Card("Contribution activity over the last twelve months", W, h)
    c.frame()
    c.eyebrow(PAD, 40, "Contributions", cls="rise", style=delay(.05))
    c.text(W - PAD, 41, f"{s['total']:,} in the last year", font="mono", size=13, fill=DIM,
           anchor="end", cls="rise", style=delay(.1))
    c.rule(PAD, 54, W - 2 * PAD, cls="fade", style=delay(.14))

    seen_month = None
    for idx, iso in enumerate(ordered):
        col, row = divmod(idx + offset, 7)
        x, y = x0 + col * pitch, top + row * pitch
        c.rect(x, y, cell, cell, LEVELS[s["levels"][iso]], rx=2,
               cls="fade" if not STATIC else "",
               style=delay(.25 + col * .009, "animation-duration:.26s") if not STATIC else "")
        day = date.fromisoformat(iso)
        if day.day <= 7 and seen_month != iso[:7]:
            seen_month = iso[:7]
            c.text(x, top - 14, MONTHS[day.month - 1], font="mono", size=10, fill=MUTED,
                   cls="fade", style=delay(.2 + col * .008))

    legend_y = top + rows * pitch + 24
    lx = W - PAD - 5 * pitch - 38
    c.text(lx - 8, legend_y, "Less", font="mono", size=10, fill=MUTED, anchor="end",
           cls="fade", style=delay(.95))
    for i, colour in enumerate(LEVELS):
        c.rect(lx + i * pitch, legend_y - 9, cell, cell, colour, rx=2,
               cls="fade", style=delay(.98 + i * .04))
    c.text(W - PAD, legend_y, "More", font="mono", size=10, fill=MUTED, anchor="end",
           cls="fade", style=delay(1.2))
    c.write("graph.svg")


def card_activity(s: dict) -> None:
    h = 206
    c = Card("Contributions per month, streaks and busiest day", W, h)
    c.frame()
    c.eyebrow(PAD, 40, "Activity", cls="rise", style=delay(.05))
    c.text(W - PAD, 41, "contributions per month", font="mono", size=13, fill=DIM,
           anchor="end", cls="rise", style=delay(.1))
    c.rule(PAD, 54, W - 2 * PAD, cls="fade", style=delay(.14))

    months = s["months"]
    peak = max(v for _, v in months) or 1
    base_y, max_h = 158, 74
    bar_w, gap = 32, 14.5

    for i, (key, value) in enumerate(months):
        x = PAD + i * (bar_w + gap)
        bar_h = max(2, round(max_h * value / peak))
        best = key == s["best_month"]
        c.rect(x, base_y - bar_h, bar_w, bar_h, ACCENT if best else BAR,
               cls="growy" if not STATIC else "",
               style=delay(.3 + i * .045, "animation-duration:.6s") if not STATIC else "")
        if best:
            count_up(c, x + bar_w / 2, base_y - bar_h - 12, value, font="display", size=16,
                     fill=ACCENT, anchor="middle", start=.95, duration=.45, frames=12)
        c.text(x + bar_w / 2, base_y + 20, MONTHS[int(key[5:]) - 1], font="mono", size=10,
               fill=DIM if best else MUTED, anchor="middle",
               cls="fade", style=delay(.4 + i * .04))

    c.rule(PAD, base_y + 1, 12 * bar_w + 11 * gap, fill=LINE_HI)

    sx = 616
    c.rect(sx - 28, 70, 1, h - 104, LINE)
    streak = (
        ("Current streak", f"{s['current_streak']} days", TEXT)
        if s["current_streak"]
        else ("Last active", f"{s['last_active'].day} {MONTHS[s['last_active'].month - 1]}", DIM)
    )
    rows = [
        streak,
        ("Longest streak", f"{s['longest_streak']} days", TEXT),
        ("Active days", f"{s['active']} of {s['span']}", TEXT),
        ("Busiest day", f"{s['busiest_count']} on {s['busiest'].day} "
                        f"{MONTHS[s['busiest'].month - 1]}", TEXT),
        ("Merged pull requests", f"{s['stats']['merged_prs']:,}", TEXT),
    ]
    for i, (label, value, colour) in enumerate(rows):
        y = 80 + i * 27
        c.eyebrow(sx, y, label, cls="rise", style=delay(.5 + i * .07))
        c.text(W - PAD, y, value, font="monomd", size=14, fill=colour, anchor="end",
               cls="rise", style=delay(.54 + i * .07))
    c.write("activity.svg")


TILES = [
    ("Repositories", "public on GitHub", lambda s: s["stats"]["public_repos"]),
    ("Merged pull requests", "across every repository", lambda s: s["stats"]["merged_prs"]),
    ("Upstream projects", "other maintainers' repositories",
     lambda s: s["stats"]["external_repo_count"]),
]


def card_tile(s: dict, index: int) -> None:
    label, sub, value = TILES[index]
    w, h = 286, 128
    c = Card(f"{label} - {sub}", w, h)
    c.add(f'<g class="rise" style="{delay(.1 + index * .1)}">' if not STATIC else "<g>")
    c.frame()
    c.rect(1, 1, 2, h - 2, ACCENT, opacity=.5)
    c.eyebrow(24, 38, label)
    count_up(c, 24, 88, value(s), font="display", size=38, start=.45 + index * .1, duration=.8)
    c.text(24, 108, sub, font="sans", size=13, fill=MUTED)
    c.add("</g>")
    c.write(f"tile-{index + 1}.svg")


def card_upstream(s: dict) -> None:
    rows = s["stats"]["upstream"][:5]
    top = 98
    h = top + len(rows) * 25 + 14
    c = Card("Merged pull requests in upstream projects", W, h)
    c.frame()
    c.eyebrow(PAD, 40, "Upstream", cls="rise", style=delay(.05))
    c.text(W - PAD, 41, "pull requests in other maintainers' repositories", font="mono",
           size=13, fill=DIM, anchor="end", cls="rise", style=delay(.1))
    c.rule(PAD, 54, W - 2 * PAD, cls="fade", style=delay(.14))

    head_y = 76
    for x, title, anchor in ((PAD, "Project", "start"), (236, "Repository", "start"),
                             (742, "Merged", "end"), (W - PAD, "Open", "end")):
        c.text(x, head_y, title.upper(), font="mono", size=9, fill=FAINT, anchor=anchor,
               spacing=1.4, cls="fade", style=delay(.18))
    c.rule(PAD, head_y + 12, W - 2 * PAD, cls="fade", style=delay(.2))

    peak = max((u["merged"] for u in rows), default=1) or 1
    for i, u in enumerate(rows):
        y = top + 16 + i * 25
        d = .26 + i * .07
        c.text(PAD, y, u["label"], font="sans", size=15, fill=TEXT, cls="rise", style=delay(d))
        c.text(236, y, c.fit("mono", u["repo"], 12, 300), font="mono", size=12, fill=MUTED,
               cls="rise", style=delay(d + .03))

        bar_x, bar_w = 568, 136
        c.rect(bar_x, y - 9, bar_w, 6, TRACK, rx=3)
        if u["merged"]:
            c.rect(bar_x, y - 9, max(6, round(bar_w * u["merged"] / peak)), 6, ACCENT_DIM, rx=3,
                   cls="growx" if not STATIC else "", style=delay(d + .08) if not STATIC else "")
        c.text(742, y, str(u["merged"]), font="monomd", size=14,
               fill=TEXT if u["merged"] else MUTED, anchor="end", cls="rise", style=delay(d + .1))
        c.text(W - PAD, y, str(u["open"]) if u["open"] else "—", font="mono", size=14,
               fill=DIM if u["open"] else FAINT, anchor="end", cls="rise", style=delay(d + .12))
    c.write("upstream.svg")


# GitHub has no description for this one; this is the line its sibling repo carries.
DESCRIPTION_FALLBACK = {
    "pointblank-club/Kitten": "Resize your disk, pull the plug, the cat doesn't flinch.",
}


def card_repo(repo: dict, index: int) -> None:
    w, h = 286, 160
    c = Card(f"{repo['full_name']} - {repo['description'][:60]}", w, h)
    c.add(f'<g class="rise" style="{delay(.12 + index * .1)}">' if not STATIC else "<g>")
    c.frame()

    c.text(22, 42, c.fit("display", repo["name"], 16, w - 44), font="display", size=16,
           fill=TEXT)
    c.text(22, 60, repo["full_name"].partition("/")[0], font="mono", size=11, fill=MUTED)

    desc = repo["description"] or DESCRIPTION_FALLBACK.get(repo["full_name"], "")
    for i, line in enumerate(wrap("sans", desc, 13, w - 44, 3)):
        c.text(22, 88 + i * 17, line, font="sans", size=13, fill=DIM)

    c.rule(22, 130, w - 44)
    facts = []
    if repo["stars"]:
        facts.append(f"{repo['stars']} stars")
    if repo["merged_prs"]:
        facts.append(f"{repo['merged_prs']} PRs")
    x = 22
    if repo["language"]:
        c.add(f'<circle cx="{x + 4}" cy="146" r="4" '
              f'fill="{LANG_COLOR.get(repo["language"], LANG_COLOR[""])}"/>')
        c.text(x + 14, 150, repo["language"], font="mono", size=11, fill=DIM)
        x += 14 + c.width_of("mono", repo["language"], 11)
    if facts:
        c.text(w - 22, 150, "  ·  ".join(facts), font="mono", size=11, fill=MUTED, anchor="end")
    c.add("</g>")
    c.write(f"repo-{index + 1}.svg")


def main() -> None:
    s = load_stats()
    print(f"rendering {THEME} cards ({'static' if STATIC else 'animated'}) "
          f"from data fetched {s['cal']['fetched_at']}")
    card_hero(s)
    card_graph(s)
    card_activity(s)
    for i in range(len(TILES)):
        card_tile(s, i)
    card_upstream(s)
    for i, repo in enumerate(s["stats"]["repos"][:3]):
        card_repo(repo, i)
    out = CARDS if THEME == "dark" else CARDS / THEME
    total = sum(p.stat().st_size for p in out.glob("*.svg")) / 1024
    print(f"  {'total':<20} {total:6.1f} KB")


if __name__ == "__main__":
    main()
