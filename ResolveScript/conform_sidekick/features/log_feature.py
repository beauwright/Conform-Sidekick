"""Base class for "form + log" features.

The three ported davinci-resolve-scripts (Rename Clips From Markers, Bulk
Enable/Disable Nodes, Lay Matching Bin Clips) all share the same shell: a column
of input widgets, a read-only output log, and Run / Cancel buttons that drive a
core operation taking ``log`` / ``pump`` / ``should_cancel`` callbacks.

This base builds that shell and wires Run/Cancel against :class:`ui_kit.RunState`
and :class:`ui_kit.LogController`. Subclasses provide the form widgets, the
persisted-state mapping, and the core operation.

Unlike the standalone scripts, success never closes the window - the tab simply
shows its results and stays put.
"""

import traceback

from .base import Feature
from .. import ui_kit
from .. import ui_strings as us


class LogFeature(Feature):
    run_label = "Run"

    def __init__(self):
        self._run = ui_kit.RunState()

    # -- subclass hooks ----------------------------------------------------

    def form_rows(self, ui):
        """Return a list of UIManager widgets for the input area."""
        return []

    def state_store(self):
        """Return a :class:`state.StateStore` for persistence, or None."""
        return None

    def apply_state(self, items, state):
        """Populate the form widgets from a loaded state dict."""

    def gather(self, items):
        """Return ``(params_dict, state_dict)`` read from the form widgets.

        ``params_dict`` is passed straight to :meth:`run`; ``state_dict`` (or
        None) is persisted via the state store.
        """
        raise NotImplementedError

    def run(self, ctx, params, log, pump, should_cancel):
        """Execute the core operation. Return the result dict (or None)."""
        raise NotImplementedError

    # -- shared shell ------------------------------------------------------

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
                            "ID": self.wid("Run"),
                            "Text": self.run_label,
                            "Default": True,
                            "MinimumSize": [110, 0],
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
        rows.append(ui_kit.bottom_layout_pad(ui))
        return ui.VGroup({"Spacing": 8, "Weight": 1}, rows)

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win

        log_ctl = ui_kit.LogController(ctx.dispatcher, items[self.wid("Log")])
        run_btn = items[self.wid("Run")]
        cancel_btn = items[self.wid("Cancel")]

        store = self.state_store()
        if store is not None:
            try:
                self.apply_state(items, store.load())
            except Exception as exc:
                print(f"Conform Sidekick: {self.id} apply_state failed: {exc}")

        def set_running(running):
            try:
                run_btn.Enabled = not running
                run_btn.Text = "Running..." if running else self.run_label
                cancel_btn.Enabled = running
                cancel_btn.Text = "Cancel"
            except Exception:
                pass

        def on_run():
            if self._run.running:
                return
            try:
                params, state = self.gather(items)
            except Exception as exc:
                log_ctl.reset()
                log_ctl.log(f"Check your settings: {exc}")
                return
            if store is not None and state is not None:
                store.save(state)

            log_ctl.reset()
            self._run.begin()
            set_running(True)
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

        win.On[self.wid("Run")].Clicked = lambda ev: on_run()
        win.On[self.wid("Cancel")].Clicked = lambda ev: on_cancel()


class TrackFilterLogFeature(LogFeature):
    """Log feature with a master track-filter checkbox and per-track dropdowns."""

    track_filter_label_width = 130

    def track_filter_rows(self, ui):
        from .. import track_filter_ui

        return track_filter_ui.build_track_filter_block(
            ui, self, self.track_filter_label_width
        )

    def bind(self, ctx):
        from .. import track_filter_ui

        track_filter_ui.init_track_combos(ctx.items, self)
        track_filter_ui.refresh_track_filter_ui(ctx, self, ctx.items)
        track_filter_ui.bind_track_filter(ctx, self, ctx.items, ctx.win)
        super().bind(ctx)
        track_filter_ui.set_track_filter_enabled(
            ctx.items,
            self,
            bool(ctx.items[self.wid("UseTrackFilter")].Checked),
        )

    def on_show(self, ctx):
        from .. import track_filter_ui
        from .. import ui_kit

        track_filter_ui.refresh_track_filter_ui(ctx, self, ctx.items)
        track_filter_ui.set_track_filter_enabled(
            ctx.items,
            self,
            bool(ctx.items[self.wid("UseTrackFilter")].Checked),
        )
        ui_kit.recalc_layout(ctx.win)
        ui_kit.pump(ctx.dispatcher)
