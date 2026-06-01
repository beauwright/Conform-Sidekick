# Conform Sidekick - Resolve-native edition (`resolve-native` branch)

This branch replaces the Tauri (Rust + React/TypeScript) desktop app with a
**pure-Python tool that runs inside DaVinci Resolve** via the
**Workspace → Scripts** menu, built on Fusion's `UIManager`.

It also folds in three additional features ported from the
`davinci-resolve-scripts` repo (Rename Clips From Markers, Lay Matching Bin
Clips, Bulk Enable/Disable Color Nodes), so all six tools live behind one
window with a tab per feature.

## Why native?

- No separate app to alt-tab to; it lives in Resolve.
- In-process, so no "Connecting to DaVinci Resolve" step and far fewer
  connection failure modes than the old external sidecar.
- No code-signing / notarization pipeline.
- Likely works on the free version of Resolve as well (running from the Scripts
  menu is not "external scripting"). **Verify which calls are Studio-gated**
  before promising this - `MediaPoolItem.ReplaceClip` in particular.

## Architecture

```
ResolveScript/                         # this is what gets installed into Resolve
  Conform Sidekick.py                  # thin launcher (the menu entry)
  conform_sidekick/                    # shared package, all logic
    __init__.py                        # puts _vendor/ on sys.path
    app.py                             # builds the tabbed window + dispatcher loop
    resolve_conn.py                    # connect to resolve/fusion/ui/dispatcher
    resolve_api.py                     # media-pool / timeline queries (ex-ResolveController)
    timecode_utils.py                  # frame <-> TC via the timecode library
    ui_kit.py                          # log panel, pump, run/cancel, Tree helpers
    state.py                           # persisted per-feature UI state
    timeline_filters.py                # shared track/index/layer/In-Out parsing
    features/
      base.py                          # Feature interface + AppContext
      table_scan.py                    # base: scan -> Tree -> jump to timecode
      log_feature.py                   # base: form + log + Run/Cancel
      interlaced.py                    # scan-table feature
      compound_clips.py                # scan-table feature
      odd_res_photos.py                # scan-table + convert/ReplaceClip
      rename_from_markers.py           # log feature
      lay_matching_clips.py            # log feature
      bulk_node_enable.py              # log feature
    ops/                               # UI-agnostic ported core operations
      rename_markers.py
      bulk_nodes.py
      lay_clips.py                     # timecode math via the timecode library
      odd_res.py                       # 1px stretch (Pillow when available)
    _vendor/
      timecode/                        # vendored pure-Python dependency
```

### Two Python environments (dependency strategy)

1. **The in-Resolve script** runs in Resolve's own interpreter. Pure-Python
   dependencies are **vendored** as source (`_vendor/timecode`) so they import
   without anyone running `pip`.
2. **The image helper** (still TODO) is a small **bundled executable** built
   from `PythonInterface/convert_photos.py` via PyInstaller, carrying the
   compiled `Pillow` / `pillow_heif`. The odd-resolution feature shells out to
   it for the 1px stretch, then calls `ReplaceClip` natively. This is the only
   bundled binary; everything else is plain Python source.

Rule of thumb: pure-Python dep → vendor it; compiled dep → push the feature
that needs it into a bundled helper and bundle only what that helper uses.

### Timecode

All timecode-string / fps-dependent conversions go through `timecode_utils`
(the `timecode` library), **not** hand-rolled SMPTE math. This is the intended
fix for the drop-frame / off-by-one bugs seen in the Lay Matching Bin Clips
reconform feature; its `_tc_to_frames` / Start-TC remap will be reworked onto
`timecode` during the port.

## Status

- ✅ Package scaffold, vendored `timecode`, shared UI kit, ported media queries.
- ✅ All six tabs are implemented:
  - **Identify Interlaced** / **Identify Compound Clips** - scope selector → Tree
    → select a row and Go to / Copy Timecode (double-click a row to jump).
  - **Fix Odd Resolution Photos** - scan, then Convert All Listed / Convert
    Selected (1px stretch + `ReplaceClip`).
  - **Rename Clips From Markers**, **Lay Matching Bin Clips**, **Bulk
    Enable/Disable Nodes** - form inputs + live log + Run/Cancel, ported from the
    davinci-resolve-scripts.
- ⚠️ The odd-resolution conversion uses Pillow when it's importable in Resolve's
  Python; bundling the image helper for a Pillow-free Resolve Python is still a
  packaging TODO. `ReplaceClip` may also require Resolve Studio.

## Install (development)

Copy or symlink the `ResolveScript` contents into Resolve's Scripts folder:

- **Windows:** `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\`
- **macOS:** `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`
- **Linux:** `~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/`

Both `Conform Sidekick.py` **and** the `conform_sidekick/` package must sit in
that `Utility/` folder. Then launch via **Workspace → Scripts → Utility →
Conform Sidekick** (restart Resolve or use Scripts → Reload if available).

For end users, the plan is to keep shipping a one-click installer (reusing the
GitHub release pipeline) whose only job is to copy these files + the image
helper into that folder, so the "download, double-click, open from the menu"
experience is preserved.

## Open items to verify in Resolve

- `ui.Tree` checkbox + sorting behaviour on the target Resolve build.
- Panel `Hidden`-toggle tab switching (isolated to `app._make_show_panel`).
- Which APIs are Studio-only (esp. `ReplaceClip`).
