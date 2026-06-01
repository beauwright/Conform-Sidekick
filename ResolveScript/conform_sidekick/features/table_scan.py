"""Base for "scan -> table -> jump to timecode" features.

Generalised from the Identify Interlaced proof-of-concept. A subclass picks the
finder (which ``ResolveAPI`` query to run), the table columns, and how to turn a
media record + timeline instance into a row. Everything else - the scope
selector, the responsive/cancellable scan, the results Tree, and the
selected-row timecode actions (Go to / Copy) - is shared.

Project-wide scans on large projects are slow (the media-pool walk is the known
bottleneck), so the scan keeps the UI responsive by pumping the event loop as it
goes and can be aborted with the Cancel button. The scan runs inside the Scan
click handler (i.e. while RunLoop is active), which is the only context where
pumping is safe.
"""

from .base import Feature
from .. import ui_kit
from .. import ui_strings as us
from ..resolve_api import ScanCancelled


class TableScanFeature(Feature):
    # Subclasses set these.
    intro = ""
    noun_plural = "item(s)"
    columns = ["Name", "Bin Location", "Resolution", "Track", "Timecode"]
    column_widths = [220, 300, 120, 80, 140]
    tc_column = 4

    def __init__(self):
        self._run = ui_kit.RunState()
        self._selected_tc = ""

    # -- subclass hooks ----------------------------------------------------

    def find(self, api, scope, on_progress, should_cancel):
        """Return a list of media records for the given scope."""
        raise NotImplementedError

    def row_values(self, media, inst):
        """Return the list of cell strings for one media record + instance."""
        raise NotImplementedError

    # -- layout ------------------------------------------------------------

    def build_layout(self, ui):
        return ui.VGroup(
            {"Spacing": 8, "Weight": 1},
            [
                ui.Label({"Text": self.intro, "Weight": 0}),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui.Label(
                            {"Text": us.LABEL_SEARCH_IN, "Weight": 0, "MinimumSize": [60, 0]}
                        ),
                        ui.ComboBox(
                            {"ID": self.wid("Scope"), "Weight": 0,
                             "MinimumSize": [220, 26], "MaximumSize": [320, 26]}
                        ),
                        ui.HGap(16, 0.0),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Scan"), "Text": "Scan", "Default": True,
                             "MinimumSize": [88, 0]},
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("Cancel"), "Text": "Cancel",
                             "Enabled": False, "MinimumSize": [80, 0]},
                        ),
                        ui.HGap(0, 1.0),
                    ],
                ),
                ui.Label(
                    {"ID": self.wid("Status"), "Text": us.STATUS_CHOOSE_SCOPE,
                     "Weight": 0, "StyleSheet": "font-weight: bold;"}
                ),
                ui.Tree(
                    {"ID": self.wid("Tree"), "Weight": 1, "SortingEnabled": True}
                ),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui.Label({"Text": "Selected:", "Weight": 0,
                                  "MinimumSize": [70, 0]}),
                        ui.Label(
                            {"ID": self.wid("SelTC"), "Text": "\u2014", "Weight": 0,
                             "MinimumSize": [130, 0], "StyleSheet": "font-weight: bold;"}
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("GoTC"), "Text": "Jump to Clip",
                             "Enabled": False, "MinimumSize": [120, 0]},
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("CopyTC"), "Text": "Copy Timecode",
                             "Enabled": False, "MinimumSize": [120, 0]},
                        ),
                        ui.HGap(0, 1.0),
                    ],
                ),
            ],
        )

    # -- behaviour ---------------------------------------------------------

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win
        api = ctx.api

        scope_combo = items[self.wid("Scope")]
        scope_combo.AddItem(us.SCOPE_ENTIRE_PROJECT)
        scope_combo.AddItem(us.SCOPE_CURRENT_TIMELINE)

        tree = items[self.wid("Tree")]
        ui_kit.setup_tree(tree, self.columns, self.column_widths)

        status = items[self.wid("Status")]
        scan_btn = items[self.wid("Scan")]
        cancel_btn = items[self.wid("Cancel")]
        sel_tc_label = items[self.wid("SelTC")]
        go_tc_btn = items[self.wid("GoTC")]
        copy_tc_btn = items[self.wid("CopyTC")]

        def set_status(text):
            try:
                status.Text = text
            except Exception:
                pass
            ui_kit.pump(ctx.dispatcher)

        def set_selected_tc(tc):
            self._selected_tc = tc or ""
            try:
                sel_tc_label.Text = self._selected_tc or "\u2014"
                go_tc_btn.Enabled = bool(self._selected_tc)
                copy_tc_btn.Enabled = bool(self._selected_tc)
            except Exception:
                pass

        def set_running(running):
            try:
                scan_btn.Enabled = not running
                scan_btn.Text = "Scanning..." if running else "Scan"
                cancel_btn.Enabled = running
                cancel_btn.Text = "Cancel"
                scope_combo.Enabled = not running
            except Exception:
                pass

        def on_scan():
            if self._run.running:
                return
            scope = "timeline" if scope_combo.CurrentIndex == 1 else "project"
            ui_kit.clear_tree(tree)
            set_selected_tc("")

            if ctx.conn.get_project() is None:
                set_status(us.STATUS_NO_PROJECT)
                return

            self._run.begin()
            set_running(True)
            set_status("Scanning… this may take a while on large projects.")

            def on_progress(count):
                try:
                    status.Text = f"Scanning… {count} clips checked (click Cancel to stop)"
                except Exception:
                    pass
                ui_kit.pump(ctx.dispatcher)

            cancelled = False
            results = []
            try:
                results = self.find(
                    api, scope, on_progress=on_progress,
                    should_cancel=self._run.should_cancel,
                )
            except ScanCancelled:
                cancelled = True
            except Exception as exc:
                self._run.end()
                set_running(False)
                set_status(f"Error while scanning: {exc}")
                return

            row_count = 0
            for media in results:
                instances = media["clips"] or [{"track": "", "timecode": ""}]
                for inst in instances:
                    ui_kit.add_row(tree, self.row_values(media, inst))
                    row_count += 1

            self._run.end()
            set_running(False)

            scope_label = us.scope_area_label(scope)
            if cancelled:
                set_status(f"Scan stopped early. Showing {row_count} result(s) so far.")
            elif row_count == 0:
                set_status(f"No {self.noun_plural} found in {scope_label}.")
            else:
                set_status(
                    f"Found {row_count} {self.noun_plural} in {scope_label}. "
                    "Select a row, then Jump to Clip or Copy Timecode "
                    "(double-click a row to jump)."
                )

        def on_cancel():
            if self._run.running:
                self._run.request_cancel()
                try:
                    cancel_btn.Text = "Cancelling..."
                    cancel_btn.Enabled = False
                except Exception:
                    pass

        def tc_of(item):
            if item is None:
                return ""
            try:
                return item.Text[self.tc_column]
            except Exception:
                return ""

        def jump_to(tc):
            if not tc:
                return
            if api.go_to_timecode(tc):
                set_status(f"Playhead moved to {tc}.")
            else:
                set_status(f"Could not jump to {tc} — open the timeline first.")

        def on_select(ev):
            set_selected_tc(tc_of(ui_kit.get_event_item(ev)))

        def on_double(ev):
            jump_to(tc_of(ui_kit.get_event_item(ev)))

        def on_go():
            jump_to(self._selected_tc)

        def on_copy():
            tc = self._selected_tc
            if not tc:
                return
            if ui_kit.copy_to_clipboard(tc):
                set_status(f"Copied {tc} to the clipboard.")
            else:
                set_status(f"Could not copy {tc} to the clipboard.")

        win.On[self.wid("Scan")].Clicked = lambda ev: on_scan()
        win.On[self.wid("Cancel")].Clicked = lambda ev: on_cancel()
        win.On[self.wid("GoTC")].Clicked = lambda ev: on_go()
        win.On[self.wid("CopyTC")].Clicked = lambda ev: on_copy()
        win.On[self.wid("Tree")].ItemDoubleClicked = on_double
        win.On[self.wid("Tree")].ItemClicked = on_select
        win.On[self.wid("Tree")].CurrentItemChanged = on_select

    def on_show(self, ctx):
        try:
            names = ctx.api.project_and_timeline_names()
        except Exception:
            return
        combo = ctx.items[self.wid("Scope")]
        if not names["timelineName"]:
            try:
                combo.CurrentIndex = 0
            except Exception:
                pass
