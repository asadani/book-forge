# -*- coding: utf-8 -*-
"""Fit cover art to a full-bleed page.

The reference script only did one thing: fill by width and trim the excess
height. That works for 2:3 art on A4 and hard-fails on anything shorter --
which is three of the seven books (a 1.33, a 1.25, and a square 1.00). So the
fit is a mode:

    crop     fill the page, trim the overflow asymmetrically (the original)
    contain  fit the whole artwork inside the page, pad with `matte`
    matte    like contain, but sample the pad colour from the art's border
"""
import os

from PIL import Image

from .errors import ConfigError, MissingAssetError

MM_PER_IN = 25.4
PAGE_MM = {"A4": (210.0, 297.0), "Letter": (215.9, 279.4)}


def _page_px(size, dpi):
    if size not in PAGE_MM:
        raise ConfigError("unknown page size %r" % size)
    w_mm, h_mm = PAGE_MM[size]
    return (int(round(w_mm / MM_PER_IN * dpi)), int(round(h_mm / MM_PER_IN * dpi)))


def _border_colour(im, band=8):
    """Median colour of the art's outer band -- the pad that reads as intentional."""
    w, h = im.size
    px = []
    for x in range(0, w, max(1, w // 64)):
        px.append(im.getpixel((x, 0)))
        px.append(im.getpixel((x, h - 1)))
    for y in range(0, h, max(1, h // 64)):
        px.append(im.getpixel((0, y)))
        px.append(im.getpixel((w - 1, y)))
    chans = list(zip(*px))
    return tuple(sorted(c)[len(c) // 2] for c in chans)


def render(art_path, dst, page="A4", dpi=300, fit="crop",
           trim_top_share=0.47, matte=None, quiet=False):
    if not os.path.exists(art_path):
        raise MissingAssetError("cover art not found: %s" % art_path)

    pw, ph = _page_px(page, dpi)
    im = Image.open(art_path).convert("RGB")
    iw, ih = im.size

    if fit == "crop":
        scale = pw / float(iw)
        new_h = int(round(ih * scale))
        if new_h < ph:
            raise ConfigError(
                "cover.fit is 'crop' but the art is shorter than the page "
                "(%dx%d scales to %dx%d, page is %dx%d).\n"
                "  Use fit: contain or fit: matte for this cover."
                % (iw, ih, pw, new_h, pw, ph))
        im = im.resize((pw, new_h), Image.LANCZOS)
        excess = new_h - ph
        top = int(round(excess * trim_top_share))
        im = im.crop((0, top, pw, top + ph))
        note = "trimmed %dpx top / %dpx bottom" % (top, excess - top)

    elif fit in ("contain", "matte"):
        scale = min(pw / float(iw), ph / float(ih))
        nw, nh = int(round(iw * scale)), int(round(ih * scale))
        art = im.resize((nw, nh), Image.LANCZOS)
        if fit == "matte":
            pad = _border_colour(im)
        else:
            pad = tuple(matte) if matte else (255, 255, 255)
        canvas = Image.new("RGB", (pw, ph), pad)
        canvas.paste(art, ((pw - nw) // 2, (ph - nh) // 2))
        im = canvas
        note = "padded %dpx x / %dpx y, matte rgb%s" % ((pw - nw) // 2, (ph - nh) // 2, pad)
    else:
        raise ConfigError("unknown cover.fit: %r" % fit)

    parent = os.path.dirname(dst)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    im.save(dst, "JPEG", quality=92, optimize=True, progressive=True, dpi=(dpi, dpi))
    if not quiet:
        print("  cover  %dx%d px (%s @ %ddpi), fit=%s, %s, %d KB"
              % (pw, ph, page, dpi, fit, note, os.path.getsize(dst) // 1024))
    return dst
