"""Install / support directory paths (outside Resolve's Scripts tree)."""

import os
import sys

_ENV_HOME = "CONFORM_SIDEKICK_HOME"


def get_support_home() -> str:
    """Root folder containing ``conform_sidekick/`` and optional ``helpers/``."""
    override = os.environ.get(_ENV_HOME, "").strip()
    if override:
        return os.path.abspath(override)
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Conform Sidekick")
