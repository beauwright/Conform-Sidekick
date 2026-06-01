# Conform Sidekick installer (resolve-native)

End users download a platform ZIP from [GitHub Releases](https://github.com/beauwright/Conform-Sidekick/releases), extract it, and run:

| Platform | Action |
|----------|--------|
| **Windows** | Double-click `Install-ConformSidekick.bat` (or run `Install-ConformSidekick.ps1`) |
| **macOS / Linux** | `chmod +x install_conform_sidekick.sh && ./install_conform_sidekick.sh` |

That installs:

| What | Where |
|------|--------|
| `Conform Sidekick.py` (launcher only) | Resolve **Scripts → Utility** |
| `conform_sidekick/` (full package) | Application Support (see below) |

Support directory (package root):

- **macOS:** `~/Library/Application Support/Conform Sidekick/`
- **Windows:** `%APPDATA%\Conform Sidekick\`
- **Linux:** `~/.local/share/Conform Sidekick/`

Only the launcher lives under Utility so Resolve's script menu shows a single
entry. Upgrading removes any legacy `Utility/conform_sidekick/` folder from
older installs.

Then the installer pip-installs into **Resolve's Python** (not your shell `PATH`).

## Prerequisites

- **DaVinci Resolve Studio** (scripting API required)
- **Python from [python.org](https://www.python.org/downloads/)** — the same kind of install Resolve expects:
  - **macOS:** `/Library/Frameworks/Python.framework/Versions/<version>/`
  - **Windows:** `C:\Program Files\Python3xx\` or `%LOCALAPPDATA%\Programs\Python\Python3xx\`

In Resolve, set **DaVinci Resolve → Preferences → System → General → External scripting using → Local** (macOS/Windows) so Workspace scripts run.

Match the Python version shown under **Fusion → Fusion Settings → Script → Default Script Language** (or the scripting version Resolve reports). The installer picks the newest compatible python.org install in those locations.

## What gets pip installed

Only packages needed for **Fix Odd Resolution Photos** (Pillow + pillow_heif). The `timecode` library is **bundled inside** `conform_sidekick/_vendor/` — no pip install needed for timecode.

Override the interpreter with `CONFORM_SIDEKICK_PYTHON`. Override the package location with `CONFORM_SIDEKICK_HOME`.

Skip dependency install: `-SkipDeps` (PowerShell) or `--skip-deps` (shell).

Developers can use link scripts instead: `ResolveScript/link_to_resolve.ps1` or `link_to_resolve.sh`.
