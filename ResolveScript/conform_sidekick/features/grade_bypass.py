"""Bypass / restore the color grade on the current clip in the Color page.

Keeps the configured color input and output nodes enabled while disabling
everything else on ``Timeline.GetCurrentVideoItem()``. Restore turns back on
only the nodes that bypass disabled (stored in persisted state).
"""

import traceback

from .log_feature import LogFeature
from ..state import StateStore
from .. import ui_kit
from .. import ui_strings as us
from ..ops.grade_bypass import (
    current_clip_key,
    grade_bypass,
    normalize_snapshots_by_clip,
    snapshot_has_graph_data,
)


DEFAULTS = {
    "input_index_spec": "",
    "input_label_regex": "",
    "output_index_spec": "",
    "output_label_regex": "",
    "ignore_label_regex": "",
    "layer_spec": "",
    "include_color_group": False,
    "dry_run": False,
    "bypass_snapshots_by_clip": {},
}

BYPASS_LABEL = "Bypass grade"
RESTORE_LABEL = "Restore grade"


def _row(ui, label, widget):
    return ui.HGroup(
        {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
        [ui.Label({"Text": label, "Weight": 0, "MinimumSize": [130, 0]}), widget],
    )


def _clip_has_bypass(state, clip_key):
    if not clip_key:
        return False
    by_clip = normalize_snapshots_by_clip(state)
    return snapshot_has_graph_data(by_clip.get(clip_key))


class GradeBypassFeature(LogFeature):
    id = "gradebypass"
    title = "Bypass Grade (Current Clip)"
    category = "color"

    def state_store(self):
        return StateStore("grade_bypass", DEFAULTS)

    def form_rows(self, ui):
        return [
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
                us.LABEL_GRADE_BYPASS_IGNORE,
                ui.LineEdit(
                    {
                        "ID": self.wid("IgnoreLabelRegex"),
                        "PlaceholderText": us.PLACEHOLDER_GRADE_BYPASS_IGNORE,
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

    def build_layout(self, ui):
        rows = list(self.form_rows(ui))
        rows.append(ui.Label({"Text": us.OUTPUT_HEADER, "Weight": 0}))
        rows.append(
            ui.TextEdit(
                {
                    "ID": self.wid("Log"),
                    "ReadOnly": True,
                    "PlaceholderText": us.OUTPUT_PLACEHOLDER,
                    "Weight": 1,
                }
            )
        )
        rows.append(
            ui.HGroup(
                ui_kit.button_row_props(),
                [
                    ui_kit.action_button(
                        ui,
                        {
                            "ID": self.wid("Bypass"),
                            "Text": BYPASS_LABEL,
                            "Default": True,
                            "MinimumSize": [120, 0],
                        },
                    ),
                    ui_kit.action_button(
                        ui,
                        {
                            "ID": self.wid("Restore"),
                            "Text": RESTORE_LABEL,
                            "MinimumSize": [120, 0],
                        },
                    ),
                    ui_kit.action_button(
                        ui,
                        {
                            "ID": self.wid("Cancel"),
                            "Text": "Cancel",
                            "Enabled": False,
                            "MinimumSize": [80, 0],
                        },
                    ),
                    ui.HGap(0, 1.0),
                ],
            )
        )
        return ui.VGroup({"Spacing": 8, "Weight": 1}, rows)

    def apply_state(self, items, state):
        items[self.wid("InputIndexSpec")].Text = state["input_index_spec"]
        items[self.wid("InputLabelRegex")].Text = state["input_label_regex"]
        items[self.wid("OutputIndexSpec")].Text = state["output_index_spec"]
        items[self.wid("OutputLabelRegex")].Text = state["output_label_regex"]
        items[self.wid("IgnoreLabelRegex")].Text = state.get("ignore_label_regex", "")
        items[self.wid("LayerSpec")].Text = state["layer_spec"]
        items[self.wid("IncludeColorGroup")].Checked = bool(
            state.get("include_color_group", False)
        )
        items[self.wid("DryRun")].Checked = bool(state["dry_run"])

    def gather(self, items, restore=False):
        params = {
            "restore": restore,
            "input_index_spec": items[self.wid("InputIndexSpec")].Text,
            "input_label_regex": items[self.wid("InputLabelRegex")].Text,
            "output_index_spec": items[self.wid("OutputIndexSpec")].Text,
            "output_label_regex": items[self.wid("OutputLabelRegex")].Text,
            "ignore_label_regex": items[self.wid("IgnoreLabelRegex")].Text,
            "layer_spec": items[self.wid("LayerSpec")].Text,
            "include_color_group": bool(
                items[self.wid("IncludeColorGroup")].Checked
            ),
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "input_index_spec": params["input_index_spec"],
            "input_label_regex": params["input_label_regex"],
            "output_index_spec": params["output_index_spec"],
            "output_label_regex": params["output_label_regex"],
            "ignore_label_regex": params["ignore_label_regex"],
            "layer_spec": params["layer_spec"],
            "include_color_group": params["include_color_group"],
            "dry_run": params["dry_run"],
        }
        store = self.state_store()
        if store is not None:
            existing = store.load()
            state["bypass_snapshots_by_clip"] = normalize_snapshots_by_clip(existing)
        return params, state

    def run(self, ctx, params, log, pump, should_cancel):
        store = self.state_store()
        prior = store.load() if store is not None else {}
        by_clip = normalize_snapshots_by_clip(prior)
        clip_key = current_clip_key(ctx.conn)

        params = dict(params)
        if params.get("restore"):
            params["bypass_snapshot"] = dict(by_clip.get(clip_key) or {})
        else:
            params["bypass_snapshot"] = {}

        result = grade_bypass(
            ctx.conn,
            log=log,
            pump=pump,
            should_cancel=should_cancel,
            **params,
        )

        if store is not None and not result.get("error") and not params.get("dry_run"):
            state = store.load()
            by_clip = normalize_snapshots_by_clip(state)
            affected_key = (result.get("clip_key") or clip_key or "").strip()
            if params.get("restore"):
                if affected_key:
                    by_clip.pop(affected_key, None)
            elif result.get("snapshot") and affected_key:
                by_clip[affected_key] = result["snapshot"]
            state["bypass_snapshots_by_clip"] = by_clip
            state.pop("bypass_snapshot", None)
            store.save(state)

        return result

    def _update_restore_enabled(self, items, store, conn=None):
        if store is None:
            return
        try:
            clip_key = current_clip_key(conn) if conn is not None else ""
            items[self.wid("Restore")].Enabled = _clip_has_bypass(
                store.load(), clip_key
            )
        except Exception:
            pass

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win

        log_ctl = ui_kit.LogController(ctx.dispatcher, items[self.wid("Log")])
        bypass_btn = items[self.wid("Bypass")]
        restore_btn = items[self.wid("Restore")]
        cancel_btn = items[self.wid("Cancel")]

        store = self.state_store()
        if store is not None:
            try:
                self.apply_state(items, store.load())
            except Exception as exc:
                print(f"Conform Sidekick: {self.id} apply_state failed: {exc}")

        self._update_restore_enabled(items, store, ctx.conn)

        def set_running(running, active=None):
            try:
                bypass_btn.Enabled = not running
                bypass_btn.Text = (
                    "Running..." if running and active == "bypass" else BYPASS_LABEL
                )
                restore_btn.Text = (
                    "Running..." if running and active == "restore" else RESTORE_LABEL
                )
                cancel_btn.Enabled = running
                cancel_btn.Text = "Cancel"
            except Exception:
                pass
            if not running:
                self._update_restore_enabled(items, store, ctx.conn)

        def on_action(restore):
            if self._run.running:
                return
            try:
                params, state = self.gather(items, restore=restore)
            except Exception as exc:
                log_ctl.reset()
                log_ctl.log(f"Check your settings: {exc}")
                return
            if store is not None and state is not None:
                store.save(state)

            log_ctl.reset()
            self._run.begin()
            active = "restore" if restore else "bypass"
            set_running(True, active)
            try:
                self.run(
                    ctx,
                    params,
                    log_ctl.log,
                    log_ctl.pump,
                    self._run.should_cancel,
                )
            except Exception as exc:
                log_ctl.log(f"Unhandled error: {type(exc).__name__}: {exc}")
                log_ctl.log(traceback.format_exc())
            finally:
                self._run.end()
                set_running(False)

        def on_cancel():
            if self._run.running:
                self._run.request_cancel()
                try:
                    cancel_btn.Text = "Cancelling..."
                    cancel_btn.Enabled = False
                except Exception:
                    pass

        win.On[self.wid("Bypass")].Clicked = lambda ev: on_action(restore=False)
        win.On[self.wid("Restore")].Clicked = lambda ev: on_action(restore=True)
        win.On[self.wid("Cancel")].Clicked = lambda ev: on_cancel()

    def on_show(self, ctx):
        self._update_restore_enabled(ctx.items, self.state_store(), ctx.conn)
