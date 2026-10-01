"""Offline tests for the odd-resolution image fix (``ops.odd_res``).

The converted file replaces the original in the project, so it has to match the
source in everything except the extra pixel. A bare ``Image.save()`` does not:
it recompresses JPEGs at quality 75 / 4:2:0 and drops the ICC profile, EXIF
orientation and DPI. Two 16-bit cases are pinned as well:

- 16-bit RGB(A) is refused. Pillow has no such mode and would hand back 8-bit.
- Big-endian 16-bit greyscale (the usual TIFF byte order) is resampled
  correctly. Pillow's filters read ``I;16B`` as little-endian and scramble it.

Needs Pillow, which is the one third-party package the feature itself needs;
without it the whole suite reports SKIP.
"""

import glob
import os
import struct
import subprocess
import sys
import tempfile
import zlib

from _harness import Results

from conform_sidekick.ops import odd_res

W, H = 101, 51  # both odd

# Entry point of the optional PyInstaller image helper. It lives outside the
# shipped package, so it is absent from an installed copy.
HELPER_CLI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, os.pardir, "PythonInterface", "convert_photos_cli.py",
)


def _write_png16(path, color_type):
    """Minimal 16-bit PNG writer (Pillow cannot write 16-bit RGB). 2 = RGB."""
    channels = {0: 1, 2: 3, 6: 4}[color_type]

    def chunk(kind, data):
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    rows = b"".join(
        b"\x00" + b"".join(
            struct.pack(">H", (x * 257 + y * 131) % 65536) * channels
            for x in range(W)
        )
        for y in range(H)
    )
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 16, color_type, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(rows)))
        fh.write(chunk(b"IEND", b""))


def _outputs(folder):
    return sorted(glob.glob(os.path.join(folder, "*_converted_*")))


def run():
    r = Results("odd res")
    try:
        from PIL import Image, ImageCms, JpegImagePlugin
    except Exception as exc:
        r.skip("all odd-res conversion checks", f"Pillow not importable: {exc}")
        return r.summary()

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotated 90 degrees
    noise = Image.effect_noise((W, H), 60)
    base = Image.merge("RGB", [noise, noise.rotate(7), noise.rotate(13)])

    with tempfile.TemporaryDirectory() as tmp:
        def path(name):
            return os.path.join(tmp, name)

        def convert(name):
            out, err = odd_res.convert_single_photo(path(name))
            return (Image.open(out) if out else None), err

        r.section("JPEG keeps its quality and metadata")
        base.save(path("hq.jpg"), quality=98, subsampling=0, icc_profile=icc,
                  exif=exif, dpi=(300, 300))
        with open(path("hq.jpg"), "rb") as fh:
            original_bytes = fh.read()
        src = Image.open(path("hq.jpg"))
        out, err = convert("hq.jpg")
        r.check("converted", (err, out.size), (None, (W + 1, H + 1)))
        r.check("same quantization tables", out.quantization == src.quantization, True)
        r.check("chroma stays 4:4:4", JpegImagePlugin.get_sampling(out), 0)
        r.check("ICC profile kept", out.info.get("icc_profile") == icc, True)
        r.check("EXIF orientation kept", out.getexif().get(0x0112), 6)
        r.check("DPI kept", tuple(int(v) for v in out.info["dpi"]), (300, 300))
        with open(path("hq.jpg"), "rb") as fh:
            r.check("original file untouched", fh.read() == original_bytes, True)

        base.save(path("web.jpg"), quality=80, subsampling=2)
        src = Image.open(path("web.jpg"))
        out, err = convert("web.jpg")
        r.check("4:2:0 source stays 4:2:0, same tables",
                (JpegImagePlugin.get_sampling(out), out.quantization == src.quantization),
                (2, True))

        base.convert("L").save(path("grey.jpg"), quality=92)
        out, err = convert("grey.jpg")
        r.check("greyscale JPEG converts", (err, out.mode), (None, "L"))

        r.section("PNG and TIFF keep their metadata")
        base.save(path("pic.png"), icc_profile=icc, dpi=(144, 144))
        out, err = convert("pic.png")
        r.check("PNG ICC + DPI kept",
                (out.info.get("icc_profile") == icc,
                 tuple(round(v) for v in out.info["dpi"])),
                (True, (144, 144)))

        base.save(path("pic.tif"), compression="tiff_lzw", icc_profile=icc,
                  dpi=(300, 300), tiffinfo={274: 3})
        out, err = convert("pic.tif")
        r.check("TIFF compression, ICC, DPI and orientation kept",
                (out.info.get("compression"), out.info.get("icc_profile") == icc,
                 tuple(round(float(v)) for v in out.info["dpi"]), out.tag_v2.get(274)),
                ("tiff_lzw", True, (300, 300), 3))

        r.section("16-bit sources")
        before = len(_outputs(tmp))
        _write_png16(path("deep.png"), 2)
        out, err = convert("deep.png")
        r.check("16-bit RGB PNG refused", (out, "16-bit" in (err or "")), (None, True))
        _write_png16(path("deep_alpha.png"), 6)
        out, err = convert("deep_alpha.png")
        r.check("16-bit RGBA PNG refused", (out, "16-bit" in (err or "")), (None, True))
        r.check("no file written for a refusal", len(_outputs(tmp)), before)

        _write_png16(path("grey16.png"), 0)
        out, err = convert("grey16.png")
        r.check("16-bit greyscale PNG stays 16-bit", (err, out.mode), (None, "I;16"))

        # Horizontal ramp, 257 per pixel, stored big-endian as TIFF does.
        ramp = b"".join(struct.pack(">H", x * 257) for x in range(W)) * H
        Image.frombytes("I;16B", (W, H), ramp).save(path("grey16.tif"))
        src = Image.open(path("grey16.tif"))
        r.check("fixture really is big-endian 16-bit", src.mode, "I;16B")
        out, err = convert("grey16.tif")
        r.check("big-endian greyscale TIFF converts", (err, out.size), (None, (W + 1, H + 1)))
        r.check("...still 16-bit", out.tag_v2.get(258), (16,))
        # A scrambled resample lands thousands of levels off; a correct one
        # stays within a pixel's worth of the ramp.
        worst = max(
            abs(out.getpixel((x, H // 2)) - round(x * W / (W + 1)) * 257)
            for x in range(0, W + 1, 10)
        )
        r.check("...with the ramp intact (not byte-swapped)", worst <= 257, True)

        r.section("refusals")
        base.resize((W + 1, H + 1)).save(path("even.png"))
        out, err = convert("even.png")
        r.check("already even", (out, "already even" in (err or "")), (None, True))
        out, err = odd_res.convert_single_photo(path("missing.jpg"))
        r.check("missing file", (out, "not found" in (err or "")), (None, True))
        out, err = odd_res.convert_single_photo(path("clip.mov"))
        r.check("unsupported type", (out, "Unsupported" in (err or "")), (None, True))

        r.section("image helper entry point shares the converter")
        if not os.path.isfile(HELPER_CLI):
            r.skip("helper checks", "PythonInterface/ is not part of this copy")
        else:
            # The contract ops.odd_res._convert_via_helper relies on: exit
            # code, output path as the last stdout line, reason on stderr.
            def helper(name):
                return subprocess.run(
                    [sys.executable, HELPER_CLI, "--file", path(name)],
                    capture_output=True, text=True, timeout=120,
                )

            proc = helper("hq.jpg")
            lines = proc.stdout.split("\n")
            out_path = lines[-2] if len(lines) > 1 else ""
            r.check("exits 0 and prints an existing path",
                    (proc.returncode, os.path.isfile(out_path)), (0, True))
            if os.path.isfile(out_path):
                out = Image.open(out_path)
                r.check("same quality rules as the in-Resolve path",
                        (JpegImagePlugin.get_sampling(out),
                         out.info.get("icc_profile") == icc,
                         out.getexif().get(0x0112)),
                        (0, True, 6))
            proc = helper("deep.png")
            r.check("refusal exits 1 with the reason on stderr",
                    (proc.returncode, "16-bit" in proc.stderr), (1, True))
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
