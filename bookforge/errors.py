# -*- coding: utf-8 -*-
"""Failure types.

The reference pipeline called ``sys.exit("...")`` from library code, which makes
it impossible to build more than one book in a process. These carry the same
messages as exceptions instead, so the batch driver can keep going.
"""


class ForgeError(Exception):
    """Any failure the user can act on. The CLI prints these without a traceback."""


class ConfigError(ForgeError):
    """meta.yaml is missing a key, or a key has an unusable value."""


class MissingAssetError(ForgeError):
    """A font, cover, or generated asset is not where the config says it is."""


class RenderError(ForgeError):
    """Chrome failed, or produced nothing."""
