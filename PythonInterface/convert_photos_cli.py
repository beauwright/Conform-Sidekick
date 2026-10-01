"""PyInstaller entry point for the odd-resolution image helper.

No Resolve dependency — only Pillow + pillow_heif (bundled by PyInstaller) and
the shared converter in ``conform_sidekick.ops.odd_res``.
Stdout: absolute path to the converted file on success.
Stderr: the reason on failure (shown in the Conform Sidekick log). Exit code 0 / 1.
"""

import argparse
import sys

from convert_photos import convert_photo


def main():
    parser = argparse.ArgumentParser(description="Stretch odd image dimensions by 1px")
    parser.add_argument("--file", required=True, help="Image file to convert")
    args = parser.parse_args()

    output_path, error = convert_photo(args.file)
    if output_path:
        print(output_path)
        return 0
    print(error or "Conversion failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
