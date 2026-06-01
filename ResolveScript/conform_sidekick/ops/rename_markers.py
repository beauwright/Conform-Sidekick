"""Rename Clips From Markers - core operation.

Ported from davinci-resolve-scripts/Edit/RenameClipsFromMarkers.py. Operates in
integer frame space (marker frame ids, clip start/end), so no timecode library
is needed. The module-global ``resolve`` of the original is replaced by the
passed-in connection.
"""

from .. import timeline_filters as tf


def _noop():
    pass


def rename_clips_from_markers(
    conn,
    pattern_str,
    affix,
    prepend,
    use_inout=False,
    track_filter_spec="",
    dry_run=False,
    log=print,
    pump=_noop,
    pump_every=5,
    should_cancel=lambda: False,
):
    result = {
        "scanned": 0,
        "matched": 0,
        "skipped_no_match": 0,
        "renamed": 0,
        "rename_failures": 0,
        "skipped_out_of_scope": 0,
        "clip_errors": 0,
        "error": False,
        "cancelled": False,
    }

    pump_state = {"n": 0}
    effective_pump_every = max(1, int(pump_every))

    def maybe_pump():
        pump_state["n"] += 1
        if pump_state["n"] >= effective_pump_every:
            pump_state["n"] = 0
            pump()

    if not pattern_str:
        log("No regex pattern provided. Aborting.")
        result["error"] = True
        return result

    pattern, regex_err = tf.compile_regex(pattern_str)
    if regex_err is not None:
        log(f"Invalid regex: {regex_err}")
        result["error"] = True
        return result

    project = conn.get_project()
    if project is None:
        log("No project is currently open.")
        result["error"] = True
        return result

    timeline = conn.get_timeline()
    if timeline is None:
        log("No timeline is currently loaded.")
        result["error"] = True
        return result

    markers = timeline.GetMarkers() or {}
    if not markers:
        log("Current timeline has no markers.")
        result["error"] = True
        return result

    timeline_start = timeline.GetStartFrame()
    video_track_count = timeline.GetTrackCount("video") or 0

    track_set, track_err = tf.parse_track_filter(track_filter_spec, video_track_count)
    if track_err:
        log(f"{track_err}")
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

    track_indices = (
        sorted(track_set)
        if track_set is not None
        else list(range(1, video_track_count + 1))
    )

    items_by_track = {
        idx: (timeline.GetItemListInTrack("video", idx) or [])
        for idx in track_indices
    }

    header = "Rename Clips From Markers - DRY RUN" if dry_run else "Rename Clips From Markers"
    log(header)
    if scope_range is not None:
        log(f"  Scope: In/Out range [{scope_range[0]}-{scope_range[1]}] (absolute timeline frames)")
    if track_set is not None:
        log(f"  Tracks: V{sorted(track_set)} (filtered)")
    else:
        log(f"  Tracks: all {video_track_count} video track(s)")
    pump()

    cancelled = False
    for frame_id, info in markers.items():
        if should_cancel():
            cancelled = True
            break

        result["scanned"] += 1
        name = info.get("name") or ""
        note = info.get("note") or ""
        combined = (name + " " + note).strip()

        match = pattern.search(combined)
        if match is None:
            result["skipped_no_match"] += 1
            continue

        base = match.group(0)
        new_name = (affix + base) if prepend else (base + affix)
        result["matched"] += 1

        marker_start = timeline_start + float(frame_id)
        duration = float(info.get("duration") or 1)
        marker_end = marker_start + max(duration, 1.0)

        for track_idx, items in items_by_track.items():
            if cancelled:
                break
            for item in items:
                if should_cancel():
                    cancelled = True
                    break

                if item is None:
                    result["clip_errors"] += 1
                    log(
                        f"  [ERR]  V{track_idx} (marker {frame_id}): null clip "
                        f"object in track item list; skipping."
                    )
                    maybe_pump()
                    continue

                try:
                    item_start = item.GetStart()
                    item_end = item.GetEnd()
                except Exception as exc:
                    result["clip_errors"] += 1
                    log(
                        f"  [ERR]  V{track_idx} (marker {frame_id}): reading clip "
                        f"start/end raised {type(exc).__name__}: {exc}; skipping."
                    )
                    maybe_pump()
                    continue

                if item_start is None or item_end is None:
                    result["clip_errors"] += 1
                    log(
                        f"  [ERR]  V{track_idx} (marker {frame_id}): clip returned "
                        f"null start/end (start={item_start}, end={item_end}); skipping."
                    )
                    maybe_pump()
                    continue

                if not (item_start < marker_end and marker_start < item_end):
                    continue

                if scope_range is not None:
                    scope_in, scope_out = scope_range
                    if not (item_start < scope_out and scope_in < item_end):
                        result["skipped_out_of_scope"] += 1
                        continue

                try:
                    current_name = item.GetName() or "(unnamed)"
                except Exception:
                    current_name = "(unnamed)"
                location = f"V{track_idx} {item_start}-{item_end}"

                if dry_run:
                    result["renamed"] += 1
                    log(f"  [PLAN] {location}: '{current_name}' -> '{new_name}'")
                    maybe_pump()
                    continue

                set_name = getattr(item, "SetName", None)
                if not callable(set_name):
                    result["clip_errors"] += 1
                    log(
                        f"  [ERR]  {location}: '{current_name}' -> '{new_name}': "
                        f"clip has no callable SetName (got "
                        f"{type(set_name).__name__}); skipping. "
                        f"marker={frame_id}, base='{base}'."
                    )
                    maybe_pump()
                    continue

                try:
                    renamed_ok = set_name(new_name)
                except Exception as exc:
                    result["clip_errors"] += 1
                    log(
                        f"  [ERR]  {location}: '{current_name}' -> '{new_name}': "
                        f"SetName raised {type(exc).__name__}: {exc}; skipping. "
                        f"marker={frame_id}, base='{base}'."
                    )
                    maybe_pump()
                    continue

                if renamed_ok:
                    result["renamed"] += 1
                    log(f"  [OK]   {location}: '{current_name}' -> '{new_name}'")
                else:
                    result["rename_failures"] += 1
                    log(f"  [FAIL] {location}: '{current_name}' -> '{new_name}'")
                maybe_pump()

        if cancelled:
            break

    if cancelled:
        result["cancelled"] = True
        log("Run cancelled by user. Showing partial results below.")
        pump()

    summary_label = "Clips that would be renamed:" if dry_run else "Clips renamed:               "
    log("  Markers scanned:                " + str(result["scanned"]))
    log("  Markers matched by regex:       " + str(result["matched"]))
    log("  Markers skipped (no match):     " + str(result["skipped_no_match"]))
    log(f"  {summary_label}    {result['renamed']}")
    if result["rename_failures"]:
        log(f"  Rename failures:                {result['rename_failures']}")
    if result["clip_errors"]:
        log(f"  Clips skipped (errors):         {result['clip_errors']}")
    if result["skipped_out_of_scope"]:
        log(f"  Clips skipped (out of scope):   {result['skipped_out_of_scope']}")
    if dry_run:
        log("  (Dry run: no changes were applied.)")
    pump()

    return result
