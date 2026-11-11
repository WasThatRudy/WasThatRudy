"""Font helpers: subset to the glyphs a card prints, embed as WOFF, measure text.

Each face is declared under a short family name of our own. The name a font
carries internally is irrelevant once @font-face names it explicitly, and short
ASCII-only names avoid the CSS rule that a family whose last token starts with
a digit has to be quoted wherever it is used.
"""
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
    "display": ("ITightSemi", "InterTight-SemiBold.ttf"),
    "sans": ("ITight", "InterTight-Regular.ttf"),
    "mono": ("JBMono", "JetBrainsMono-Regular.ttf"),
    "monomd": ("JBMonoMed", "JetBrainsMono-Medium.ttf"),
}

CHARSET = "".join(chr(c) for c in range(0x20, 0x7F)) + "·—–’“”…→★"


@lru_cache(maxsize=None)
def _ttf(key: str) -> TTFont:
    return TTFont(FONT_DIR / FONTS[key][1])


@lru_cache(maxsize=None)
def family(key: str) -> str:
    return FONTS[key][0]


@lru_cache(maxsize=None)
def _subset_woff(key: str, chars: str) -> str:
    font = TTFont(FONT_DIR / FONTS[key][1])
    options = subset.Options()
    options.flavor = "woff"
    options.notdef_outline = True
    # Keep the subsetter defaults for everything else. Retaining layout
    # features ("*") can leave GSUB/GDEF pointing at dropped glyphs, and a
    # browser then refuses the whole face without reporting anything.
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

    Subsetting per card rather than per font is what keeps each SVG small.
    """
    chars = "".join(sorted(set(chars) | set(" ")))
    return (
        "@font-face{font-family:%s;font-style:normal;font-weight:400;"
        "src:url(data:font/woff;base64,%s) format('woff')}"
        % (family(key), _subset_woff(key, chars))
    )


@lru_cache(maxsize=None)
def _metrics(key: str):
    font = _ttf(key)
    return font["head"].unitsPerEm, font.getBestCmap(), font["hmtx"]


def width(key: str, text: str, size: float, spacing: float = 0.0) -> float:
    """Advance width of `text` at `size` px, in px."""
    upm, cmap, hmtx = _metrics(key)
    total = 0
    for ch in text:
        name = cmap.get(ord(ch)) or cmap.get(ord("?"))
        if name is not None:
            total += hmtx[name][0]
    return total * size / upm + spacing * max(0, len(text) - 1)


def fit(key: str, text: str, size: float, max_width: float, ellipsis: str = "…") -> str:
    """Truncate `text` so it fits `max_width` at `size`."""
    if width(key, text, size) <= max_width:
        return text
    out = text
    while out and width(key, out + ellipsis, size) > max_width:
        out = out[:-1]
    return out.rstrip(" ,.;:-") + ellipsis
