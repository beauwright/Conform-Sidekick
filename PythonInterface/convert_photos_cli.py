"""PyInstaller entry point for the odd-resolution image helper.

No Resolve dependency — only Pillow + pillow_heif (bundled by PyInstaller).
Stdout: absolute path to the converted file on success.
Stderr: short error message on failure. Exit code 0 / 1.
"""

import argparse
import sys

from convert_photos import convert_single_photo


def main():
    parser = argparse.ArgumentParser(description="Stretch odd image dimensions by 1px")
    parser.add_argument("--file", required=True, help="Image file to convert")
    args = parser.parse_args()

    result = convert_single_photo(args.file)
    if result:
        print(result)
        return 0
    print("Conversion failed (unsupported type, missing file, or already even).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
