#!/usr/bin/env python
"""Conform Sidekick launcher.

Install locations (per OS):
    Launcher: .../DaVinci Resolve/Fusion/Scripts/Utility/Conform Sidekick.py
    Package:  ~/Library/Application Support/Conform Sidekick/conform_sidekick/  (macOS)
              %APPDATA%\\Conform Sidekick\\conform_sidekick\\                  (Windows)
              ~/.local/share/Conform Sidekick/conform_sidekick/               (Linux)

Launch from:
    DaVinci Resolve menu -> Workspace -> Scripts -> Utility -> Conform Sidekick

Only this file lives under Utility so Resolve's script scanner lists a single entry.
The package is installed separately (see installer/ or conform_sidekick.paths).
"""

import os
import sys

if "__file__" in globals():
    _HERE = os.path.dirname(os.path.abspath(__file__))
else:  # Resolve usually defines __file__; fall back to CWD just in case.
    _HERE = os.getcwd()


def _support_home():
    # Keep in sync with conform_sidekick.paths.get_support_home (imported after sys.path).
    override = os.environ.get("CONFORM_SIDEKICK_HOME", "").strip()
    if override:
        return os.path.abspath(override)
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Conform Sidekick")


def _package_sys_path_entry():
    support = _support_home()
    if os.path.isdir(os.path.join(support, "conform_sidekick")):
        return support
    dev = os.path.join(_HERE, "conform_sidekick")
    if os.path.isdir(dev):
        return _HERE
    return support


_PKG_ROOT = _package_sys_path_entry()
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

# Resolve keeps one Python interpreter alive for the whole session, so modules
# imported on a previous run are cached. Purge the package before importing so
# each launch always runs the latest code (important while developing).
for _mod_name in list(sys.modules):
    if _mod_name == "conform_sidekick" or _mod_name.startswith("conform_sidekick."):
        del sys.modules[_mod_name]

from conform_sidekick.app import main

main(injected_globals=globals())
