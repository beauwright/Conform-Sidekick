"""Recolor Markers.

Change every marker of one color to another, on the timeline ruler and/or on
the timeline's clips, with In/Out and track scoping and a dry-run preview. See
:mod:`conform_sidekick.ops.recolor_markers`.
"""

from .log_feature import TrackFilterLogFeature
from ..state import StateStore
from .. import track_filter_ui
from .. import ui_strings as us
from ..ops.recolor_markers import ANY_COLOR, MARKER_COLORS, recolor_markers

FROM_CHOICES = [ANY_COLOR] + MARKER_COLORS

DEFAULTS = {
    "from_index": 1,  # Blue
    "to_index": 2,  # Green
    "timeline_markers": True,
    "clip_markers": False,
    "include_audio": False,
    "use_inout": False,
    "use_track_filter": False,
    "track_filter": "",
    "dry_run": True,
}


def _row(ui, label, widget):
    return ui.HGroup(
        {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
        [ui.Label({"Text": label, "Weight": 0, "MinimumSize": [130, 0]}), widget],
    )


def _index(value, choices, default):
    return value if isinstance(value, int) and 0 <= value < len(choices) else default


class RecolorMarkersFeature(TrackFilterLogFeature):
    id = "recolormarkers"
    title = "Recolor Markers"
    category = "edit"
    run_label = "Recolor"

    def state_store(self):
        return StateStore("recolor_markers", DEFAULTS)

    def form_rows(self, ui):
        return [
            _row(ui, "Change markers of:", ui.ComboBox({"ID": self.wid("From"), "Weight": 1})),
            _row(ui, "To:", ui.ComboBox({"ID": self.wid("To"), "Weight": 1})),
            ui.CheckBox({"ID": self.wid("TimelineMarkers"),
                         "Text": "Timeline markers (on the ruler)", "Weight": 0}),
            ui.CheckBox({"ID": self.wid("ClipMarkers"),
                         "Text": "Clip markers on video clips", "Weight": 0}),
            ui.CheckBox({"ID": self.wid("IncludeAudio"),
                         "Text": "Also clip markers on audio clips (all audio tracks)",
                         "Weight": 0}),
        ] + self.track_filter_rows(ui) + [
            ui.CheckBox({"ID": self.wid("UseInOut"),
                         "Text": "Only inside the timeline In/Out range "
                                 "(timeline markers by position, clip markers by clip)",
                         "Weight": 0}),
            ui.CheckBox({"ID": self.wid("DryRun"), "Text": us.CHECK_PREVIEW_ONLY,
                         "Checked": True, "Weight": 0}),
        ]

    def apply_state(self, items, state):
        from_combo = items[self.wid("From")]
        to_combo = items[self.wid("To")]
        for color in FROM_CHOICES:
            from_combo.AddItem(color)
        for color in MARKER_COLORS:
            to_combo.AddItem(color)
        from_combo.CurrentIndex = _index(state.get("from_index"), FROM_CHOICES, 1)
        to_combo.CurrentIndex = _index(state.get("to_index"), MARKER_COLORS, 2)
        items[self.wid("TimelineMarkers")].Checked = bool(state.get("timeline_markers", True))
        items[self.wid("ClipMarkers")].Checked = bool(state.get("clip_markers", False))
        items[self.wid("IncludeAudio")].Checked = bool(state.get("include_audio", False))
        track_filter_ui.apply_track_filter_state(items, self, state)
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("DryRun")].Checked = bool(state.get("dry_run", True))

    def gather(self, items):
        from_index = _index(items[self.wid("From")].CurrentIndex, FROM_CHOICES, 1)
        to_index = _index(items[self.wid("To")].CurrentIndex, MARKER_COLORS, 2)
        track_spec, _use, track_state = track_filter_ui.gather_track_filter(items, self)
        params = {
            "from_color": FROM_CHOICES[from_index],
            "to_color": MARKER_COLORS[to_index],
            "timeline_markers": bool(items[self.wid("TimelineMarkers")].Checked),
            "clip_markers": bool(items[self.wid("ClipMarkers")].Checked),
            "include_audio": bool(items[self.wid("IncludeAudio")].Checked),
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "track_filter_spec": track_spec,
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "from_index": from_index,
            "to_index": to_index,
            "timeline_markers": params["timeline_markers"],
            "clip_markers": params["clip_markers"],
            "include_audio": params["include_audio"],
            "use_inout": params["use_inout"],
            "dry_run": params["dry_run"],
            **track_state,
        }
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        return recolor_markers(
            ctx.conn, log=log, pump=pump, should_cancel=should_cancel, **params
        )
