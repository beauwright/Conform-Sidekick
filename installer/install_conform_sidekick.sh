#!/usr/bin/env bash
# Install Conform Sidekick into DaVinci Resolve (macOS / Linux).
# Run from the extracted release folder (same directory as "Conform Sidekick.py").

set -euo pipefail

SOURCE="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$SOURCE/Conform Sidekick.py"
PACKAGE="$SOURCE/conform_sidekick"

if [[ ! -f "$LAUNCHER" ]]; then
  echo "Could not find 'Conform Sidekick.py' in: $SOURCE" >&2
  echo "Extract the release archive first, then run this installer from that folder." >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin)
    DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    ;;
  Linux)
    DEST="$HOME/.local/share/DaVinciResolve/Fusion/Scripts/Utility"
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac

mkdir -p "$DEST"

echo "Installing Conform Sidekick..."
echo "  From: $SOURCE"
echo "    To: $DEST"
echo ""

cp -f "$LAUNCHER" "$DEST/"
rm -rf "$DEST/conform_sidekick"
cp -R "$PACKAGE" "$DEST/"

if [[ -d "$SOURCE/helpers" ]]; then
  mkdir -p "$DEST/helpers"
  cp -f "$SOURCE/helpers/"* "$DEST/helpers/" 2>/dev/null || true
  echo "  Image helper installed."
else
  echo "  Warning: no helpers/ in this package." >&2
fi

echo ""
echo "Done. In Resolve: Workspace -> Scripts -> Utility -> Conform Sidekick"
echo "Restart Resolve, or use Scripts -> Reload if your version supports it."
