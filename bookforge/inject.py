# -*- coding: utf-8 -*-
"""Marker-delimited, idempotent injection into a hand-authored manuscript.

    <!-- BOOK-FORGE:ABOUT v1 sha=8c1f0a2b3d4e -->
      ...generated...
    <!-- /BOOK-FORGE:ABOUT -->

Everything outside a marker pair is preserved byte for byte. Running twice is a
no-op: the sha in the opening marker is the hash of the rendered block, so
`--check` can answer "is this book's matter current?" without writing anything.

Markers rather than a DOM rewrite on purpose. These are hand-authored files
whose indentation and comment banners matter, and lxml/bs4 would reformat every
line of a 1,500-line manuscript.
"""
import hashlib
import re

from .errors import ConfigError

OPEN_RE = "<!--\\s*BOOK-FORGE:%s\\b[^>]*-->"
CLOSE_RE = "<!--\\s*/BOOK-FORGE:%s\\s*-->"

UNCHANGED, UPDATED, INSERTED = "unchanged", "updated", "inserted"


def digest(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def wrap(name, body):
    return ("<!-- BOOK-FORGE:%s v1 sha=%s -->\n%s\n<!-- /BOOK-FORGE:%s -->"
            % (name, digest(body), body, name))


def _region(name):
    return re.compile(OPEN_RE % name + r".*?" + CLOSE_RE % name, re.S)


def integrity(text, names):
    """Marker pairs must be balanced and unique. Returns a list of problems."""
    out = []
    for name in names:
        opens = len(re.findall(OPEN_RE % name, text))
        closes = len(re.findall(CLOSE_RE % name, text))
        if opens != closes:
            out.append("marker %s: %d open, %d close" % (name, opens, closes))
        elif opens > 1:
            out.append("marker %s appears %d times; expected at most 1" % (name, opens))
    return out


def apply(text, name, body, anchor_before=None, anchor_after=None):
    """Replace the named region, or insert it at an anchor. Returns (text, status)."""
    block = wrap(name, body)
    rx = _region(name)
    found = rx.search(text)
    if found:
        if found.group(0) == block:
            return text, UNCHANGED
        return text[:found.start()] + block + text[found.end():], UPDATED

    if anchor_before:
        idx = text.find(anchor_before)
        if idx < 0:
            raise ConfigError(_anchor_help(name, "anchor_before", anchor_before, text))
        return text[:idx] + block + "\n\n" + text[idx:], INSERTED

    if anchor_after:
        idx = text.find(anchor_after)
        if idx < 0:
            raise ConfigError(_anchor_help(name, "anchor_after", anchor_after, text))
        end = idx + len(anchor_after)
        return text[:end] + "\n\n" + block + text[end:], INSERTED

    raise ConfigError(
        "no %s markers in the manuscript and no anchor configured.\n"
        "  Add matter.%s.anchor_before or anchor_after to meta.yaml, or paste\n"
        "  the marker pair where the section should go."
        % (name, name.lower().replace("-matter", "").replace("-", "_")))


def _anchor_help(name, key, anchor, text):
    """Anchors are literal strings from a hand-edited file, so failing usefully matters."""
    needle = anchor.strip()[:24]
    near = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if needle and needle[:12] in line:
            near.append("    %d: %s" % (line_no, line.strip()[:100]))
        if len(near) >= 5:
            break
    hint = ("\n  nearest lines containing %r:\n%s" % (needle[:12], "\n".join(near))
            if near else "\n  (nothing similar found in the file)")
    return "%s %s not found: %r%s" % (name, key, anchor, hint)
