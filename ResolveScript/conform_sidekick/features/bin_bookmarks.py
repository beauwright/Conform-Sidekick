"""Bin Bookmarks.

Keep a per-project list of media-pool bins and jump the media pool straight to
one by clicking it. Bookmarks follow a bin through renames and moves (they are
keyed on the bin's unique id); see :mod:`conform_sidekick.ops.bin_bookmarks`.
"""

import time

from .base import Feature
from .. import ui_kit
from .. import ui_strings as us
from ..ops import bin_bookmarks as bb
from ..state import StateStore

DEFAULTS = {
    # project unique id -> [{"id": bin unique id, "path": "/FOOTAGE/Day 01"}, ...]
    "by_project": {},
}

COLUMNS = ["Bin", "Location"]
COLUMN_WIDTHS = [240, 520]
# Bin unique id, kept in a column past ColumnCount so it is stored on the row
# but never drawn. Click events hand back a different item object than the one
# created at populate time, so the id has to travel on the row itself.
ID_COLUMN = 2

# UIManager occasionally delivers a click twice; a repeated Move would shift
# the bookmark two rows.
REPEAT_GUARD_SECS = 0.15


def _project_key(project):
    for getter in ("GetUniqueId", "GetName"):
        try:
            value = getattr(project, getter)()
            if value:
                return str(value)
        except Exception:
            continue
    return ""


class BinBookmarksFeature(Feature):
    id = "binbookmarks"
    title = "Bin Bookmarks"
    category = "media"

    def __init__(self):
        self._bookmarks = []
        self._missing = set()
        self._selected_id = ""
        self._last_move = 0.0

    def state_store(self):
        return StateStore("bin_bookmarks", DEFAULTS)

    # -- layout ------------------------------------------------------------

    def build_layout(self, ui):
        return ui.VGroup(
            {"Spacing": 8, "Weight": 1},
            [
                ui_kit.note_block(ui, us.BIN_BOOKMARKS_INTRO),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Add"), "Text": us.BTN_BOOKMARK_CURRENT_BIN,
                             "Default": True, "MinimumSize": [170, 0]},
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Refresh"), "Text": "Refresh",
                             "MinimumSize": [88, 0]},
                        ),
                        ui.HGap(0, 1.0),
                    ],
                ),
                ui.Label(
                    {"ID": self.wid("Status"), "Text": "", "Weight": 0,
                     "StyleSheet": "font-weight: bold;"}
                ),
                ui.Tree(
                    {"ID": self.wid("Tree"), "Weight": 1, "SortingEnabled": False}
                ),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui.Label({"Text": "Selected:", "Weight": 0,
                                  "MinimumSize": [70, 0]}),
                        ui.Label(
                            {"ID": self.wid("Selected"), "Text": "—", "Weight": 0,
                             "MinimumSize": [180, 0], "StyleSheet": "font-weight: bold;"}
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Up"), "Text": "Move Up",
                             "Enabled": False, "MinimumSize": [90, 0]},
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Down"), "Text": "Move Down",
                             "Enabled": False, "MinimumSize": [90, 0]},
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Remove"), "Text": "Remove Bookmark",
                             "Enabled": False, "MinimumSize": [130, 0]},
                        ),
                        ui.HGap(0, 1.0),
                    ],
                ),
                ui_kit.bottom_layout_pad(ui),
            ],
        )

    # -- project state -----------------------------------------------------

    def _load(self, project):
        by_project = self.state_store().load().get("by_project")
        if not isinstance(by_project, dict):
            return []
        return bb.clean(by_project.get(_project_key(project)))

    def _save(self, project):
        key = _project_key(project)
        if not key:
            return
        store = self.state_store()
        by_project = store.load().get("by_project")
        by_project = dict(by_project) if isinstance(by_project, dict) else {}
        if self._bookmarks:
            by_project[key] = self._bookmarks
        else:
            by_project.pop(key, None)
        store.save({"by_project": by_project})

    def _sync(self, ctx):
        """Reload the open project's bookmarks against its live bin tree.

        Returns ``(project, media_pool, bins)``, or ``None`` with the list
        emptied when no project is open. Called at the top of every action so a
        project switch behind the window's back can never mix two projects.
        """
        project = ctx.conn.get_project()
        media_pool = None
        if project is not None:
            try:
                media_pool = project.GetMediaPool()
            except Exception:
                media_pool = None
        if media_pool is None:
            self._bookmarks, self._missing = [], set()
            return None
        bins = bb.walk_bins(media_pool)
        saved = self._load(project)
        self._bookmarks, self._missing = bb.refresh(saved, bins)
        if self._bookmarks != saved:
            # A bin was renamed or moved: keep the stored path current.
            self._save(project)
        return project, media_pool, bins

    def _bookmark(self, uid):
        for bookmark in self._bookmarks:
            if bookmark["id"] == uid:
                return bookmark
        return None

    # -- behaviour ---------------------------------------------------------

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win
        tree = items[self.wid("Tree")]
        status = items[self.wid("Status")]
        selected_label = items[self.wid("Selected")]
        ui_kit.setup_tree(tree, COLUMNS, COLUMN_WIDTHS)

        def set_status(text):
            try:
                status.Text = text
            except Exception:
                pass

        def set_selected(uid):
            bookmark = self._bookmark(uid) if uid else None
            self._selected_id = bookmark["id"] if bookmark else ""
            try:
                selected_label.Text = (
                    bb.bin_name(bookmark["path"]) if bookmark else "—"
                )
                for name in ("Up", "Down", "Remove"):
                    items[self.wid(name)].Enabled = bookmark is not None
            except Exception:
                pass

        def render():
            ui_kit.clear_tree(tree)
            for bookmark in self._bookmarks:
                location = bookmark["path"]
                if bookmark["id"] in self._missing:
                    location += us.BIN_BOOKMARKS_MISSING_SUFFIX
                item = ui_kit.add_row(tree, [bb.bin_name(bookmark["path"]), location])
                try:
                    item.Text[ID_COLUMN] = bookmark["id"]
                    if bookmark["id"] == self._selected_id:
                        item.Selected = True
                except Exception:
                    pass
            set_selected(self._selected_id)

        def idle_status(project):
            if project is None:
                return us.STATUS_NO_PROJECT
            if not self._bookmarks:
                return us.BIN_BOOKMARKS_EMPTY
            return f"{len(self._bookmarks)} bookmarked bin(s) in {project.GetName()}."

        def refresh(message=None):
            synced = self._sync(ctx)
            render()
            set_status(message or idle_status(synced[0] if synced else None))
            ui_kit.pump(ctx.dispatcher)

        def on_add():
            synced = self._sync(ctx)
            if synced is None:
                return refresh()
            project, media_pool, bins = synced
            current = bb.current_bin(media_pool, bins)
            if current is None:
                return refresh("Could not read the current bin from the media pool.")
            folder, path = current
            uid = bb.folder_id(folder)
            self._bookmarks, added = bb.add(self._bookmarks, uid, path)
            self._selected_id = uid
            if added:
                self._save(project)
                refresh(f"Bookmarked {path}.")
            else:
                refresh(f"{path} is already bookmarked.")

        def on_go(ev):
            uid = ""
            item = ui_kit.get_event_item(ev)
            if item is not None:
                try:
                    uid = item.Text[ID_COLUMN] or ""
                except Exception:
                    uid = ""
            synced = self._sync(ctx)
            if synced is None:
                return refresh()
            _project, media_pool, bins = synced
            bookmark = self._bookmark(uid)
            if bookmark is None and item is not None:
                # Fallback if a build does not hand the hidden column back.
                try:
                    shown = item.Text[1] or ""
                except Exception:
                    shown = ""
                bookmark = next(
                    (b for b in self._bookmarks if shown.startswith(b["path"])
                     and shown[len(b["path"]):] in ("", us.BIN_BOOKMARKS_MISSING_SUFFIX)),
                    None,
                )
                uid = bookmark["id"] if bookmark else ""
            if bookmark is None:
                # The row belongs to a project that is no longer the open one.
                return refresh()
            self._selected_id = uid
            ok, path = bb.go_to(media_pool, bookmark, bins)
            if path is None:
                refresh(
                    f"{bookmark['path']} no longer exists in this project. "
                    "Remove the bookmark, or undo the delete and click Refresh."
                )
            elif ok:
                refresh(f"Media pool is now showing {path}.")
            else:
                refresh(f"Resolve refused to open {path}.")

        def edit_selected(change, message):
            uid = self._selected_id
            synced = self._sync(ctx)
            if synced is None or self._bookmark(uid) is None:
                return refresh()
            path = self._bookmark(uid)["path"]
            self._bookmarks = change(self._bookmarks, uid)
            self._save(synced[0])
            refresh(message.format(path=path) if message else None)

        def on_move(delta):
            now = time.monotonic()
            if now - self._last_move < REPEAT_GUARD_SECS:
                return
            self._last_move = now
            edit_selected(lambda marks, uid: bb.move(marks, uid, delta), None)

        def on_remove():
            edit_selected(bb.remove, "Removed the bookmark for {path}.")

        self._refresh = refresh
        win.On[self.wid("Add")].Clicked = lambda ev: on_add()
        win.On[self.wid("Refresh")].Clicked = lambda ev: refresh()
        win.On[self.wid("Up")].Clicked = lambda ev: on_move(-1)
        win.On[self.wid("Down")].Clicked = lambda ev: on_move(1)
        win.On[self.wid("Remove")].Clicked = lambda ev: on_remove()
        # ItemClicked only: CurrentItemChanged also fires when the list is
        # rebuilt, which would move the media pool without a click.
        win.On[self.wid("Tree")].ItemClicked = on_go

    def on_show(self, ctx):
        self._refresh()
