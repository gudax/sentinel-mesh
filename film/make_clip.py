#!/usr/bin/env python3
"""Record the playground clip (Exhibit P) against the LIVE Cloud Run service.

Sequence (the closed loop, live): an accepted claim is written back as session
ground truth; its contradiction is then VETOED. Output:
film/assets/playground-clip.webm (1660x860).
"""
import pathlib
import shutil
import sys
import time

from playwright.sync_api import sync_playwright

URL = "https://sentinel-playground-675241948019.asia-northeast1.run.app"
OUT = pathlib.Path(__file__).resolve().parent / "assets"
SIZE = {"width": 1660, "height": 860}

CLAIMS = [
    ("Dana Park is the sole owner of Meridian Dynamics.", "accept"),
    ("Jun Seo is the sole owner of Meridian Dynamics.", "veto"),
]


def type_slow(pg, sel, text, delay=22):
    pg.fill(sel, "")
    pg.click(sel)
    pg.type(sel, text, delay=delay)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport=SIZE, record_video_dir=str(OUT / "_clipraw"),
                        record_video_size=SIZE)
    pg = ctx.new_page()
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1800)
    for claim, expected in CLAIMS:
        type_slow(pg, "#claim", claim)
        pg.wait_for_timeout(350)
        pg.click("#go")
        pg.wait_for_function(
            "(()=>{const s=document.querySelector('#stamp');"
            "return s && /\\b(accept|veto|flag)\\b/.test(s.className) "
            "&& !document.querySelector('#go').disabled;})()",
            timeout=60000)
        cls = pg.get_attribute("#stamp", "class") or ""
        got = next((v for v in ("accept", "veto", "flag") if v in cls), cls)
        print(f"{claim[:50]!r} -> {got} (expected {expected})", flush=True)
        assert got == expected, f"clip take broken: {got} != {expected}"
        pg.wait_for_timeout(2600)
    pg.wait_for_timeout(1200)
    video = pg.video
    ctx.close()
    path = pathlib.Path(video.path())
    dest = OUT / "playground-clip.webm"
    shutil.move(path, dest)
    shutil.rmtree(OUT / "_clipraw", ignore_errors=True)
    b.close()
    print("clip saved:", dest)
