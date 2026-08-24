# -*- coding: utf-8 -*-
"""Rendering the matter partials.

The reference pipeline did this with patch_matter.py: a list of (old, new)
string pairs replaced into the manuscript in place, exiting on "ANCHOR NOT
FOUND". It could only ever run once, and its anchors were copies of the very
prose they replaced, so they rotted the moment a sentence changed.

Here the partials are Jinja templates fed from meta.yaml + data/author.yaml.
"""
import io
import os

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .errors import ConfigError
from .paths import forge_asset

# In sheet mode the host already styles its own plate/backmatter classes, so the
# wrapper keeps them and the book renders exactly as before.
DEFAULT_SECTION_CLASS = {
    "sheet": {"front": "sheet plate", "about": "sheet backmatter about"},
    "flow": {"front": None, "about": None},
}


def _data(name):
    with io.open(forge_asset("data", name), encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _env():
    env = Environment(
        loader=FileSystemLoader(forge_asset("partials")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )
    return env


def _year(cfg):
    d = cfg.get("date")
    if d is None:
        return ""
    return str(d)[:4]


def context(cfg, qr_svgs=None):
    """Everything both partials need."""
    author = _data("author.yaml")
    licenses = _data("licenses.yaml")

    lic_id = cfg.get("license.id")
    if not lic_id:
        raise ConfigError(
            "meta.yaml needs license.id -- it has no default, because the "
            "pipeline this replaced hardcoded CC BY 4.0 and would relicense "
            "any book that ships under different terms")
    if lic_id not in licenses:
        raise ConfigError("unknown license.id %r (known: %s)"
                          % (lic_id, ", ".join(sorted(licenses))))
    lic = dict(licenses[lic_id])
    lic["id"] = lic_id

    mode = cfg.get("matter.mode", "sheet")
    defaults = DEFAULT_SECTION_CLASS[mode]

    front = dict(cfg.get("matter.front") or {})
    front.setdefault("heading", "Copyright, permissions, and how this was made")
    front.setdefault("section_class", defaults["front"])
    front.setdefault("work_line", cfg.get("title"))
    front.setdefault("sources_html", None)
    front.setdefault("imprint", "")

    about = dict(cfg.get("matter.about") or {})
    about.setdefault("heading", "About the author")
    about.setdefault("section_class", defaults["about"])
    about.setdefault("closing_html", None)

    ctx = {
        "mode": mode,
        "author": author,
        "title": cfg.get("title"),
        "subtitle": cfg.get("subtitle"),
        "slug": cfg.slug,
        "year": _year(cfg),
        "license": lic,
        "front": front,
        "about": about,
        "colophon_html": cfg.get("matter.colophon_html"),
    }

    # The licence grant names the author and the title, so it is itself a template.
    ctx["grant_html"] = _env().from_string(lic.get("grant_html", "")).render(**ctx).strip()

    # A book may supply its own disclosure inline. The named variants in
    # author.yaml are shared across every title, so a work that is not a book --
    # a paper, a journal, a report -- would otherwise be stuck calling itself one.
    inline = front.get("ai_disclosure_html")
    which = front.get("ai_disclosure")
    if inline:
        ctx["disclosure"] = inline.strip()
    elif which:
        variants = author.get("ai_disclosure", {})
        if which not in variants:
            raise ConfigError(
                "matter.front.ai_disclosure is %r; data/author.yaml has: %s"
                % (which, ", ".join(sorted(variants))))
        ctx["disclosure"] = variants[which].strip()
    else:
        ctx["disclosure"] = None

    # QR cards: author.yaml supplies the defaults, meta.yaml may override the
    # presentation of a card. Codes are matched to cards BY INDEX, not by target
    # string -- keying on the target meant an override that changed it silently
    # produced a card with no QR in it at all.
    svgs = list(qr_svgs or [])
    cards = []
    for i, card in enumerate(author.get("qr", [])):
        card = dict(card)
        for ov in about.get("qr_override") or []:
            if int(ov.get("index", -1)) == i:
                if "target" in ov:
                    raise ConfigError(
                        "matter.about.qr_override[%d] sets `target`. The qr: list "
                        "is the source of truth for what a code encodes -- change "
                        "it there, or the printed code and the caption drift apart."
                        % i)
                card.update({k: v for k, v in ov.items() if k != "index"})
        card["svg"] = svgs[i] if i < len(svgs) else ""
        cards.append(card)
    ctx["cards"] = cards
    return ctx


def front_matter(cfg, qr_svgs=None):
    return _env().get_template("front-matter.html.j2").render(**context(cfg, qr_svgs)).strip()


def about_author(cfg, qr_svgs=None):
    return _env().get_template("about-author.html.j2").render(**context(cfg, qr_svgs)).strip()


def matter_css():
    path = forge_asset("partials", "matter.css")
    if not os.path.exists(path):
        return ""
    with io.open(path, encoding="utf-8") as fh:
        return fh.read().strip()
