"""Rename Clips From Markers.

Renames timeline clips from a regex match against marker name + note, with
optional prepend/append affix, track + In/Out scoping, and a dry-run preview.
Port of davinci-resolve-scripts/Edit/RenameClipsFromMarkers.py.
"""

from .log_feature import TrackFilterLogFeature
from ..state import StateStore
from .. import track_filter_ui
from .. import ui_strings as us
from ..ops.rename_markers import rename_clips_from_markers

DEFAULTS = {
    "pattern": "",
    "affix": "",
    "position_index": 1,  # 0 = prepend, 1 = append
    "use_inout": False,
    "use_track_filter": False,
    "track_filter": "",
    "dry_run": False,
}


class RenameFromMarkersFeature(TrackFilterLogFeature):
    id = "rename"
    title = "Rename Clips From Markers"
    category = "edit"
    run_label = "Rename Clips"
    track_filter_label_width = 80

    def state_store(self):
        return StateStore("rename_from_markers", DEFAULTS)

    def form_rows(self, ui):
        return [
            ui.Label(
                {"Text": us.LABEL_MARKER_PATTERN,
                 "Weight": 0}
            ),
            ui.LineEdit(
                {"ID": self.wid("Pattern"),
                 "PlaceholderText": us.PLACEHOLDER_MARKER_PATTERN,
                 "Text": "", "Weight": 0}
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Add this text:", "Weight": 0, "MinimumSize": [80, 0]}),
                    ui.LineEdit(
                        {"ID": self.wid("Affix"),
                         "PlaceholderText": "Optional — added before or after the match"}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Where to add:", "Weight": 0, "MinimumSize": [80, 0]}),
                    ui.ComboBox({"ID": self.wid("Position"), "Weight": 1}),
                ],
            ),
        ] + self.track_filter_rows(ui) + [
            ui.CheckBox(
                {"ID": self.wid("UseInOut"),
                 "Text": us.CHECK_TIMELINE_INOUT,
                 "Checked": False, "Weight": 0}
            ),
            ui.CheckBox(
                {"ID": self.wid("DryRun"),
                 "Text": us.CHECK_PREVIEW_ONLY,
                 "Checked": False, "Weight": 0}
            ),
        ]

    def apply_state(self, items, state):
        combo = items[self.wid("Position")]
        combo.AddItem("Before the matched text")
        combo.AddItem("After the matched text")
        items[self.wid("Pattern")].Text = state["pattern"]
        items[self.wid("Affix")].Text = state["affix"]
        pos = state["position_index"] if state["position_index"] in (0, 1) else 1
        combo.CurrentIndex = pos
        track_filter_ui.apply_track_filter_state(items, self, state)
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])

    def gather(self, items):
        position_index = items[self.wid("Position")].CurrentIndex
        track_spec, _use_tracks, track_state = track_filter_ui.gather_track_filter(
            items, self
        )
        params = {
            "pattern_str": items[self.wid("Pattern")].Text,
            "affix": items[self.wid("Affix")].Text,
            "prepend": position_index == 0,
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "track_filter_spec": track_spec,
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "pattern": params["pattern_str"],
            "affix": params["affix"],
            "position_index": position_index,
            "use_inout": params["use_inout"],
            "dry_run": params["dry_run"],
            **track_state,
        }
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        return rename_clips_from_markers(
            ctx.conn, log=log, pump=pump, should_cancel=should_cancel, **params
        )
