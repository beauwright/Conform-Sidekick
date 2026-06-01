"""Lay Matching Bin Clips On New Track.

Reconform helper: pair timeline clips with bin clips by regex and lay the bin
clip on a new track at the original record position with source timecode
preserved. Optional grade/attribute copy, clip color, originals-disable, and a
comparison track. Port of
davinci-resolve-scripts/Edit/LayMatchingBinClipsOnNewTrack.py, with the
timecode math moved onto the vendored ``timecode`` library.
"""

from .log_feature import LogFeature
from ..state import StateStore
from .. import timeline_filters as tf
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
    "track_filter": "",
    "dry_run": False,
    "add_offset_track": False,
    "offset_track_frames": -1,
}


class LayMatchingClipsFeature(LogFeature):
    id = "layclips"
    title = "Lay Matching Bin Clips"
    run_label = "Lay Clips"

    def state_store(self):
        return StateStore("lay_matching_clips", DEFAULTS)

    def form_rows(self, ui):
        return [
            ui.Label(
                {"Text": "Regex (matched against TimelineItem AND MediaPoolItem names):",
                 "Weight": 0}
            ),
            ui.LineEdit(
                {"ID": self.wid("Pattern"),
                 "PlaceholderText": r"e.g. ^(SHOT_\d+)  (group 1 is the pairing key)",
                 "Text": "", "Weight": 0}
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "New track name:", "Weight": 0,
                              "MinimumSize": [130, 0]}),
                    ui.LineEdit(
                        {"ID": self.wid("TrackName"),
                         "PlaceholderText": "(optional) name for the new video track"}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Clip color:", "Weight": 0,
                              "MinimumSize": [130, 0]}),
                    ui.ComboBox({"ID": self.wid("ClipColor"), "Weight": 1}),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {"ID": self.wid("CopyGrade"), "Text": "Copy grade from original",
                         "Checked": True, "Weight": 1}
                    ),
                    ui.CheckBox(
                        {"ID": self.wid("CopyAttrs"), "Text": "Copy video attributes",
                         "Checked": True, "Weight": 1}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {"ID": self.wid("DisableOriginals"),
                         "Text": "Disable original TimelineItems",
                         "Checked": False, "Weight": 1}
                    ),
                    ui.CheckBox(
                        {"ID": self.wid("SkipDisabledTLIs"),
                         "Text": "Skip disabled TimelineItems",
                         "Checked": True, "Weight": 1}
                    ),
                ],
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Tracks:", "Weight": 0, "MinimumSize": [130, 0]}),
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
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {"ID": self.wid("AddOffsetTrack"),
                         "Text": "Also lay a comparison track with source-frame offset:",
                         "Checked": False, "Weight": 1}
                    ),
                    ui.SpinBox(
                        {"ID": self.wid("OffsetTrackFrames"), "Minimum": -240,
                         "Maximum": 240, "Value": -1, "MinimumSize": [80, 0],
                         "MaximumSize": [80, 16777215], "Weight": 0}
                    ),
                    ui.Label({"Text": "frames", "Weight": 0, "MinimumSize": [50, 0]}),
                ],
            ),
            ui.CheckBox(
                {"ID": self.wid("DryRun"), "Text": "Dry run (preview only)",
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
        items[self.wid("TrackFilter")].Text = state.get("track_filter", "")
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])
        items[self.wid("AddOffsetTrack")].Checked = bool(state.get("add_offset_track", False))
        try:
            items[self.wid("OffsetTrackFrames")].Value = int(state.get("offset_track_frames", -1))
        except (TypeError, ValueError):
            items[self.wid("OffsetTrackFrames")].Value = -1

    def gather(self, items):
        color_idx = items[self.wid("ClipColor")].CurrentIndex
        clip_color = CLIP_COLORS[color_idx] if 0 <= color_idx < len(CLIP_COLORS) else ""
        try:
            offset_track_frames = int(items[self.wid("OffsetTrackFrames")].Value)
        except (TypeError, ValueError):
            offset_track_frames = -1
        params = {
            "pattern_str": items[self.wid("Pattern")].Text,
            "new_track_name": items[self.wid("TrackName")].Text,
            "clip_color": clip_color,
            "copy_grade": bool(items[self.wid("CopyGrade")].Checked),
            "copy_attrs": bool(items[self.wid("CopyAttrs")].Checked),
            "disable_originals": bool(items[self.wid("DisableOriginals")].Checked),
            "skip_disabled_tlis": bool(items[self.wid("SkipDisabledTLIs")].Checked),
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "track_filter_spec": items[self.wid("TrackFilter")].Text,
            "dry_run": bool(items[self.wid("DryRun")].Checked),
            "add_offset_track": bool(items[self.wid("AddOffsetTrack")].Checked),
            "offset_track_frames": offset_track_frames,
        }
        state = {
            "pattern": params["pattern_str"],
            "new_track_name": params["new_track_name"],
            "color_index": color_idx,
            "copy_grade": params["copy_grade"],
            "copy_attrs": params["copy_attrs"],
            "disable_originals": params["disable_originals"],
            "skip_disabled_tlis": params["skip_disabled_tlis"],
            "track_filter": params["track_filter_spec"],
            "use_inout": params["use_inout"],
            "dry_run": params["dry_run"],
            "add_offset_track": params["add_offset_track"],
            "offset_track_frames": offset_track_frames,
        }
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        return lay_matching_bin_clips(
            ctx.conn, log=log, pump=pump, should_cancel=should_cancel, **params
        )
