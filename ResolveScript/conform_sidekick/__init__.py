"""Conform Sidekick - Resolve-native edition.

This package runs *inside* DaVinci Resolve via the Workspace > Scripts menu
using Fusion's UIManager, replacing the previous Tauri/Rust desktop app.

Importing the package puts the bundled (vendored) pure-Python dependencies on
sys.path so they can be imported by their normal top-level names (e.g.
``from timecode import Timecode``) without the user having to ``pip install``
anything into Resolve's Python.
"""

import os
import sys

_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vendor")
if os.path.isdir(_VENDOR_DIR) and _VENDOR_DIR not in sys.path:
    # Insert at the front so the vendored copies win over anything that may
    # happen to be installed in Resolve's interpreter.
    sys.path.insert(0, _VENDOR_DIR)

__all__ = ["__version__"]
__version__ = "2.0.0"
