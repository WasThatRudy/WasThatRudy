"""Font helpers: subset to a small charset, embed as base64 WOFF, measure text."""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "fonts"

FONTS = {
    "display": ("Jersey 25", "Jersey25-Regular.ttf"),
    "pixel": ("Press Start 2P", "PressStart2P-Regular.ttf"),
    "mono": ("VT323", "VT323-Regular.ttf"),
}

# Printable ASCII plus the handful of symbols the cards actually draw.
CHARSET = "".join(chr(c) for c in range(0x20, 0x7F)) + "→←↑↓·•×★☆—–’‘“”…≈"


@lru_cache(maxsize=None)
def _ttf(key: str) -> TTFont:
    return TTFont(FONT_DIR / FONTS[key][1])


@lru_cache(maxsize=None)
def family(key: str) -> str:
    return FONTS[key][0]


@lru_cache(maxsize=None)
def _subset_woff(key: str, chars: str) -> str:
    """Subset the font to `chars` and return it base64-encoded as WOFF."""
    font = TTFont(FONT_DIR / FONTS[key][1])
    options = subset.Options()
    options.flavor = "woff"
    options.notdef_outline = True
    # Keep the defaults for everything else. Retaining layout features
    # ("*") leaves Jersey 25 with GSUB/GDEF tables that point at dropped
    # glyphs, and Chrome quietly refuses the whole face.
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=chars)
    subsetter.subset(font)
    buf = io.BytesIO()
    font.flavorData = None
    font.save(buf)
    font.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")


def face(key: str, chars: str = CHARSET) -> str:
    """An @font-face rule carrying only `chars`, inlined as a data URI.

    Subsetting per card rather than per font is what keeps each SVG small:
    a card that only prints uppercase and digits ships a ~15 KB face instead
    of a ~50 KB one.
    """
    name = family(key)
    chars = "".join(sorted(set(chars) | set(" ")))
    return (
        "@font-face{font-family:'%s';font-style:normal;font-weight:400;"
        "src:url(data:font/woff;base64,%s) format('woff')}" % (name, _subset_woff(key, chars))
    )


@lru_cache(maxsize=None)
def _metrics(key: str):
    font = _ttf(key)
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    return upm, cmap, hmtx


def width(key: str, text: str, size: float) -> float:
    """Advance width of `text` at `size` px, in px."""
    upm, cmap, hmtx = _metrics(key)
    total = 0
    for ch in text:
        name = cmap.get(ord(ch)) or cmap.get(ord("?"))
        if name is None:
            continue
        total += hmtx[name][0]
    return total * size / upm


def fit(key: str, text: str, size: float, max_width: float, ellipsis: str = "…") -> str:
    """Truncate `text` so it fits `max_width` at `size`."""
    if width(key, text, size) <= max_width:
        return text
    out = text
    while out and width(key, out + ellipsis, size) > max_width:
        out = out[:-1]
    return out.rstrip(" ,.;:-") + ellipsis
