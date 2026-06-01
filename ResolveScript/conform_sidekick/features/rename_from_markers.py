"""Rename Clips From Markers.

Renames timeline clips from a regex match against marker name + note, with
optional prepend/append affix, track + In/Out scoping, and a dry-run preview.
Port of davinci-resolve-scripts/Edit/RenameClipsFromMarkers.py.
"""

from .log_feature import LogFeature
from ..state import StateStore
from ..ops.rename_markers import rename_clips_from_markers

DEFAULTS = {
    "pattern": "",
    "affix": "",
    "position_index": 1,  # 0 = prepend, 1 = append
    "use_inout": False,
    "track_filter": "",
    "dry_run": False,
}


class RenameFromMarkersFeature(LogFeature):
    id = "rename"
    title = "Rename Clips From Markers"
    category = "edit"
    run_label = "Rename Clips"

    def state_store(self):
        return StateStore("rename_from_markers", DEFAULTS)

    def form_rows(self, ui):
        return [
            ui.Label(
                {"Text": "Regex pattern (matched against marker name + note):",
                 "Weight": 0}
            ),
            ui.LineEdit(
                {"ID": self.wid("Pattern"),
                 "PlaceholderText": r"e.g. ^[A-Z]{2,4}_\d+", "Text": "", "Weight": 0}
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Affix:", "Weight": 0, "MinimumSize": [80, 0]}),
                    ui.LineEdit(
                        {"ID": self.wid("Affix"),
                         "PlaceholderText": "(optional) text to prepend or append"}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Position:", "Weight": 0, "MinimumSize": [80, 0]}),
                    ui.ComboBox({"ID": self.wid("Position"), "Weight": 1}),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Tracks:", "Weight": 0, "MinimumSize": [80, 0]}),
                    ui.LineEdit(
                        {"ID": self.wid("TrackFilter"),
                         "PlaceholderText": "blank = all video tracks; e.g. 1,3-5",
                         "Weight": 1}
                    ),
                ],
            ),
            ui.CheckBox(
                {"ID": self.wid("UseInOut"),
                 "Text": "Only clips overlapping timeline In/Out range",
                 "Checked": False, "Weight": 0}
            ),
            ui.CheckBox(
                {"ID": self.wid("DryRun"),
                 "Text": "Dry run (preview only - no changes applied)",
                 "Checked": False, "Weight": 0}
            ),
        ]

    def apply_state(self, items, state):
        combo = items[self.wid("Position")]
        combo.AddItem("Prepend (affix + match)")
        combo.AddItem("Append (match + affix)")
        items[self.wid("Pattern")].Text = state["pattern"]
        items[self.wid("Affix")].Text = state["affix"]
        pos = state["position_index"] if state["position_index"] in (0, 1) else 1
        combo.CurrentIndex = pos
        items[self.wid("TrackFilter")].Text = state.get("track_filter", "")
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])

    def gather(self, items):
        position_index = items[self.wid("Position")].CurrentIndex
        params = {
            "pattern_str": items[self.wid("Pattern")].Text,
            "affix": items[self.wid("Affix")].Text,
            "prepend": position_index == 0,
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "track_filter_spec": items[self.wid("TrackFilter")].Text,
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "pattern": params["pattern_str"],
            "affix": params["affix"],
            "position_index": position_index,
            "track_filter": params["track_filter_spec"],
            "use_inout": params["use_inout"],
            "dry_run": params["dry_run"],
        }
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        return rename_clips_from_markers(
            ctx.conn, log=log, pump=pump, should_cancel=should_cancel, **params
        )
