"""VFX delivery vs timeline audit.

Compare a VFX spreadsheet (CSV or Excel) against clips on the current timeline.
Rows from the sheet that are absent from the scoped tracks are reported as
unmatched; matches can optionally flag overlapping clips on higher video tracks
within the same track-filter range.
"""

import csv
import os
import re

from .. import timecode_utils
from .. import timeline_filters as tf
from ..resolve_api import ScanCancelled


TIMELINE_KEY_FIELDS = ("clip_name", "media_name", "file_path")

# (preset_id, label, regex). Named groups ``base`` and ``ver`` are preferred.
VERSION_PATTERN_PRESETS = (
    ("comp_v", "Comp _v###", r"^(?P<base>.+)_v(?P<ver>\d+)$"),
    ("underscore_digits", "Trailing _###", r"^(?P<base>.+)_(?P<ver>\d{3,})$"),
    ("dot_digits", "Trailing .###", r"^(?P<base>.+)\.(?P<ver>\d{3,})$"),
    ("custom", "Custom regex…", ""),
)

DEFAULT_VERSION_PRESET = "comp_v"

_VERSION_SEGMENT_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)

_XLSX_EXTENSIONS = (".xlsx", ".xlsm")
_OPENPYXL_HELP = (
    "Excel (.xlsx) files require openpyxl in Resolve's Python. "
    "Re-run the Conform Sidekick installer, or export the sheet as CSV."
)


def _is_intish(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def _resolve_column(selector, header, has_header, label):
    if has_header and not _is_intish(selector):
        try:
            return header.index(selector)
        except ValueError:
            raise ValueError(
                f"{label}: column '{selector}' not found in header {header}"
            )
    if not _is_intish(selector):
        raise ValueError(
            f"{label}: without a header, column must be a 1-based index, "
            f"got '{selector}'"
        )
    idx = int(selector) - 1
    if idx < 0:
        raise ValueError(
            f"{label}: 1-based column index must be >= 1, got {selector}"
        )
    if has_header and idx >= len(header):
        raise ValueError(
            f"{label}: column index {selector} exceeds header width {len(header)}"
        )
    return idx


def _cell_text(val):
    if val is None:
        return ""
    return str(val)


def _basename_for_match(s):
    """Return the final path segment for clip names or file paths."""
    normalized = s.replace("\\", "/")
    if "/" in normalized:
        return normalized.rsplit("/", 1)[-1]
    return normalized


def _strip_file_extension(s):
    """Remove a trailing ``.ext`` from a clip name or path tail."""
    if not s:
        return s
    name = _basename_for_match(s)
    stem, ext = os.path.splitext(name)
    if ext and stem:
        return stem
    return name


def version_preset_pattern(preset_id, custom_pattern=""):
    """Resolve a preset id + optional custom pattern to a regex string."""
    if preset_id == "custom":
        return (custom_pattern or "").strip()
    for pid, _label, pattern in VERSION_PATTERN_PRESETS:
        if pid == preset_id:
            return pattern
    return VERSION_PATTERN_PRESETS[0][2]


def compile_version_pattern(pattern_str):
    """Compile a version regex, returning ``(pattern_or_None, error_or_None)``."""
    pattern_str = (pattern_str or "").strip()
    if not pattern_str:
        return None, "Version pattern is empty."
    pattern, err = tf.compile_regex(pattern_str)
    if err is not None:
        return None, f"Invalid version pattern: {err}"
    return pattern, None


def parse_version_key(pattern, normalized_key):
    """Return ``(normalized_base, version_int)`` when ``pattern`` matches."""
    if pattern is None or not normalized_key:
        return None
    match = pattern.search(normalized_key)
    if match is None:
        return None

    groups = match.groupdict()
    base = groups.get("base")
    ver_text = groups.get("ver")
    if base is None and match.lastindex and match.lastindex >= 1:
        base = match.group(1)
    if ver_text is None and match.lastindex and match.lastindex >= 2:
        ver_text = match.group(2)
    if base is None or ver_text is None:
        return None
    try:
        version = int(str(ver_text))
    except (TypeError, ValueError):
        return None
    return str(base), version


def format_version_note(sheet_version, project_version):
    delta = int(project_version) - int(sheet_version)
    sign = "+" if delta > 0 else ""
    return f"v{sheet_version} \u2192 v{project_version} ({sign}{delta})"


def build_identity_version_index(timeline_records, version_pattern, key_field="comparison_key"):
    """Map normalized shot identity to timeline entries with parsed versions."""
    index = {}
    if version_pattern is None:
        return index
    for record in timeline_records:
        lookup_key = record.get(key_field) or record.get("normalized_key", "")
        parsed = parse_version_key(version_pattern, lookup_key)
        if parsed is None:
            continue
        base, version = parsed
        entry = dict(record)
        entry["identity_base"] = base
        entry["version"] = version
        index.setdefault(base, []).append(entry)
    return index


def _best_timeline_version(entries, pick="max"):
    if not entries:
        return None
    if pick == "min":
        return min(entries, key=lambda item: item["version"])
    return max(entries, key=lambda item: item["version"])


def _clip_enabled(item):
    try:
        return bool(item.GetClipEnabled())
    except Exception:
        return True


def _build_match_warnings(inst, occluders=None):
    """Combine optional cover occluders with disabled-clip notice."""
    parts = []
    if not inst.get("clip_enabled", True):
        parts.append("Clip disabled on timeline")
    if occluders:
        parts.append("; ".join(occluders))
    return "; ".join(parts)


def _resolve_match_status(base, *, covered=False, disabled=False):
    """Return a status id from a base match type plus covered/disabled flags."""
    if base == "matched":
        if covered and disabled:
            return "matched_covered_disabled"
        if covered:
            return "matched_covered"
        if disabled:
            return "matched_disabled"
        return "matched"
    if base == "matched_normalized":
        if covered and disabled:
            return "matched_normalized_covered_disabled"
        if covered:
            return "matched_normalized_covered"
        if disabled:
            return "matched_normalized_disabled"
        return "matched_normalized"
    if disabled and base in ("newer_in_project", "older_in_project"):
        return f"{base}_disabled"
    return base


def _result_from_timeline_instance(
    status,
    vfx_key,
    version_note,
    instance,
    cover_warning="",
):
    return {
        "status": status,
        "vfx_key": vfx_key,
        "version_note": version_note,
        "track": instance.get("track", ""),
        "timecode": instance.get("timecode", ""),
        "clip_name": instance.get("clip_name", ""),
        "cover_warning": cover_warning,
    }


def _normalize_segment(token):
    if token.isdigit():
        return str(int(token))
    ver_match = _VERSION_SEGMENT_RE.match(token)
    if ver_match:
        return f"v{int(ver_match.group(1))}"
    return token


def normalize_numeric_segments(s, separator="_"):
    """Fold underscore-separated tokens so leading zeros in numbers are ignored."""
    if not s:
        return s
    return separator.join(_normalize_segment(part) for part in s.split(separator))


def comparison_key_for(normalized_key, normalize_numeric_segments_enabled=False):
    if not normalize_numeric_segments_enabled:
        return normalized_key
    return normalize_numeric_segments(normalized_key)


def normalize_key(
    val,
    trim=True,
    case_insensitive=True,
    strip_extension=False,
):
    s = "" if val is None else str(val)
    if trim:
        s = s.strip()
    if strip_extension and s:
        s = _strip_file_extension(s)
    if case_insensitive:
        s = s.lower()
    return s


def _append_vfx_row(
    rows,
    row,
    col_idx,
    trim,
    case_insensitive,
    skip_empty,
    strip_extension,
):
    raw_key = row[col_idx] if col_idx < len(row) else ""
    norm_key = normalize_key(
        raw_key, trim, case_insensitive, strip_extension=strip_extension
    )
    if skip_empty and norm_key == "":
        return
    rows.append(
        {
            "raw_key": _cell_text(raw_key),
            "normalized_key": norm_key,
            "row": row,
        }
    )


def read_vfx_csv(
    path,
    col_selector,
    *,
    has_header=True,
    delimiter=",",
    encoding="utf-8-sig",
    trim=True,
    case_insensitive=True,
    skip_empty=True,
    strip_extension=False,
):
    """Return ``[{raw_key, normalized_key, row}, ...]`` from a VFX CSV."""
    rows = []
    try:
        fh = open(path, "r", encoding=encoding, newline="")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Could not read '{path}' as text CSV ({exc}). "
            "If this is an Excel file, use .xlsx or export as CSV."
        ) from exc

    with fh:
        reader = csv.reader(fh, delimiter=delimiter)
        header = []
        if has_header:
            try:
                header = next(reader)
            except StopIteration:
                return rows
        col_idx = _resolve_column(col_selector, header, has_header, "VFX sheet")

        for row in reader:
            _append_vfx_row(
                rows, row, col_idx, trim, case_insensitive, skip_empty, strip_extension
            )
    return rows


def read_vfx_xlsx(
    path,
    col_selector,
    *,
    has_header=True,
    trim=True,
    case_insensitive=True,
    skip_empty=True,
    strip_extension=False,
):
    """Return ``[{raw_key, normalized_key, row}, ...]`` from a VFX Excel sheet."""
    try:
        import openpyxl
    except ImportError as exc:
        raise ValueError(_OPENPYXL_HELP) from exc

    rows = []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        row_iter = ws.iter_rows(values_only=True)
        header = []
        if has_header:
            try:
                header_row = next(row_iter)
            except StopIteration:
                return rows
            header = [_cell_text(c) for c in header_row]

        col_idx = _resolve_column(col_selector, header, has_header, "VFX sheet")

        for raw_row in row_iter:
            row = [_cell_text(c) for c in raw_row]
            _append_vfx_row(
                rows, row, col_idx, trim, case_insensitive, skip_empty, strip_extension
            )
    finally:
        wb.close()
    return rows


def read_vfx_delivery(
    path,
    col_selector,
    *,
    has_header=True,
    delimiter=",",
    encoding="utf-8-sig",
    trim=True,
    case_insensitive=True,
    skip_empty=True,
    strip_extension=False,
):
    """Read VFX keys from CSV or Excel (.xlsx/.xlsm)."""
    if not path or not os.path.isfile(path):
        raise ValueError(f"VFX delivery file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext in _XLSX_EXTENSIONS:
        return read_vfx_xlsx(
            path,
            col_selector,
            has_header=has_header,
            trim=trim,
            case_insensitive=case_insensitive,
            skip_empty=skip_empty,
            strip_extension=strip_extension,
        )
    if ext == ".xls":
        raise ValueError(
            "Old Excel .xls format is not supported. Save as .xlsx or export as CSV."
        )
    return read_vfx_csv(
        path,
        col_selector,
        has_header=has_header,
        delimiter=delimiter,
        encoding=encoding,
        trim=trim,
        case_insensitive=case_insensitive,
        skip_empty=skip_empty,
        strip_extension=strip_extension,
    )


def _prop(clip, key):
    try:
        return clip.GetClipProperty(key) or ""
    except Exception:
        return ""


def extract_timeline_key(item, key_field):
    if key_field == "clip_name":
        try:
            return item.GetName() or ""
        except Exception:
            return ""
    mpi = None
    try:
        mpi = item.GetMediaPoolItem()
    except Exception:
        mpi = None
    if mpi is None:
        return ""
    if key_field == "media_name":
        try:
            return mpi.GetName() or ""
        except Exception:
            return ""
    if key_field == "file_path":
        return _prop(mpi, "File Path")
    return ""


def record_ranges_overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def collect_timeline_index(
    conn,
    *,
    track_set,
    scope_range,
    key_field,
    trim=True,
    case_insensitive=True,
    strip_extension=False,
    normalize_numeric=False,
    should_cancel=None,
    on_progress=None,
):
    """Walk scoped video tracks and return timeline index structures."""
    project = conn.get_project()
    timeline = conn.get_timeline()
    if project is None or timeline is None:
        raise ValueError("Open a project and timeline first.")

    if key_field not in TIMELINE_KEY_FIELDS:
        raise ValueError(f"Unknown timeline key field: {key_field}")

    try:
        video_track_count = int(timeline.GetTrackCount("video") or 0)
    except (TypeError, ValueError):
        video_track_count = 0

    track_indices = (
        sorted(track_set)
        if track_set is not None
        else list(range(1, video_track_count + 1))
    )

    frame_rate, drop_frame = timecode_utils.get_timeline_framerate_and_dropframe(
        project, timeline
    )

    items_by_track = {idx: [] for idx in track_indices}
    key_to_instances = {}
    fold_key_to_instances = {}
    scanned = 0

    for track_idx in track_indices:
        if should_cancel is not None and should_cancel():
            raise ScanCancelled()
        for item in timeline.GetItemListInTrack("video", track_idx) or []:
            if should_cancel is not None and should_cancel():
                raise ScanCancelled()
            scanned += 1
            if on_progress is not None and scanned % 25 == 0:
                on_progress(scanned)

            try:
                start = int(item.GetStart())
                end = int(item.GetEnd())
            except (TypeError, ValueError):
                start = None
                end = None

            if (
                scope_range is not None
                and start is not None
                and end is not None
            ):
                scope_in, scope_out = scope_range
                if not record_ranges_overlap(start, end, scope_in, scope_out):
                    continue

            raw_key = extract_timeline_key(item, key_field)
            norm_key = normalize_key(
                raw_key, trim, case_insensitive, strip_extension=strip_extension
            )

            try:
                clip_name = item.GetName() or ""
            except Exception:
                clip_name = ""

            timecode = ""
            if start is not None:
                try:
                    timecode = timecode_utils.frame_to_timecode(
                        frame_rate, drop_frame, start
                    )
                except Exception:
                    timecode = ""

            comp_key = comparison_key_for(norm_key, normalize_numeric)
            record = {
                "item": item,
                "track": track_idx,
                "start": start,
                "end": end,
                "raw_key": raw_key,
                "normalized_key": norm_key,
                "comparison_key": comp_key,
                "clip_name": clip_name,
                "timecode": timecode,
                "clip_enabled": _clip_enabled(item),
            }
            items_by_track[track_idx].append(record)
            if norm_key:
                key_to_instances.setdefault(norm_key, []).append(record)
            if normalize_numeric and comp_key:
                fold_key_to_instances.setdefault(comp_key, []).append(record)

    if on_progress is not None:
        on_progress(scanned)

    return {
        "items_by_track": items_by_track,
        "key_to_instances": key_to_instances,
        "fold_key_to_instances": fold_key_to_instances,
        "clips_scanned": scanned,
        "track_indices": track_indices,
    }


def find_occlusions(instance, items_by_track, track_set):
    """Return occluder labels for clips on higher tracks within ``track_set``."""
    track = instance.get("track")
    start = instance.get("start")
    end = instance.get("end")
    if track is None or start is None or end is None:
        return []

    candidate_tracks = sorted(
        idx for idx in items_by_track if idx > track
    )
    if track_set is not None:
        candidate_tracks = [idx for idx in candidate_tracks if idx in track_set]

    occluders = []
    for track_idx in candidate_tracks:
        for other in items_by_track.get(track_idx, []):
            o_start = other.get("start")
            o_end = other.get("end")
            if o_start is None or o_end is None:
                continue
            if not record_ranges_overlap(start, end, o_start, o_end):
                continue
            name = other.get("clip_name") or "(unnamed)"
            occluders.append(f"V{track_idx} {name}")

    return occluders


def _all_timeline_records(items_by_track):
    records = []
    for track_items in items_by_track.values():
        records.extend(track_items)
    return records


def _resolve_version_drift(
    vfx_row,
    identity_index,
    version_pattern,
    warn_cover,
    items_by_track,
    track_set,
    comparison_key=None,
):
    """Return a result row when timeline has newer/older version, else None."""
    lookup_key = comparison_key if comparison_key is not None else vfx_row["normalized_key"]
    parsed = parse_version_key(version_pattern, lookup_key)
    if parsed is None:
        return None

    base, sheet_version = parsed
    entries = identity_index.get(base)
    if not entries:
        return None

    best = _best_timeline_version(entries, pick="max")
    project_version = best["version"]
    raw_key = vfx_row["raw_key"]

    if project_version > sheet_version:
        status = "newer_in_project"
    elif project_version < sheet_version:
        status = "older_in_project"
    else:
        return None

    version_note = format_version_note(sheet_version, project_version)
    occluders = []
    if warn_cover and status == "newer_in_project":
        occluders = find_occlusions(best, items_by_track, track_set)
    disabled = not best.get("clip_enabled", True)
    status = _resolve_match_status(status, disabled=disabled)

    return _result_from_timeline_instance(
        status,
        raw_key,
        version_note,
        best,
        cover_warning=_build_match_warnings(best, occluders=occluders or None),
    )


def run_version_audit(
    conn,
    *,
    vfx_csv_path,
    vfx_key_column,
    timeline_key_field="clip_name",
    vfx_has_header=True,
    vfx_delimiter=",",
    vfx_encoding="utf-8-sig",
    trim=True,
    case_insensitive=True,
    skip_empty_keys=True,
    strip_extension=True,
    normalize_numeric=False,
    detect_version_drift=False,
    version_preset=DEFAULT_VERSION_PRESET,
    version_pattern="",
    track_filter_spec="",
    use_track_filter=False,
    use_inout=False,
    warn_cover=False,
    should_cancel=None,
    on_progress=None,
):
    """Run the audit and return summary + result rows for the UI table."""
    version_regex = None
    if detect_version_drift:
        pattern_str = version_preset_pattern(version_preset, version_pattern)
        version_regex, pattern_err = compile_version_pattern(pattern_str)
        if pattern_err:
            raise ValueError(pattern_err)
    vfx_rows = read_vfx_delivery(
        vfx_csv_path,
        vfx_key_column,
        has_header=vfx_has_header,
        delimiter=vfx_delimiter,
        encoding=vfx_encoding,
        trim=trim,
        case_insensitive=case_insensitive,
        skip_empty=skip_empty_keys,
        strip_extension=strip_extension,
    )

    timeline = conn.get_timeline()
    if timeline is None:
        raise ValueError("Open a timeline first.")

    try:
        video_track_count = int(timeline.GetTrackCount("video") or 0)
    except (TypeError, ValueError):
        video_track_count = 0

    track_set = None
    if use_track_filter:
        track_set, err = tf.parse_track_filter(track_filter_spec, video_track_count)
        if err:
            raise ValueError(err)
        if not track_set:
            raise ValueError("No tracks selected in the track filter.")

    scope_range = tf.get_inout_range(timeline) if use_inout else None
    if use_inout and scope_range is None:
        raise ValueError("Timeline In/Out marks are not set.")

    index = collect_timeline_index(
        conn,
        track_set=track_set,
        scope_range=scope_range,
        key_field=timeline_key_field,
        trim=trim,
        case_insensitive=case_insensitive,
        strip_extension=strip_extension,
        normalize_numeric=normalize_numeric,
        should_cancel=should_cancel,
        on_progress=on_progress,
    )
    key_to_instances = index["key_to_instances"]
    fold_key_to_instances = index["fold_key_to_instances"]
    items_by_track = index["items_by_track"]
    timeline_records = _all_timeline_records(items_by_track)
    identity_index = {}
    if version_regex is not None:
        identity_index = build_identity_version_index(
            timeline_records,
            version_regex,
            key_field="comparison_key" if normalize_numeric else "normalized_key",
        )

    results = []
    matched_count = 0
    normalized_count = 0
    unmatched_count = 0
    covered_count = 0
    disabled_count = 0
    newer_count = 0
    older_count = 0

    for vfx_row in vfx_rows:
        if should_cancel is not None and should_cancel():
            raise ScanCancelled()

        norm_key = vfx_row["normalized_key"]
        raw_key = vfx_row["raw_key"]
        comp_key = comparison_key_for(norm_key, normalize_numeric)

        instances = key_to_instances.get(norm_key, [])
        match_mode = "exact"
        if not instances and normalize_numeric:
            instances = fold_key_to_instances.get(comp_key, [])
            if instances:
                match_mode = "normalized"

        if not instances:
            drift_row = None
            if version_regex is not None:
                drift_row = _resolve_version_drift(
                    vfx_row,
                    identity_index,
                    version_regex,
                    warn_cover,
                    items_by_track,
                    track_set,
                    comparison_key=comp_key,
                )
            if drift_row is not None:
                status = drift_row["status"]
                if status.startswith("newer_in_project"):
                    newer_count += 1
                elif status.startswith("older_in_project"):
                    older_count += 1
                if status.endswith("_disabled"):
                    disabled_count += 1
                results.append(drift_row)
                continue

            unmatched_count += 1
            results.append(
                _result_from_timeline_instance(
                    "not_in_edit",
                    raw_key,
                    "",
                    {
                        "track": "",
                        "timecode": "",
                        "clip_name": "",
                    },
                )
            )
            continue

        for inst in instances:
            occluders = (
                find_occlusions(inst, items_by_track, track_set)
                if warn_cover
                else []
            )
            covered = bool(occluders)
            disabled = not inst.get("clip_enabled", True)
            base = "matched_normalized" if match_mode == "normalized" else "matched"
            status = _resolve_match_status(
                base, covered=covered, disabled=disabled
            )
            if match_mode == "normalized":
                normalized_count += 1
            else:
                matched_count += 1
            if covered:
                covered_count += 1
            if disabled:
                disabled_count += 1
            results.append(
                _result_from_timeline_instance(
                    status,
                    raw_key,
                    "",
                    inst,
                    cover_warning=_build_match_warnings(
                        inst, occluders=occluders or None
                    ),
                )
            )

    return {
        "results": results,
        "vfx_rows": len(vfx_rows),
        "matched_count": matched_count,
        "normalized_count": normalized_count,
        "unmatched_count": unmatched_count,
        "covered_count": covered_count,
        "disabled_count": disabled_count,
        "newer_count": newer_count,
        "older_count": older_count,
        "clips_scanned": index["clips_scanned"],
        "track_indices": index["track_indices"],
    }


def default_audit_export_path(vfx_source_path, show_filter="all"):
    """Suggest a CSV path beside the VFX delivery file."""
    base, _ext = os.path.splitext(vfx_source_path or "")
    if not base:
        return ""
    suffix = "" if show_filter == "all" else f"_{show_filter}"
    return f"{base}_audit{suffix}.csv"


def write_results_csv(path, headers, rows):
    """Write table rows to a UTF-8 CSV with Excel-friendly BOM."""
    if not path:
        raise ValueError("Export path is empty.")
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    return path
