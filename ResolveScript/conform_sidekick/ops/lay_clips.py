"""Lay Matching Bin Clips On New Track(s) - core operation.

Ported from davinci-resolve-scripts/Edit/LayMatchingBinClipsOnNewTrack.py, with
important behaviour changes over the original:

* Source ranges are primarily taken from the timeline's **Edit Index** (exported
  via ``Timeline.Export(..., EXPORT_TEXT_CSV)``). The scripting API's
  ``GetSourceStartFrame()``/``GetSourceEndFrame()`` floor an internal float
  position and intermittently come back 1 frame low (the "intermittent -1
  source-frame offset" bug: an in-point of 24 stored internally as 23.99999...
  is reported as 23), whereas the Edit Index timecodes are rounded correctly by
  Resolve's display layer. When no Edit Index row is available the API ints are
  used, refined by the float ``GetSourceStartTime()`` and the record duration
  (``GetEnd() - GetStart()``).
* Every bin clip that matches a key is laid (split screens often ship a LEFT
  and a RIGHT plate for the same record range). When a key matches several bin
  clips, a timeline item pairs only with the bin clips whose name matches it
  exactly (ignoring extension) when such clips exist, so a ``.._LEFT`` timeline
  item takes the ``.._LEFT.mov`` and not its ``.._RIGHT.mov`` sibling.
  Placements spill onto additional new video tracks whenever they would
  overlap, adding as many tracks as needed.
"""

import csv
import os
import tempfile

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


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _media_fps(mpi):
    if mpi is None:
        return None
    try:
        return _to_float(mpi.GetClipProperty("FPS"))
    except Exception:
        return None


def _name_stem(name):
    stem, _ext = os.path.splitext(name or "")
    return stem.strip().lower()


def _load_edit_index(resolve, timeline, frame_rate_str, log):
    """Export the timeline's Edit Index and return
    ``{(video_track_index, record_in_frame): row_dict}`` or None.

    The Edit Index is the authoritative source for per-event Source In/Out
    timecodes: unlike ``GetSourceStartFrame()``, its TC strings are rounded
    correctly from Resolve's internal float positions.
    """
    export_type = getattr(resolve, "EXPORT_TEXT_CSV", None)
    if export_type is None:
        log("  [warn] This Resolve version cannot export the Edit Index via scripting.")
        return None

    try:
        fd, path = tempfile.mkstemp(prefix="conform_sidekick_edit_index_", suffix=".csv")
        os.close(fd)
    except Exception as exc:
        log(f"  [warn] Could not create a temp file for the Edit Index: {exc}")
        return None

    try:
        try:
            subtype = getattr(resolve, "EXPORT_NONE", None)
            if subtype is not None:
                ok = bool(timeline.Export(path, export_type, subtype))
            else:
                ok = bool(timeline.Export(path, export_type))
        except Exception as exc:
            log(f"  [warn] Edit Index export raised: {exc}")
            return None
        if not ok:
            log("  [warn] Edit Index export failed.")
            return None

        index = {}
        try:
            with open(path, newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    if (row.get("C") or "").strip() != "C":
                        continue
                    track = (row.get("V") or "").strip()
                    if not track.startswith("V"):
                        continue
                    try:
                        v_idx = int(track[1:])
                    except ValueError:
                        continue
                    source_in = (row.get("Source In") or "").strip()
                    source_out = (row.get("Source Out") or "").strip()
                    source_start = (row.get("Source Start") or "").strip()
                    record_in = (row.get("Record In") or "").strip()
                    if not (source_in and source_out and source_start and record_in):
                        continue
                    record_frame = _start_tc_frames(frame_rate_str, record_in)
                    if record_frame is None:
                        continue
                    index[(v_idx, record_frame)] = {
                        "source_in": source_in,
                        "source_out": source_out,
                        "source_start": source_start,
                        "fps": (row.get("Source FPS") or "").strip(),
                        "name": (row.get("Name") or "").strip(),
                    }
        except Exception as exc:
            log(f"  [warn] Could not parse the exported Edit Index: {exc}")
            return None
        return index
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


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


def _refined_source_frame(tli, getter_name, floored_frame, media_fps):
    """Correct Resolve's floored source-frame int using the float-time API.

    ``GetSourceStartFrame()``/``GetSourceEndFrame()`` floor an internal float
    position, so they are intermittently 1 frame low. The paired float getters
    (``GetSourceStartTime()``/``GetSourceEndTime()``) expose the un-floored
    position, but their units (seconds vs frames) are not documented, so an
    interpretation is only trusted when it rounds to the reported frame or the
    frame directly above it (the only two values a floor error allows).

    Returns ``(frame, corrected)``.
    """
    try:
        value = float(getattr(tli, getter_name)())
    except Exception:
        return floored_frame, False

    candidates = []
    if media_fps:
        candidates.append(int(round(value * media_fps)))  # seconds
    candidates.append(int(round(value)))  # float frames

    for candidate in candidates:
        if candidate in (floored_frame, floored_frame + 1):
            return candidate, candidate != floored_frame
    return floored_frame, False


def _translate_source_range(orig_tli, new_mpi, timeline_fps_str, edit_row=None):
    """Translate the original TLI's source frame range into the new MPI's
    numbering, anchored on Start TC (falling back to file-offset).

    ``edit_row`` is the item's Edit Index row when available; its timecodes are
    the authoritative source range. Without it the scripting API's floored
    ints are used, refined via the float-time API and the record duration.
    """
    record_duration = _to_int(orig_tli.GetEnd()) - _to_int(orig_tli.GetStart())
    src_start_raw = _to_int(orig_tli.GetSourceStartFrame())
    src_end_raw = _to_int(orig_tli.GetSourceEndFrame())

    orig_mpi = None
    try:
        orig_mpi = orig_tli.GetMediaPoolItem()
    except Exception:
        orig_mpi = None

    orig_fps = _media_fps(orig_mpi)

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

    # Parse all TCs at one shared rate. The clips' own rate is the correct
    # base for their TC; the timeline rate is only a fallback.
    tc_fps = orig_fps if orig_fps else _media_fps(new_mpi)
    tc_fps_str = str(tc_fps) if tc_fps else timeline_fps_str

    parsed_row = None
    if edit_row is not None:
        row_fps = _to_float(edit_row.get("fps"))
        row_fps_str = str(row_fps) if row_fps else tc_fps_str
        in_f = _start_tc_frames(row_fps_str, edit_row.get("source_in"))
        out_f = _start_tc_frames(row_fps_str, edit_row.get("source_out"))
        file_f = _start_tc_frames(row_fps_str, edit_row.get("source_start"))
        if in_f is not None and out_f is not None and file_f is not None:
            parsed_row = (in_f, out_f, file_f, row_fps_str)

    start_corrected = False
    if parsed_row is not None:
        in_f, out_f, file_f, row_fps_str = parsed_row
        src_source = "edit-index"
        src_start = orig_mpi_start + (in_f - file_f)
        span = out_f - in_f
        retimed = abs(span - record_duration) > 1
        src_end = src_start + (span if retimed else record_duration)
        start_corrected = src_start != src_start_raw
        # Anchor the TC delta on the Edit Index's own clip-start TC; this
        # works even when the original's MediaPoolItem link is unavailable.
        orig_tc_str = edit_row.get("source_start")
        orig_tc_frames = file_f
        new_tc_frames = _start_tc_frames(row_fps_str, new_tc_str)
    else:
        src_source = "api"
        src_start, start_corrected = _refined_source_frame(
            orig_tli, "GetSourceStartTime", src_start_raw, orig_fps
        )
        # A source span that disagrees with the record span by more than the
        # +/-1 rounding jitter means the item is retimed; reconstructing the
        # end from the record duration would then be wrong.
        retimed = abs(src_end_raw - (src_start_raw + record_duration)) > 1
        if retimed:
            src_end, _ = _refined_source_frame(
                orig_tli, "GetSourceEndTime", src_end_raw, orig_fps
            )
        else:
            src_end = src_start + record_duration
        orig_tc_frames = _start_tc_frames(tc_fps_str, orig_tc_str)
        new_tc_frames = _start_tc_frames(tc_fps_str, new_tc_str)

    file_offset_in = src_start - orig_mpi_start
    file_offset_out = src_end - orig_mpi_start

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
        "src_source": src_source,
        "new_start_frame": new_start_frame,
        "new_end_frame": new_end_frame,
        "orig_src_start": src_start,
        "orig_src_end": src_end,
        "src_start_raw": src_start_raw,
        "src_end_raw": src_end_raw,
        "start_corrected": start_corrected,
        "retimed": retimed,
        "record_duration": record_duration,
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


def _format_remap(remap):
    notes = []
    if remap["start_corrected"]:
        shift = remap["orig_src_start"] - remap["src_start_raw"]
        if remap["src_source"] == "edit-index":
            notes.append(f"start {shift:+d}f vs API")
        else:
            notes.append(f"start {shift:+d}f float fix")
    if remap["retimed"]:
        notes.append("retimed")
    note_str = f" [{'; '.join(notes)}]" if notes else ""
    base = (
        f"orig src [{remap['orig_src_start']}-{remap['orig_src_end']}] "
        f"(raw [{remap['src_start_raw']}-{remap['src_end_raw']}], "
        f"rec dur {remap['record_duration']}f){note_str} "
        f"@Start={remap['orig_mpi_start']}"
    )
    source_label = remap["src_source"]
    if remap["method"] == "tc":
        return (
            f"src remap (TC, {source_label}): {base} "
            f"TC={remap['orig_tc_str']} ({remap['orig_tc_frames']}f) -> "
            f"new TC={remap['new_tc_str']} ({remap['new_tc_frames']}f) "
            f"delta={remap['delta_tc']}f -> "
            f"new src [{remap['new_start_frame']}-{remap['new_end_frame']}] "
            f"@Start={remap['new_mpi_start']}"
        )
    return (
        f"src remap (file-offset, {source_label}, no Start TC available): {base} -> "
        f"new src [{remap['new_start_frame']}-{remap['new_end_frame']}] "
        f"@Start={remap['new_mpi_start']}"
    )


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


def _fit_to_new_mpi(new_start, new_end, new_mpi):
    """Clamp an (exclusive-end) source range to the new clip's extents.

    Returns ``(start, end, status, extents)`` with status ``"ok"``,
    ``"clamped"`` or ``"disjoint"``. The media pool "End" property is the last
    frame (inclusive) when ``End - Start == Frames - 1``; detect that so a clip
    used all the way to its final frame is not trimmed by the clamp.
    """
    try:
        mpi_start = _to_int(new_mpi.GetClipProperty("Start"))
        mpi_end = _to_int(new_mpi.GetClipProperty("End"))
        frame_count = _to_int(new_mpi.GetClipProperty("Frames"))
    except Exception:
        return new_start, new_end, "ok", None

    if mpi_end <= mpi_start:
        return new_start, new_end, "ok", None

    if frame_count and mpi_end - mpi_start == frame_count - 1:
        max_end = mpi_end + 1
    else:
        max_end = mpi_end

    extents = (mpi_start, mpi_end)
    if new_end <= mpi_start or new_start >= max_end:
        return new_start, new_end, "disjoint", extents

    clamped_start = max(mpi_start, min(new_start, max_end))
    clamped_end = max(mpi_start, min(new_end, max_end))
    status = (
        "clamped"
        if (clamped_start != new_start or clamped_end != new_end)
        else "ok"
    )
    return clamped_start, clamped_end, status, extents


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
    log=print,
    pump=_noop,
    pump_every=5,
    should_cancel=lambda: False,
):
    result = {
        "bin_scanned": 0,
        "bin_matched": 0,
        "bin_unused": 0,
        "tli_scanned": 0,
        "tli_skipped_disabled": 0,
        "tli_skipped_out_of_scope": 0,
        "tli_matched": 0,
        "tli_unpaired": 0,
        "placements": 0,
        "laid": 0,
        "tracks_added": 0,
        "range_failures": 0,
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

    header = (
        "Lay Matching Bin Clips On New Track - DRY RUN"
        if dry_run
        else "Lay Matching Bin Clips On New Track"
    )
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

    # The Edit Index is the authoritative source for per-event source TCs
    # (the scripting API's source frames can be 1 frame low).
    edit_index = _load_edit_index(resolve, timeline, frame_rate_str, log)
    if edit_index:
        log(f"  Edit Index exported: {len(edit_index)} video events (authoritative source TCs).")
    else:
        log(
            "  [warn] Edit Index unavailable; source ranges come from the "
            "scripting API and may be 1 frame low on some clips."
        )
    pump()

    # 1) Scan the open bin and build a key -> [MediaPoolItem, ...] map. Every
    # clip matching a key is laid (split screens: LEFT + RIGHT plates).
    bin_clips = current_folder.GetClipList() or []
    key_to_mpis = {}
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
        key_to_mpis.setdefault(key, []).append(mpi)
        result["bin_matched"] += 1
        maybe_pump()

    if result["cancelled"]:
        log("Run cancelled by user.")
        pump()
        return result

    if not key_to_mpis:
        log("No MediaPoolItems in the open bin matched the regex. Nothing to do.")
        pump()
        return result

    for key in sorted(key_to_mpis):
        mpis = key_to_mpis[key]
        if len(mpis) > 1:
            names = ", ".join(f"'{m.GetName()}'" for m in mpis)
            log(
                f"  Key '{key}' matches {len(mpis)} bin clips ({names}); "
                "each lays against timeline clips with the same name when "
                "one exists, otherwise against all of the key's clips."
            )

    # 2) Collect matching TimelineItems with their pairing keys. Dedupe by
    # name + record range so a plate on V1+V2 generates one overlay, but
    # stacked split-screen items (.._LEFT / .._RIGHT sharing a record range)
    # both survive. Each item pairs with the key's bin clips whose name
    # matches it exactly (sans extension) when such clips exist, otherwise
    # with all of the key's bin clips.
    track_indices = (
        sorted(track_set)
        if track_set is not None
        else list(range(1, video_track_count + 1))
    )
    pairings = []  # (item, src_track_idx, key, record_start, record_end, [mpis])
    paired_keys = set()
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
            # Match on the name first: every Get* call is an IPC round-trip
            # into Resolve, so non-matching items (the vast majority) should
            # cost exactly one call.
            name = item.GetName() or ""
            key = tf.match_key(pattern, name)
            if key is None:
                continue
            if skip_disabled_tlis:
                try:
                    enabled = item.GetClipEnabled()
                except Exception:
                    enabled = True
                if not enabled:
                    result["tli_skipped_disabled"] += 1
                    continue
            try:
                item_start = item.GetStart()
                item_end = item.GetEnd()
            except Exception:
                item_start = None
                item_end = None
            if scope_range is not None and item_start is not None and item_end is not None:
                scope_in, scope_out = scope_range
                if not (item_start < scope_out and scope_in < item_end):
                    result["tli_skipped_out_of_scope"] += 1
                    continue
            result["tli_matched"] += 1
            if key not in key_to_mpis:
                result["tli_unpaired"] += 1
                continue
            if item_start is None or item_end is None:
                log(
                    f"  [WARN] V{track_idx}: could not read the record range of "
                    f"'{name}'; skipping it."
                )
                continue
            dedupe_key = (key, name, item_start, item_end)
            if dedupe_key in seen_record_keys:
                continue
            seen_record_keys.add(dedupe_key)
            candidates = key_to_mpis[key]
            if len(candidates) > 1:
                tli_stem = _name_stem(name)
                exact = [
                    m for m in candidates
                    if _name_stem(m.GetName() or "") == tli_stem
                ]
                if exact:
                    candidates = exact
            pairings.append((item, track_idx, key, item_start, item_end, candidates))
            paired_keys.add(key)
            maybe_pump()
        if result["cancelled"]:
            break

    if result["cancelled"]:
        log("Run cancelled by user.")
        pump()
        return result

    if not pairings:
        for key in sorted(key_to_mpis):
            for mpi in key_to_mpis[key]:
                log(
                    f"  [WARN] Bin item '{mpi.GetName()}' (key='{key}') was not laid: "
                    f"no matching TimelineItem on the current timeline."
                )
        log("No TimelineItems could be paired with a bin item. Nothing to lay.")
        pump()
        return result

    # 3) Expand pairings to one placement per (TimelineItem, bin clip) and
    # sort by record frame so track assignment is deterministic.
    placements = []
    attempted_mpi_ids = set()
    for item, src_track, key, rec_start, rec_end, candidates in pairings:
        for mpi in candidates:
            placements.append((item, src_track, mpi, key, rec_start, rec_end))
            attempted_mpi_ids.add(id(mpi))
    placements.sort(key=lambda p: (p[4], p[3], p[2].GetName() or ""))
    result["placements"] = len(placements)

    laid_mpi_ids = set()
    disabled_tli_ids = set()
    tracks = []  # {"index": int, "name": str, "used": [(start, end), ...]}

    def _lay_track_name(ordinal):
        if not new_track_name:
            return ""
        return new_track_name if ordinal == 1 else f"{new_track_name} {ordinal}"

    def _add_lay_track():
        ordinal = len(tracks) + 1
        index = video_track_count + ordinal
        name = _lay_track_name(ordinal)
        if not dry_run:
            if not timeline.AddTrack("video"):
                log(f"  [FAIL] Could not add video track V{index}. Aborting.")
                result["error"] = True
                return None
            if name:
                try:
                    timeline.SetTrackName("video", index, name)
                except Exception:
                    pass
        result["tracks_added"] += 1
        entry = {"index": index, "name": name, "used": []}
        tracks.append(entry)
        log(
            f"  {'Would add' if dry_run else 'Added'} track V{index}"
            + (f" ('{name}')" if name else "")
        )
        pump()
        return entry

    def _find_track(rec_start, rec_end):
        """First existing lay track where this record range is free; else a new one."""
        for entry in tracks:
            if not any(rec_start < e and s < rec_end for s, e in entry["used"]):
                return entry
        return _add_lay_track()

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

    log(
        f"  Timeline clips to cover: {len(pairings)}; "
        f"placements to make: {len(placements)}"
    )
    pump()

    if _add_lay_track() is None:
        return result

    for original_tli, src_track, mpi, key, record_frame, end_record_frame in placements:
        if should_cancel():
            result["cancelled"] = True
            break

        original_name = original_tli.GetName() or "(unnamed)"
        location = f"V{src_track} {record_frame}-{end_record_frame}"
        mpi_name = mpi.GetName() or "(unnamed)"

        edit_row = None
        if edit_index:
            edit_row = edit_index.get((src_track, record_frame))
            if (
                edit_row is not None
                and edit_row.get("name")
                and original_name
                and edit_row["name"] != original_name
            ):
                # Row mismatch (should not happen); don't trust it.
                edit_row = None

        remap = _translate_source_range(original_tli, mpi, frame_rate_str, edit_row)
        new_source_start = remap["new_start_frame"]
        new_source_end = remap["new_end_frame"]

        fit_start, fit_end, fit_status, extents = _fit_to_new_mpi(
            new_source_start, new_source_end, mpi
        )
        if fit_status == "disjoint":
            result["range_failures"] += 1
            log(
                f"  [FAIL] {location}: '{original_name}' -> '{mpi_name}': remapped "
                f"source range [{new_source_start}-{new_source_end}] does not exist "
                f"in the new clip (extents [{extents[0]}-{extents[1]}]). Check the "
                f"clips' Start TC and the original's media link."
            )
            log(f"         {_format_remap(remap)}")
            maybe_pump()
            continue
        if fit_status == "clamped":
            log(
                f"         [warn] {location}: requested src "
                f"[{new_source_start}-{new_source_end}] exceeds new clip extents "
                f"[{extents[0]}-{extents[1]}]; clamped to [{fit_start}-{fit_end}]."
            )
        new_source_start, new_source_end = fit_start, fit_end

        track_entry = _find_track(record_frame, end_record_frame)
        if track_entry is None:
            return result

        if dry_run:
            result["laid"] += 1
            track_entry["used"].append((record_frame, end_record_frame))
            laid_mpi_ids.add(id(mpi))
            log(
                f"  [PLAN] {location}: '{original_name}' (key='{key}') -> "
                f"'{mpi_name}' on V{track_entry['index']}"
            )
            log(f"         {_format_remap(remap)}")
            maybe_pump()
            continue

        clip_info = {
            "mediaPoolItem": mpi,
            "startFrame": new_source_start,
            "endFrame": new_source_end,
            "trackIndex": track_entry["index"],
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
                f"on V{track_entry['index']}."
            )
            log(f"         {_format_remap(remap)}")
            maybe_pump()
            continue

        recovered = _reacquire_appended_tli(
            timeline, track_entry["index"], record_frame, hint=appended[0]
        )
        new_tli = recovered if recovered is not None else appended[0]

        result["laid"] += 1
        track_entry["used"].append((record_frame, end_record_frame))
        laid_mpi_ids.add(id(mpi))
        log(
            f"  [OK]   {location}: '{original_name}' -> '{mpi_name}' "
            f"on V{track_entry['index']}"
        )
        log(f"         {_format_remap(remap)}")
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

        if disable_originals and id(original_tli) not in disabled_tli_ids:
            try:
                if original_tli.SetClipEnabled(False):
                    result["originals_disabled"] += 1
                    disabled_tli_ids.add(id(original_tli))
            except Exception as exc:
                log(f"         [warn] Disabling original failed: {exc}")

        maybe_pump()

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

    unused = []
    for key in sorted(key_to_mpis):
        for mpi in key_to_mpis[key]:
            if id(mpi) not in laid_mpi_ids:
                unused.append((key, mpi))
    if unused:
        log("")
        for key, mpi in unused:
            if id(mpi) in attempted_mpi_ids:
                log(
                    f"  [WARN] Bin item '{mpi.GetName()}' (key='{key}') matched "
                    "timeline clip(s) but could not be placed - see [FAIL] lines above."
                )
            elif key in paired_keys:
                log(
                    f"  [WARN] Bin item '{mpi.GetName()}' (key='{key}') was not laid: "
                    "the key's timeline item(s) were name-matched to other bin clips."
                )
            else:
                log(
                    f"  [WARN] Bin item '{mpi.GetName()}' (key='{key}') was not laid "
                    "(no matching TimelineItem on the current timeline)."
                )
    result["bin_unused"] = len(unused)

    log("")
    log(f"  Bin clips scanned:              {result['bin_scanned']}")
    log(f"  Bin clips matched:              {result['bin_matched']}")
    if result["bin_unused"]:
        log(f"  Bin clips not laid:             {result['bin_unused']}")
    log(f"  Timeline clips scanned:         {result['tli_scanned']}")
    if skip_disabled_tlis and result["tli_skipped_disabled"]:
        log(f"  Disabled TLIs skipped:          {result['tli_skipped_disabled']}")
    if result["tli_skipped_out_of_scope"]:
        log(f"  Out-of-scope TLIs skipped:      {result['tli_skipped_out_of_scope']}")
    log(f"  Timeline clips matched:         {result['tli_matched']}")
    log(f"  Timeline matches w/o bin pair:  {result['tli_unpaired']}")
    if dry_run:
        log(f"  Clips that would be laid:       {result['laid']} (of {result['placements']} planned)")
        log(f"  Tracks that would be added:     {result['tracks_added']}")
    else:
        log(f"  Clips laid:                     {result['laid']} (of {result['placements']} planned)")
        log(f"  New tracks added:               {result['tracks_added']}")
    if result["range_failures"]:
        log(f"  Source-range failures:          {result['range_failures']}")
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
