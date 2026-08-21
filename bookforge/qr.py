# -*- coding: utf-8 -*-
"""Inline SVG QR codes.

Vector, so they stay crisp at any print size and cost a couple of KB rather than
a raster's hundreds. Error correction is high enough that the codes still scan
from a folded or poorly lit page.

Unlike the reference script these are returned as strings rather than written to
``assets/*.svg`` and read back, and any ids they carry are namespaced per book:
two of the host documents we inject into already define ``<marker id="arw">``.
"""
import io
import re

import segno


def _namespace_ids(svg, prefix):
    """Rewrite id="x" -> id="<prefix>-x" and every url(#x) that refers to it."""
    ids = set(re.findall(r'\sid="([^"]+)"', svg))
    for i in sorted(ids, key=len, reverse=True):
        new = "%s-%s" % (prefix, i)
        svg = svg.replace(' id="%s"' % i, ' id="%s"' % new)
        svg = svg.replace("url(#%s)" % i, "url(#%s)" % new)
        svg = svg.replace('href="#%s"' % i, 'href="#%s"' % new)
    return svg


def make(target, dark="#161A21", error="h", ns=None, label=None):
    """Return a self-contained, container-scaled SVG string for `target`."""
    qr = segno.make(target, error=error)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=1, border=0, dark=dark,
            svgclass=None, lineclass=None, xmldecl=False, svgns=True)
    svg = buf.getvalue().decode("utf-8").strip()

    # Scale to the container instead of carrying fixed pixel dimensions.
    svg = re.sub(r'\swidth="[^"]*"', "", svg, count=1)
    svg = re.sub(r'\sheight="[^"]*"', "", svg, count=1)
    size = qr.symbol_size(scale=1, border=0)[0]
    if "viewBox" not in svg:
        svg = svg.replace(
            "<svg",
            '<svg viewBox="0 0 %d %d" preserveAspectRatio="xMidYMid meet"' % (size, size),
            1)

    attrs = ['class="bf-qr"', 'role="img"',
             'aria-label="%s"' % (label or ("QR code for %s" % target)),
             'shape-rendering="crispEdges"']
    svg = svg.replace("<svg", "<svg " + " ".join(attrs), 1)

    if ns:
        svg = _namespace_ids(svg, "bf-" + ns)
    return svg


def modules(target, error="h"):
    """Module count, for reporting."""
    return segno.make(target, error=error).symbol_size(scale=1, border=0)[0]
