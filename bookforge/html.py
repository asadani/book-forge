# -*- coding: utf-8 -*-
"""Template slot filling.

Deliberately plain string substitution, exactly as the reference pipeline did
it. These are hand-authored files whose indentation and comment banners the
author cares about; a DOM round-trip would reformat 1,500+ lines.
"""
import base64
import io
import re

from .errors import ConfigError

SLOT_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def data_uri(path, mime):
    with open(path, "rb") as fh:
        blob = fh.read()
    return "data:%s;base64,%s" % (mime, base64.b64encode(blob).decode("ascii")), len(blob)


def fill(template_text, slots, required=()):
    """Replace {{SLOT}} tokens. `required` names slots that must be present."""
    for name in required:
        if "{{%s}}" % name not in template_text:
            raise ConfigError("template has no {{%s}} slot" % name)
    out = template_text
    for name, value in slots.items():
        out = out.replace("{{%s}}" % name, value)
    return out


def unfilled(text):
    """Any {{SLOT}} tokens still present after filling."""
    return sorted(set(SLOT_RE.findall(text)))
