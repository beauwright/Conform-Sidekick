"""Lay Matching Bin Clips On New Track(s).

Reconform helper: pair timeline clips with bin clips by regex and lay every
matching bin clip on new tracks at the original record position with source
timecode preserved. When a key matches multiple bin clips (e.g. split-screen
LEFT/RIGHT plates) or record ranges overlap, placements spill onto additional
tracks automatically. Optional grade/attribute copy, clip color, and
originals-disable. Port of
davinci-resolve-scripts/Edit/LayMatchingBinClipsOnNewTrack.py, with the
timecode math moved onto the vendored ``timecode`` library.
"""

from .log_feature import TrackFilterLogFeature
from ..state import StateStore
from .. import timeline_filters as tf
from .. import track_filter_ui
from .. import ui_strings as us
from ..ops.lay_clips import lay_matching_bin_clips

CLIP_COLORS = tf.CLIP_COLORS

DEFAULTS = {
    "pattern": "",
    "new_track_name": "Reconform",
    "color_index": 6,  # Teal
    "copy_grade": True,
    "copy_attrs": True,
    "disable_originals": False,
    "skip_disabled_tlis": True,
    "use_inout": False,
    "use_track_filter": False,
    "track_filter": "",
    "dry_run": False,
}


class LayMatchingClipsFeature(TrackFilterLogFeature):
    id = "layclips"
    title = "Lay Matching Bin Clips"
    category = "edit"
    run_label = "Lay Clips"

    def state_store(self):
        return StateStore("lay_matching_clips", DEFAULTS)

    def form_rows(self, ui):
        return [
            ui.Label(
                {"Text": us.LABEL_CLIP_NAME_PATTERN,
                 "Weight": 0}
            ),
            ui.LineEdit(
                {"ID": self.wid("Pattern"),
                 "PlaceholderText": us.PLACEHOLDER_CLIP_NAME_PATTERN,
                 "Text": "", "Weight": 0}
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "New track name:", "Weight": 0,
                              "MinimumSize": [130, 0]}),
                    ui.LineEdit(
                        {"ID": self.wid("TrackName"),
                         "PlaceholderText": "Optional — base name for the new video track(s)"}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Tag new clips:", "Weight": 0,
                              "MinimumSize": [130, 0]}),
                    ui.ComboBox({"ID": self.wid("ClipColor"), "Weight": 1}),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {"ID": self.wid("CopyGrade"), "Text": "Copy grade from original clip",
                         "Checked": True, "Weight": 1}
                    ),
                    ui.CheckBox(
                        {"ID": self.wid("CopyAttrs"), "Text": "Copy transform & sizing",
                         "Checked": True, "Weight": 1}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {"ID": self.wid("DisableOriginals"),
                         "Text": "Disable original clips after laying new ones",
                         "Checked": False, "Weight": 1}
                    ),
                    ui.CheckBox(
                        {"ID": self.wid("SkipDisabledTLIs"),
                         "Text": "Skip clips that are already disabled",
                         "Checked": True, "Weight": 1}
                    ),
                ],
            ),
        ] + self.track_filter_rows(ui) + [
            ui.CheckBox(
                {"ID": self.wid("UseInOut"),
                 "Text": us.CHECK_TIMELINE_INOUT,
                 "Checked": False, "Weight": 0}
            ),
            ui.CheckBox(
                {"ID": self.wid("DryRun"), "Text": us.CHECK_PREVIEW_ONLY,
                 "Checked": False, "Weight": 0}
            ),
        ]

    def apply_state(self, items, state):
        color_combo = items[self.wid("ClipColor")]
        for color in CLIP_COLORS:
            color_combo.AddItem(color)

        items[self.wid("Pattern")].Text = state["pattern"]
        items[self.wid("TrackName")].Text = state["new_track_name"]
        color_index = state["color_index"] if 0 <= state["color_index"] < len(CLIP_COLORS) else 6
        color_combo.CurrentIndex = color_index
        items[self.wid("CopyGrade")].Checked = bool(state["copy_grade"])
        items[self.wid("CopyAttrs")].Checked = bool(state["copy_attrs"])
        items[self.wid("DisableOriginals")].Checked = bool(state["disable_originals"])
        items[self.wid("SkipDisabledTLIs")].Checked = bool(state["skip_disabled_tlis"])
        track_filter_ui.apply_track_filter_state(items, self, state)
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])

    def gather(self, items):
        color_idx = items[self.wid("ClipColor")].CurrentIndex
        clip_color = CLIP_COLORS[color_idx] if 0 <= color_idx < len(CLIP_COLORS) else ""
        track_spec, _use_tracks, track_state = track_filter_ui.gather_track_filter(
            items, self
        )
        params = {
            "pattern_str": items[self.wid("Pattern")].Text,
            "new_track_name": items[self.wid("TrackName")].Text,
            "clip_color": clip_color,
            "copy_grade": bool(items[self.wid("CopyGrade")].Checked),
            "copy_attrs": bool(items[self.wid("CopyAttrs")].Checked),
            "disable_originals": bool(items[self.wid("DisableOriginals")].Checked),
            "skip_disabled_tlis": bool(items[self.wid("SkipDisabledTLIs")].Checked),
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "track_filter_spec": track_spec,
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "pattern": params["pattern_str"],
            "new_track_name": params["new_track_name"],
            "color_index": color_idx,
            "copy_grade": params["copy_grade"],
            "copy_attrs": params["copy_attrs"],
            "disable_originals": params["disable_originals"],
            "skip_disabled_tlis": params["skip_disabled_tlis"],
            "use_inout": params["use_inout"],
            "dry_run": params["dry_run"],
            **track_state,
        }
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        return lay_matching_bin_clips(
            ctx.conn, log=log, pump=pump, should_cancel=should_cancel, **params
        )
