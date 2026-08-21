# -*- coding: utf-8 -*-
"""book-forge -- a shared build pipeline for the Ko-fi books.

Extracted from the pipeline that produced *Speed Is the Moat*, which lived
git-ignored in a single repo. Everything book-specific that used to be a module
constant is now a key in the book's own ``meta.yaml``.
"""
import io
import os

__all__ = ["__version__", "FORGE_ROOT"]

FORGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_version():
    path = os.path.join(FORGE_ROOT, "VERSION")
    try:
        return io.open(path, encoding="utf-8").read().strip()
    except IOError:
        return "0.0.0+unknown"


__version__ = _read_version()
