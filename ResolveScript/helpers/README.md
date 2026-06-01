# Image helper (optional)

Place the PyInstaller-built `convert_photos_helper-*` executable in the
Application Support folder when Resolve's Python does not include Pillow:

- **macOS:** `~/Library/Application Support/Conform Sidekick/helpers/`
- **Windows:** `%APPDATA%\Conform Sidekick\helpers\`
- **Linux:** `~/.local/share/Conform Sidekick/helpers/`

Build from the repo root:

- Windows: `PythonInterface/build_convert_photos_helper.ps1`
- macOS/Linux: `PythonInterface/build_convert_photos_helper.sh`

Copy the artifact from `PythonInterface/dist/` into that `helpers/` folder.
