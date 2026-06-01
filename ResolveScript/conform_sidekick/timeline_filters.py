"""Shared timeline scoping / filter helpers.

These were duplicated across the davinci-resolve-scripts (Rename Clips From
Markers, Bulk Enable/Disable Nodes, Lay Matching Bin Clips). Centralised here so
every ported feature parses track / index / layer specs and In/Out ranges
identically.
"""

import re


# DaVinci Resolve's standard 16-color clip palette, plus an explicit sentinel
# for "never tagged" (TimelineItem.GetClipColor returns "").
CLIP_COLORS = [
    "Orange", "Apricot", "Yellow", "Lime",
    "Olive", "Green", "Teal", "Navy",
    "Blue", "Purple", "Violet", "Pink",
    "Tan", "Beige", "Brown", "Chocolate",
]
UNCOLORED_SENTINEL = "(Uncolored)"

# Video attribute keys copied from an original TimelineItem to a newly-laid one
# (Lay Matching Bin Clips). Read-only / context-disabled keys are tolerated via
# try/except in the copy loop so they never abort a run.
VIDEO_ATTR_KEYS = [
    "Pan", "Tilt", "ZoomX", "ZoomY", "ZoomGang",
    "RotationAngle", "AnchorPointX", "AnchorPointY",
    "Pitch", "Yaw", "FlipX", "FlipY",
    "CropLeft", "CropRight", "CropTop", "CropBottom",
    "CropSoftness", "CropRetain",
    "DynamicZoomEase",
    "CompositeMode", "Opacity",
    "Distortion",
    "RetimeProcess", "MotionEstimation",
    "Scaling", "ResizeFilter",
]


def parse_int_spec(spec, max_index=None, what="index"):
    """Parse a comma/range spec ("1,3-5") into a sorted set of 1-based ints.

    Returns ``(set_or_None, error_message_or_None)``. ``None`` set means "no
    spec given" so callers can fast-path. Out-of-range entries (when
    ``max_index`` is a positive int) are reported as an error rather than
    silently dropped.
    """
    if spec is None:
        return None, None
    spec = spec.strip()
    if not spec:
        return None, None

    out = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo_str, _, hi_str = chunk.partition("-")
            try:
                lo_i = int(lo_str.strip())
                hi_i = int(hi_str.strip())
            except ValueError:
                return None, f"Invalid range '{chunk}' in {what}."
            if lo_i > hi_i:
                lo_i, hi_i = hi_i, lo_i
            for i in range(lo_i, hi_i + 1):
                out.add(i)
        else:
            try:
                out.add(int(chunk))
            except ValueError:
                return None, f"Invalid {what} '{chunk}'."

    if not out:
        return None, None

    if max_index is not None and max_index > 0:
        invalid = sorted(i for i in out if i < 1 or i > max_index)
        if invalid:
            return (
                None,
                f"{what.capitalize()} references out-of-range indices {invalid}; "
                f"valid range is 1..{max_index}.",
            )

    return out, None


def parse_track_filter(spec, max_track):
    """Parse a video-track filter spec into a sorted set of 1-based indices."""
    return parse_int_spec(spec, max_index=max_track, what="track filter")


def resolve_layer_spec(spec, max_layers):
    """Translate a node-stack layer spec into the list of layer indices to hit.

    blank/None -> [1]; "all"/"*" -> [1..max_layers]; otherwise a comma/range
    spec. Returns ``(layer_list_or_None, error_message_or_None)``.
    """
    if max_layers is None or max_layers < 1:
        max_layers = 1
    if spec is None or not spec.strip():
        return [1], None
    spec = spec.strip().lower()
    if spec in ("all", "*"):
        return list(range(1, max_layers + 1)), None
    layer_set, err = parse_int_spec(spec, max_index=max_layers, what="layer")
    if err is not None:
        return None, err
    if not layer_set:
        return [1], None
    return sorted(layer_set), None


def get_inout_range(timeline):
    """Return the timeline In/Out mark as absolute frame numbers, or None.

    ``GetMarkInOut()`` values have historically been reported either as
    absolute frames or as offsets from ``GetStartFrame()``; we normalise both
    onto the absolute numbering that ``TimelineItem.GetStart()/GetEnd()`` use.
    """
    try:
        marks = timeline.GetMarkInOut() or {}
    except Exception:
        return None
    bucket = marks.get("video") or marks.get("audio")
    if not bucket or "in" not in bucket or "out" not in bucket:
        return None
    try:
        in_val = int(bucket["in"])
        out_val = int(bucket["out"])
    except (TypeError, ValueError):
        return None
    try:
        start = int(timeline.GetStartFrame() or 0)
    except Exception:
        start = 0
    if in_val < start:
        in_val += start
    if out_val < start:
        out_val += start
    if out_val <= in_val:
        return None
    return in_val, out_val


def compile_regex(pattern_str):
    """Compile a regex, returning ``(pattern_or_None, error_message_or_None)``."""
    if not pattern_str:
        return None, None
    try:
        return re.compile(pattern_str), None
    except re.error as exc:
        return None, str(exc)


def match_name(pattern, text):
    """True if the regex matches text; True when pattern is None (no filter)."""
    if pattern is None:
        return True
    if not text:
        return False
    return pattern.search(text) is not None


def match_key(pattern, text):
    """Return the pairing key for text: capture group 1 if the regex has
    groups, otherwise the whole match. None when there's no match."""
    if not text:
        return None
    m = pattern.search(text)
    if m is None:
        return None
    if m.groups():
        return m.group(1)
    return m.group(0)
