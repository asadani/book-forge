# -*- coding: utf-8 -*-
"""Path and executable discovery.

Replaces the reference pipeline's module-level ``os.chdir(REPO)``. Nothing here
changes the process working directory: every path is resolved against the book
root, which is wherever ``meta.yaml`` lives.
"""
import os

from . import FORGE_ROOT
from .errors import MissingAssetError

CACHE_DIRNAME = ".bf-cache"

# Checked in order. The reference pipeline hardcoded the first one.
CHROME_CANDIDATES = [
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def book_root(meta_path):
    """The book repo root: the directory holding meta.yaml."""
    return os.path.dirname(os.path.abspath(meta_path))


def in_book(root, *parts):
    return os.path.normpath(os.path.join(root, *parts))


def cache_dir(root):
    path = in_book(root, CACHE_DIRNAME)
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def forge_asset(*parts):
    """A file shipped inside book-forge itself (fonts, themes, partials)."""
    return os.path.normpath(os.path.join(FORGE_ROOT, *parts))


def resolve_font(name):
    """Font files resolve inside book-forge/fonts unless given as an absolute path."""
    if os.path.isabs(name):
        path = name
    else:
        path = forge_asset("fonts", name)
    if not os.path.exists(path):
        raise MissingAssetError(
            "font not found: %s\n  run `bf assets --fonts` to cut the static faces" % path)
    return path


def find_chrome(explicit=None):
    """--chrome > $BOOK_FORGE_CHROME > the candidate list."""
    if explicit:
        if not os.path.exists(explicit):
            raise MissingAssetError("chrome not found at %s" % explicit)
        return explicit
    env = os.environ.get("BOOK_FORGE_CHROME")
    if env:
        if not os.path.exists(env):
            raise MissingAssetError("BOOK_FORGE_CHROME points at nothing: %s" % env)
        return env
    for cand in CHROME_CANDIDATES:
        if os.path.exists(cand):
            return cand
    raise MissingAssetError(
        "no Chrome/Edge/Chromium found. Pass --chrome PATH or set BOOK_FORGE_CHROME.")
