# -*- coding: utf-8 -*-
"""meta.yaml + theme.yaml loading, defaults, and validation.

Every value the reference pipeline hardcoded at module level lives here instead.
Defaults are deliberately thin: anything whose wrong value would silently damage
a published book (the licence, the cover art) has no default and must be stated.
"""
import io
import os

import yaml

from .errors import ConfigError
from .paths import book_root, forge_asset, in_book

# Page geometry in PDF points, for the verifier. Chrome gets these from CSS.
PAGE_SIZES = {
    "A4": (595.3, 841.9),
    "Letter": (612.0, 792.0),
}

DEFAULTS = {
    "theme": "sheet-oxblood",
    "source": {"template": "book.html.in"},
    "output": {"html": "index.html", "pdf": None},        # pdf -> "<slug>.pdf"
    "page": {"size": "A4"},
    # page: render a full-bleed cover page and embed it at {{COVER_PAGE_URI}}.
    # Flow-mode essays usually draw their own cover in the document, so they
    # set this false and keep `art` only as the Ko-fi / shelf thumbnail.
    "cover": {"fit": "crop", "trim_top_share": 0.47, "dpi": 300, "page": True},
    # flow is the house default: books read as one continuous page on screen
    # and still paginate in print via the manuscript's own break-before rules.
    # Sheet mode -- a fixed card per printed page -- is opt-in per book.
    "matter": {"mode": "flow"},
    "folio": {
        # Some manuscripts paginate themselves via @page { @bottom-center {
        # content: counter(page) } }. Stamping those adds a second number next
        # to the first, so they set enabled: false.
        "enabled": True,
        "font": "IBMPlexMono-Regular.ttf",
        "size": 8,
        "color": [0.49, 0.52, 0.58],
        "skip_pages": [1],
        "first_number": 1,
    },
    "pdf": {"virtual_time_budget_ms": 30000, "timeout_s": 300},
    "verify": {
        "cover_probes": [],
        "body_probes": [],
        "matter_probes": [],
        "min_images": 1,
        "expect_pages": None,
        "page_tolerance": 2,
        # Some books deliberately use a system-font stack (no @font-face, no
        # webfonts). Those legitimately embed Times/Arial/Liberation depending
        # on the rendering machine, and must not be failed for it. Set true
        # only when the manuscript declares no webfonts of its own.
        "allow_system_fonts": False,
    },
}

REQUIRED = ["slug", "title"]


def _merge(base, over):
    """Recursive dict merge; `over` wins. Lists are replaced, never concatenated."""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml(path):
    if not os.path.exists(path):
        raise ConfigError("no such file: %s" % path)
    with io.open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Config(object):
    """A book's resolved configuration, plus the paths derived from it."""

    def __init__(self, data, root, meta_path):
        self.data = data
        self.root = root
        self.meta_path = meta_path
        self.theme = _load_yaml(forge_asset("themes", data["theme"], "theme.yaml"))

    # -- dotted access ---------------------------------------------------
    def get(self, dotted, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def need(self, dotted):
        val = self.get(dotted)
        if val is None:
            raise ConfigError("meta.yaml is missing required key: %s" % dotted)
        return val

    # -- derived paths ---------------------------------------------------
    def path(self, dotted):
        """A book-relative path from config, absolutised."""
        return in_book(self.root, self.need(dotted))

    @property
    def slug(self):
        return self.data["slug"]

    @property
    def template(self):
        return self.path("source.template")

    @property
    def html_out(self):
        return self.path("output.html")

    @property
    def pdf_out(self):
        return in_book(self.root, self.data["output"]["pdf"])

    @property
    def cover_art(self):
        return self.path("cover.art")

    @property
    def page_points(self):
        size = self.get("page.size", "A4")
        if size not in PAGE_SIZES:
            raise ConfigError(
                "unknown page.size %r (known: %s)" % (size, ", ".join(sorted(PAGE_SIZES))))
        return PAGE_SIZES[size]

    @property
    def faces(self):
        """[(family, weight, filename)] from the theme."""
        out = []
        for f in self.theme.get("faces", []):
            out.append((f["family"], int(f["weight"]), f["file"]))
        return out


def load(meta_path):
    raw = _load_yaml(meta_path)
    missing = [k for k in REQUIRED if not raw.get(k)]
    if missing:
        raise ConfigError("meta.yaml is missing required key(s): %s" % ", ".join(missing))

    data = _merge(DEFAULTS, raw)
    if not data["output"].get("pdf"):
        data["output"]["pdf"] = "%s.pdf" % data["slug"]

    fit = data["cover"].get("fit")
    if fit not in ("crop", "contain", "matte"):
        raise ConfigError("cover.fit must be crop|contain|matte, got %r" % fit)
    if data["matter"].get("mode") not in ("sheet", "flow"):
        raise ConfigError("matter.mode must be sheet|flow")

    theme_dir = forge_asset("themes", data["theme"])
    if not os.path.isdir(theme_dir):
        raise ConfigError("unknown theme %r (no such directory: %s)" % (data["theme"], theme_dir))

    return Config(data, book_root(meta_path), meta_path)
