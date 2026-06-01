"""Bypass / restore the color grade on the current clip in the Color page.

Keeps the configured color input and output nodes enabled while disabling
everything else on ``Timeline.GetCurrentVideoItem()``. Restore turns back on
only the nodes that bypass disabled (stored in persisted state).
"""

from .log_feature import LogFeature
from ..state import StateStore
from .. import ui_strings as us
from ..ops.grade_bypass import grade_bypass


DEFAULTS = {
    "operation_index": 0,  # 0 = Bypass, 1 = Restore
    "input_index_spec": "",
    "input_label_regex": "",
    "output_index_spec": "",
    "output_label_regex": "",
    "layer_spec": "",
    "include_color_group": False,
    "dry_run": False,
    "bypass_snapshot": {},
}


def _row(ui, label, widget):
    return ui.HGroup(
        {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
        [ui.Label({"Text": label, "Weight": 0, "MinimumSize": [130, 0]}), widget],
    )


class GradeBypassFeature(LogFeature):
    id = "gradebypass"
    title = "Bypass Grade (Current Clip)"
    category = "color"
    run_label = "Apply"

    def state_store(self):
        return StateStore("grade_bypass", DEFAULTS)

    def form_rows(self, ui):
        return [
            _row(
                ui,
                "Action:",
                ui.ComboBox({"ID": self.wid("Operation"), "Weight": 1}),
            ),
            _row(
                ui,
                "Color input node:",
                ui.LineEdit(
                    {
                        "ID": self.wid("InputIndexSpec"),
                        "PlaceholderText": "e.g. 1",
                        "Weight": 1,
                    }
                ),
            ),
            _row(
                ui,
                "Or input label (regex):",
                ui.LineEdit(
                    {
                        "ID": self.wid("InputLabelRegex"),
                        "PlaceholderText": us.PLACEHOLDER_NODE_LABEL_PATTERN,
                        "Weight": 1,
                    }
                ),
            ),
            _row(
                ui,
                "Color output node:",
                ui.LineEdit(
                    {
                        "ID": self.wid("OutputIndexSpec"),
                        "PlaceholderText": "e.g. last node number",
                        "Weight": 1,
                    }
                ),
            ),
            _row(
                ui,
                "Or output label (regex):",
                ui.LineEdit(
                    {
                        "ID": self.wid("OutputLabelRegex"),
                        "PlaceholderText": us.PLACEHOLDER_NODE_LABEL_PATTERN,
                        "Weight": 1,
                    }
                ),
            ),
            _row(
                ui,
                "Node layer:",
                ui.LineEdit(
                    {
                        "ID": self.wid("LayerSpec"),
                        "PlaceholderText": "Blank = layer 1; all = every layer; or 1, 3-5",
                        "Weight": 1,
                    }
                ),
            ),
            ui.CheckBox(
                {
                    "ID": self.wid("IncludeColorGroup"),
                    "Text": us.CHECK_INCLUDE_COLOR_GROUP,
                    "Checked": False,
                    "Weight": 0,
                }
            ),
            ui.CheckBox(
                {
                    "ID": self.wid("DryRun"),
                    "Text": us.CHECK_PREVIEW_ONLY,
                    "Checked": False,
                    "Weight": 0,
                }
            ),
        ]

    def apply_state(self, items, state):
        op = items[self.wid("Operation")]
        op.AddItem("Bypass grade")
        op.AddItem("Restore grade")

        op_idx = state["operation_index"] if state["operation_index"] in (0, 1) else 0
        op.CurrentIndex = op_idx
        items[self.wid("InputIndexSpec")].Text = state["input_index_spec"]
        items[self.wid("InputLabelRegex")].Text = state["input_label_regex"]
        items[self.wid("OutputIndexSpec")].Text = state["output_index_spec"]
        items[self.wid("OutputLabelRegex")].Text = state["output_label_regex"]
        items[self.wid("LayerSpec")].Text = state["layer_spec"]
        items[self.wid("IncludeColorGroup")].Checked = bool(
            state.get("include_color_group", False)
        )
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])

    def gather(self, items):
        operation_index = items[self.wid("Operation")].CurrentIndex
        params = {
            "restore": operation_index == 1,
            "input_index_spec": items[self.wid("InputIndexSpec")].Text,
            "input_label_regex": items[self.wid("InputLabelRegex")].Text,
            "output_index_spec": items[self.wid("OutputIndexSpec")].Text,
            "output_label_regex": items[self.wid("OutputLabelRegex")].Text,
            "layer_spec": items[self.wid("LayerSpec")].Text,
            "include_color_group": bool(
                items[self.wid("IncludeColorGroup")].Checked
            ),
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "operation_index": operation_index,
            "input_index_spec": params["input_index_spec"],
            "input_label_regex": params["input_label_regex"],
            "output_index_spec": params["output_index_spec"],
            "output_label_regex": params["output_label_regex"],
            "layer_spec": params["layer_spec"],
            "include_color_group": params["include_color_group"],
            "dry_run": params["dry_run"],
        }
        store = self.state_store()
        if store is not None:
            existing = store.load()
            state["bypass_snapshot"] = existing.get("bypass_snapshot") or {}
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        store = self.state_store()
        prior = store.load() if store is not None else {}
        params = dict(params)
        params["bypass_snapshot"] = prior.get("bypass_snapshot") or {}

        result = grade_bypass(
            ctx.conn,
            log=log,
            pump=pump,
            should_cancel=should_cancel,
            **params,
        )

        if store is not None and not result.get("error") and not params.get("dry_run"):
            state = store.load()
            if params.get("restore"):
                state["bypass_snapshot"] = {}
            elif result.get("snapshot"):
                state["bypass_snapshot"] = result["snapshot"]
            store.save(state)

        return result
