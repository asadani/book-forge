# -*- coding: utf-8 -*-
"""Headless Chrome render, then folio stamping with PyMuPDF.

Chrome is driven directly rather than through Playwright/Puppeteer -- one fewer
dependency, and the flags below are the ones that make print output
deterministic. Page numbers are painted onto the PDF afterwards; they exist in
the PDF only, never in the HTML.
"""
import os
import shutil
import subprocess
import tempfile

from .errors import RenderError
from .paths import find_chrome, resolve_font


def render(html_path, chrome=None, budget_ms=30000, timeout_s=300, quiet=False):
    """HTML -> raw PDF via headless Chrome. Returns the temp PDF path."""
    exe = find_chrome(chrome)
    raw = os.path.join(tempfile.gettempdir(),
                       "bf-raw-%s.pdf" % os.path.basename(html_path).replace(".", "-"))
    if os.path.exists(raw):
        os.remove(raw)
    profile = tempfile.mkdtemp(prefix="bf-chrome-")
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    cmd = [
        exe, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=%d" % budget_ms,
        "--user-data-dir=" + profile,
        "--print-to-pdf=" + raw,
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(raw):
        raise RenderError("chrome produced no pdf\nstdout:%s\nstderr:%s"
                          % (r.stdout[-1500:], r.stderr[-1500:]))
    if not quiet:
        print("  chrome rendered %d KB" % (os.path.getsize(raw) // 1024))
    return raw


def stamp(raw, dst, folio, quiet=False):
    """Paint folios and save. Returns (written_path, page_count)."""
    import fitz

    doc = fitz.open(raw)
    n = doc.page_count
    ttf = resolve_font(folio.get("font", "IBMPlexMono-Regular.ttf"))
    skip = set(int(p) for p in folio.get("skip_pages", [1]))
    first = int(folio.get("first_number", 1))
    size = float(folio.get("size", 8))
    color = tuple(folio.get("color", [0.49, 0.52, 0.58]))

    for i, page in enumerate(doc):
        if (i + 1) in skip:
            continue
        w, h = page.rect.width, page.rect.height
        page.insert_text(
            (w / 2.0 - 12, h - 30),
            "%d" % (i + first),
            fontsize=size,
            fontfile=ttf,
            fontname="PlexMono",
            color=color,
        )
    doc.subset_fonts()

    # Write beside the target first, then swap. A PDF held open by a viewer
    # cannot be replaced on Windows; that should not fail the whole build.
    staged = dst + ".staged"
    doc.save(staged, garbage=4, deflate=True)
    doc.close()
    out = dst
    try:
        os.replace(staged, dst)
    except PermissionError:
        out = dst.replace(".pdf", ".new.pdf")
        os.replace(staged, out)
        print("  NOTE   %s is open in a viewer; wrote %s instead"
              % (os.path.basename(dst), os.path.basename(out)))
    if not quiet:
        print("  pdf    %s, %d pages, %d KB"
              % (os.path.basename(out), n, os.path.getsize(out) // 1024))
    return out, n
