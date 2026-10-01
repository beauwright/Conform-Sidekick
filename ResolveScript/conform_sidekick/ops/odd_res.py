"""Fix Odd Resolution Photos - image conversion.

Detection is native (see ``ResolveAPI.find_odd_resolution``); this module does
the 1px stretch into a new file. It is the only implementation: the legacy
``PythonInterface/convert_photos*.py`` entry points call
:func:`convert_with_pillow` rather than carrying their own copy.

Conversion order:

1. Pillow in Resolve's Python (when importable).
2. Optional PyInstaller helper in ``ResolveScript/helpers/`` (see README).
"""

import os
import subprocess
import sys
import uuid

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".heic")

# Built helper names (see PythonInterface/build_convert_photos_helper.*).
_HELPER_NAMES = {
    "win32": (
        "convert_photos_helper.exe",
        "convert_photos_helper-x86_64-pc-windows-msvc.exe",
    ),
    "darwin": (
        "convert_photos_helper",
        "convert_photos_helper-x86_64-apple-darwin",
    ),
    "linux": (
        "convert_photos_helper",
        "convert_photos_helper-x86_64-unknown-linux-gnu",
    ),
}


def _platform_key():
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _realpath(path):
    try:
        return os.path.realpath(path)
    except Exception:
        return path


def _resolve_script_roots():
    """Directories where ``helpers/`` or a helper exe may live."""
    roots = []
    try:
        from ..paths import get_support_home

        install_root = get_support_home()
        roots.append(install_root)
        roots.append(_realpath(install_root))
    except Exception:
        pass
    env = os.environ.get("CONFORM_SIDEKICK_HELPER", "").strip()
    if env:
        roots.append(os.path.dirname(os.path.abspath(env)))
    seen = set()
    out = []
    for root in roots:
        if root and root not in seen:
            seen.add(root)
            out.append(root)
    return out


def _helper_candidate_paths():
    names = _HELPER_NAMES.get(_platform_key(), _HELPER_NAMES["linux"])
    env = os.environ.get("CONFORM_SIDEKICK_HELPER", "").strip()
    if env:
        yield os.path.abspath(env)
    for root in _resolve_script_roots():
        for name in names:
            yield os.path.join(root, "helpers", name)
            yield os.path.join(root, name)


def find_helper_executable():
    """Return the path to the bundled convert helper, or None."""
    for path in _helper_candidate_paths():
        if path and os.path.isfile(path):
            return path
    return None


def _load_pillow():
    try:
        from PIL import Image
    except Exception as exc:
        return None, (
            "Pillow is not available in Resolve's Python "
            f"({exc})."
        )
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        pass  # HEIC support is optional; other formats still work.
    return Image, None


# Used when a JPEG's own quantization tables cannot be reused.
_JPEG_FALLBACK = {"quality": 95, "subsampling": 0}
_TIFF_ORIENTATION = 274


def _resample_safe(img, Image):
    """Return *img* in a mode Pillow resamples correctly.

    Pillow's filters read ``I;16B`` (big-endian 16-bit greyscale, the usual
    TIFF byte order) as little-endian, which scrambles every pixel; only
    NEAREST is unaffected. ``convert("I;16")`` clips to 255, so the bytes are
    re-read in the native order instead.
    """
    if img.mode != "I;16B":
        return img
    return Image.frombytes("I;16", img.size, img.tobytes(), "raw", "I;16B")


def _depth_reduced(img):
    """True when Pillow decodes a 16-bit-per-channel file into an 8-bit mode.

    Pillow has no 16-bit RGB(A) mode, so such a PNG / TIFF opens as plain
    ``RGB`` and would be written back at 8 bits. The decoder's raw mode (e.g.
    ``RGB;16B``) is the only place the source depth still shows; 16-bit
    greyscale opens as ``I;16`` and survives. Must be called before the image
    data is loaded, which empties ``img.tile``.
    """
    if ";" in img.mode or img.mode in ("I", "F"):
        return False
    try:
        if int(img.info.get("bit_depth") or 8) > 8:  # set by pillow_heif
            return True
    except (TypeError, ValueError):
        pass
    for tile in getattr(img, "tile", None) or []:
        args = tile[3] if len(tile) > 3 else None
        if not isinstance(args, (tuple, list)):
            args = (args,)
        if any(isinstance(arg, str) and ";16" in arg for arg in args):
            return True
    return False


def _save_options(img, ext):
    """``Image.save`` arguments that carry the source's quality and metadata.

    A bare ``save()`` writes Pillow's defaults: a JPEG is recompressed at
    quality 75 with 4:2:0 chroma, and the ICC profile, EXIF (orientation
    included) and DPI are dropped. The project is repointed at the result, so
    it has to match the source in everything but the extra pixel.
    """
    info = img.info
    options = {}
    for key in ("icc_profile", "dpi"):
        if info.get(key):
            options[key] = info[key]

    ext = ext.lower()
    if ext in (".tif", ".tiff"):
        # No EXIF pass-through here: a TIFF's "EXIF" is its own IFD, layout
        # tags and all, which must not be copied onto the resized image.
        if info.get("compression"):
            options["compression"] = info["compression"]
        try:
            orientation = img.tag_v2.get(_TIFF_ORIENTATION)
        except Exception:
            orientation = None
        if orientation and orientation != 1:
            options["tiffinfo"] = {_TIFF_ORIENTATION: orientation}
        return options

    if info.get("exif"):
        options["exif"] = info["exif"]
    if ext in (".jpg", ".jpeg"):
        qtables = getattr(img, "quantization", None)
        if qtables:
            # The source's own quantization tables and chroma layout: what
            # quality="keep" does, which Pillow refuses on a resized image.
            from PIL import JpegImagePlugin

            options["qtables"] = qtables
            options["subsampling"] = JpegImagePlugin.get_sampling(img)
        else:
            options.update(_JPEG_FALLBACK)
    elif ext == ".heic":
        options["quality"] = 95
    return options


def _convert_in_process(file_path, Image):
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

    if _depth_reduced(img):
        return None, (
            "16-bit color image: converting it here would reduce it to 8-bit, "
            "so it was left alone. Resize it in an image editor instead."
        )

    directory = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(
        directory, f"{base_name}_converted_{uuid.uuid4().hex}{ext}"
    )

    try:
        options = _save_options(img, ext)
        resized = _resample_safe(img, Image).resize(
            (new_width, new_height), Image.LANCZOS
        )
        try:
            resized.save(output_path, **options)
        except Exception:
            if "qtables" not in options:
                raise
            # Pillow rejects some sources' tables (e.g. 16-bit entries).
            options.pop("qtables")
            options.update(_JPEG_FALLBACK)
            resized.save(output_path, **options)
    except Exception as exc:
        try:
            os.remove(output_path)  # never leave a partial file beside the source
        except OSError:
            pass
        return None, f"Could not write converted image: {type(exc).__name__}: {exc}"

    return output_path, None


def _convert_via_helper(file_path):
    helper = find_helper_executable()
    if not helper:
        return None, (
            "No image helper found. Build PythonInterface/convert_photos_cli "
            "with build_convert_photos_helper.ps1 (or .sh) and copy the exe "
            "into ResolveScript/helpers/, or set CONFORM_SIDEKICK_HELPER."
        )

    if not os.path.isfile(file_path):
        return None, f"File not found on disk: {file_path}"

    kwargs = {
        "args": [helper, "--file", file_path],
        "capture_output": True,
        "text": True,
        "timeout": 600,
    }
    if sys.platform.startswith("win"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        proc = subprocess.run(**kwargs)
    except subprocess.TimeoutExpired:
        return None, "Image helper timed out."
    except Exception as exc:
        return None, f"Image helper failed to run: {type(exc).__name__}: {exc}"

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return None, detail or "Image helper exited with an error."

    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return None, "Image helper did not return an output path."
    output_path = lines[-1]
    if not os.path.isfile(output_path):
        return None, f"Image helper returned a missing file: {output_path}"
    return output_path, None


def convert_with_pillow(file_path):
    """In-process conversion only; same return shape as :func:`convert_single_photo`.

    For the standalone helper, which bundles its own Pillow and must never go
    looking for a helper executable (it would find itself).
    """
    if not file_path:
        return None, "No file path given."
    Image, pillow_err = _load_pillow()
    if Image is None:
        return None, pillow_err
    return _convert_in_process(file_path, Image)


def convert_single_photo(file_path):
    """Stretch an odd-dimension image by 1px into a new file beside the original.

    Returns ``(output_path_or_None, error_message_or_None)``. The original file
    is never modified.
    """
    if not file_path:
        return None, "No file path on this media item."

    Image, pillow_err = _load_pillow()
    if Image is not None:
        return _convert_in_process(file_path, Image)

    output_path, helper_err = _convert_via_helper(file_path)
    if output_path:
        return output_path, None

    parts = [pillow_err]
    if helper_err:
        parts.append(helper_err)
    return None, " ".join(p for p in parts if p)
