#!/usr/bin/env bash
# Dev install: link launcher into Resolve's Utility folder and package into
# Application Support (outside the Scripts tree so only one menu entry appears).
#
#   ./link_to_resolve.sh

set -euo pipefail

src="$(cd "$(dirname "$0")" && pwd)"

case "$(uname -s)" in
  Darwin)
    utility="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
    support="$HOME/Library/Application Support/Conform Sidekick"
    ;;
  Linux)
    utility="$HOME/.local/share/DaVinciResolve/Fusion/Scripts/Utility"
    support="$HOME/.local/share/Conform Sidekick"
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac

mkdir -p "$utility" "$support"

link_path() {
  local dest="$1"
  local target="$2"
  rm -rf "$dest"
  ln -s "$target" "$dest"
  echo "LINK $dest -> $target"
}

# Remove legacy dev/install layout under Utility/.
if [[ -e "$utility/conform_sidekick" ]]; then
  echo "Removing legacy Utility/conform_sidekick..."
  rm -rf "$utility/conform_sidekick"
fi
if [[ -e "$utility/helpers" ]]; then
  rm -rf "$utility/helpers"
fi

link_path "$utility/Conform Sidekick.py" "$src/Conform Sidekick.py"
link_path "$support/conform_sidekick" "$src/conform_sidekick"

if [[ -d "$src/helpers" ]]; then
  link_path "$support/helpers" "$src/helpers"
fi

echo ""
echo "Launcher: $utility/Conform Sidekick.py"
echo "Package:  $support/conform_sidekick"
echo "Launch:   Workspace -> Scripts -> Utility -> Conform Sidekick"
