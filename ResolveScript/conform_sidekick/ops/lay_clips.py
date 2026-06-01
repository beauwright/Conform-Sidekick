"""Lay Matching Bin Clips On New Track - core operation.

Ported from davinci-resolve-scripts/Edit/LayMatchingBinClipsOnNewTrack.py. The
hand-rolled SMPTE / drop-frame math (``_tc_to_frames``) is replaced with the
vendored ``timecode`` library via :mod:`conform_sidekick.timecode_utils`, which
is the suspected fix for the intermittent -1 source-frame offset bug. The
module-global ``resolve`` is replaced by the passed-in connection.
"""

from .. import timecode_utils
from .. import timeline_filters as tf


def _noop():
    pass


def _is_media_clip(mpi):
    """Filter out timelines / generators / adjustment clips living in the bin."""
    try:
        clip_type = mpi.GetClipProperty("Type") or ""
    except Exception:
        return True
    bad = {"Timeline", "Generator", "Fusion Generator", "Adjustment Clip"}
    return clip_type not in bad


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _start_tc_frames(frame_rate_str, tc_str):
    """Return the absolute frame index for a source 'Start TC', or None.

    Uses the timecode library; drop-frame is inferred from the ';' separator in
    the timecode string. The library counts frames 1-based and our helper
    returns a 0-based index, but since these values are only ever used as a
    *delta* between two clips' Start TC the base cancels out.
    """
    if not tc_str or not isinstance(tc_str, str):
        return None
    drop_frame = ";" in tc_str
    try:
        return timecode_utils.timecode_to_frames(frame_rate_str, drop_frame, tc_str)
    except Exception:
        return None


def _translate_source_range(orig_tli, new_mpi, frame_rate_str):
    """Translate the original TLI's source frame range into the new MPI's
    numbering, anchored on Start TC (falling back to file-offset)."""
    src_start = orig_tli.GetSourceStartFrame()
    src_end = orig_tli.GetSourceEndFrame()

    orig_mpi = None
    try:
        orig_mpi = orig_tli.GetMediaPoolItem()
    except Exception:
        orig_mpi = None

    orig_mpi_start = 0
    if orig_mpi is not None:
        try:
            orig_mpi_start = _to_int(orig_mpi.GetClipProperty("Start"))
        except Exception:
            orig_mpi_start = 0
    try:
        new_mpi_start = _to_int(new_mpi.GetClipProperty("Start"))
    except Exception:
        new_mpi_start = 0

    file_offset_in = src_start - orig_mpi_start
    file_offset_out = src_end - orig_mpi_start

    orig_tc_str = None
    new_tc_str = None
    try:
        orig_tc_str = orig_mpi.GetClipProperty("Start TC") if orig_mpi else None
    except Exception:
        orig_tc_str = None
    try:
        new_tc_str = new_mpi.GetClipProperty("Start TC")
    except Exception:
        new_tc_str = None

    orig_tc_frames = _start_tc_frames(frame_rate_str, orig_tc_str)
    new_tc_frames = _start_tc_frames(frame_rate_str, new_tc_str)

    if orig_tc_frames is not None and new_tc_frames is not None:
        delta_tc = orig_tc_frames - new_tc_frames
        new_start_frame = new_mpi_start + file_offset_in + delta_tc
        new_end_frame = new_mpi_start + file_offset_out + delta_tc
        method = "tc"
    else:
        delta_tc = 0
        new_start_frame = new_mpi_start + file_offset_in
        new_end_frame = new_mpi_start + file_offset_out
        method = "file-offset"

    return {
        "method": method,
        "new_start_frame": new_start_frame,
        "new_end_frame": new_end_frame,
        "orig_src_start": src_start,
        "orig_src_end": src_end,
        "file_offset_in": file_offset_in,
        "file_offset_out": file_offset_out,
        "orig_mpi_start": orig_mpi_start,
        "new_mpi_start": new_mpi_start,
        "orig_tc_str": orig_tc_str,
        "new_tc_str": new_tc_str,
        "orig_tc_frames": orig_tc_frames,
        "new_tc_frames": new_tc_frames,
        "delta_tc": delta_tc,
    }


def _reacquire_appended_tli(timeline, track_index, record_frame, hint=None):
    """Walk the timeline to recover the just-placed TimelineItem (the
    AppendToTimeline return value can't reliably accept SetProperty/CopyGrades)."""
    items = timeline.GetItemListInTrack("video", track_index) or []
    if not items:
        return None

    hint_id = None
    if hint is not None:
        try:
            hint_id = hint.GetUniqueId()
        except Exception:
            hint_id = None

    if hint_id:
        for item in items:
            try:
                if item.GetUniqueId() == hint_id:
                    return item
            except Exception:
                continue

    for item in items:
        try:
            if int(item.GetStart()) == int(record_frame):
                return item
        except Exception:
            continue

    return None


def _clamp_to_new_mpi(new_start, new_end, new_mpi, log, location_label):
    try:
        mpi_start = _to_int(new_mpi.GetClipProperty("Start"))
        mpi_end = _to_int(new_mpi.GetClipProperty("End"))
    except Exception:
        return new_start, new_end

    if mpi_end <= mpi_start:
        return new_start, new_end

    clamped_start = max(mpi_start, min(new_start, mpi_end))
    clamped_end = max(mpi_start, min(new_end, mpi_end))

    if clamped_start != new_start or clamped_end != new_end:
        log(
            f"         [warn] {location_label}: requested src [{new_start}-{new_end}] is outside new MPI extents [{mpi_start}-{mpi_end}]; clamped to [{clamped_start}-{clamped_end}]."
        )

    return clamped_start, clamped_end


def lay_matching_bin_clips(
    conn,
    pattern_str,
    new_track_name,
    clip_color,
    copy_grade,
    copy_attrs,
    disable_originals,
    skip_disabled_tlis,
    use_inout=False,
    track_filter_spec="",
    dry_run=False,
    add_offset_track=False,
    offset_track_frames=-1,
    log=print,
    pump=_noop,
    pump_every=5,
    should_cancel=lambda: False,
):
    result = {
        "bin_scanned": 0,
        "bin_matched": 0,
        "bin_duplicates_skipped": 0,
        "bin_unused": 0,
        "tli_scanned": 0,
        "tli_skipped_disabled": 0,
        "tli_skipped_out_of_scope": 0,
        "tli_matched": 0,
        "tli_unpaired": 0,
        "laid": 0,
        "overlap_skipped": 0,
        "append_failures": 0,
        "originals_disabled": 0,
        "grades_copied": 0,
        "groups_assigned": 0,
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

    resolve = conn.resolve
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

    media_pool = project.GetMediaPool()
    if media_pool is None:
        log("Could not access Media Pool.")
        result["error"] = True
        return result

    current_folder = media_pool.GetCurrentFolder()
    if current_folder is None:
        log("No bin is currently opened in the Media Pool.")
        result["error"] = True
        return result

    frame_rate_str, _drop_frame = timecode_utils.get_timeline_framerate_and_dropframe(
        project, timeline
    )
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

    header = "Lay Matching Bin Clips On New Track - DRY RUN" if dry_run else "Lay Matching Bin Clips On New Track"
    log(header)
    log(f"  Open bin: {current_folder.GetName()}")
    log(f"  Timeline: {timeline.GetName()} @ {frame_rate_str} fps")
    if scope_range is not None:
        log(f"  Scope: In/Out range [{scope_range[0]}-{scope_range[1]}] (absolute timeline frames)")
    if track_set is not None:
        log(f"  Tracks: V{sorted(track_set)} (filtered)")
    else:
        log(f"  Tracks: all {video_track_count} video track(s)")
    pump()

    # 1) Scan the open bin and build a key -> MediaPoolItem map.
    bin_clips = current_folder.GetClipList() or []
    key_to_mpi = {}
    for mpi in bin_clips:
        if should_cancel():
            result["cancelled"] = True
            break
        result["bin_scanned"] += 1
        if not _is_media_clip(mpi):
            continue
        name = mpi.GetName() or ""
        key = tf.match_key(pattern, name)
        if key is None:
            continue
        if key in key_to_mpi:
            result["bin_duplicates_skipped"] += 1
            log(f"  [WARN] Bin has multiple matches for key '{key}'. Keeping first; ignoring '{name}'.")
            continue
        key_to_mpi[key] = mpi
        result["bin_matched"] += 1
        maybe_pump()

    if result["cancelled"]:
        log("Run cancelled by user.")
        pump()
        return result

    if not key_to_mpi:
        log("No MediaPoolItems in the open bin matched the regex. Nothing to do.")
        pump()
        return result

    # 2) Collect matching TimelineItems with their pairing keys (dedupe by
    # record range + key so a plate on V1+V2 generates one overlay).
    track_indices = (
        sorted(track_set)
        if track_set is not None
        else list(range(1, video_track_count + 1))
    )
    pairings = []
    seen_record_keys = set()
    for track_idx in track_indices:
        if should_cancel():
            result["cancelled"] = True
            break
        items = timeline.GetItemListInTrack("video", track_idx) or []
        for item in items:
            if should_cancel():
                result["cancelled"] = True
                break
            result["tli_scanned"] += 1
            if skip_disabled_tlis:
                try:
                    enabled = item.GetClipEnabled()
                except Exception:
                    enabled = True
                if not enabled:
                    result["tli_skipped_disabled"] += 1
                    continue
            if scope_range is not None:
                try:
                    item_start = item.GetStart()
                    item_end = item.GetEnd()
                except Exception:
                    item_start = None
                    item_end = None
                if item_start is None or item_end is None:
                    pass
                else:
                    scope_in, scope_out = scope_range
                    if not (item_start < scope_out and scope_in < item_end):
                        result["tli_skipped_out_of_scope"] += 1
                        continue
            name = item.GetName() or ""
            key = tf.match_key(pattern, name)
            if key is None:
                continue
            result["tli_matched"] += 1
            mpi = key_to_mpi.get(key)
            if mpi is None:
                result["tli_unpaired"] += 1
                continue
            dedupe_key = (key, item.GetStart(), item.GetEnd())
            if dedupe_key in seen_record_keys:
                continue
            seen_record_keys.add(dedupe_key)
            pairings.append((item, track_idx, mpi, key))
            maybe_pump()
        if result["cancelled"]:
            break

    if result["cancelled"]:
        log("Run cancelled by user.")
        pump()
        return result

    if not pairings:
        for key in sorted(key_to_mpi):
            mpi = key_to_mpi[key]
            log(
                f"  [WARN] Bin item '{mpi.GetName()}' (key='{key}') was not laid: "
                f"no matching TimelineItem on the current timeline."
            )
        log("No TimelineItems could be paired with a bin item. Nothing to lay.")
        pump()
        return result

    # 3) Sort by record frame so overlap handling is deterministic.
    pairings.sort(key=lambda p: p[0].GetStart())

    laid_bin_keys = set()

    def _format_remap(remap, source_offset=0):
        offset_suffix = f" ({source_offset:+d}f comparison shift)" if source_offset else ""
        base = (
            f"orig src [{remap['orig_src_start']}-{remap['orig_src_end']}] "
            f"@Start={remap['orig_mpi_start']}"
        )
        if remap["method"] == "tc":
            return (
                f"src remap (TC){offset_suffix}: {base} "
                f"TC={remap['orig_tc_str']} ({remap['orig_tc_frames']}f) -> "
                f"new TC={remap['new_tc_str']} ({remap['new_tc_frames']}f) "
                f"delta={remap['delta_tc']}f -> "
                f"new src [{remap['new_start_frame'] + source_offset}-"
                f"{remap['new_end_frame'] + source_offset}] @Start={remap['new_mpi_start']}"
            )
        return (
            f"src remap (file-offset, no Start TC available){offset_suffix}: {base} -> "
            f"new src [{remap['new_start_frame'] + source_offset}-"
            f"{remap['new_end_frame'] + source_offset}] @Start={remap['new_mpi_start']}"
        )

    def _lay_pairs_on_track(target_track_index, target_track_name, source_offset, role_label):
        if not dry_run:
            if not timeline.AddTrack("video"):
                log(f"Failed to add a new video track for {role_label} pass. Aborting.")
                result["error"] = True
                return False
            if target_track_name:
                try:
                    timeline.SetTrackName("video", target_track_index, target_track_name)
                except Exception:
                    pass

        offset_label = f" with source offset {source_offset:+d}f" if source_offset else ""
        log(
            f"  {role_label.capitalize()} track: V{target_track_index}"
            + (f" ('{target_track_name}')" if target_track_name else "")
            + offset_label
        )
        pump()

        used_ranges = []

        def overlaps(start, end):
            for s, e in used_ranges:
                if start < e and s < end:
                    return True
            return False

        for original_tli, src_track, mpi, key in pairings:
            if should_cancel():
                result["cancelled"] = True
                break

            record_frame = original_tli.GetStart()
            end_record_frame = original_tli.GetEnd()

            original_name = original_tli.GetName() or "(unnamed)"
            location = f"V{src_track} {record_frame}-{end_record_frame}"
            mpi_name = mpi.GetName() or "(unnamed)"

            if overlaps(record_frame, end_record_frame):
                result["overlap_skipped"] += 1
                log(
                    f"  [SKIP] {location}: '{original_name}' (key='{key}') -> "
                    f"'{mpi_name}' would overlap a previously laid clip on "
                    f"V{target_track_index}."
                )
                maybe_pump()
                continue

            remap = _translate_source_range(original_tli, mpi, frame_rate_str)
            new_source_start = remap["new_start_frame"] + source_offset
            new_source_end = remap["new_end_frame"] + source_offset

            new_source_start, new_source_end = _clamp_to_new_mpi(
                new_source_start, new_source_end, mpi, log, location
            )

            if dry_run:
                result["laid"] += 1
                used_ranges.append((record_frame, end_record_frame))
                laid_bin_keys.add(key)
                log(
                    f"  [PLAN] {location}: '{original_name}' (key='{key}') -> "
                    f"'{mpi_name}' on V{target_track_index} ({role_label})"
                )
                log(f"         {_format_remap(remap, source_offset)}")
                maybe_pump()
                continue

            clip_info = {
                "mediaPoolItem": mpi,
                "startFrame": new_source_start,
                "endFrame": new_source_end,
                "trackIndex": target_track_index,
                "recordFrame": record_frame,
            }
            try:
                appended = media_pool.AppendToTimeline([clip_info]) or []
            except Exception as exc:
                appended = []
                log(f"  [FAIL] {location}: AppendToTimeline raised: {exc}")

            if not appended:
                result["append_failures"] += 1
                log(
                    f"  [FAIL] {location}: could not place '{mpi_name}' "
                    f"on V{target_track_index}."
                )
                maybe_pump()
                continue

            recovered = _reacquire_appended_tli(
                timeline, target_track_index, record_frame, hint=appended[0]
            )
            new_tli = recovered if recovered is not None else appended[0]

            result["laid"] += 1
            used_ranges.append((record_frame, end_record_frame))
            laid_bin_keys.add(key)
            log(
                f"  [OK]   {location}: '{original_name}' -> '{mpi_name}' "
                f"on V{target_track_index} ({role_label})"
            )
            log(f"         {_format_remap(remap, source_offset)}")
            if recovered is None:
                log(
                    "         [warn] Could not reacquire the new TimelineItem;"
                    " grade/attr copies may not stick."
                )

            if clip_color:
                try:
                    new_tli.SetClipColor(clip_color)
                except Exception as exc:
                    log(f"         [warn] SetClipColor('{clip_color}') failed: {exc}")

            if copy_grade:
                try:
                    orig_group = original_tli.GetColorGroup()
                except Exception as exc:
                    orig_group = None
                    log(f"         [warn] GetColorGroup raised: {exc}")
                if orig_group is not None:
                    try:
                        if new_tli.AssignToColorGroup(orig_group):
                            result["groups_assigned"] += 1
                            try:
                                group_name = orig_group.GetName() or "(unnamed group)"
                            except Exception:
                                group_name = "(unnamed group)"
                            log(f"         color group: assigned to '{group_name}'")
                        else:
                            log("         [warn] AssignToColorGroup returned False.")
                    except Exception as exc:
                        log(f"         [warn] AssignToColorGroup raised: {exc}")

                try:
                    if original_tli.CopyGrades([new_tli]):
                        result["grades_copied"] += 1
                    else:
                        log("         [warn] CopyGrades reported failure.")
                except Exception as exc:
                    log(f"         [warn] CopyGrades raised: {exc}")

            if copy_attrs:
                copied = 0
                attempted = 0
                for key_name in tf.VIDEO_ATTR_KEYS:
                    try:
                        value = original_tli.GetProperty(key_name)
                    except Exception:
                        continue
                    if value is None:
                        continue
                    attempted += 1
                    try:
                        if new_tli.SetProperty(key_name, value):
                            copied += 1
                    except Exception:
                        pass
                log(
                    f"         attributes copied: {copied}/{attempted} "
                    f"(of {len(tf.VIDEO_ATTR_KEYS)} known keys)"
                )

            if disable_originals and role_label == "primary":
                try:
                    if original_tli.SetClipEnabled(False):
                        result["originals_disabled"] += 1
                except Exception as exc:
                    log(f"         [warn] Disabling original failed: {exc}")

            maybe_pump()

        return True

    primary_track_index = video_track_count + 1

    # CopyGrades only applies while the Color page is active; switch and restore.
    original_page = None
    page_switched = False
    if copy_grade and not dry_run:
        try:
            original_page = resolve.GetCurrentPage()
        except Exception:
            original_page = None
        try:
            page_switched = bool(resolve.OpenPage("color"))
        except Exception:
            page_switched = False
        if page_switched:
            log("  Switched to Color page (required for CopyGrades to apply).")
        else:
            log("  [warn] Could not switch to Color page; grade copy may silently no-op.")
        pump()

    log(f"  Pairs to lay: {len(pairings)}")
    if add_offset_track:
        log(
            f"  Comparison pass enabled: extra track will be laid with "
            f"source offset {int(offset_track_frames):+d}f."
        )
    pump()

    if not _lay_pairs_on_track(primary_track_index, new_track_name, 0, "primary"):
        return result

    if add_offset_track and not result["cancelled"]:
        offset_int = int(offset_track_frames)
        comparison_track_index = primary_track_index + 1
        if new_track_name:
            comparison_track_name = f"{new_track_name} ({offset_int:+d}f)"
        else:
            comparison_track_name = f"Reconform ({offset_int:+d}f)"
        _lay_pairs_on_track(
            comparison_track_index, comparison_track_name, offset_int, "comparison"
        )

    if result["cancelled"]:
        log("Run cancelled by user. Showing partial results below.")
        pump()

    if page_switched and original_page and original_page != "color":
        try:
            if resolve.OpenPage(original_page):
                log(f"  Restored {original_page} page.")
        except Exception:
            pass
        pump()

    unused_bin_keys = sorted(set(key_to_mpi.keys()) - laid_bin_keys)
    if unused_bin_keys:
        log("")
        for key in unused_bin_keys:
            mpi = key_to_mpi[key]
            log(
                f"  [WARN] Bin item '{mpi.GetName()}' (key='{key}') was not laid "
                "(no matching TimelineItem on the current timeline)."
            )
    result["bin_unused"] = len(unused_bin_keys)

    log("")
    log(f"  Bin clips scanned:              {result['bin_scanned']}")
    log(f"  Bin clips matched:              {result['bin_matched']}")
    if result["bin_duplicates_skipped"]:
        log(f"  Bin duplicate keys ignored:     {result['bin_duplicates_skipped']}")
    if result["bin_unused"]:
        log(f"  Bin clips not laid:             {result['bin_unused']}")
    log(f"  Timeline clips scanned:         {result['tli_scanned']}")
    if skip_disabled_tlis and result["tli_skipped_disabled"]:
        log(f"  Disabled TLIs skipped:          {result['tli_skipped_disabled']}")
    if result["tli_skipped_out_of_scope"]:
        log(f"  Out-of-scope TLIs skipped:      {result['tli_skipped_out_of_scope']}")
    log(f"  Timeline clips matched:         {result['tli_matched']}")
    log(f"  Timeline matches w/o bin pair:  {result['tli_unpaired']}")
    if add_offset_track:
        lay_label = (
            "Clip placements that would be made:" if dry_run
            else "Clip placements made (across both tracks):"
        )
    else:
        lay_label = (
            "Clips that would be laid:" if dry_run
            else "Clips laid on new track:    "
        )
    log(f"  {lay_label}    {result['laid']}")
    if result["overlap_skipped"]:
        log(f"  Skipped (overlap on new trk):   {result['overlap_skipped']}")
    if result["append_failures"]:
        log(f"  Append failures:                {result['append_failures']}")
    if copy_grade and not dry_run:
        log(f"  Grades copied:                  {result['grades_copied']}")
        log(f"  Color groups assigned:          {result['groups_assigned']}")
    if disable_originals and not dry_run:
        log(f"  Originals disabled:             {result['originals_disabled']}")
    if dry_run:
        log("  (Dry run: no changes were applied.)")
    pump()

    return result
