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
- No code-signing / notarization pipeline for the main app (one small optional
  image helper binary may still be shipped for Pillow-free Resolve Python).

## Architecture

```
ResolveScript/                         # install into Resolve Scripts/Utility/
  Conform Sidekick.py                  # thin launcher (menu entry)
  helpers/                             # optional: PyInstaller image helper exe(s)
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
      odd_res.py                       # 1px stretch (Pillow or helper exe)
    _vendor/timecode/                  # vendored pure-Python dependency
```

### Two Python environments (dependency strategy)

1. **In-Resolve script** — runs in Resolve's bundled Python. Pure-Python deps are
   **vendored** as source (`_vendor/timecode`) so nothing requires `pip` in
   Resolve.
2. **Image helper (optional)** — a small **PyInstaller one-file executable** built
   from `PythonInterface/convert_photos_cli.py` (same logic as
   `PythonInterface/convert_photos.py`, with Pillow + pillow_heif bundled).
   Used only when Pillow is not importable inside Resolve's Python. Odd-res
   detection and `ReplaceClip` still run in-process; the helper only writes
   the stretched file beside the original.

Rule of thumb: pure-Python dep → vendor it; compiled dep → bundle a helper exe.

### Timecode

All timecode / fps conversions go through `timecode_utils` (the `timecode`
library), not hand-rolled SMPTE math — especially for Lay Matching Bin Clips.

## Status

- ✅ All six tools implemented and verified on Resolve Studio.
- ✅ Responsive/cancellable project & timeline scans; sidebar navigation.
- ⚠️ **Image helper** — in-process Pillow works when Resolve's Python has it;
  otherwise install a built helper under `ResolveScript/helpers/` (see below).

## Install (development)

Copy or symlink the `ResolveScript` folder contents into Resolve's Scripts
folder:

- **Windows:** `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\`
- **macOS:** `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`
- **Linux:** `~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/`

Both `Conform Sidekick.py` and the `conform_sidekick/` package must live in
`Utility/`. If you use junctions/symlinks for dev, also link **`helpers/`**
(see `link_to_resolve.ps1`). Launch via **Workspace → Scripts → Utility →
Conform Sidekick**.

### Optional: image helper

If **Fix Odd Resolution Photos** reports that Pillow is unavailable, build and
copy the helper:

```powershell
cd PythonInterface
pip install -r requirements.txt
.\build_convert_photos_helper.ps1
```

Then copy the file from `PythonInterface/dist/` into `ResolveScript/helpers/`
next to your installed script (create `helpers/` if needed). On macOS/Linux use
`build_convert_photos_helper.sh` instead.

The odd-res feature looks for these names (first match wins):

| Platform | Filenames searched |
|----------|-------------------|
| Windows | `convert_photos_helper.exe`, `convert_photos_helper-x86_64-pc-windows-msvc.exe` |
| macOS | `convert_photos_helper`, `convert_photos_helper-x86_64-apple-darwin` |
| Linux | `convert_photos_helper`, `convert_photos_helper-x86_64-unknown-linux-gnu` |

Search paths: `helpers/` under the install folder, the install folder itself,
or `CONFORM_SIDEKICK_HELPER` pointing at the executable.

## Shipping

GitHub Actions (`.github/workflows/resolve-native-release.yml`) builds per-OS
ZIPs: script package + image helper + installer. End users extract the ZIP and
run:

- **Windows:** `Install-ConformSidekick.bat`
- **macOS / Linux:** `./install_conform_sidekick.sh`

See `installer/README.md`. Releases are published when a `v*` tag is pushed on
this branch.

## Legacy Tauri app

The `TauriApp/` and `PythonInterface/even_photos_resolve.py` sidecar remain on
`main` for reference. The resolve-native branch does not use them; odd-res
conversion is in `conform_sidekick.ops.odd_res` with an optional
`convert_photos` helper instead of the old all-in-one `even_photos_resolve`
binary.
