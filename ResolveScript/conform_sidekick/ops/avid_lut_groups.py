"""Color Groups from Avid LUTs - core operation.

Reads an Avid bin (``.avb``, via the vendored ``pyavb``) for each master clip's
shot LUT, matches the current timeline's clips back to those bin clips, and
assigns every matched clip to the existing Resolve color group the user mapped
its LUT to. Groups are never given nodes or LUTs here: the point is to drop
clips into groups that already hold the show-LUT node trees.

What the bin carries for each master clip (all in the clip's ``_USER``
attributes, i.e. the bin's custom/metadata columns):

* the LUT the assistants logged, in a custom column (``LUT`` by default);
* the camera's own LUT from the ARRI metadata: ``lut3DFilename`` when a custom
  look was loaded in camera, else ``lut3DID`` (e.g. the stock Rec709 LUT);
* the camera file name (``clipName``, e.g. ``A_0018C003_260921_161258_p1CQI``)
  and, on the picture track's tape source mob, the camera roll
  (``A_0018_1CQI``).

Matching tries, in order, whichever of these the user enabled:

1. Resolve's File Name / Clip Name (extension stripped) against the bin's
   camera file name: the reliable match when conforming camera originals.
2. Resolve's Reel Name against the bin's camera roll. A roll holds many shots
   that may carry different LUTs, so a roll match only counts when every bin
   clip on that roll resolves to the same LUT.
3. Resolve's Clip Name / timeline item name against the Avid clip name, for
   conforms that still point at the dailies.

Clips that are already in a color group are always skipped, so re-running
never moves a clip a colorist has grouped by hand.
"""

import os
import re

from .. import timecode_utils
from .. import timeline_filters as tf

# Which bin value supplies a clip's LUT, in priority order.
LUT_SOURCE_COLUMN_THEN_CAMERA = "column_then_camera"
LUT_SOURCE_CAMERA_THEN_COLUMN = "camera_then_column"
LUT_SOURCE_COLUMN_ONLY = "column"
LUT_SOURCE_CAMERA_ONLY = "camera"
LUT_SOURCES = (
    LUT_SOURCE_COLUMN_THEN_CAMERA,
    LUT_SOURCE_CAMERA_THEN_COLUMN,
    LUT_SOURCE_COLUMN_ONLY,
    LUT_SOURCE_CAMERA_ONLY,
)

# Camera metadata keys that name the LUT used on set, most specific first.
CAMERA_LUT_KEYS = ("lut3DFilename", "lut3DID")
CAMERA_FILE_KEY = "clipName"

MATCH_CAMERA_FILE = "camera_file"
MATCH_CAMERA_ROLL = "camera_roll"
MATCH_CLIP_NAME = "clip_name"
MATCH_METHODS = (MATCH_CAMERA_FILE, MATCH_CAMERA_ROLL, MATCH_CLIP_NAME)
MATCH_LABELS = {
    MATCH_CAMERA_FILE: "camera file",
    MATCH_CAMERA_ROLL: "camera roll",
    MATCH_CLIP_NAME: "clip name",
}

# Mapping value meaning "create an empty group named after the LUT".
NEW_GROUP = "\u0000new"

# Extensions stripped before comparing names (Resolve File Names carry them,
# Avid camera file names and clip names do not).
_MEDIA_EXTENSIONS = {
    ".mxf", ".mov", ".mp4", ".ari", ".arx", ".r3d", ".braw", ".dng", ".dpx",
    ".exr", ".crm", ".mts", ".avi", ".wav", ".tif", ".tiff",
}
_LUT_EXTENSIONS = {".cube", ".3dl", ".lut", ".ilut", ".olut", ".csp", ".dat", ".vlt"}


def _noop():
    pass


# ---------------------------------------------------------------------------
# Name helpers (pure)
# ---------------------------------------------------------------------------

def strip_extension(name, extensions=_MEDIA_EXTENSIONS):
    name = (name or "").strip()
    root, ext = os.path.splitext(name)
    return root if ext.lower() in extensions else name


def name_key(name):
    """Case-insensitive comparison key with a media extension removed."""
    return strip_extension(name).casefold()


# Spanned camera clips land in Resolve as one file per segment
# (``A_0001C002_..._p1CQI_S001.mxf``); the Avid bin names the whole clip.
_SEGMENT_SUFFIX = re.compile(r"_s\d{3}$")


def camera_file_keys(name):
    """Keys to try against the bin's camera file names, most exact first."""
    key = name_key(name)
    if not key:
        return []
    unsegmented = _SEGMENT_SUFFIX.sub("", key)
    return [key] if unsegmented == key else [key, unsegmented]


def lut_stem(lut):
    """LUT name without its file extension: the default new-group name."""
    return strip_extension(lut, _LUT_EXTENSIONS)


def _alnum(text):
    return re.sub(r"[^0-9a-z]+", "", (text or "").casefold())


def lut_core(lut):
    """The shot-look part of a show LUT name.

    ``Quit-Clinic-Int_v01_65p_LogC4.cube`` -> ``Quit-Clinic-Int``: the version
    and everything after it (output size, input gamma) is dropped.
    """
    stem = lut_stem(lut)
    return re.split(r"[_\s.-]v\d+", stem, maxsplit=1, flags=re.IGNORECASE)[0] or stem


def suggest_group(lut, group_names):
    """Best existing group name for ``lut``, or ``""`` when nothing is close.

    Exact (case/punctuation-insensitive) matches on the LUT stem or its core
    win; otherwise the longest group name contained in the core, or containing
    it, as long as it is at least four characters (so ``Int`` alone never
    claims ``Quit-Clinic-Int``).
    """
    stem_key = _alnum(lut_stem(lut))
    core_key = _alnum(lut_core(lut))
    if not core_key:
        return ""
    keyed = [(name, _alnum(name)) for name in group_names if _alnum(name)]
    for wanted in (stem_key, core_key):
        for name, key in keyed:
            if key == wanted:
                return name
    best = ""
    best_len = 0
    for name, key in keyed:
        if len(key) < 4:
            continue
        if key in core_key or core_key in key:
            if len(key) > best_len:
                best, best_len = name, len(key)
    return best


# ---------------------------------------------------------------------------
# Avid bin reading
# ---------------------------------------------------------------------------

def _tape_name(mob, depth=0):
    """Name of the first tape source mob reached from the picture track."""
    if depth > 4:
        return ""
    for track in getattr(mob, "tracks", None) or []:
        if depth == 0 and getattr(track, "media_kind", "picture") != "picture":
            continue
        component = track.component
        for clip in getattr(component, "components", [component]):
            if clip.__class__.__name__ != "SourceClip":
                continue
            try:
                source = clip.mob
            except Exception:
                source = None
            if source is None:
                continue
            if type(getattr(source, "descriptor", None)).__name__ == "TapeDescriptor":
                return (source.name or "").strip()
            found = _tape_name(source, depth + 1)
            if found:
                return found
    return ""


def _text(value):
    return "" if value is None else str(value).strip()


def bin_clip_from_attrs(name, user_attrs, tape="", lut_column="LUT"):
    """One bin clip record from a master clip's ``_USER`` attributes."""
    user = user_attrs or {}
    camera_lut = ""
    for key in CAMERA_LUT_KEYS:
        camera_lut = _text(user.get(key))
        if camera_lut:
            break
    return {
        "name": _text(name),
        "column_lut": _text(user.get(lut_column)) if lut_column else "",
        "camera_lut": camera_lut,
        "camera_file": _text(user.get(CAMERA_FILE_KEY)),
        "tape": _text(tape),
    }


def read_avid_bin(path, lut_column="LUT"):
    """Return the bin's master clips as records (see :func:`bin_clip_from_attrs`).

    Raises ``OSError`` / ``ValueError`` for an unreadable or non-bin file.
    """
    import avb  # vendored; imported here so the rest of the module loads without it

    clips = []
    with avb.open(path) as bin_file:
        for item in bin_file.content.items:
            mob = item.mob
            if getattr(mob, "mob_type", "") != "MasterMob":
                continue
            attrs = getattr(mob, "attributes", None) or {}
            try:
                user = attrs.get("_USER") or {}
            except Exception:
                user = {}
            clips.append(
                bin_clip_from_attrs(mob.name, user, _tape_name(mob), lut_column)
            )
    return clips


def clip_lut(clip, lut_source):
    """``(lut, origin)`` for a bin clip under ``lut_source``; origin is
    ``"column"``, ``"camera"`` or ``""`` when neither has a value."""
    order = {
        LUT_SOURCE_COLUMN_THEN_CAMERA: ("column", "camera"),
        LUT_SOURCE_CAMERA_THEN_COLUMN: ("camera", "column"),
        LUT_SOURCE_COLUMN_ONLY: ("column",),
        LUT_SOURCE_CAMERA_ONLY: ("camera",),
    }.get(lut_source, ("column", "camera"))
    for origin in order:
        value = clip.get(f"{origin}_lut", "")
        if value:
            return value, origin
    return "", ""


# ---------------------------------------------------------------------------
# Matching (pure)
# ---------------------------------------------------------------------------

class BinIndex:
    """Lookups from Resolve-side names to bin clips."""

    def __init__(self, clips):
        self.clips = list(clips)
        self.by_camera_file = {}
        self.by_tape = {}
        self.by_name = {}
        for clip in self.clips:
            if clip["camera_file"]:
                self.by_camera_file.setdefault(name_key(clip["camera_file"]), []).append(clip)
            if clip["tape"]:
                self.by_tape.setdefault(clip["tape"].casefold(), []).append(clip)
            if clip["name"]:
                self.by_name.setdefault(name_key(clip["name"]), []).append(clip)

    def candidates(self, method, keys):
        """Bin clips matching the Resolve ``keys`` dict by one method."""
        if method == MATCH_CAMERA_FILE:
            table = self.by_camera_file
            names = [k for n in (keys.get("file_name"), keys.get("clip_name"))
                     for k in camera_file_keys(n)]
        elif method == MATCH_CAMERA_ROLL:
            names, table = [(keys.get("reel_name") or "").strip().casefold()], self.by_tape
        elif method == MATCH_CLIP_NAME:
            names, table = (keys.get("clip_name"), keys.get("item_name")), self.by_name
            names = [name_key(n) for n in names]
        else:
            return []
        for key in names:
            if key and key in table:
                return table[key]
        return []


def resolve_lut(index, keys, methods, lut_source):
    """Find the shot LUT for one timeline clip.

    Returns a dict with ``status`` (``matched`` / ``ambiguous`` / ``no_lut`` /
    ``no_match``), ``method`` (the match that decided it), ``lut``,
    ``origin`` and, for ambiguous matches, the competing ``luts``.
    """
    matched_any = None
    for method in methods:
        clips = index.candidates(method, keys)
        if not clips:
            continue
        luts = {}
        blank = False
        for clip in clips:
            lut, origin = clip_lut(clip, lut_source)
            if lut:
                luts.setdefault(lut, origin)
            else:
                blank = True
        if luts and blank:
            # Some shots on the roll have a LUT and some have none: the roll
            # alone cannot say which this clip is.
            luts[""] = ""
        if len(luts) == 1:
            lut, origin = next(iter(luts.items()))
            return {"status": "matched", "method": method, "lut": lut,
                    "origin": origin, "bin_clip": clips[0]["name"]}
        if len(luts) > 1:
            # A roll (or a duplicated name) spanning several LUTs: try the
            # next, more specific method before giving up.
            matched_any = matched_any or {
                "status": "ambiguous", "method": method, "lut": "",
                "origin": "", "luts": sorted(lut or "(no LUT)" for lut in luts),
                "bin_clip": clips[0]["name"],
            }
            continue
        matched_any = matched_any or {
            "status": "no_lut", "method": method, "lut": "", "origin": "",
            "bin_clip": clips[0]["name"],
        }
    return matched_any or {"status": "no_match", "method": "", "lut": "", "origin": ""}


def lut_counts(records):
    """``{lut: matched timeline clip count}`` for the mapping table."""
    counts = {}
    for record in records:
        if record["status"] == "matched":
            counts[record["lut"]] = counts.get(record["lut"], 0) + 1
    return counts


def bin_luts(clips, lut_source):
    """Every LUT the bin assigns to at least one clip under ``lut_source``."""
    found = set()
    for clip in clips:
        lut, _origin = clip_lut(clip, lut_source)
        if lut:
            found.add(lut)
    return sorted(found, key=str.casefold)


def mapping_target(mapping, lut):
    """``(group_name, create)`` for a LUT, ``("", False)`` when unmapped."""
    value = (mapping or {}).get(lut, "")
    if value == NEW_GROUP:
        return lut_stem(lut), True
    return value or "", False


# ---------------------------------------------------------------------------
# Resolve side
# ---------------------------------------------------------------------------

def color_groups(project):
    """``{name: ColorGroup}`` for the project's existing groups."""
    groups = {}
    try:
        group_list = project.GetColorGroupsList() or []
    except Exception:
        group_list = []
    for group in group_list:
        try:
            name = group.GetName() or ""
        except Exception:
            name = ""
        if name and name not in groups:
            groups[name] = group
    return groups


def _clip_property(mpi, key):
    try:
        return mpi.GetClipProperty(key) or ""
    except Exception:
        return ""


def item_keys(item):
    """The Resolve names a timeline item can be matched on."""
    keys = {"item_name": "", "file_name": "", "clip_name": "", "reel_name": ""}
    try:
        keys["item_name"] = item.GetName() or ""
    except Exception:
        pass
    try:
        mpi = item.GetMediaPoolItem()
    except Exception:
        mpi = None
    if mpi is not None:
        keys["file_name"] = _clip_property(mpi, "File Name")
        keys["clip_name"] = _clip_property(mpi, "Clip Name")
        keys["reel_name"] = _clip_property(mpi, "Reel Name")
    return keys


def _current_group_name(item):
    try:
        group = item.GetColorGroup()
    except Exception:
        return ""
    if group is None:
        return ""
    try:
        return group.GetName() or "(unnamed group)"
    except Exception:
        return "(unnamed group)"


def scan_timeline(
    timeline,
    index,
    methods,
    lut_source,
    track_filter_spec="",
    log=print,
    pump=_noop,
    should_cancel=lambda: False,
):
    """Match every video clip on ``timeline`` against the bin.

    Returns ``(records, error)``. Each record carries the item, its track and
    record frame, the Resolve names, the current color group and the
    :func:`resolve_lut` result.
    """
    try:
        track_count = int(timeline.GetTrackCount("video") or 0)
    except Exception:
        track_count = 0
    track_set, track_err = tf.parse_track_filter(track_filter_spec, track_count)
    if track_err:
        return [], f"Tracks: {track_err}"
    tracks = sorted(track_set) if track_set is not None else range(1, track_count + 1)

    records = []
    for track in tracks:
        try:
            items = timeline.GetItemListInTrack("video", track) or []
        except Exception:
            items = []
        for item in items:
            if should_cancel():
                return records, None
            keys = item_keys(item)
            if not (keys["file_name"] or keys["clip_name"]):
                continue  # generators, titles, adjustment clips
            try:
                start = int(item.GetStart())
            except Exception:
                start = None
            record = {
                "item": item,
                "track": track,
                "start": start,
                "keys": keys,
                "group": _current_group_name(item),
            }
            record.update(resolve_lut(index, keys, methods, lut_source))
            records.append(record)
            if len(records) % 50 == 0:
                pump()
    return records, None


def _where(record, fps, drop):
    tc = ""
    if record["start"] is not None and fps:
        try:
            tc = timecode_utils.frame_to_timecode(fps, drop, record["start"])
        except Exception:
            tc = str(record["start"])
    name = record["keys"]["item_name"] or record["keys"]["clip_name"]
    return f"V{record['track']} {tc} {name}".replace("  ", " ")


def assign_color_groups(
    conn,
    bin_clips,
    mapping,
    methods,
    lut_source,
    track_filter_spec="",
    dry_run=False,
    log=print,
    pump=_noop,
    should_cancel=lambda: False,
):
    """Put each matched timeline clip into its LUT's mapped color group."""
    result = {
        "scanned": 0, "assigned": 0, "failed": 0, "already_grouped": 0,
        "unmapped": 0, "no_match": 0, "no_lut": 0, "ambiguous": 0,
        "groups_created": 0, "cancelled": False, "error": False,
    }
    project = conn.get_project()
    timeline = conn.get_timeline()
    if project is None or timeline is None:
        log("Open a project and a timeline first.")
        result["error"] = True
        return result
    if not methods:
        log("Pick at least one way to match clips (camera file, camera roll or clip name).")
        result["error"] = True
        return result

    try:
        fps, drop = timecode_utils.get_timeline_framerate_and_dropframe(project, timeline)
    except Exception:
        fps, drop = "", False

    log("Color Groups from Avid LUTs - DRY RUN" if dry_run else "Color Groups from Avid LUTs")
    log(f"  Timeline: {timeline.GetName()}")
    log(f"  Match by: {', '.join(MATCH_LABELS[m] for m in methods)}")
    pump()

    index = BinIndex(bin_clips)
    records, err = scan_timeline(
        timeline, index, methods, lut_source, track_filter_spec, log, pump, should_cancel
    )
    if err:
        log(err)
        result["error"] = True
        return result
    result["scanned"] = len(records)

    groups = color_groups(project)
    leftovers = {"already": [], "unmapped": [], "no_match": [], "no_lut": [], "ambiguous": []}

    for position, record in enumerate(records, 1):
        if should_cancel():
            result["cancelled"] = True
            break
        if position % 25 == 0:
            pump()
        where = _where(record, fps, drop)
        if record["group"]:
            result["already_grouped"] += 1
            leftovers["already"].append(f"{where}  (in '{record['group']}')")
            continue
        status = record["status"]
        if status != "matched":
            result[status] += 1
            if status == "ambiguous":
                detail = f"{MATCH_LABELS[record['method']]} spans {', '.join(record['luts'])}"
            elif status == "no_lut":
                detail = f"bin clip '{record['bin_clip']}' has no LUT"
            else:
                detail = ""
            leftovers[status].append(f"{where}  ({detail})" if detail else where)
            continue

        lut = record["lut"]
        group_name, create = mapping_target(mapping, lut)
        if not group_name:
            result["unmapped"] += 1
            leftovers["unmapped"].append(f"{where}  ({lut})")
            continue

        group = groups.get(group_name)
        if group is None and create:
            if dry_run:
                log(f"  [PLAN] create empty color group '{group_name}'")
                groups[group_name] = "planned"
                result["groups_created"] += 1
            else:
                try:
                    group = project.AddColorGroup(group_name)
                except Exception as exc:
                    group = None
                    log(f"  [FAIL] AddColorGroup('{group_name}') raised: {exc}")
                if group:
                    groups[group_name] = group
                    result["groups_created"] += 1
                    log(f"  [OK]   created empty color group '{group_name}'")
            group = groups.get(group_name)
        if group is None:
            result["failed"] += 1
            log(f"  [FAIL] {where}: color group '{group_name}' does not exist.")
            continue

        via = MATCH_LABELS[record["method"]]
        if dry_run:
            result["assigned"] += 1
            log(f"  [PLAN] {where} -> '{group_name}'  ({lut}, by {via})")
        else:
            try:
                ok = bool(record["item"].AssignToColorGroup(group))
            except Exception as exc:
                ok = False
                log(f"  [FAIL] {where}: AssignToColorGroup raised: {exc}")
            if ok:
                result["assigned"] += 1
                log(f"  [OK]   {where} -> '{group_name}'  ({lut}, by {via})")
            else:
                result["failed"] += 1
                log(f"  [FAIL] {where}: AssignToColorGroup('{group_name}') returned False.")

    sections = (
        ("already", "Skipped, already in a color group"),
        ("unmapped", "Skipped, LUT not mapped to a group"),
        ("no_lut", "Skipped, matched bin clip has no LUT"),
        ("ambiguous", "Skipped, match spans several LUTs"),
        ("no_match", "Not found in the Avid bin"),
    )
    for key, title in sections:
        if leftovers[key]:
            log("")
            log(f"{title} ({len(leftovers[key])}):")
            for line in leftovers[key]:
                log(f"  {line}")
    if result["cancelled"]:
        log("Run cancelled by user. Showing partial results above.")

    log("")
    log(f"  Timeline clips scanned:          {result['scanned']}")
    if dry_run:
        log(f"  Would be assigned:               {result['assigned']}")
    else:
        log(f"  Assigned:                        {result['assigned']}")
    if result["groups_created"]:
        if dry_run:
            log(f"  Groups to create:                {result['groups_created']}")
        else:
            log(f"  Groups created:                  {result['groups_created']}")
    log(f"  Already grouped (skipped):       {result['already_grouped']}")
    log(f"  LUT not mapped:                  {result['unmapped']}")
    log(f"  Bin clip without LUT:            {result['no_lut']}")
    log(f"  Ambiguous roll/name:             {result['ambiguous']}")
    log(f"  Not in the bin:                  {result['no_match']}")
    if result["failed"]:
        log(f"  Failures:                        {result['failed']}")
    if dry_run:
        log("  (Dry run: no changes were applied.)")
    pump()
    return result
