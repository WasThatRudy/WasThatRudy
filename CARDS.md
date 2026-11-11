# How the cards are made

A GitHub README can't run JavaScript or load a stylesheet. What it *can* do is
show an `<img>`, and an SVG behind an `<img>` keeps its own `<style>` block —
so every block of this profile is an SVG drawn by one Python script from real
contribution and pull-request data, redrawn each morning by a GitHub Action.

## What survives in a README

GitHub strips scripts, styles and most attributes from README HTML. `<img>`,
`<a>`, `<picture>`, `width` and `align` survive. So the layout lives in the
markdown and everything visual lives inside the images:

```html
<a href="...">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./cards/tile-1.svg" />
    <img src="./cards/light/tile-1.svg" width="32.5%" alt="Public repositories" />
  </picture>
</a>
```

Three images at 32.5% sit in a row with a gap, and each one is its own link.
An SVG shown through `<img>` is sandboxed: no scripts, no external requests.
Its own CSS keyframes still run.

Every card is rendered twice, once per theme, and `<picture>` picks one — so a
light-mode profile doesn't get dark blocks on a white page. `THEME=light`
selects the palette; the light cards land in `cards/light/`.

## Fonts

An SVG in an `<img>` can't reach Google Fonts, so Inter Tight and JetBrains
Mono are subset to the characters each card actually prints and inlined as
base64 WOFF. Subsetting per card rather than per font keeps a card around
10–30 KB instead of 100 KB.

Two things cost me a render, and both fail the same way — the text renders, in
a fallback serif, with no error reported anywhere:

* Retaining all layout features (`options.layout_features = ["*"]`) can leave a
  subset font with GSUB/GDEF tables pointing at dropped glyphs, and the browser
  refuses the whole face. The subsetter defaults are what you want.
* A CSS family name whose last token starts with a digit is parsed as a number
  and discarded, so `font-family="Jersey 25"` silently does nothing. Each face
  here is therefore declared under a short ASCII name of its own (`ITightSemi`,
  `JBMono`); what a font calls itself internally doesn't matter once
  `@font-face` names it explicitly.

One more, specific to SVG: a `transform` in a CSS keyframe *replaces* the
element's `transform` attribute rather than composing with it. Anything
positioned by attribute and animated by class needs two nested `<g>`s.

## The animations

Everything is CSS keyframes, staggered so the page plays top to bottom: the
hero, the contribution graph, the monthly bars, the three figures, then the
repositories. Nothing loops — the cards settle within about two seconds and
then hold still.

Counting a number up takes one `<text>` element per value, each shown for a few
milliseconds by a pair of zero-length animations, because CSS can't change
text. Keeping it in CSS rather than SMIL is what lets
`prefers-reduced-motion` switch it off, which it does for every animation here.

## Refreshed every morning

`scripts/fetch_github_data.py` scrapes the contribution calendar and asks the
REST API for repository and pull-request counts, into `data/`. Every search is
pinned to `is:public` so a run with a personal token and a run inside Actions
produce the same numbers. `scripts/render_readme_cards.py` reads those files
and redraws every card. The Action runs both and commits the SVGs back.

To check a layout without waiting for animations, the renderer has a `STATIC=1`
mode that draws every card at its end state:

```bash
pip install -r requirements.txt
python scripts/fetch_github_data.py
STATIC=1 python scripts/render_readme_cards.py
STATIC=1 THEME=light python scripts/render_readme_cards.py
python scripts/preview.py              # writes preview.html for the dark cards
THEME=light python scripts/preview.py  # ... and for the light ones
```
