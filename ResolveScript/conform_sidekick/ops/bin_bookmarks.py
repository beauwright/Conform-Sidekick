"""Bin bookmarks: remember media-pool bins per project and jump back to them.

Verified against Resolve Studio 21.0.4:

* ``Folder.GetUniqueId()`` is stable for the life of the bin, so a bookmark
  survives the bin being renamed or moved. The stored path is only a fallback
  (and the label shown in the list); it is refreshed whenever the bin is found
  by id.
* ``MediaPool.SetCurrentFolder(folder)`` returns ``True`` and moves the media
  pool to that bin on whichever page is showing it.
* There is no "find folder by id" call, so the bin tree is walked each time.
  That is cheap (62 bins in 35 ms) because no clip lists are read.

* ``Folder`` has no color call (documented or otherwise), so a bin's color tag
  cannot be read. A bookmark's color is therefore one the user picks in the
  panel; it does not follow the bin's tag in Resolve.

Everything here is UI-agnostic: bookmarks are plain ``{"id", "path"}`` dicts in
display order (plus ``"color"`` when one is set), and the functions that change
the list return a new one.
"""

from ..timeline_filters import CLIP_COLORS

ROOT_PATH = "/"

# Resolve's clip color names -> approximate RGB of the swatch Resolve draws.
COLOR_RGB = {
    "Orange": (235, 110, 1),
    "Apricot": (255, 168, 51),
    "Yellow": (226, 169, 28),
    "Lime": (159, 198, 21),
    "Olive": (94, 153, 32),
    "Green": (68, 143, 101),
    "Teal": (0, 152, 153),
    "Navy": (21, 98, 132),
    "Blue": (67, 118, 161),
    "Purple": (153, 115, 160),
    "Violet": (208, 86, 141),
    "Pink": (233, 140, 181),
    "Tan": (185, 175, 151),
    "Beige": (198, 160, 119),
    "Brown": (153, 102, 0),
    "Chocolate": (140, 90, 63),
}
COLORS = [name for name in CLIP_COLORS if name in COLOR_RGB]


def _mark(uid, path, color=""):
    mark = {"id": uid, "path": path}
    if color in COLOR_RGB:
        mark["color"] = color
    return mark


def _call(obj, method, default=None):
    try:
        value = getattr(obj, method)()
    except Exception:
        return default
    return default if value is None else value


def walk_bins(media_pool):
    """Return ``[(folder, path), ...]`` for every bin, parents before children.

    Paths look like ``/FOOTAGE/Day 01``; the root bin is ``/``.
    """
    root = _call(media_pool, "GetRootFolder")
    if root is None:
        return []
    out = []
    queue = [(root, ROOT_PATH)]
    while queue:
        folder, path = queue.pop(0)
        out.append((folder, path))
        for sub in _call(folder, "GetSubFolderList", []) or []:
            name = _call(sub, "GetName", "") or ""
            sub_path = f"/{name}" if path == ROOT_PATH else f"{path}/{name}"
            queue.append((sub, sub_path))
    return out


def folder_id(folder):
    return str(_call(folder, "GetUniqueId", "") or "")


def bin_name(path):
    """Last path component; the root bin reads as ``Master``."""
    if not path or path == ROOT_PATH:
        return "Master"
    return path.rsplit("/", 1)[-1]


def index_bins(bins):
    """``(by_id, by_path)`` lookups over a :func:`walk_bins` result."""
    by_id, by_path = {}, {}
    for folder, path in bins:
        uid = folder_id(folder)
        if uid:
            by_id.setdefault(uid, (folder, path))
        by_path.setdefault(path, (folder, path))
    return by_id, by_path


def resolve_bookmark(bookmark, by_id, by_path):
    """Return ``(folder, path)`` for a bookmark, or ``None`` when the bin is gone.

    The id wins; the saved path covers projects whose ids changed (an archive
    restored or a project imported under a new database entry).
    """
    found = by_id.get(bookmark.get("id") or "")
    if found is None:
        found = by_path.get(bookmark.get("path") or "")
    return found


def refresh(bookmarks, bins):
    """Re-resolve every bookmark against the live bin tree.

    Returns ``(bookmarks, missing_ids)``: bookmarks whose bin was found carry
    its current id and path (and keep their color); the ones that were not are kept untouched (the bin
    may be back after an undo) and reported in ``missing_ids``.
    """
    by_id, by_path = index_bins(bins)
    out, missing = [], set()
    for bookmark in bookmarks:
        found = resolve_bookmark(bookmark, by_id, by_path)
        if found is None:
            out.append(dict(bookmark))
            missing.add(bookmark.get("id") or "")
            continue
        folder, path = found
        out.append(_mark(folder_id(folder) or bookmark.get("id") or "", path,
                         bookmark.get("color")))
    return out, missing


def clean(raw):
    """Coerce whatever was loaded from disk into a list of bookmark dicts."""
    out, seen = [], set()
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        uid, path = str(entry.get("id") or ""), str(entry.get("path") or "")
        if not uid or not path or uid in seen:
            continue
        seen.add(uid)
        out.append(_mark(uid, path, entry.get("color")))
    return out


def add(bookmarks, uid, path):
    """Append a bookmark. Returns ``(bookmarks, added)``; no duplicates."""
    if not uid or any(b["id"] == uid for b in bookmarks):
        return list(bookmarks), False
    return list(bookmarks) + [{"id": uid, "path": path}], True


def remove(bookmarks, uid):
    return [b for b in bookmarks if b["id"] != uid]


def set_color(bookmarks, uid, color):
    """Tag a bookmark with one of :data:`COLORS`; anything else clears it."""
    return [
        _mark(b["id"], b["path"], color if b["id"] == uid else b.get("color"))
        for b in bookmarks
    ]


def move(bookmarks, uid, delta):
    """Shift a bookmark up (``-1``) or down (``+1``) in the list."""
    out = list(bookmarks)
    for index, bookmark in enumerate(out):
        if bookmark["id"] == uid:
            target = index + delta
            if 0 <= target < len(out):
                out[index], out[target] = out[target], out[index]
            break
    return out


def current_bin(media_pool, bins=None):
    """``(folder, path)`` of the bin the media pool is showing, or ``None``."""
    current = _call(media_pool, "GetCurrentFolder")
    if current is None:
        return None
    uid = folder_id(current)
    for folder, path in bins if bins is not None else walk_bins(media_pool):
        if uid and folder_id(folder) == uid:
            return folder, path
    return None


def go_to(media_pool, bookmark, bins=None):
    """Point the media pool at a bookmarked bin.

    Returns ``(ok, path)``: ``path`` is the bin's current location, or ``None``
    when the bin no longer exists.
    """
    if bins is None:
        bins = walk_bins(media_pool)
    found = resolve_bookmark(bookmark, *index_bins(bins))
    if found is None:
        return False, None
    folder, path = found
    try:
        ok = bool(media_pool.SetCurrentFolder(folder))
    except Exception:
        ok = False
    return ok, path
