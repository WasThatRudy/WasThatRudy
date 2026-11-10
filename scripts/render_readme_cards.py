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
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pixelfont as pf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
DATA = ROOT / "data"
ASSETS = ROOT / "assets"

STATIC = os.environ.get("STATIC") == "1"

W = 880  # README content width Github renders at 100%

# -------------------------------------------------------------- palette
# Terraria at night: the underground inventory panel, not the daylight forest.
INK = "#05070f"       # deepest background
PANEL = "#0e1224"     # panel fill
PANEL_HI = "#171c38"  # panel fill, lit edge
PANEL_LO = "#080a16"  # panel fill, shadowed edge
EDGE = "#02030a"      # outer 1px border
STUD = "#242b52"      # inner highlight / rivets
SLOT = "#111532"      # empty inventory slot

BONE = "#efe4cb"      # primary text
BONE_DIM = "#a49c8c"  # secondary text
MUTED = "#6b6782"     # tertiary text
GOLD = "#c8a878"      # frame gold
GOLD_LO = "#6d552f"

MINT = "#5eead4"      # brand accent: the contribution map
CYAN = "#69ffff"      # rarity: cyan
ORANGE = "#ffc896"    # rarity: orange
GREEN = "#96ff96"     # rarity: green
PINK = "#ffb4c8"      # rarity: pink
YELLOW = "#ffe85a"    # rarity: yellow

# Contribution levels, dark navy through to the mint accent.
LEVELS = ["#0c1024", "#134b45", "#1a7d6f", "#2fb59c", "#5eead4"]

LANG_COLOR = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "Kotlin": "#A97BFF",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "C": "#555555",
    "Shell": "#89e051",
    "TeX": "#3D6117",
    "HTML": "#e34c26",
    "": "#6b6782",
}


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Card:
    """An SVG document that tracks which glyphs it actually prints."""

    def __init__(self, name: str, w: int, h: int, bg: str = INK):
        self.name = name
        self.w = w
        self.h = h
        self.bg = bg
        self.defs: list[str] = []
        self.body: list[str] = []
        self.extra_css: list[str] = []
        self.used: dict[str, set] = {"display": set(), "pixel": set(), "mono": set()}

    # ---------------------------------------------------------- primitives
    def add(self, markup: str) -> None:
        self.body.append(markup)

    def define(self, markup: str) -> None:
        self.defs.append(markup)

    def css(self, rule: str) -> None:
        self.extra_css.append(rule)

    def rect(self, x, y, w, h, fill, *, opacity=None, cls="", style="", rx=0, extra="") -> None:
        bits = [f'x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}"']
        if rx:
            bits.append(f'rx="{rx:g}"')
        if opacity is not None:
            bits.append(f'opacity="{opacity:g}"')
        if cls:
            bits.append(f'class="{cls}"')
        if style:
            bits.append(f'style="{style}"')
        if extra:
            bits.append(extra)
        self.add(f"<rect {' '.join(bits)}/>")

    def text(
        self,
        x,
        y,
        content,
        *,
        font="pixel",
        size=10,
        fill=BONE,
        anchor="start",
        cls="",
        style="",
        outline=None,
        spacing=None,
        opacity=None,
        extra="",
    ) -> None:
        content = str(content)
        self.used[font].update(content)
        bits = [
            f'x="{x:g}" y="{y:g}"',
            # the family name needs its own quotes inside the attribute: a CSS
            # family whose last token starts with a digit ("Jersey 25") is
            # otherwise parsed as a number and the whole face is discarded
            f'font-family="&apos;{pf.family(font)}&apos;"',
            f'font-size="{size:g}"',
            f'fill="{fill}"',
        ]
        if anchor != "start":
            bits.append(f'text-anchor="{anchor}"')
        if spacing is not None:
            bits.append(f'letter-spacing="{spacing:g}"')
        if outline:
            bits.append(f'stroke="{outline}" stroke-width="3" paint-order="stroke" stroke-linejoin="round"')
        if opacity is not None:
            bits.append(f'opacity="{opacity:g}"')
        if cls:
            bits.append(f'class="{cls}"')
        if style:
            bits.append(f'style="{style}"')
        if extra:
            bits.append(extra)
        self.add(f"<text {' '.join(bits)}>{esc(content)}</text>")

    def width_of(self, font, content, size) -> float:
        return pf.width(font, str(content), size)

    def fit(self, font, content, size, max_width) -> str:
        return pf.fit(font, str(content), size, max_width)

    # ------------------------------------------------------------ chrome
    def panel(self, x, y, w, h, *, fill=PANEL, border=GOLD, cls="", style="") -> None:
        """A Terraria inventory panel: dark fill, gold hairline, bevelled inside."""
        g = f'<g class="{cls}" style="{style}">' if (cls or style) else "<g>"
        self.add(g)
        self.rect(x, y, w, h, EDGE)
        self.rect(x + 1, y + 1, w - 2, h - 2, border, opacity=0.55)
        self.rect(x + 2, y + 2, w - 4, h - 4, fill)
        self.rect(x + 2, y + 2, w - 4, 1, STUD, opacity=0.9)
        self.rect(x + 2, y + h - 3, w - 4, 1, PANEL_LO)
        self.rect(x + 2, y + 2, 1, h - 4, STUD, opacity=0.5)
        self.add("</g>")

    def slot(self, x, y, size, *, fill=SLOT, border="#2b3160") -> None:
        """An inventory slot: the little rounded square items sit in."""
        self.rect(x, y, size, size, border, rx=3)
        self.rect(x + 1.5, y + 1.5, size - 3, size - 3, fill, rx=2)
        self.rect(x + 1.5, y + 1.5, size - 3, 1, "#39407a", rx=0, opacity=0.8)

    # ------------------------------------------------------------ output
    def render(self) -> str:
        faces = "".join(
            pf.face(key, "".join(sorted(chars))) for key, chars in self.used.items() if chars
        )
        motion = "" if STATIC else "".join(KEYFRAMES)
        rules = "".join(self.extra_css)
        if STATIC:
            style = f"{faces}{BASE_CSS}{rules}{REST_CSS}"
        else:
            style = (
                f"{faces}{motion}{BASE_CSS}{ANIM_CSS}{rules}"
                f"@media (prefers-reduced-motion: reduce){{{REST_CSS}}}"
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}" role="img" aria-label="{esc(self.name)}">'
            f"<style>{style}</style>"
            f"<defs>{''.join(self.defs)}</defs>"
            f'<rect width="{self.w}" height="{self.h}" fill="{self.bg}"/>'
            f"{''.join(self.body)}"
            "</svg>"
        )

    def write(self, filename: str) -> None:
        CARDS.mkdir(parents=True, exist_ok=True)
        path = CARDS / filename
        path.write_text(self.render())
        kb = path.stat().st_size / 1024
        print(f"  {filename:<22} {kb:6.1f} KB")


# ------------------------------------------------------------------- motion
# Every animated element starts from its "before" state in BASE_CSS and is
# driven forwards by ANIM_CSS. REST_CSS puts everything at its end state and is
# what both STATIC=1 and prefers-reduced-motion get.

KEYFRAMES = [
    "@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}",
    "@keyframes fade{from{opacity:0}to{opacity:1}}",
    "@keyframes pop{0%{opacity:0;transform:scale(.4)}70%{opacity:1;transform:scale(1.12)}100%{opacity:1;transform:scale(1)}}",
    "@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}",
    "@keyframes swing{0%{opacity:0;transform:translateY(42px) rotate(-7deg)}"
    "55%{opacity:1;transform:translateY(-7px) rotate(1.6deg)}"
    "78%{transform:translateY(2px) rotate(-.5deg)}100%{opacity:1;transform:none}}",
    "@keyframes slide{from{opacity:0;transform:translateX(-18px)}to{opacity:1;transform:none}}",
    "@keyframes ring{0%{opacity:.55;transform:scale(.35)}100%{opacity:0;transform:scale(1.9)}}",
    "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}",
    "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-2.5px)}}",
    "@keyframes nudge{0%,70%,100%{transform:translateX(0)}80%{transform:translateX(3.5px)}}",
    "@keyframes twinkle{0%,100%{opacity:.85}50%{opacity:.35}}",
    "@keyframes show{to{opacity:1}}",
    "@keyframes hide{to{opacity:0}}",
]

BASE_CSS = (
    "text{dominant-baseline:auto}"
    ".fx{transform-box:fill-box}"
)

ANIM_CSS = (
    ".rise{opacity:0;animation:rise .62s cubic-bezier(.2,.8,.25,1) both}"
    ".fade{opacity:0;animation:fade .5s linear both}"
    ".pop{opacity:0;transform-box:fill-box;transform-origin:50% 50%;animation:pop .34s cubic-bezier(.3,1.4,.5,1) both}"
    ".grow{transform-box:fill-box;transform-origin:50% 100%;animation:grow .7s cubic-bezier(.18,.9,.3,1) both}"
    ".swing{opacity:0;transform-box:fill-box;transform-origin:50% 100%;animation:swing .95s cubic-bezier(.22,.92,.3,1) both}"
    ".slide{opacity:0;animation:slide .55s cubic-bezier(.2,.8,.25,1) both}"
    ".ring{transform-box:fill-box;transform-origin:50% 50%;animation:ring 1.1s ease-out both}"
    ".blink{animation:blink 1.06s steps(1,end) infinite}"
    ".bob{transform-box:fill-box;animation:bob 2.6s ease-in-out infinite}"
    ".nudge{transform-box:fill-box;animation:nudge 2.8s ease-in-out infinite}"
    ".twinkle{animation:twinkle 2.2s ease-in-out infinite}"
    ".cnt{opacity:0}"
)

REST_CSS = (
    "*{animation:none!important}"
    ".rise,.fade,.pop,.grow,.swing,.slide,.bob,.nudge,.twinkle{opacity:1!important;transform:none!important}"
    ".ring,.cnt,.shine{display:none!important}"
    ".cnt-end{display:inline!important;opacity:1!important}"
)


def delay(seconds: float, extra: str = "") -> str:
    return f"animation-delay:{seconds:.3f}s;{extra}"


# -------------------------------------------------------------- pixel art

def pixel_runs(path: Path, *, alpha_min: int = 24):
    """Read a PNG into (x, y, run_length, '#rrggbb', alpha) rows.

    Horizontal runs of one colour collapse into a single <rect>, which is what
    keeps a 48x48 sprite down to a few dozen nodes.
    """
    from PIL import Image

    img = Image.open(path).convert("RGBA")
    px = img.load()
    runs = []
    for y in range(img.height):
        x = 0
        while x < img.width:
            r, g, b, a = px[x, y]
            if a < alpha_min:
                x += 1
                continue
            run = 1
            while x + run < img.width and px[x + run, y] == (r, g, b, a):
                run += 1
            runs.append((x, y, run, f"#{r:02x}{g:02x}{b:02x}", a / 255))
            x += run
    return runs, img.width, img.height


def draw_sprite(card: Card, path: Path, x, y, scale, *, cls="", style="", opacity=1.0):
    """Blit a PNG as <rect> runs.

    The animated class goes on an outer <g> and the placement transform on an
    inner one: a CSS `transform` in a keyframe replaces the element's own
    transform attribute outright, which would drop the sprite at the origin.
    """
    runs, w, h = pixel_runs(path)
    card.add(f'<g class="{cls}" style="{style}" opacity="{opacity:g}">')
    card.add(
        f'<g transform="translate({x:g},{y:g}) scale({scale:g})" shape-rendering="crispEdges">'
    )
    for rx, ry, run, colour, alpha in runs:
        op = "" if alpha > 0.99 else f' opacity="{alpha:.2f}"'
        card.add(f'<rect x="{rx}" y="{ry}" width="{run}" height="1" fill="{colour}"{op}/>')
    card.add("</g></g>")
    return w * scale, h * scale


def count_up(card: Card, x, y, value: int, *, font="display", size=44, fill=BONE,
             anchor="middle", start=0.0, duration=0.72, frames=16, outline=EDGE):
    """A number that ticks up from zero.

    CSS cannot change text, so each intermediate value is its own <text> shown
    for a few milliseconds by a pair of zero-length animations.
    """
    if STATIC or value <= 0:
        card.text(x, y, f"{value:,}", font=font, size=size, fill=fill, anchor=anchor,
                  outline=outline, cls="cnt-end")
        return
    step = duration / frames
    for i in range(frames):
        shown = round(value * ((i + 1) / frames) ** 0.75)
        card.text(
            x, y, f"{shown:,}", font=font, size=size, fill=fill, anchor=anchor, outline=outline,
            cls="cnt",
            style=f"animation:show 1ms linear {start + i * step:.3f}s forwards,"
                  f"hide 1ms linear {start + (i + 1) * step:.3f}s forwards",
        )
    card.text(
        x, y, f"{value:,}", font=font, size=size, fill=fill, anchor=anchor, outline=outline,
        cls="cnt cnt-end",
        style=f"animation:show 1ms linear {start + duration:.3f}s forwards",
    )


def shine(card: Card, gid: str, x, y, w, base: str, hot: str, *, dur=4.4, begin=1.2):
    """A highlight that sweeps across a word, as an animated gradient fill."""
    card.define(
        f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
        f'x1="{x - w:g}" y1="{y}" x2="{x:g}" y2="{y}">'
        f'<stop offset="0" stop-color="{base}"/>'
        f'<stop offset=".42" stop-color="{base}"/>'
        f'<stop offset=".5" stop-color="{hot}"/>'
        f'<stop offset=".58" stop-color="{base}"/>'
        f'<stop offset="1" stop-color="{base}"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'from="0 0" to="{w * 2.2:g} 0" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
        "</linearGradient>"
    )


# ---------------------------------------------------------------- the data

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


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
    busiest = date.fromisoformat(busiest_iso)

    months: dict[str, int] = {}
    for iso in ordered:
        months.setdefault(iso[:7], 0)
        months[iso[:7]] += counts[iso]
    month_keys = sorted(months)[-12:]

    return {
        "cal": cal,
        "stats": stats,
        "days": days,
        "counts": counts,
        "levels": levels,
        "ordered": ordered,
        "total": cal["total"],
        "active": sum(1 for v in counts.values() if v > 0),
        "span": len(ordered),
        "current_streak": current,
        "longest_streak": longest,
        "last_active": date.fromisoformat(last_active),
        "busiest": busiest,
        "busiest_count": counts[busiest_iso],
        "months": [(k, months[k]) for k in month_keys],
        "best_month": max(month_keys, key=lambda k: months[k]),
    }


# ---------------------------------------------------------------- the cards

def card_hero(s: dict) -> None:
    h = 224
    c = Card("Rudraksha Singh Sengar - software engineer, Bangalore", W, h)
    c.panel(0, 0, W, h)

    # cave dust: a fixed scatter, no randomness so reruns stay byte-stable
    for i, (dx, dy, o) in enumerate([(612, 44, .5), (690, 74, .3), (786, 36, .45),
                                     (742, 122, .25), (648, 96, .3), (826, 162, .35)]):
        c.rect(dx, dy, 2, 2, MINT, opacity=o, cls="twinkle",
               style=delay(i * 0.4) if not STATIC else "")

    tx = 44
    name_size = 66
    c.text(tx, 96, "RUDRAKSHA", font="display", size=name_size, fill=BONE,
           outline=EDGE, spacing=2, cls="rise", style=delay(.12))

    surname = "SINGH SENGAR"
    sw = c.width_of("display", surname, name_size)
    shine(c, "goldshine", tx + sw, 152, sw, GOLD, "#fff4d2")
    c.text(tx, 152, surname, font="display", size=name_size, fill=GOLD,
           outline=EDGE, spacing=2, cls="rise", style=delay(.26))
    if not STATIC:
        c.text(tx, 152, surname, font="display", size=name_size, fill="url(#goldshine)",
               spacing=2, cls="rise shine", style=delay(.26))

    c.text(tx + 3, 182, "SOFTWARE ENGINEER", font="pixel", size=10, fill=CYAN,
           outline=EDGE, spacing=1.2, cls="rise", style=delay(.4))
    role_w = c.width_of("pixel", "SOFTWARE ENGINEER", 10) + 1.2 * len("SOFTWARE ENGINEER")
    c.text(tx + 3 + role_w + 20, 182, "BANGALORE",
           font="pixel", size=10, fill=MUTED, outline=EDGE, spacing=1.2,
           cls="rise", style=delay(.48))

    tagline = "I build for the web and contribute upstream."
    c.text(tx + 3, 206, tagline, font="mono", size=21, fill=BONE_DIM,
           cls="rise", style=delay(.56))
    cw = c.width_of("mono", tagline, 21)
    c.rect(tx + 9 + cw, 193, 9, 15, MINT, opacity=.8, cls="blink" if not STATIC else "")

    # HUD hearts, top right, exactly as the site renders them
    hx = W - 36
    for i in range(5):
        x = hx - (4 - i) * 26
        c.add(f'<g class="bob" style="{delay(i * .16)}">' if not STATIC else "<g>")
        draw_sprite(c, ASSETS / "sprites" / "heart.png", x - 18, 30, 1.1)
        c.add("</g>")

    link = "RUDRAKSHA.TECH  →"
    c.text(W - 36, 160, link, font="pixel", size=10, fill=GOLD, anchor="end",
           outline=EDGE, spacing=1.2, cls="nudge" if not STATIC else "",
           style=delay(1.1) if not STATIC else "")
    c.write("hero.svg")


def card_graph(s: dict) -> None:
    pitch, cell = 15, 12
    pad_left, top = 56, 72
    h = 208
    c = Card("Contribution map, last 12 months", W, h)
    c.panel(0, 0, W, h)

    c.text(24, 32, "CONTRIBUTION MAP", font="pixel", size=10, fill=GOLD,
           outline=EDGE, spacing=1.4, cls="rise", style=delay(.05))
    total = f"{s['total']:,} contributions in the last year"
    c.text(W - 26, 34, total, font="mono", size=21, fill=BONE_DIM, anchor="end",
           cls="rise", style=delay(.12))

    first = date.fromisoformat(s["ordered"][0])
    offset = (first.weekday() + 1) % 7  # GitHub weeks start on Sunday

    seen_month = None
    for idx, iso in enumerate(s["ordered"]):
        col = (idx + offset) // 7
        row = (idx + offset) % 7
        day = date.fromisoformat(iso)
        level = s["levels"][iso]  # GitHub's own bucketing, straight from the calendar
        x = pad_left + col * pitch
        y = top + row * pitch
        d = 0 if STATIC else 0.34 + col * 0.0125 + row * 0.012
        c.rect(x, y, cell, cell, LEVELS[level], cls="pop" if not STATIC else "",
               style=delay(d, "animation-duration:.3s") if not STATIC else "")
        if day.day <= 7 and seen_month != iso[:7]:
            seen_month = iso[:7]
            c.text(x, top - 12, MONTHS[day.month - 1].upper(), font="pixel", size=7,
                   fill=MUTED, cls="fade", style=delay(.2 + col * .01))

    for row, label in ((1, "MON"), (3, "WED"), (5, "FRI")):
        c.text(24, top + row * pitch + 10, label, font="pixel", size=7, fill=MUTED,
               cls="fade", style=delay(.3))

    lx = W - 26 - 5 * 15 - 72
    c.text(lx, top + 7 * pitch + 22, "LESS", font="pixel", size=7, fill=MUTED,
           cls="fade", style=delay(1.1))
    for i, colour in enumerate(LEVELS):
        c.rect(lx + 36 + i * 15, top + 7 * pitch + 12, cell, cell, colour,
               cls="fade", style=delay(1.15 + i * .04))
    c.text(W - 26, top + 7 * pitch + 22, "MORE", font="pixel", size=7, fill=MUTED,
           anchor="end", cls="fade", style=delay(1.35))
    c.write("graph.svg")


def card_activity(s: dict) -> None:
    h = 212
    c = Card("Contributions per month, streaks and busiest day", W, h)
    c.panel(0, 0, W, h)
    c.text(24, 32, "ACTIVITY LOG", font="pixel", size=10, fill=GOLD, outline=EDGE,
           spacing=1.4, cls="rise", style=delay(.05))

    months = s["months"]
    peak = max(v for _, v in months) or 1
    base_y, max_h = 166, 96
    bar_w, gap = 30, 14
    x0 = 36

    for i, (key, value) in enumerate(months):
        x = x0 + i * (bar_w + gap)
        bar_h = max(2, round(max_h * value / peak))
        best = key == s["best_month"]
        colour = MINT if best else "#28305c"
        c.rect(x, base_y - max_h, bar_w, max_h, "#0b0f21")  # the slot behind the bar
        c.rect(x, base_y - bar_h, bar_w, bar_h, colour,
               cls="grow" if not STATIC else "",
               style=delay(.5 + i * .055, "animation-duration:.65s") if not STATIC else "")
        if best:
            c.rect(x, base_y - bar_h, bar_w, 2, "#b6fff0")
            count_up(c, x + bar_w / 2, base_y - bar_h - 10, value, font="display", size=26,
                     fill=MINT, start=1.15, duration=.5, frames=12, outline=EDGE)
        month_label = MONTHS[int(key[5:]) - 1].upper()
        c.text(x + bar_w / 2, base_y + 18, month_label, font="pixel", size=7,
               fill=BONE_DIM if best else MUTED, anchor="middle",
               cls="fade", style=delay(.6 + i * .05))

    c.rect(x0, base_y + 2, 12 * (bar_w + gap) - gap, 1, "#2a3160")

    sx = 620
    c.rect(sx - 22, 46, 1, h - 92, "#1b2142")
    if s["current_streak"]:
        streak_row = ("CURRENT STREAK", f"{s['current_streak']} days", MINT)
    else:
        last = s["last_active"]
        streak_row = ("LAST ACTIVE", f"{last.day} {MONTHS[last.month - 1]}", BONE_DIM)
    rows = [
        streak_row,
        ("LONGEST STREAK", f"{s['longest_streak']} days", BONE),
        ("ACTIVE DAYS", f"{s['active']} / {s['span']}", BONE),
        ("BUSIEST DAY", f"{s['busiest_count']} on {s['busiest'].day} {MONTHS[s['busiest'].month - 1]}", BONE),
        ("MERGED PRS", f"{s['stats']['merged_prs']:,}", GOLD),
    ]
    for i, (label, value, colour) in enumerate(rows):
        y = 62 + i * 33
        c.text(sx, y, label, font="pixel", size=7, fill=MUTED, spacing=1.1,
               cls="slide", style=delay(.8 + i * .09))
        c.text(W - 26, y + 2, value, font="mono", size=23, fill=colour, anchor="end",
               cls="slide", style=delay(.86 + i * .09))
        c.rect(sx, y + 10, W - 26 - sx, 1, "#161b38", opacity=.9)
    c.write("activity.svg")


# Editorial values that no API knows about. Everything else is fetched.
BOSSES_DEFEATED = 6

TILES = [
    {
        "slot": "1",
        "label": "BUILD",
        "sub": "public repositories",
        "colour": ORANGE,
        "sprite": "pickaxe-mythril.png",
        "scale": 0.95,
        "value": lambda s: s["stats"]["public_repos"],
    },
    {
        "slot": "2",
        "label": "OPEN SOURCE",
        "sub": "merged pull requests",
        "colour": GREEN,
        "sprite": "gem-emerald.png",
        "scale": 1.9,
        "value": lambda s: s["stats"]["merged_prs"],
    },
    {
        "slot": "3",
        "label": "BOSSES",
        "sub": "hackathons, CTFs, firsts",
        "colour": PINK,
        "sprite": "sword-excalibur.png",
        "scale": 0.78,
        "value": lambda s: BOSSES_DEFEATED,
    },
]


def card_tile(s: dict, tile: dict, index: int) -> None:
    w, h = 286, 180
    c = Card(f"{tile['label']} - {tile['sub']}", w, h)
    swing_delay = 0.18 + index * 0.16
    c.add(f'<g class="swing" style="{delay(swing_delay)}">' if not STATIC else "<g>")
    c.panel(0, 0, w, h)

    c.text(10, 18, tile["slot"], font="pixel", size=8, fill=MUTED)

    sx, sy, ss = 18, 20, 48
    c.slot(sx, sy, ss)
    sprite = ASSETS / "sprites" / tile["sprite"]
    sw, sh = pixel_runs(sprite)[1:]
    scale = tile["scale"]
    draw_sprite(
        c, sprite,
        sx + (ss - sw * scale) / 2, sy + (ss - sh * scale) / 2, scale,
        cls="bob" if not STATIC else "", style=delay(swing_delay + .9) if not STATIC else "",
    )
    if not STATIC:
        c.add(
            f'<circle class="ring" cx="{sx + ss / 2:g}" cy="{sy + ss / 2:g}" r="{ss * .62:g}" '
            f'fill="none" stroke="{tile["colour"]}" stroke-width="2" '
            f'style="{delay(swing_delay + .45)}"/>'
        )

    c.text(sx + ss + 16, sy + 22, tile["label"], font="pixel", size=10, fill=tile["colour"],
           outline=EDGE, spacing=1.2)
    c.text(sx + ss + 16, sy + 42, c.fit("mono", tile["sub"], 18, w - sx - ss - 30),
           font="mono", size=18, fill=MUTED)

    c.rect(18, 104, w - 36, 1, "#1b2142")
    count_up(c, 20, 158, tile["value"](s), font="display", size=52, fill=BONE,
             anchor="start", start=swing_delay + .5, duration=.8, frames=18)
    c.text(w - 20, 152, "→", font="pixel", size=14, fill=tile["colour"], anchor="end",
           cls="nudge" if not STATIC else "",
           style=delay(swing_delay + 1.1) if not STATIC else "")
    c.add("</g>")
    c.write(f"tile-{tile['label'].split()[0].lower()}.svg")


ORG_COLOUR = {"CNCF": CYAN, "Containers": ORANGE, "Red Hat": PINK, "Flatcar": YELLOW}


def card_upstream(s: dict) -> None:
    rows = [u for u in s["stats"]["upstream"]][:5]
    h = 70 + len(rows) * 28 + 20
    c = Card("Merged pull requests in upstream projects", W, h)
    c.panel(0, 0, W, h)
    c.text(24, 32, "UPSTREAM", font="pixel", size=10, fill=GOLD, outline=EDGE,
           spacing=1.4, cls="rise", style=delay(.05))
    c.text(W - 26, 34, "pull requests in other people's repositories", font="mono",
           size=21, fill=MUTED, anchor="end", cls="rise", style=delay(.12))
    c.rect(24, 46, W - 48, 1, "#1b2142")

    peak = max((u["merged"] for u in rows), default=1) or 1
    for i, u in enumerate(rows):
        y = 70 + i * 28
        d = .35 + i * .1
        colour = ORG_COLOUR.get(u["org"], MUTED)
        c.text(24, y + 14, u["org"].upper(), font="pixel", size=7, fill=colour,
               cls="slide", style=delay(d))
        c.text(150, y + 16, u["label"], font="mono", size=22, fill=BONE,
               cls="slide", style=delay(d + .04))
        c.text(316, y + 16, c.fit("mono", u["repo"], 18, 212), font="mono", size=18,
               fill=MUTED, cls="slide", style=delay(d + .08))

        bar_x, bar_w = 542, 108
        c.rect(bar_x, y + 5, bar_w, 10, "#0b0f21")
        filled = max(3, round(bar_w * u["merged"] / peak))
        c.rect(bar_x, y + 5, filled, 10, MINT if u["merged"] else "#28305c",
               cls="grow" if not STATIC else "",
               style=delay(d + .1, "transform-origin:0 50%;animation-duration:.6s") if not STATIC else "")
        c.text(752, y + 16, f"{u['merged']} merged", font="mono", size=20,
               fill=BONE_DIM if u["merged"] else MUTED, anchor="end",
               cls="slide", style=delay(d + .14))
        if u["open"]:
            c.text(W - 26, y + 16, f"{u['open']} open", font="mono", size=20, fill=MUTED,
                   anchor="end", cls="slide", style=delay(d + .18))
    c.write("upstream.svg")


def wrap(font: str, text: str, size: float, max_width: float, lines: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        probe = f"{line} {word}".strip()
        if pf.width(font, probe, size) <= max_width:
            line = probe
        else:
            out.append(line)
            line = word
            if len(out) == lines:
                break
    if line and len(out) < lines:
        out.append(line)
    if len(out) == lines and words:
        joined = " ".join(out)
        remaining = text[len(joined):].strip()
        if remaining:
            out[-1] = pf.fit(font, out[-1] + " " + remaining, size, max_width)
    return out[:lines]


# GitHub has no description for these; this is the one the sibling repo carries.
DESCRIPTION_FALLBACK = {
    "pointblank-club/Kitten": "Resize your disk, pull the plug, the cat doesn't flinch.",
}


def card_repo(repo: dict, index: int) -> None:
    w, h = 286, 152
    c = Card(f"{repo['full_name']} - {repo['description'][:60]}", w, h)
    c.add(f'<g class="slide" style="{delay(.25 + index * .14)}">' if not STATIC else "<g>")
    c.panel(0, 0, w, h)

    lang_colour = LANG_COLOR.get(repo["language"], LANG_COLOR[""])
    c.slot(16, 18, 42)
    cx, cy = 37, 39
    c.add(f'<g class="bob" style="{delay(.95 + index * .14)}">' if not STATIC else "<g>")
    c.add(f'<g transform="translate({cx},{cy})">')
    c.add(f'<rect x="-9" y="-9" width="18" height="18" fill="{lang_colour}" transform="rotate(45)"/>')
    c.add('<rect x="-9" y="-9" width="18" height="5" fill="#ffffff" opacity=".28" transform="rotate(45)"/>')
    c.add("</g></g>")

    owner, _, name = repo["full_name"].partition("/")
    c.text(70, 34, c.fit("pixel", name, 10, w - 92), font="pixel", size=10, fill=BONE,
           outline=EDGE)
    c.text(70, 52, owner, font="mono", size=17, fill=MUTED)

    desc = repo["description"] or DESCRIPTION_FALLBACK.get(repo["full_name"], "")
    for i, line in enumerate(wrap("mono", desc, 18, w - 36, 3)):
        c.text(18, 86 + i * 18, line, font="mono", size=18, fill=BONE_DIM)

    foot = []
    x = 18
    if repo["stars"]:
        c.text(x, 144, "★", font="pixel", size=9, fill=GOLD)
        x += 16
        foot.append(f"{repo['stars']}")
    if repo["language"]:
        foot.append(repo["language"])
    if repo["merged_prs"]:
        foot.append(f"{repo['merged_prs']} merged")
    c.rect(18, 126, w - 36, 1, "#1b2142")
    c.text(x, 144, "  ·  ".join(foot), font="mono", size=17, fill=MUTED)
    c.add("</g>")
    c.write(f"repo-{index + 1}.svg")


def main() -> None:
    s = load_stats()
    mode = "static" if STATIC else "animated"
    print(f"rendering cards ({mode}) from data fetched {s['cal']['fetched_at']}")
    card_hero(s)
    card_graph(s)
    card_activity(s)
    for i, tile in enumerate(TILES):
        card_tile(s, tile, i)
    card_upstream(s)
    for i, repo in enumerate(s["stats"]["repos"][:3]):
        card_repo(repo, i)
    total = sum(p.stat().st_size for p in CARDS.glob("*.svg")) / 1024
    print(f"  {'total':<22} {total:6.1f} KB")


if __name__ == "__main__":
    main()
