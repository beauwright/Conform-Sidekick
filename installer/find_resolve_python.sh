#!/usr/bin/env bash
# Locate the Python interpreter DaVinci Resolve uses for Workspace scripts.
# Resolve does not use $PATH; it loads python.org installs from fixed locations.

set -euo pipefail

_resolve_python_version_key() {
  local py="$1"
  "$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null
}

_resolve_python_ok() {
  local py="$1"
  [[ -x "$py" ]] || return 1
  "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)' 2>/dev/null
}

find_resolve_python() {
  if [[ -n "${CONFORM_SIDEKICK_PYTHON:-}" ]]; then
    if _resolve_python_ok "$CONFORM_SIDEKICK_PYTHON"; then
      printf '%s\n' "$CONFORM_SIDEKICK_PYTHON"
      return 0
    fi
    echo "CONFORM_SIDEKICK_PYTHON is set but not usable: $CONFORM_SIDEKICK_PYTHON" >&2
    return 1
  fi

  local -a candidates=()
  local ver dir py

  case "$(uname -s)" in
    Darwin)
      if [[ -d /Library/Frameworks/Python.framework/Versions ]]; then
        while IFS= read -r ver; do
          candidates+=("/Library/Frameworks/Python.framework/Versions/$ver/bin/python3")
          candidates+=("/Library/Frameworks/Python.framework/Versions/$ver/bin/python")
        done < <(
          find /Library/Frameworks/Python.framework/Versions -maxdepth 1 -mindepth 1 \
            -type d ! -name 'Current' -exec basename {} \; 2>/dev/null \
            | sort -Vr
        )
      fi
      ;;
    Linux)
      candidates+=(
        /usr/bin/python3
        /usr/local/bin/python3
      )
      ;;
    *)
      echo "Unsupported OS for Resolve Python lookup: $(uname -s)" >&2
      return 1
      ;;
  esac

  for py in "${candidates[@]}"; do
    if _resolve_python_ok "$py"; then
      printf '%s\n' "$py"
      return 0
    fi
  done

  echo "Could not find Resolve's Python interpreter." >&2
  case "$(uname -s)" in
    Darwin)
      echo "Install Python from https://www.python.org/downloads/ (use the macOS installer)." >&2
      echo "Resolve loads /Library/Frameworks/Python.framework/Versions/<version>/, not pyenv or Homebrew." >&2
      ;;
    Linux)
      echo "Install Python 3.6+ system-wide (e.g. python3 package)." >&2
      ;;
  esac
  echo "Or set CONFORM_SIDEKICK_PYTHON to the full path of Resolve's Python." >&2
  return 1
}

install_resolve_python_deps() {
  local source_dir="$1"
  local req="$source_dir/requirements-resolve.txt"
  local py

  if [[ ! -f "$req" ]]; then
    echo "Missing dependency list: $req" >&2
    return 1
  fi

  py="$(find_resolve_python)" || return 1
  echo "Using Resolve Python: $py ($(_resolve_python_version_key "$py"))"

  if ! "$py" -m pip --version >/dev/null 2>&1; then
    echo "pip is not available for this Python; bootstrapping with ensurepip..." >&2
    "$py" -m ensurepip --upgrade >/dev/null
  fi

  echo "Installing Python dependencies for Fix Odd Resolution Photos..."
  "$py" -m pip install --disable-pip-version-check -r "$req"
  echo "Python dependencies installed."
}
