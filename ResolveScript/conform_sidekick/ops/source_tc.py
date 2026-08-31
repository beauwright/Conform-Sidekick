"""Set Source TC From Date Created - core operation.

Clips that arrive with a source TC of ``00:00:00:00`` cannot be conformed or
matched by timecode, and a pool full of identical zero TCs makes every
TC-driven tool useless. This op invents a unique, stable source TC for those
clips from their creation date.

Behaviour verified empirically against Resolve Studio 21.0.4 (the scripting
README documents none of it):

* ``MediaPoolItem.SetClipProperty('Start TC', 'HH:MM:SS:FF')`` returns ``True``
  and sticks. Only ``Start TC`` / ``End TC`` move - ``Start``, ``End``,
  ``Frames`` and ``Duration`` are untouched, because media frame numbering is
  0-based and independent of the clip's TC.
* **Changing Start TC orphans any timeline item using that clip.**
  ``TimelineItem.GetMediaPoolItem()`` starts returning ``None`` and the source
  range is lost. Resolve dereferences timeline item -> media pool item by TC at
  query time, so writing the original TC back relinks the item and restores the
  exact source range. That recovery was only ever verified *in-session*; it was
  never tested across a save + reload, so clips in use are excluded by default
  and the caller must never leave one changed on the assumption it can be fixed
  later. See :func:`revert_source_tc`.
* ``Date Created`` is the embedded container date when the media carries one and
  the filesystem birthtime otherwise, rendered in the **workstation's local
  timezone** (DST-correct per instant). Converting local -> UTC recovers the
  original embedded value exactly, which is what makes a timezone choice
  meaningful here.

Every clip this op touches was at exactly ``00:00:00:00`` by definition, so
reverting needs no snapshot of prior values - it writes ``00:00:00:00`` back.
Only the *set of clips changed* has to be remembered.
"""

import datetime as dt
import os

ZERO_TC = "00:00:00:00"

# Sentinel for "machine local". Implemented as identity rather than a tz
# conversion: local -> UTC -> local is a no-op, so this path needs no IANA
# database and reproduces exactly what Resolve shows in its Date Created column.
ZONE_LOCAL = ""

# Resolve types image sequences as 'Video', so filtering on the reported Type
# barely helps - extension is what actually separates stills from footage.
IMAGE_EXTS = frozenset(
    {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".psd",
     ".arw", ".dng", ".cr2", ".cr3", ".nef", ".exr", ".dpx", ".tga", ".bmp",
     ".gif", ".webp"}
)
AUDIO_EXTS = frozenset({".wav", ".aif", ".aiff", ".mp3", ".m4a", ".flac", ".aac"})

# Offered in the timezone dropdown ahead of the free-text override.
CURATED_ZONES = (
    "America/Los_Angeles",
    "America/Denver",
    "America/Chicago",
    "America/New_York",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Pacific/Auckland",
)

# Give up spilling a crowded second after this many frames rather than looping.
_MAX_SPILL_FRAMES = 3600


def _noop():
    pass


# ---------------------------------------------------------------------------
# Pure helpers - no Resolve calls, so they can be exercised standalone
# ---------------------------------------------------------------------------

# 'Thu Feb 12 2026 16:47:29' is the shape Resolve uses for Date Created, with
# the day *not* zero-padded ('Mon May 4 2026 13:42:28'). Date Modified uses a
# different field order entirely (year last); it is accepted defensively so a
# locale or version that returns that shape degrades instead of skipping the
# clip, but Date Created is the only source this op reads.
_DATE_FORMATS = (
    "%a %b %d %Y %H:%M:%S",
    "%b %d %Y %H:%M:%S",
    "%a %b %d %H:%M:%S %Y",
)


def parse_date_created(value):
    """Parse a Resolve ``Date Created`` string to a naive local datetime.

    Returns ``None`` for anything unparseable so the caller can skip and log
    rather than inventing a wrong timecode.
    """
    if not value or not isinstance(value, str):
        return None
    text = " ".join(value.split())
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def resolve_zone(zone_name):
    """Return a ``tzinfo`` for *zone_name*, or ``None`` meaning machine local.

    Raises ``ValueError`` when the zone cannot be resolved. Callers must abort
    on that rather than falling back, because a silently wrong zone writes
    silently wrong timecodes.
    """
    name = (zone_name or "").strip()
    if not name:
        return None
    if name.upper() == "UTC":
        return dt.timezone.utc
    try:
        from zoneinfo import ZoneInfo
    except ImportError as exc:  # pragma: no cover - Python < 3.9
        raise ValueError(
            f"This Python has no 'zoneinfo' module, so '{name}' cannot be "
            f"resolved ({exc}). Choose 'Machine local' or 'UTC'."
        )
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError(
            f"Unknown timezone '{name}': {type(exc).__name__}: {exc}. Use an "
            f"IANA name such as 'America/Denver', or choose 'Machine local'."
        )


def to_zone(naive_local, zone):
    """Convert a naive *local* datetime into *zone*, returning it naive again.

    ``zone`` of ``None`` is identity (machine local). The round trip goes
    through UTC: ``astimezone()`` on a naive value interprets it as local time,
    which is exactly how Resolve rendered it in the first place.

    Note this must be given a real zone, never a captured offset -
    ``datetime.now().astimezone().tzinfo`` is a fixed ``timezone`` with no DST
    rules and silently shifts out-of-season clips by an hour.
    """
    if zone is None:
        return naive_local
    return naive_local.astimezone().astimezone(zone).replace(tzinfo=None)


def _fps_int(fps):
    """Frames-per-second as a positive int, defaulting to 24 when unusable."""
    try:
        value = int(round(float(fps)))
    except (TypeError, ValueError):
        return 24
    return value if value > 0 else 24


def derive_tc(moment, frame_offset=0, fps=24):
    """Build a non-drop ``HH:MM:SS:FF`` string for *moment*.

    ``frame_offset`` beyond one second's worth of frames rolls into the
    following second, so a crowded timestamp spreads forwards in time instead
    of producing an out-of-range frame number.
    """
    per_second = _fps_int(fps)
    extra, frames = divmod(int(frame_offset), per_second)
    if extra:
        moment = moment + dt.timedelta(seconds=extra)
    return f"{moment.strftime('%H:%M:%S')}:{frames:02d}"


def assign_timecodes(candidates, zone=None):
    """Assign a unique timecode to each candidate.

    ``candidates`` are dicts carrying at least ``name``, ``uid``, ``created_dt``
    and ``fps``. Ordering is by ``(name, uid)`` so a re-run over the same media
    produces byte-identical timecodes.

    Timestamps only resolve to the second, and roughly half of a real project's
    zero-TC clips share a second with another clip, so collisions are the normal
    case rather than an edge case. Each clip takes the first free
    ``(second, frame)`` slot at or after its own timestamp, which keeps every
    assignment unique even when spilling pushes one clip into a second that
    another clip already occupies.

    Returns ``[(candidate, timecode, spilled_bool), ...]`` in assignment order.
    """
    ordered = sorted(candidates, key=lambda c: (c.get("name") or "", c.get("uid") or ""))
    # Reserve 00:00:00:00 itself. A clip created at 23:59:59 that has to spill can
    # otherwise wrap straight onto the sentinel this whole mode exists to clear,
    # and would be picked up as a candidate again on the next run.
    used = {ZERO_TC}
    assigned = []
    for cand in ordered:
        moment = to_zone(cand["created_dt"], zone)
        per_second = _fps_int(cand.get("fps"))
        chosen = None
        offset = 0
        while offset < _MAX_SPILL_FRAMES:
            candidate_tc = derive_tc(moment, offset, per_second)
            if candidate_tc not in used:
                chosen = candidate_tc
                used.add(chosen)
                break
            offset += 1
        assigned.append((cand, chosen, chosen is not None and offset >= per_second))
    return assigned


# ---------------------------------------------------------------------------
# Resolve-touching
# ---------------------------------------------------------------------------

def _prop(item, key):
    try:
        return item.GetClipProperty(key)
    except Exception:
        return ""


def _uid(item):
    try:
        return item.GetUniqueId() or ""
    except Exception:
        return ""


def _ext(path):
    return os.path.splitext(path or "")[1].lower()


def timeline_usage_ids(conn, log=print, pump=_noop, should_cancel=lambda: False):
    """Return the set of ``MediaPoolItem`` unique ids used by any timeline.

    The clip property ``Usage`` cannot be trusted for this. Measured on a
    48-timeline project with no timeline open, it reported ``'0'`` for 5248 of
    5249 clips - including all 477 sitting at ``00:00:00:00`` - while a real
    walk found 75 of them in use. Resolve appears to populate ``Usage`` lazily,
    so the property reads as "unused" in exactly the situation where a caller
    would most want to rely on it, which would silently orphan timeline clips
    the user believed were protected.

    Walking every track of every timeline costs ~12s on that project, which is
    the price of the safety guarantee. Cancellable, and progress is logged.
    """
    used = set()
    project = conn.get_project()
    if project is None:
        return used
    try:
        count = int(project.GetTimelineCount() or 0)
    except Exception:
        count = 0
    if not count:
        return used

    log(f"  Checking which clips are used across {count} timeline(s)...")
    pump()
    for index in range(1, count + 1):
        if should_cancel():
            break
        try:
            timeline = project.GetTimelineByIndex(index)
        except Exception:
            continue
        if timeline is None:
            continue
        for kind in ("video", "audio"):
            try:
                tracks = int(timeline.GetTrackCount(kind) or 0)
            except Exception:
                tracks = 0
            for track in range(1, tracks + 1):
                if should_cancel():
                    break
                try:
                    items = timeline.GetItemListInTrack(kind, track) or []
                except Exception:
                    continue
                for item in items:
                    try:
                        media = item.GetMediaPoolItem()
                    except Exception:
                        continue
                    if media is not None:
                        uid = _uid(media)
                        if uid:
                            used.add(uid)
        if index % 10 == 0:
            pump()
    pump()
    return used


def _scoped_folders(api, project, scope):
    """Return the ``MediaFolder`` list for *scope* ('project' or 'bin')."""
    folders = api.get_all_folders(project)
    if scope != "bin":
        return folders

    media_pool = project.GetMediaPool()
    try:
        current = media_pool.GetCurrentFolder()
    except Exception:
        current = None
    if current is None:
        return folders

    current_uid = ""
    try:
        current_uid = current.GetUniqueId() or ""
    except Exception:
        pass

    root = None
    for entry in folders:
        try:
            if current_uid and (entry.folder.GetUniqueId() or "") == current_uid:
                root = entry
                break
        except Exception:
            continue
    if root is None:
        return folders

    prefix = root.bin_location
    return [
        entry
        for entry in folders
        if entry.bin_location == prefix
        or entry.bin_location.startswith(prefix.rstrip("/") + "/")
    ]


def find_candidates(
    conn,
    api,
    scope="project",
    include_images=False,
    include_audio=False,
    include_in_timeline=False,
    log=print,
    pump=_noop,
    pump_every=200,
    should_cancel=lambda: False,
):
    """Collect the zero-TC clips this op would act on, plus rejection counts.

    Follows the scan strategy documented in :mod:`conform_sidekick.resolve_api`:
    read only the single classifying property (``Start TC``) for every clip, and
    pull the full property snapshot solely for the few that match. On a real
    project that is ~5000 cheap reads plus a few hundred expensive ones, rather
    than a full snapshot per clip.
    """
    counts = {
        "scanned": 0,
        "zero_tc": 0,
        "skipped_no_path": 0,
        "skipped_image": 0,
        "skipped_audio": 0,
        "skipped_in_timeline": 0,
        "skipped_no_date": 0,
        "cancelled": False,
    }
    candidates = []

    project = conn.get_project()
    if project is None:
        log("[ERR]  No project is open.")
        return candidates, counts

    # Always computed, not just when filtering: it is also what makes the
    # "these are in a timeline" warning truthful when the user opts in.
    used_ids = timeline_usage_ids(conn, log=log, pump=pump, should_cancel=should_cancel)
    if should_cancel():
        counts["cancelled"] = True
        return candidates, counts

    seen = 0
    for entry in _scoped_folders(api, project, scope):
        for item in (entry.folder.GetClipList() or []):
            if should_cancel():
                counts["cancelled"] = True
                return candidates, counts
            counts["scanned"] += 1
            seen += 1
            if seen % pump_every == 0:
                pump()

            if _prop(item, "Start TC") != ZERO_TC:
                continue
            counts["zero_tc"] += 1

            props = {}
            try:
                props = item.GetClipProperty() or {}
            except Exception:
                props = {}

            name = ""
            try:
                name = item.GetName() or ""
            except Exception:
                pass
            path = props.get("File Path") or ""

            # Compound clips and Fusion generators have no backing file and so
            # no creation date to invent a timecode from.
            if not path:
                counts["skipped_no_path"] += 1
                continue

            ext = _ext(path)
            if not include_images and (
                ext in IMAGE_EXTS or (props.get("Type") or "") == "Still"
            ):
                counts["skipped_image"] += 1
                continue
            if not include_audio and (
                ext in AUDIO_EXTS or (props.get("Type") or "") == "Audio"
            ):
                counts["skipped_audio"] += 1
                continue

            # The computed set is authoritative; the Usage property is only a
            # belt-and-braces union in case an item's id could not be read.
            uid = _uid(item)
            in_timeline = (
                (uid and uid in used_ids)
                or (props.get("Usage") or "0").strip() not in ("", "0")
            )
            if in_timeline and not include_in_timeline:
                counts["skipped_in_timeline"] += 1
                continue

            created_raw = props.get("Date Created") or ""
            created_dt = parse_date_created(created_raw)
            if created_dt is None:
                counts["skipped_no_date"] += 1
                log(f"  [SKIP] {name}: no usable Date Created ({created_raw!r}).")
                continue

            candidates.append({
                "item": item,
                "name": name,
                "uid": uid,
                "path": path,
                "bin": entry.bin_location,
                "created_raw": created_raw,
                "created_dt": created_dt,
                "fps": props.get("FPS"),
                "in_timeline": bool(in_timeline),
            })

    pump()
    return candidates, counts


def set_source_tc(
    conn,
    api,
    scope="project",
    zone_name=ZONE_LOCAL,
    include_images=False,
    include_audio=False,
    include_in_timeline=False,
    dry_run=True,
    log=print,
    pump=_noop,
    should_cancel=lambda: False,
):
    """Invent and apply a source TC for every zero-TC clip in scope."""
    result = {
        "scanned": 0,
        "zero_tc": 0,
        "candidates": 0,
        "planned": 0,
        "applied": 0,
        "failed": 0,
        "verify_mismatch": 0,
        "spilled": 0,
        "exhausted": 0,
        "in_timeline_touched": 0,
        "applied_ids": [],
        "error": False,
        "cancelled": False,
    }

    try:
        zone = resolve_zone(zone_name)
    except ValueError as exc:
        log(f"[ERR]  {exc}")
        result["error"] = True
        return result

    zone_label = zone_name.strip() or "machine local"
    log(f"Scanning for clips with a source TC of {ZERO_TC} ({zone_label})...")
    pump()

    candidates, counts = find_candidates(
        conn, api, scope,
        include_images=include_images,
        include_audio=include_audio,
        include_in_timeline=include_in_timeline,
        log=log, pump=pump, should_cancel=should_cancel,
    )
    result.update({k: counts[k] for k in ("scanned", "zero_tc")})
    result["cancelled"] = counts["cancelled"]
    result["candidates"] = len(candidates)

    if counts["cancelled"]:
        log("Run cancelled by user. Nothing was changed.")
        pump()
        return result

    if not candidates:
        _log_scan_summary(log, counts, 0)
        log("  No clips to change.")
        pump()
        return result

    _log_scan_summary(log, counts, len(candidates))
    log("")

    for cand, tc, spilled in assign_timecodes(candidates, zone):
        if should_cancel():
            result["cancelled"] = True
            log("Run cancelled by user. Showing partial results below.")
            break

        label = cand["name"] or "(unnamed)"
        if cand["in_timeline"]:
            result["in_timeline_touched"] += 1

        if tc is None:
            result["exhausted"] += 1
            log(f"  [ERR]  {label}: could not find a free timecode slot; skipped.")
            pump()
            continue
        if spilled:
            result["spilled"] += 1

        if dry_run:
            result["planned"] += 1
            log(f"  [PLAN] {label}: {ZERO_TC} -> {tc}"
                + ("  (in timeline)" if cand["in_timeline"] else ""))
            pump()
            continue

        try:
            ok = cand["item"].SetClipProperty("Start TC", tc)
        except Exception as exc:
            result["failed"] += 1
            log(f"  [ERR]  {label}: SetClipProperty raised "
                f"{type(exc).__name__}: {exc}; skipping.")
            pump()
            continue

        readback = _prop(cand["item"], "Start TC")
        if not ok or readback != tc:
            result["failed"] += 1
            if readback != tc:
                result["verify_mismatch"] += 1
            log(f"  [FAIL] {label}: {ZERO_TC} -> {tc} "
                f"(returned {ok!r}, reads back {readback!r})")
        else:
            result["applied"] += 1
            result["applied_ids"].append(cand["uid"])
            log(f"  [OK]   {label}: {ZERO_TC} -> {tc}"
                + ("  (in timeline)" if cand["in_timeline"] else ""))
        pump()

    log("")
    verb = "Clips that would be changed:" if dry_run else "Clips changed:              "
    log(f"  {verb}    {result['planned'] if dry_run else result['applied']}")
    if result["failed"]:
        log(f"  Failed:                         {result['failed']}")
    if result["verify_mismatch"]:
        log(f"  Wrote but read back different:  {result['verify_mismatch']}")
    if result["spilled"]:
        log(f"  Nudged to a later second:       {result['spilled']} "
            f"(shared a timestamp with another clip)")
    if result["exhausted"]:
        log(f"  No free slot found:             {result['exhausted']}")
    if result["in_timeline_touched"]:
        log("")
        log(f"  !! {result['in_timeline_touched']} of these are used in a timeline.")
        log("     Those timeline clips lose their media link until you press Revert.")
    if dry_run:
        log("  (Preview only: nothing was changed.)")
    pump()
    return result


def revert_source_tc(
    conn,
    api,
    applied_ids,
    log=print,
    pump=_noop,
    should_cancel=lambda: False,
):
    """Write ``00:00:00:00`` back to every clip listed in *applied_ids*.

    No prior-value snapshot is needed: this op only ever touches clips that were
    at exactly ``00:00:00:00``. Reverting also relinks any timeline item that
    was orphaned by the change, restoring its original source range.
    """
    result = {
        "requested": len(applied_ids or []),
        "reverted": 0,
        "failed": 0,
        "not_found": 0,
        "error": False,
        "cancelled": False,
    }
    wanted = set(applied_ids or [])
    if not wanted:
        log("Nothing to revert - no clips were changed from this workstation.")
        pump()
        return result

    project = conn.get_project()
    if project is None:
        log("[ERR]  No project is open.")
        result["error"] = True
        return result

    log(f"Reverting {len(wanted)} clip(s) to {ZERO_TC}...")
    pump()

    seen = 0
    for entry in api.get_all_folders(project):
        for item in (entry.folder.GetClipList() or []):
            if should_cancel():
                result["cancelled"] = True
                log("Revert cancelled by user. Showing partial results below.")
                break
            uid = _uid(item)
            if uid not in wanted:
                continue
            wanted.discard(uid)
            seen += 1
            label = ""
            try:
                label = item.GetName() or "(unnamed)"
            except Exception:
                label = "(unnamed)"
            try:
                ok = item.SetClipProperty("Start TC", ZERO_TC)
            except Exception as exc:
                result["failed"] += 1
                log(f"  [ERR]  {label}: SetClipProperty raised "
                    f"{type(exc).__name__}: {exc}")
                continue
            readback = _prop(item, "Start TC")
            if ok and readback == ZERO_TC:
                result["reverted"] += 1
                log(f"  [OK]   {label}: -> {ZERO_TC}")
            else:
                result["failed"] += 1
                log(f"  [FAIL] {label}: returned {ok!r}, reads back {readback!r}")
            pump()
        if result["cancelled"]:
            break

    result["not_found"] = len(wanted)
    log("")
    log(f"  Clips reverted:                 {result['reverted']}")
    if result["failed"]:
        log(f"  Failed:                         {result['failed']}")
    if result["not_found"]:
        log(f"  Not found in this project:      {result['not_found']}")
    pump()
    return result


def _log_scan_summary(log, counts, candidate_count):
    """Summary block. Labels are padded rather than hand-spaced because one of
    them embeds ``ZERO_TC`` and would otherwise drift out of alignment."""
    def line(label, value):
        log(f"  {label.ljust(30)}{value}")

    line("Clips scanned:", counts["scanned"])
    line(f"At {ZERO_TC}:", counts["zero_tc"])
    for label, key in (
        ("Skipped (no media file):", "skipped_no_path"),
        ("Skipped (images):", "skipped_image"),
        ("Skipped (audio):", "skipped_audio"),
        ("Skipped (used in a timeline):", "skipped_in_timeline"),
        ("Skipped (no creation date):", "skipped_no_date"),
    ):
        if counts[key]:
            line(label, counts[key])
    line("Clips to change:", candidate_count)
