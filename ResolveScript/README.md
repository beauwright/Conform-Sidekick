# Conform Sidekick - Resolve-native edition (`resolve-native` branch)

This branch replaces the Tauri (Rust + React/TypeScript) desktop app with a
**pure-Python tool that runs inside DaVinci Resolve** via the
**Workspace → Scripts** menu, built on Fusion's `UIManager`.

It also folds in three additional features ported from the
`davinci-resolve-scripts` repo (Rename Clips From Markers, Lay Matching Bin
Clips, Bulk Enable/Disable Color Nodes), so all nine tools live behind one
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
Fusion/Scripts/Utility/                 # Resolve script menu (one entry only)
  Conform Sidekick.py                   # thin launcher

Application Support/Conform Sidekick/   # outside Resolve's Scripts tree
  conform_sidekick/
    app.py                              # window + sidebar nav + dispatcher loop
    remote.py                           # Stream Deck / HTTP remote control
    paths.py                            # support-dir resolution
    resolve_conn.py                     # resolve / fusion / ui / dispatcher
    resolve_api.py                      # media-pool / timeline queries
    timecode_utils.py                   # frame <-> TC via vendored timecode lib
    ui_kit.py                           # log panel, pump, buttons, Tree helpers
    state.py                            # per-feature persisted UI state
    timeline_filters.py                 # shared track / In-Out / regex helpers
    features/
      table_scan.py                     # scan -> Tree -> Go/Copy timecode
      log_feature.py                    # form + log + Run/Cancel
      interlaced.py / compound_clips.py / odd_res_photos.py
      rename_from_markers.py / lay_matching_clips.py / bulk_node_enable.py
    ops/
      odd_res.py                        # 1px stretch (Pillow in Resolve's Python)
      source_tc.py                      # invent source TC from Date Created
    _vendor/timecode/                   # vendored pure-Python dependency
    _vendor/tzdata/                     # vendored IANA tz database (Windows)
  tests/                                # offline tests (no Resolve required)
  helpers/                              # optional legacy PyInstaller image helper
  streamdeck/                           # generated remote-control launchers
```

Resolve scans every `.py` under `Scripts/` recursively, so only the launcher
lives in `Utility/`. The package is installed under Application Support (see
`conform_sidekick.paths` and `installer/`).

### Dependencies

1. **In-Resolve script** — runs in Resolve's bundled Python. Pure-Python deps are
   **vendored** as source (`_vendor/timecode`, `_vendor/tzdata`) so nothing requires
   `pip` for timecode math or timezone conversion. `tzdata` is needed only because
   Windows ships no IANA database, so `zoneinfo.ZoneInfo("America/Denver")` raises
   there without it; macOS and Linux would resolve zones from the system database.
2. **Fix Odd Resolution Photos** — needs **Pillow** (+ **pillow_heif** for HEIC)
   in Resolve's Python. The release installer runs `pip install` against Resolve's
   python.org interpreter (not your shell `PATH`). See `installer/`.

Rule of thumb: pure-Python dep → vendor it; compiled/image dep → pip into Resolve's Python.

### Tests

Offline tests live in [`tests/`](tests/) — no Resolve, no network, no third-party
packages, so they run under any interpreter including Resolve's own:

```bash
python3 ResolveScript/tests/run_tests.py
```

### Timecode

All timecode / fps conversions go through `timecode_utils` (the `timecode`
library), not hand-rolled SMPTE math — especially for Lay Matching Bin Clips.

### Lay Matching Bin Clips: source ranges come from the Edit Index

Resolve's scripting API derives `GetSourceStartFrame()` / `GetSourceEndFrame()`
by flooring an internal float position, so they intermittently report 1 frame
low (an in-point of 24 stored internally as `23.99999...` comes back as 23).
That caused laid clips to land 1 frame early on source TC or 1 frame short on
the tail. Lay Matching Bin Clips therefore exports the timeline's **Edit
Index** (`Timeline.Export(..., EXPORT_TEXT_CSV)`) once per run and takes each
event's `Source In` / `Source Out` / `Source Start` timecodes from it — those
strings are rounded correctly by Resolve's display layer. The scripting API
ints are only used as a fallback when an event has no usable Edit Index row.

When a pairing key matches several bin clips (split screens shipping
`.._LEFT` / `.._RIGHT` plates, `.._REF` / `.._SCREEN` elements), each timeline
item pairs with the bin clips whose name matches it exactly (ignoring
extension) when such clips exist, otherwise with all of the key's clips.
Placements that would overlap on the new track spill onto additional tracks
(`Reconform`, `Reconform 2`, ...) automatically.

### Set Source TC From Date Created: what the API actually does

Clips that arrive at a source TC of `00:00:00:00` get an invented one derived from
their `Date Created`. Behaviour verified against Resolve Studio 21.0.4 — none of it
is documented in the scripting README:

- `SetClipProperty('Start TC', ...)` returns `True` and sticks. Only `Start TC` and
  `End TC` move; `Start`, `End`, `Frames` and `Duration` are untouched, because media
  frame numbering is 0-based and independent of the clip's TC.
- **Changing a clip's Start TC orphans any timeline item using it.**
  `TimelineItem.GetMediaPoolItem()` starts returning `None` and the source range is
  lost. Resolve resolves timeline item → media pool item by TC at query time, so
  writing the original TC back relinks the item and restores its exact source range.
  That recovery was verified **in-session only** — never across a save + reload — so
  clips already in a timeline are excluded by default and the Revert button exists to
  put them back before the project is saved.
- `Date Created` is the embedded container date when the media has one, and the
  filesystem birthtime otherwise, rendered in the **workstation's local timezone**.
  The same media therefore reads differently on differently-zoned machines, which is
  why the mode offers a timezone dropdown and converts local → UTC → chosen zone.
  A named IANA zone is required: a captured offset
  (`datetime.now().astimezone().tzinfo`) is fixed and silently shifts out-of-season
  clips by an hour.
- `Date Created` is `'Thu Feb 12 2026 16:47:29'` with a **non-zero-padded day**, while
  `Date Modified` puts the year last. The common `[-8:]` slice works on the former
  only by luck. `Date Recorded` is unusable — empty on stills, a raw integer on MXF.
- Filter on **file extension, not Resolve's `Type`**: Resolve reports image sequences
  as `Video`, so dropping `Type == Still` barely reduces timecode collisions while
  extension filtering removes almost all of them.

Since every clip the mode touches was at exactly `00:00:00:00`, Revert needs no
snapshot of prior values — it writes `00:00:00:00` back. Only the set of changed
clips is recorded, per project, in the feature's `StateStore`; that record is
**install-local** and does not follow the project to another workstation.

## Status

- ✅ All nine tools implemented and verified on Resolve Studio.
- ✅ Responsive/cancellable project & timeline scans; sidebar navigation.
- ⚠️ **Fix Odd Resolution Photos** — run the installer so Pillow is pip-installed
  into Resolve's Python (see `installer/README.md`).

## Install (development)

Use the link scripts so only the launcher appears under Utility:

- **Windows:** `ResolveScript/link_to_resolve.ps1`
- **macOS / Linux:** `chmod +x ResolveScript/link_to_resolve.sh && ./ResolveScript/link_to_resolve.sh`

That hardlinks/symlinks `Conform Sidekick.py` into Resolve's Utility folder and
links `conform_sidekick/` into Application Support:

- **Windows:** `%APPDATA%\Conform Sidekick\conform_sidekick\`
- **macOS:** `~/Library/Application Support/Conform Sidekick/conform_sidekick/`
- **Linux:** `~/.local/share/Conform Sidekick/conform_sidekick/`

Launch via **Workspace → Scripts → Utility → Conform Sidekick**.

Override the support directory with `CONFORM_SIDEKICK_HOME`. The launcher also
falls back to a sibling `conform_sidekick/` folder next to itself for quick
repo checkout testing without linking.

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

### Bypass Grade: Stream Deck / remote control

Resolve cannot bind a keyboard shortcut to a script, and a Stream Deck "Hotkey"
action just types into whichever app has focus — the very collision with
Resolve's shortcuts we want to avoid. So `remote.py` gives the running window a
loopback HTTP listener instead (`Color → Bypass Grade → Enable remote control`,
default port 41451). Actions: `bypass`, `restore`, `toggle`, `status`. Every
request needs the per-install token (`X-Sidekick-Token` header or `?token=`);
without it any web page could fire an action through an `<img>` tag.

On start the app writes ready-made launchers into `<support home>/streamdeck/`
with the port and token baked in — `.app` applets on macOS (compiled with
`osacompile`, they show a notification with the result), silent `.vbs` on
Windows, plus `.command` / `.bat` / `.sh` fallbacks and a README. Drag one onto
a Stream Deck "System: Open" action; Companion, Keyboard Maestro or curl can hit
the URL directly.

How it is driven, established by probing Resolve Studio 21 from the `fuscript`
process the Scripts menu launches:

- `UIDispatcher.RunLoop()` holds the GIL, so a background thread never runs
  while the window idles. No threads are used anywhere in the remote.
- `ui.Timer` exists and reports `IsActive`, but its `Timeout` event never reaches
  Python, whether hooked via `win.On` or `disp.On`.
- `UIDispatcher.StepLoop()` is non-blocking and returns in well under a
  millisecond when idle. While the remote is on, `app._event_loop` swaps
  `RunLoop` for a `StepLoop` + `remote.poll()` loop (~33 Hz, ~0.1 % CPU idle);
  with the remote off the proven `RunLoop` path is untouched.
- Requests are accepted with a zero-timeout `select` and answered on the UI
  thread, so a Stream Deck press runs through exactly the same
  `GradeBypassFeature.trigger` path as a button click and the reply carries the
  outcome (or the last log line on failure).
