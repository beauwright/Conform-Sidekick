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
        rows.append(ui.Label({"Text": "Output:", "Weight": 0}))
        rows.append(
            ui.TextEdit(
                {
                    "ID": self.wid("Log"),
                    "ReadOnly": True,
                    "PlaceholderText": "Run results will appear here.",
                    "Weight": 1,
                }
            )
        )
        rows.append(
            ui.HGroup(
                # Reserve the row height so the native buttons aren't clipped
                # (UIManager won't grow a Weight:0 row to fit taller children).
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 44]},
                [
                    ui.Button(
                        {
                            "ID": self.wid("Run"),
                            "Text": self.run_label,
                            "Default": True,
                            "Weight": 0,
                            "MinimumSize": [150, 34],
                        }
                    ),
                    ui.Button(
                        {
                            "ID": self.wid("Cancel"),
                            "Text": "Cancel",
                            "Enabled": False,
                            "Weight": 0,
                            "MinimumSize": [110, 34],
                        }
                    ),
                    ui.HGap(0, 1.0),
                ],
            )
        )
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
                log_ctl.log(f"Could not read inputs: {exc}")
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
