"""Parse version."""

import os

# globals
_VERSION = None
_VERSION_FILE = os.path.join(os.path.dirname(__file__), "VERSION")
if os.path.isfile(_VERSION_FILE):
    with open(_VERSION_FILE) as _version_file:
        _VERSION = _version_file.read().strip()
__version__ = _VERSION or "0.0.0"
"""str: The version of the package."""
