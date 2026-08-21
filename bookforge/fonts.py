# -*- coding: utf-8 -*-
"""Static font instances, inlined as base64 @font-face rules.

Chrome degrades variable fonts to Type 3 when printing, which is unusable for
print -- so the variable masters are flattened to static woff2 once, and the
statics are what get embedded. ``cut()`` regenerates them; ``face_css()`` inlines
whatever is already there.
"""
import base64
import os
import sys

from .errors import MissingAssetError
from .paths import forge_asset, resolve_font

RAW = "https://raw.githubusercontent.com/google/fonts/main/ofl/%s"


def face_css(faces, quiet=False):
    """Build the @font-face block for the theme's faces."""
    out, total = [], 0
    for family, weight, filename in faces:
        path = resolve_font(filename)
        with open(path, "rb") as fh:
            blob = fh.read()
        total += len(blob)
        b64 = base64.b64encode(blob).decode("ascii")
        out.append(
            '@font-face{font-family:"%s";font-style:normal;font-weight:%d;'
            'font-display:block;src:url(data:font/woff2;base64,%s) format("woff2")}'
            % (family, weight, b64))
    if not quiet:
        print("  fonts  %d faces inlined, %d KB raw" % (len(faces), total // 1024))
    return "\n".join(out)


def cut(manifest=None):
    """Flatten the variable masters into the static woff2 instances.

    Only needed when adding a face or refreshing upstream; the cut faces are
    committed, so an ordinary build never touches the network.
    """
    import urllib.parse
    import urllib.request

    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    import yaml
    manifest = manifest or forge_asset("fonts", "manifest.yaml")
    with open(manifest, "rb") as fh:
        spec = yaml.safe_load(fh) or {}

    out_dir = forge_asset("fonts")
    made = []

    for job in spec.get("variable", []):
        varfile = job["file"]
        cache = os.path.join(
            out_dir, "_var_" + varfile.replace("[", "_").replace("]", "_"))
        if not os.path.exists(cache):
            url = RAW % (job["family_dir"] + "/" + urllib.parse.quote(varfile))
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90).read()
            with open(cache, "wb") as fh:
                fh.write(data)
            print("  fetched %-34s %d KB" % (varfile, len(data) // 1024))
        for inst in job["instances"]:
            font = TTFont(cache)
            static = instancer.instantiateVariableFont(
                font, inst["pin"], inplace=False, updateFontNames=True)
            dst = os.path.join(out_dir, inst["name"] + ".woff2")
            static.flavor = "woff2"
            static.save(dst)
            static.close()
            font.close()
            made.append(dst)
            print("  cut   %-28s %d KB" % (inst["name"] + ".woff2", os.path.getsize(dst) // 1024))

    for name in spec.get("static", []):
        src = os.path.join(out_dir, name + ".ttf")
        dst = os.path.join(out_dir, name + ".woff2")
        if os.path.exists(src) and not os.path.exists(dst):
            f = TTFont(src)
            f.flavor = "woff2"
            f.save(dst)
            f.close()
            made.append(dst)
            print("  conv  %-28s %d KB" % (name + ".woff2", os.path.getsize(dst) // 1024))

    if not made:
        print("  fonts  already cut; nothing to do")
    return made
