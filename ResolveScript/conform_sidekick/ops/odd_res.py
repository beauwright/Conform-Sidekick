"""Fix Odd Resolution Photos - image conversion.

Ported from PythonInterface/convert_photos.py. Detection is native (see
``ResolveAPI.find_odd_resolution``); this module does the 1px stretch into a new
file. The original Conform Sidekick shipped this as a PyInstaller helper exe
carrying Pillow / pillow_heif. Here we attempt the conversion in Resolve's own
Python via Pillow; if Pillow isn't importable we fail cleanly so the rest of the
feature still works and the user gets a clear message. (Bundling the image
helper for a Pillow-free Resolve Python is still a packaging TODO.)
"""

import os
import uuid

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".heic")


def _load_pillow():
    try:
        from PIL import Image
    except Exception as exc:
        return None, (
            "Pillow is not available in Resolve's Python, so images can't be "
            "converted here yet (the bundled image helper isn't installed). "
            f"[{exc}]"
        )
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        pass  # HEIC support is optional; other formats still work.
    return Image, None


def convert_single_photo(file_path):
    """Stretch an odd-dimension image by 1px into a new file beside the original.

    Returns ``(output_path_or_None, error_message_or_None)``. The original file
    is never modified.
    """
    if not file_path:
        return None, "No file path on this media item."

    Image, err = _load_pillow()
    if Image is None:
        return None, err

    ext = os.path.splitext(file_path)[1]
    if ext.lower() not in SUPPORTED_EXTS:
        return None, f"Unsupported file type '{ext}'."

    if not os.path.isfile(file_path):
        return None, f"File not found on disk: {file_path}"

    try:
        img = Image.open(file_path)
        width, height = img.size
    except Exception as exc:
        return None, f"Could not open image: {type(exc).__name__}: {exc}"

    new_width = width if width % 2 == 0 else width + 1
    new_height = height if height % 2 == 0 else height + 1
    if new_width == width and new_height == height:
        return None, "Resolution is already even; nothing to convert."

    directory = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(
        directory, f"{base_name}_converted_{uuid.uuid4().hex}{ext}"
    )

    try:
        resized = img.resize((new_width, new_height), Image.LANCZOS)
        resized.save(output_path)
    except Exception as exc:
        return None, f"Could not write converted image: {type(exc).__name__}: {exc}"

    return output_path, None
