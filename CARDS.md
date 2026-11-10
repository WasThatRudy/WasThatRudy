# How the cards are made

A GitHub README can't run JavaScript or load a stylesheet. What it *can* do is
show an `<img>`, and an SVG behind an `<img>` keeps its own `<style>` block —
so every block of my profile is an animated SVG, drawn by one Python script
from my real contribution data, and redrawn every morning by a GitHub Action.

## What survives in a README

GitHub strips scripts, styles and most attributes from README HTML. `<img>`,
`<a>`, `<picture>`, `width` and `align` survive. So the layout lives in the
markdown and everything visual lives inside the images:

```html
<a href="..."><img src="./cards/tile-build.svg" width="32.5%" /></a>
<a href="..."><img src="./cards/tile-open.svg"  width="32.5%" /></a>
<a href="..."><img src="./cards/tile-bosses.svg" width="32.5%" /></a>
```

Three images at 32.5% sit in a row with a gap, and each one is its own link.
An SVG shown through `<img>` is sandboxed: no scripts, no external requests.
Its own CSS keyframes still run.

## Fonts

An SVG in an `<img>` can't reach Google Fonts, so each font is subset to the
characters that card actually prints and inlined as a base64 WOFF. Subsetting
per card rather than per font is what keeps a card around 30 KB instead of
100 KB.

Two things cost me a render:

* Keeping all layout features (`options.layout_features = ["*"]`) left Jersey 25
  with GSUB/GDEF tables pointing at dropped glyphs. Chrome refuses the whole
  face in silence and falls back to a serif.
* `font-family="Jersey 25"` is discarded, because a CSS family name whose last
  token starts with a digit has to be quoted. The attribute needs its own
  quotes: `font-family="&apos;Jersey 25&apos;"`.

Both failures look identical from the outside: your text renders, in the wrong
font, with no error anywhere.

## The animations

Everything is CSS keyframes, staggered so the page plays top to bottom: the
hero, the contribution map, the monthly bars, the three tiles, then the repos.

* The name rises a line at a time, and a gold shine sweeps across the surname
  every few seconds. The shine is a gradient fill whose `gradientTransform` is
  animated with SMIL, because `background-clip: text` doesn't exist in SVG.
* The map pops in square by square, sweeping left to right.
* The bars grow from the baseline (`transform-box: fill-box` with
  `transform-origin: 50% 100%`), then the best month's number counts up.
* The tiles swing up from below, tilted, overshoot and settle. A ring pulses
  out of the item slot and the arrow nudges.
* Counting a number up takes one `<text>` element per value, each shown for a
  few milliseconds by a pair of zero-length animations, because CSS can't
  change text. Keeping it in CSS rather than SMIL means
  `prefers-reduced-motion` can switch it off.

All of it switches off under `prefers-reduced-motion`.

## Refreshed every morning

`scripts/fetch_github_data.py` scrapes my contribution calendar and asks the
REST API for repo and pull-request counts, into `data/`. Every search is pinned
to `is:public` so a run with my token and a run inside Actions produce the same
numbers. `scripts/render_readme_cards.py` reads those files and redraws every
card. The Action runs both and commits the SVGs back.

To check a layout without waiting for animations, the renderer has a `STATIC=1`
mode that draws every card at its end state:

```bash
pip install fonttools pillow
python scripts/fetch_github_data.py
STATIC=1 python scripts/render_readme_cards.py
python scripts/preview.py   # writes preview.html, open it or screenshot it
```
