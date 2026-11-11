#!/usr/bin/env python3
"""Lay the cards out the way the README does, for a headless screenshot."""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
rows = [
    ['<img src="cards/hero.svg" width="100%"/>'],
    ['<img src="cards/graph.svg" width="100%"/>'],
    ['<img src="cards/activity.svg" width="100%"/>'],
    ['<img src="cards/tile-1.svg" width="32.5%"/>',
     '<img src="cards/tile-2.svg" width="32.5%"/>',
     '<img src="cards/tile-3.svg" width="32.5%"/>'],
    ['<img src="cards/upstream.svg" width="100%"/>'],
    ['<img src="cards/repo-1.svg" width="32.5%"/>',
     '<img src="cards/repo-2.svg" width="32.5%"/>',
     '<img src="cards/repo-3.svg" width="32.5%"/>'],
]
body = "\n".join(f'<p>{" ".join(r)}</p>' for r in rows)
(ROOT / "preview.html").write_text(
    "<!doctype html><meta charset=utf-8>"
    "<style>body{background:#0d1117;margin:0;padding:24px;width:880px}"
    "p{margin:0 0 16px;display:flex;gap:1.5%;line-height:0}img{display:block}</style>"
    f"{body}"
)
print("wrote preview.html")
