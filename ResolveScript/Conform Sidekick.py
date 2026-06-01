#!/usr/bin/env python
"""Conform Sidekick launcher.

Install location (per OS):
    .../Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/

Launch from:
    DaVinci Resolve menu -> Workspace -> Scripts -> Utility -> Conform Sidekick

This thin launcher only puts the bundled ``conform_sidekick`` package on the
import path and hands Resolve's injected globals (``resolve``/``bmd``/``fusion``)
to the app. All real logic lives in the package next to this file.
"""

import os
import sys

if "__file__" in globals():
    _HERE = os.path.dirname(os.path.abspath(__file__))
else:  # Resolve usually defines __file__; fall back to CWD just in case.
    _HERE = os.getcwd()

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Resolve keeps one Python interpreter alive for the whole session, so modules
# imported on a previous run are cached. Purge the package before importing so
# each launch always runs the latest code (important while developing).
for _mod_name in list(sys.modules):
    if _mod_name == "conform_sidekick" or _mod_name.startswith("conform_sidekick."):
        del sys.modules[_mod_name]

from conform_sidekick.app import main

main(injected_globals=globals())
