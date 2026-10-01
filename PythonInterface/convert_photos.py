"""Legacy entry point for the 1px even-resolution stretch.

The conversion lives in ``conform_sidekick.ops.odd_res`` (under
``ResolveScript/``). This module used to carry its own copy, which saved with
Pillow's defaults: JPEGs recompressed at quality 75 / 4:2:0, ICC profile and
EXIF orientation dropped, 16-bit RGB reduced to 8-bit. Both remaining callers
(``convert_photos_cli.py`` for the optional image helper, and the Tauri sidecar
in ``resolve_controller.py``) now go through the shared implementation.

When frozen with PyInstaller the package is bundled (build with
``--paths ../ResolveScript``); from a checkout it is found next door.
"""

import argparse
import os
import sys
from typing import Optional, Tuple

_PACKAGE_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "ResolveScript"
)
if os.path.isdir(_PACKAGE_ROOT) and _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

from conform_sidekick.ops.odd_res import convert_with_pillow  # noqa: E402


def convert_photo(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(output_path, None)`` or ``(None, reason)``."""
    return convert_with_pillow(file_path)


def convert_single_photo(file_path: str) -> Optional[str]:
    """Path to the converted copy beside the original, or None if not converted."""
    output_path, _error = convert_with_pillow(file_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description='Convert an image to have even dimensions')
    parser.add_argument('--file', type=str, required=True, help='Single image file to convert')
    args = parser.parse_args()
    print(convert_single_photo(args.file))


if __name__ == '__main__':
    main()
