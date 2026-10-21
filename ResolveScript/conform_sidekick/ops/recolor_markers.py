"""Recolor Markers - core operation.

Changes markers of one color to another on the current timeline (timeline
markers) and/or on its clips (clip markers on timeline items).

The scripting API has no call that sets a marker's color, so each marker is
deleted and added back at the same frame with the same name, note, duration and
custom data. ``AddMarker`` refuses a frame that already holds a marker, which
is why the delete has to come first. If the re-add fails, the original marker
is put back in its old color; only if that also fails is the marker lost, and
the log then prints everything needed to recreate it by hand.
"""

from .. import timecode_utils
from .. import timeline_filters as tf

# Resolve's marker palette (differs from the clip color palette).
MARKER_COLORS = [
    "Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple", "Fuchsia",
    "Rose", "Lavender", "Sky", "Mint", "Lemon", "Sand", "Cocoa", "Cream",
]
ANY_COLOR = "Any color"


def _noop():
    pass


def _frame_arg(frame):
    """GetMarkers keys come back as floats (96.0); hand back an int when whole."""
    try:
        as_float = float(frame)
    except (TypeError, ValueError):
        return frame
    return int(as_float) if as_float.is_integer() else as_float


def _duration_arg(info):
    try:
        return max(1, int(round(float(info.get("duration") or 1))))
    except (TypeError, ValueError):
        return 1


def _describe(info):
    name = info.get("name") or ""
    note = info.get("note") or ""
    bits = [f"'{name}'" if name else "(no name)"]
    if note:
        bits.append(f"note '{note}'")
    return " ".join(bits)


def wanted(info, from_color, to_color):
    """True when a marker should be recolored."""
    color = info.get("color") or ""
    if color == to_color:
        return False
    return from_color == ANY_COLOR or color == from_color


def recolor_marker_set(
    owner, where, from_color, to_color, dry_run, log, result,
    frame_ok=lambda frame: True,
):
    """Recolor the matching markers of one owner (Timeline or TimelineItem).

    ``where(frame)`` formats a log location; ``frame_ok(frame)`` scopes markers
    by position. Updates ``result`` counters in place.
    """
    try:
        markers = owner.GetMarkers() or {}
    except Exception as exc:
        log(f"  [SKIP] {where(None)}: GetMarkers raised: {exc}")
        return
    for frame in sorted(markers, key=lambda f: float(f)):
        info = markers[frame] or {}
        result["markers_scanned"] += 1
        if not wanted(info, from_color, to_color):
            continue
        if not frame_ok(frame):
            result["skipped_out_of_scope"] += 1
            continue
        old_color = info.get("color") or ""
        label = f"{where(frame)} {old_color} -> {to_color} {_describe(info)}"
        if dry_run:
            result["recolored"] += 1
            log(f"  [PLAN] {label}")
            continue

        frame_id = _frame_arg(frame)
        args = (info.get("name") or "", info.get("note") or "", _duration_arg(info),
                info.get("customData") or "")
        try:
            deleted = bool(owner.DeleteMarkerAtFrame(frame_id))
        except Exception as exc:
            deleted = False
            log(f"  [FAIL] {label}: DeleteMarkerAtFrame raised: {exc}")
        if not deleted:
            result["failed"] += 1
            log(f"  [FAIL] {label}: could not remove the old marker; left unchanged.")
            continue
        try:
            added = bool(owner.AddMarker(frame_id, to_color, *args))
        except Exception as exc:
            added = False
            log(f"  [FAIL] {label}: AddMarker raised: {exc}")
        if added:
            result["recolored"] += 1
            log(f"  [OK]   {label}")
            continue
        result["failed"] += 1
        try:
            restored = bool(owner.AddMarker(frame_id, old_color, *args))
        except Exception:
            restored = False
        if restored:
            log(f"  [FAIL] {label}: AddMarker refused {to_color}; original marker restored.")
        else:
            result["lost"] += 1
            log(
                f"  [LOST] {label}: could not re-add the marker. Recreate it by hand: "
                f"frame {frame_id}, color {old_color}, name {args[0]!r}, note {args[1]!r}, "
                f"duration {args[2]}."
            )


def recolor_markers(
    conn,
    from_color,
    to_color,
    timeline_markers=True,
    clip_markers=False,
    include_audio=False,
    use_inout=False,
    track_filter_spec="",
    dry_run=False,
    log=print,
    pump=_noop,
    should_cancel=lambda: False,
):
    result = {
        "markers_scanned": 0, "recolored": 0, "failed": 0, "lost": 0,
        "skipped_out_of_scope": 0, "clips_scanned": 0,
        "error": False, "cancelled": False,
    }
    if to_color not in MARKER_COLORS:
        log(f"Unknown target color: {to_color!r}.")
        result["error"] = True
        return result
    if from_color == to_color:
        log("The from and to colors are the same; nothing to do.")
        result["error"] = True
        return result
    if not (timeline_markers or clip_markers):
        log("Choose timeline markers, clip markers, or both.")
        result["error"] = True
        return result

    timeline = conn.get_timeline()
    if timeline is None:
        log("Open a timeline first.")
        result["error"] = True
        return result

    scope_range = None
    if use_inout:
        scope_range = tf.get_inout_range(timeline)
        if scope_range is None:
            log(
                "Use timeline In/Out is checked but no In/Out range is set on the "
                "current timeline. Set one with I/O (or uncheck the option) and re-run."
            )
            result["error"] = True
            return result

    try:
        timeline_start = int(timeline.GetStartFrame() or 0)
    except Exception:
        timeline_start = 0

    try:
        fps, drop = timecode_utils.get_timeline_framerate_and_dropframe(
            conn.get_project(), timeline
        )
    except Exception:
        fps, drop = "", False

    def at(absolute_frame):
        """Timecode for an absolute timeline frame (frame number as a fallback)."""
        if fps:
            try:
                return timecode_utils.frame_to_timecode(fps, drop, int(absolute_frame))
            except Exception:
                pass
        return str(int(absolute_frame))

    log("Recolor Markers - DRY RUN" if dry_run else "Recolor Markers")
    log(f"  Timeline: {timeline.GetName()}")
    log(f"  {from_color} -> {to_color}")
    if scope_range is not None:
        log(f"  Scope: In/Out range [{scope_range[0]}-{scope_range[1]}]")
    pump()

    if timeline_markers:
        def timeline_where(frame):
            return "Timeline" if frame is None else f"Timeline marker {at(timeline_start + float(frame))}"

        def timeline_frame_ok(frame):
            if scope_range is None:
                return True
            absolute = timeline_start + float(frame)
            return scope_range[0] <= absolute < scope_range[1]

        recolor_marker_set(timeline, timeline_where, from_color, to_color, dry_run,
                           log, result, timeline_frame_ok)
        pump()

    if clip_markers:
        kinds = [("video", "V")] + ([("audio", "A")] if include_audio else [])
        for kind, prefix in kinds:
            try:
                count = int(timeline.GetTrackCount(kind) or 0)
            except Exception:
                count = 0
            if kind == "video":
                track_set, track_err = tf.parse_track_filter(track_filter_spec, count)
                if track_err:
                    log(f"Tracks: {track_err}")
                    result["error"] = True
                    return result
            else:
                track_set = None
            tracks = sorted(track_set) if track_set is not None else range(1, count + 1)
            for track in tracks:
                try:
                    items = timeline.GetItemListInTrack(kind, track) or []
                except Exception:
                    items = []
                for item in items:
                    if should_cancel():
                        result["cancelled"] = True
                        break
                    try:
                        start, end = int(item.GetStart()), int(item.GetEnd())
                    except Exception:
                        start = end = None
                    if scope_range is not None and start is not None:
                        if not (start < scope_range[1] and scope_range[0] < end):
                            continue
                    result["clips_scanned"] += 1
                    try:
                        name = item.GetName() or ""
                    except Exception:
                        name = ""

                    def item_where(frame, _t=track, _s=start, _n=name, _p=prefix):
                        base = f"{_p}{_t} {at(_s) if _s is not None else ''} '{_n}'"
                        return base if frame is None else f"{base} clip marker @{_frame_arg(frame)}"

                    recolor_marker_set(item, item_where, from_color, to_color,
                                       dry_run, log, result)
                    if result["clips_scanned"] % 25 == 0:
                        pump()
                if result["cancelled"]:
                    break
            if result["cancelled"]:
                break

    if result["cancelled"]:
        log("Run cancelled by user. Showing partial results below.")

    log("")
    log(f"  Markers scanned:                 {result['markers_scanned']}")
    if clip_markers:
        log(f"  Clips scanned:                   {result['clips_scanned']}")
    if dry_run:
        log(f"  Would be recolored:              {result['recolored']}")
    else:
        log(f"  Recolored:                       {result['recolored']}")
    if result["skipped_out_of_scope"]:
        log(f"  Outside In/Out (skipped):        {result['skipped_out_of_scope']}")
    if result["failed"]:
        log(f"  Failures:                        {result['failed']}")
    if result["lost"]:
        log(f"  LOST (see [LOST] lines above):   {result['lost']}")
    if dry_run:
        log("  (Dry run: no changes were applied.)")
    pump()
    return result
