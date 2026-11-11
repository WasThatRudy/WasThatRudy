#!/usr/bin/env python3
"""Lay the cards out the way the README does, for a headless screenshot."""
import os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
THEME = os.environ.get("THEME", "dark")
PREFIX = "cards/" if THEME == "dark" else f"cards/{THEME}/"
rows = [
    [f'<img src="{PREFIX}hero.svg" width="100%"/>'],
    [f'<img src="{PREFIX}graph.svg" width="100%"/>'],
    [f'<img src="{PREFIX}activity.svg" width="100%"/>'],
    [f'<img src="{PREFIX}tile-1.svg" width="32.5%"/>',
     f'<img src="{PREFIX}tile-2.svg" width="32.5%"/>',
     f'<img src="{PREFIX}tile-3.svg" width="32.5%"/>'],
    [f'<img src="{PREFIX}upstream.svg" width="100%"/>'],
    [f'<img src="{PREFIX}repo-1.svg" width="32.5%"/>',
     f'<img src="{PREFIX}repo-2.svg" width="32.5%"/>',
     f'<img src="{PREFIX}repo-3.svg" width="32.5%"/>'],
]
body = "\n".join(f'<p>{" ".join(r)}</p>' for r in rows)
(ROOT / "preview.html").write_text(
    "<!doctype html><meta charset=utf-8>"
    "<style>body{background:%s;" % ("#0d1117" if THEME=="dark" else "#ffffff") + "margin:0;padding:24px;width:880px}"
    "p{margin:0 0 16px;display:flex;gap:1.5%;line-height:0}img{display:block}</style>"
    f"{body}"
)
print("wrote preview.html")
