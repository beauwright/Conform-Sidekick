"""Bulk Enable / Disable Color Nodes.

Enable or disable Color page node(s) across many clips at once, targeted by node
index or label regex, with track / In/Out / name / clip-color scoping, layer and
version handling, and a dry-run preview. Port of
davinci-resolve-scripts/Color/BulkEnableDisableNodes.py.
"""

from .log_feature import TrackFilterLogFeature
from ..state import StateStore
from .. import timeline_filters as tf
from .. import track_filter_ui
from .. import ui_strings as us
from ..ops.bulk_nodes import bulk_set_node_enabled

CLIP_COLORS = tf.CLIP_COLORS + [tf.UNCOLORED_SENTINEL]

DEFAULTS = {
    "operation_index": 0,  # 0 = Disable, 1 = Enable
    "index_spec": "",
    "label_regex": "",
    "name_filter": "",
    "layer_spec": "",
    "all_versions": False,
    "use_track_filter": False,
    "track_filter": "",
    "use_inout": False,
    "use_clip_color": False,
    "clip_color_index": 6,  # Teal
    "dry_run": False,
}


def _row(ui, label, widget):
    return ui.HGroup(
        {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
        [ui.Label({"Text": label, "Weight": 0, "MinimumSize": [130, 0]}), widget],
    )


class BulkNodeEnableFeature(TrackFilterLogFeature):
    id = "bulknodes"
    title = "Enable/Disable Nodes (Bulk)"
    category = "color"
    run_label = "Apply"

    def state_store(self):
        return StateStore("bulk_node_enable", DEFAULTS)

    def form_rows(self, ui):
        return [
            _row(ui, "Action:", ui.ComboBox({"ID": self.wid("Operation"), "Weight": 1})),
            _row(ui, "Node number(s):", ui.LineEdit(
                {"ID": self.wid("IndexSpec"),
                 "PlaceholderText": "e.g. 2  or  2, 5  or  1-3", "Weight": 1})),
            _row(ui, us.LABEL_NODE_LABEL_PATTERN, ui.LineEdit(
                {"ID": self.wid("LabelRegex"),
                 "PlaceholderText": us.PLACEHOLDER_NODE_LABEL_PATTERN,
                 "Weight": 1})),
            _row(ui, "Node layer:", ui.LineEdit(
                {"ID": self.wid("LayerSpec"),
                 "PlaceholderText": "Blank = layer 1; all = every layer; or 1, 3-5",
                 "Weight": 1})),
            _row(ui, us.LABEL_CLIP_NAME_FILTER, ui.LineEdit(
                {"ID": self.wid("NameFilter"),
                 "PlaceholderText": us.PLACEHOLDER_CLIP_NAME_FILTER,
                 "Weight": 1})),
        ] + self.track_filter_rows(ui) + [
            ui.CheckBox(
                {"ID": self.wid("UseInOut"),
                 "Text": us.CHECK_TIMELINE_INOUT,
                 "Checked": False, "Weight": 0}
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {"ID": self.wid("UseClipColor"),
                         "Text": "Only clips with this clip color:",
                         "Checked": False, "Weight": 0, "MinimumSize": [220, 0]}
                    ),
                    ui.ComboBox({"ID": self.wid("ClipColor"), "Weight": 1}),
                ],
            ),
            ui.CheckBox(
                {"ID": self.wid("AllVersions"),
                 "Text": "Apply to every local version (restores your active version after)",
                 "Checked": False, "Weight": 0}
            ),
            ui.CheckBox(
                {"ID": self.wid("DryRun"), "Text": us.CHECK_PREVIEW_ONLY,
                 "Checked": False, "Weight": 0}
            ),
        ]

    def apply_state(self, items, state):
        op = items[self.wid("Operation")]
        op.AddItem("Disable")
        op.AddItem("Enable")
        color_combo = items[self.wid("ClipColor")]
        for color in CLIP_COLORS:
            color_combo.AddItem(color)

        op_idx = state["operation_index"] if state["operation_index"] in (0, 1) else 0
        op.CurrentIndex = op_idx
        items[self.wid("IndexSpec")].Text = state["index_spec"]
        items[self.wid("LabelRegex")].Text = state["label_regex"]
        items[self.wid("NameFilter")].Text = state["name_filter"]
        items[self.wid("LayerSpec")].Text = state["layer_spec"]
        track_filter_ui.apply_track_filter_state(items, self, state)
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("UseClipColor")].Checked = bool(state.get("use_clip_color", False))
        color_idx = state.get("clip_color_index", 6)
        if not (0 <= color_idx < len(CLIP_COLORS)):
            color_idx = 6
        color_combo.CurrentIndex = color_idx
        items[self.wid("AllVersions")].Checked = bool(state.get("all_versions", False))
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])

    def gather(self, items):
        operation_index = items[self.wid("Operation")].CurrentIndex
        use_clip_color = bool(items[self.wid("UseClipColor")].Checked)
        clip_color_idx = items[self.wid("ClipColor")].CurrentIndex
        if 0 <= clip_color_idx < len(CLIP_COLORS):
            clip_color_value = CLIP_COLORS[clip_color_idx]
        else:
            clip_color_value = ""
        track_spec, _use_tracks, track_state = track_filter_ui.gather_track_filter(
            items, self
        )
        params = {
            "enabled": operation_index == 1,
            "index_spec": items[self.wid("IndexSpec")].Text,
            "label_regex": items[self.wid("LabelRegex")].Text,
            "name_filter": items[self.wid("NameFilter")].Text,
            "layer_spec": items[self.wid("LayerSpec")].Text,
            "all_versions": bool(items[self.wid("AllVersions")].Checked),
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "track_filter_spec": track_spec,
            "clip_color_filter": clip_color_value if use_clip_color else "",
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "operation_index": operation_index,
            "index_spec": params["index_spec"],
            "label_regex": params["label_regex"],
            "name_filter": params["name_filter"],
            "layer_spec": params["layer_spec"],
            "all_versions": params["all_versions"],
            "use_inout": params["use_inout"],
            "use_clip_color": use_clip_color,
            "clip_color_index": clip_color_idx,
            "dry_run": params["dry_run"],
            **track_state,
        }
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        return bulk_set_node_enabled(
            ctx.conn, log=log, pump=pump, should_cancel=should_cancel, **params
        )
