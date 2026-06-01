#!/usr/bin/env bash
# Build the odd-resolution image helper (macOS / Linux).
# Output: dist/convert_photos_helper-<platform-triple>
# Copy into ResolveScript/helpers/ beside your installed Conform Sidekick.

set -euo pipefail
cd "$(dirname "$0")"

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "pyinstaller not found. Run: pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p dist

if [[ "$(uname -s)" == "Darwin" ]]; then
  NAME="convert_photos_helper-x86_64-apple-darwin"
else
  NAME="convert_photos_helper-x86_64-unknown-linux-gnu"
fi

pyinstaller convert_photos_cli.py --onefile --clean --name "$NAME"

echo ""
echo "Built: dist/$NAME"
echo "Copy into: ResolveScript/helpers/ (next to Conform Sidekick.py)"
