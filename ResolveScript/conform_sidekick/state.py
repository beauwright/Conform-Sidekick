"""Persisted per-feature UI state.

Generalised from the three davinci-resolve-scripts, which each carried their
own ``load_state``/``save_state`` pair. A single :class:`StateStore` writes one
JSON file per namespace into a per-user location that is writable even when
Resolve runs the script from a read-only install directory.
"""

import json
import os
import sys


def _state_dir() -> str:
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/DaVinci Resolve")
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    folder = os.path.join(base, "ConformSidekick")
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

    def load(self) -> dict:
        state = dict(self.defaults)
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                for key in self.defaults:
                    if key in loaded:
                        state[key] = loaded[key]
        except (OSError, ValueError):
            pass
        return state

    def save(self, state: dict) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
        except OSError as exc:  # best-effort; never fatal
            print(f"Conform Sidekick: could not save state to {self.path}: {exc}")
