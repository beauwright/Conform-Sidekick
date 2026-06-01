"""Connect to DaVinci Resolve and obtain the Fusion UIManager + dispatcher.

Two launch contexts are supported, mirroring the convention proven out in the
davinci-resolve-scripts repo:

1. **Inside Resolve** (Workspace > Scripts). Resolve injects ``resolve``, ``bmd``
   and ``fusion`` globals into the *launcher* script's namespace. Those are
   passed down to :func:`connect` as ``injected_globals`` because injected
   globals are not visible to imported modules.

2. **Externally** (a plain terminal run, mostly useful for development). The
   Blackmagic ``DaVinciResolveScript`` module is located from the documented
   ``RESOLVE_SCRIPT_API`` env var or the default per-OS install path.
"""

import os
import sys


class ResolveConnectionError(RuntimeError):
    """Raised when a usable Resolve scripting connection cannot be made."""


def _load_resolve_module():
    """Import Blackmagic's DaVinciResolveScript module for external runs."""
    try:
        import DaVinciResolveScript as module  # type: ignore
        return module
    except ImportError:
        pass

    candidates = []
    env_api = os.environ.get("RESOLVE_SCRIPT_API")
    if env_api:
        candidates.append(os.path.join(env_api, "Modules"))
    if sys.platform.startswith("darwin"):
        candidates.append(
            "/Library/Application Support/Blackmagic Design/"
            "DaVinci Resolve/Developer/Scripting/Modules"
        )
    elif os.name == "nt":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        candidates.append(
            os.path.join(
                program_data, "Blackmagic Design", "DaVinci Resolve",
                "Support", "Developer", "Scripting", "Modules",
            )
        )
    else:
        candidates.append("/opt/resolve/Developer/Scripting/Modules")
        candidates.append("/home/resolve/Developer/Scripting/Modules")

    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.append(path)

    import DaVinciResolveScript as module  # type: ignore
    return module


class ResolveConnection:
    """Bundle of the handles every feature needs to build UI and do work."""

    def __init__(self, resolve, fusion, ui, dispatcher):
        self.resolve = resolve
        self.fusion = fusion
        self.ui = ui
        self.dispatcher = dispatcher

    def get_project(self):
        try:
            return self.resolve.GetProjectManager().GetCurrentProject()
        except Exception:
            return None

    def get_timeline(self):
        project = self.get_project()
        if project is None:
            return None
        try:
            return project.GetCurrentTimeline()
        except Exception:
            return None


def connect(injected_globals=None) -> ResolveConnection:
    """Return a :class:`ResolveConnection`, or raise ``ResolveConnectionError``.

    ``injected_globals`` should be the launcher's ``globals()`` so the
    Resolve-injected ``resolve``/``bmd`` objects can be reused when running
    inside Resolve.
    """
    injected_globals = injected_globals or {}

    resolve_obj = injected_globals.get("resolve")
    dvr_module = None
    if resolve_obj is None:
        try:
            dvr_module = _load_resolve_module()
            resolve_obj = dvr_module.scriptapp("Resolve")
        except Exception as exc:  # pragma: no cover - depends on host
            raise ResolveConnectionError(
                "Could not load the DaVinci Resolve scripting module: " + str(exc)
            )

    if resolve_obj is None:
        raise ResolveConnectionError(
            "Could not connect to DaVinci Resolve. Is it running?"
        )

    try:
        fusion = resolve_obj.Fusion()
        ui = fusion.UIManager
    except Exception as exc:
        raise ResolveConnectionError("Could not access the Fusion UIManager: " + str(exc))

    dispatcher = None
    bmd_mod = injected_globals.get("bmd")
    if bmd_mod is not None:
        try:
            dispatcher = bmd_mod.UIDispatcher(ui)
        except Exception:
            dispatcher = None
    if dispatcher is None:
        if dvr_module is None:
            dvr_module = _load_resolve_module()
        dispatcher = dvr_module.UIDispatcher(ui)

    return ResolveConnection(resolve_obj, fusion, ui, dispatcher)
