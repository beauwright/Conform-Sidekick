# Conform Sidekick - Resolve-native edition (`resolve-native` branch)

This branch replaces the Tauri (Rust + React/TypeScript) desktop app with a
**pure-Python tool that runs inside DaVinci Resolve** via the
**Workspace → Scripts** menu, built on Fusion's `UIManager`.

It also folds in three additional features ported from the
`davinci-resolve-scripts` repo (Rename Clips From Markers, Lay Matching Bin
Clips, Bulk Enable/Disable Color Nodes), so all six tools live behind one
window with a sidebar navigator.

## Requirements

- **DaVinci Resolve Studio** — the scripting API (Python/Lua, media pool,
  timeline control, `ReplaceClip`, and UIManager script windows) is not
  available on the free edition. Conform Sidekick is intended for Studio only.

## Why native?

- No separate app to alt-tab to; it lives in Resolve.
- In-process, so no "Connecting to DaVinci Resolve" step and far fewer
  connection failure modes than the old external sidecar.
- No code-signing / notarization pipeline for the main app.

## Architecture

```
ResolveScript/                         # install into Resolve Scripts/Utility/
  Conform Sidekick.py                  # thin launcher (menu entry)
  conform_sidekick/
    app.py                             # window + sidebar nav + dispatcher loop
    resolve_conn.py                    # resolve / fusion / ui / dispatcher
    resolve_api.py                     # media-pool / timeline queries
    timecode_utils.py                  # frame <-> TC via vendored timecode lib
    ui_kit.py                          # log panel, pump, buttons, Tree helpers
    state.py                           # per-feature persisted UI state
    timeline_filters.py                # shared track / In-Out / regex helpers
    features/
      table_scan.py                    # scan -> Tree -> Go/Copy timecode
      log_feature.py                   # form + log + Run/Cancel
      interlaced.py / compound_clips.py / odd_res_photos.py
      rename_from_markers.py / lay_matching_clips.py / bulk_node_enable.py
    ops/
      odd_res.py                       # 1px stretch (Pillow in Resolve's Python)
    _vendor/timecode/                  # vendored pure-Python dependency
```

### Dependencies

1. **In-Resolve script** — runs in Resolve's bundled Python. Pure-Python deps are
   **vendored** as source (`_vendor/timecode`) so nothing requires `pip` for
   timecode math.
2. **Fix Odd Resolution Photos** — needs **Pillow** (+ **pillow_heif** for HEIC)
   in Resolve's Python. The release installer runs `pip install` against Resolve's
   python.org interpreter (not your shell `PATH`). See `installer/`.

Rule of thumb: pure-Python dep → vendor it; compiled/image dep → pip into Resolve's Python.

### Timecode

All timecode / fps conversions go through `timecode_utils` (the `timecode`
library), not hand-rolled SMPTE math — especially for Lay Matching Bin Clips.

## Status

- ✅ All six tools implemented and verified on Resolve Studio.
- ✅ Responsive/cancellable project & timeline scans; sidebar navigation.
- ⚠️ **Fix Odd Resolution Photos** — run the installer so Pillow is pip-installed
  into Resolve's Python (see `installer/README.md`).

## Install (development)

Copy or symlink the `ResolveScript` folder contents into Resolve's Scripts
folder:

- **Windows:** `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\`
- **macOS:** `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`
- **Linux:** `~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/`

Both `Conform Sidekick.py` and the `conform_sidekick/` package must live in
`Utility/`. Launch via **Workspace → Scripts → Utility → Conform Sidekick**.

For odd-res photo conversion during development, pip install into Resolve's Python:

```bash
# macOS example — use the version Resolve actually loads
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pip install -r installer/requirements-resolve.txt
```

Or run `installer/install_conform_sidekick.sh` / `Install-ConformSidekick.ps1` from a release-style folder.

## Shipping

GitHub Actions (`.github/workflows/resolve-native-release.yml`) builds per-OS
ZIPs: script package + installer (which pip-installs Pillow deps). End users extract the ZIP and
run:

- **Windows:** `Install-ConformSidekick.bat`
- **macOS / Linux:** `./install_conform_sidekick.sh`

See `installer/README.md`. Releases are published when a `v*` tag is pushed on
this branch.

## Legacy Tauri app

The `TauriApp/` and `PythonInterface/even_photos_resolve.py` sidecar remain on
`main` for reference. The resolve-native branch does not use them; odd-res
conversion is in `conform_sidekick.ops.odd_res` (Pillow in Resolve's Python).
Legacy PyInstaller helper scripts under `PythonInterface/` remain for reference only.
