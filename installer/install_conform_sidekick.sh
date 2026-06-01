#!/usr/bin/env bash
# Install Conform Sidekick into DaVinci Resolve (macOS / Linux).
# Run from the extracted release folder (same directory as "Conform Sidekick.py").

set -euo pipefail

SOURCE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=find_resolve_python.sh
source "$SOURCE/find_resolve_python.sh"

SKIP_DEPS=0
for arg in "$@"; do
  case "$arg" in
    --skip-deps) SKIP_DEPS=1 ;;
  esac
done
LAUNCHER="$SOURCE/Conform Sidekick.py"
PACKAGE="$SOURCE/conform_sidekick"

if [[ ! -f "$LAUNCHER" ]]; then
  echo "Could not find 'Conform Sidekick.py' in: $SOURCE" >&2
  echo "Extract the release archive first, then run this installer from that folder." >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin)
    UTILITY="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    SUPPORT="$HOME/Library/Application Support/Conform Sidekick"
    ;;
  Linux)
    UTILITY="$HOME/.local/share/DaVinciResolve/Fusion/Scripts/Utility"
    SUPPORT="$HOME/.local/share/Conform Sidekick"
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac

SUPPORT_PKG="$SUPPORT/conform_sidekick"

mkdir -p "$UTILITY" "$SUPPORT"

echo "Installing Conform Sidekick..."
echo "  Launcher -> $UTILITY"
echo "  Package  -> $SUPPORT_PKG"
echo ""

cp -f "$LAUNCHER" "$UTILITY/"

# Upgrade from older installs that put the package under Utility/.
if [[ -d "$UTILITY/conform_sidekick" ]]; then
  echo "Removing legacy package from Utility/..."
  rm -rf "$UTILITY/conform_sidekick"
fi
if [[ -d "$UTILITY/helpers" ]]; then
  rm -rf "$UTILITY/helpers"
fi

rm -rf "$SUPPORT_PKG"
cp -R "$PACKAGE" "$SUPPORT_PKG"

echo ""
if [[ "$SKIP_DEPS" -eq 0 ]]; then
  install_resolve_python_deps "$SOURCE" || {
    echo ""
    echo "Warning: could not install Python dependencies." >&2
    echo "Fix Odd Resolution Photos needs Pillow in Resolve's Python." >&2
    echo "Re-run with dependencies only: ./install_conform_sidekick.sh --skip-deps" >&2
    echo "Or install manually after locating Resolve's Python (see INSTALL.txt)." >&2
  }
else
  echo "Skipped Python dependency install (--skip-deps)."
fi

echo ""
echo "Done. In Resolve: Workspace -> Scripts -> Utility -> Conform Sidekick"
echo "Close and re-open the script if needed; restart Resolve if changes do not appear."
