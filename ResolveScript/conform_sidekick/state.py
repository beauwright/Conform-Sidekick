"""Persisted per-feature UI state.

Generalised from the three davinci-resolve-scripts, which each carried their
own ``load_state``/``save_state`` pair. A single :class:`StateStore` writes one
JSON file per namespace into a per-user location that is writable even when
Resolve runs the script from a read-only install directory.

State lives alongside the installed package under
``<support home>/state/`` (see :mod:`paths`), with one-time migration from the
legacy per-OS folders used in early resolve-native builds.
"""

import json
import os
import sys

from . import paths

APP_DEFAULTS = {
    "last_feature_id": "",
}


def _legacy_state_dir() -> str:
    """Pre-2.0.0-beta.2 state locations (read once for migration)."""
    if sys.platform == "darwin":
        base = os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Application Support",
            "DaVinci Resolve",
        )
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "ConformSidekick")


def _state_dir() -> str:
    folder = os.path.join(paths.get_support_home(), "state")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    return folder


class StateStore:
    """Load/save a flat dict of UI values for one feature namespace."""

    def __init__(self, namespace: str, defaults: dict):
        self.namespace = namespace
        self.defaults = dict(defaults)
        self.path = os.path.join(_state_dir(), f"{namespace}.json")

    def _read_path(self) -> str:
        if os.path.isfile(self.path):
            return self.path
        legacy = os.path.join(_legacy_state_dir(), f"{self.namespace}.json")
        if os.path.isfile(legacy):
            return legacy
        return self.path

    def load(self) -> dict:
        state = dict(self.defaults)
        read_path = self._read_path()
        migrated = read_path != self.path
        try:
            with open(read_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                for key in self.defaults:
                    if key in loaded:
                        state[key] = loaded[key]
        except (OSError, ValueError):
            return state
        if migrated:
            self.save(state)
        return state

    def save(self, state: dict) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
        except OSError as exc:  # best-effort; never fatal
            print(f"Conform Sidekick: could not save state to {self.path}: {exc}")


def app_state_store() -> StateStore:
    """Persisted app-level preferences (e.g. last opened mode)."""
    return StateStore("app", APP_DEFAULTS)
