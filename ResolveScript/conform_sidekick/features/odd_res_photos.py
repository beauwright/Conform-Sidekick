"""Fix Odd Resolution Photos.

Detect images whose width or height is odd (which can break ProRes /
source-resolution renders), stretch them 1px into a new file, and repoint the
project at the fixed file via ``MediaPoolItem.ReplaceClip``. Originals are left
untouched.

Detection is native (``ResolveAPI.find_odd_resolution``). The 1px stretch is
done by :mod:`conform_sidekick.ops.odd_res` (Pillow in Resolve's Python, or the
optional PyInstaller helper in ``ResolveScript/helpers/``).
"""

from .base import Feature
from .. import ui_kit
from ..resolve_api import ScanCancelled
from ..ops.odd_res import convert_single_photo

# A trailing hidden column carries a unique per-row key so we can map a clicked
# Tree row back to its record. Bin Location can't serve as the key because
# timeline-scope rows have no bin path.
COLUMNS = ["Name", "Bin Location", "Resolution", "File Path", ""]
COLUMN_WIDTHS = [220, 300, 110, 360, 0]
KEY_COL = 4


class OddResPhotosFeature(Feature):
    id = "oddres"
    title = "Fix Odd Resolution Photos"
    category = "conform"

    def __init__(self):
        self._run = ui_kit.RunState()
        self._by_key = {}
        self._order = []
        self._selected_key = ""

    def build_layout(self, ui):
        return ui.VGroup(
            {"Spacing": 8, "Weight": 1},
            [
                ui.Label(
                    {"Text": "Find images with an odd pixel width or height and "
                             "fix them by stretching 1px.", "Weight": 0}
                ),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui.Label({"Text": "Scope:", "Weight": 0, "MinimumSize": [60, 0]}),
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
                            {"ID": self.wid("CancelScan"), "Text": "Cancel",
                             "Enabled": False, "MinimumSize": [80, 0]},
                        ),
                        ui.HGap(0, 1.0),
                    ],
                ),
                ui.Label(
                    {"ID": self.wid("Status"), "Text": "Choose a scope and click Scan.",
                     "Weight": 0, "StyleSheet": "font-weight: bold;"}
                ),
                ui.Tree(
                    {"ID": self.wid("Tree"), "Weight": 3, "SortingEnabled": True}
                ),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("ConvertAll"), "Text": "Convert All Listed",
                             "Enabled": False, "MinimumSize": [145, 0]},
                        ),
                        ui_kit.action_button(
                            ui,
                            {"ID": self.wid("ConvertSel"), "Text": "Convert Selected",
                             "Enabled": False, "MinimumSize": [135, 0]},
                        ),
                        ui.HGap(0, 1.0),
                    ],
                ),
                ui.Label({"Text": "Output:", "Weight": 0}),
                # Share the flexible height with the Tree via weights (rather
                # than a fixed MinimumSize): a fixed-height log here lets the
                # Tree hog the stretch space and pushes this box off the bottom
                # of the window, where it clips (and the read-only caret shows
                # through as an orange sliver).
                ui.TextEdit(
                    {"ID": self.wid("Log"), "ReadOnly": True,
                     "PlaceholderText": "Conversion results will appear here.",
                     "Weight": 1}
                ),
            ],
        )

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win
        api = ctx.api

        scope_combo = items[self.wid("Scope")]
        scope_combo.AddItem("Project-wide")
        scope_combo.AddItem("Current Timeline")

        tree = items[self.wid("Tree")]
        ui_kit.setup_tree(tree, COLUMNS, COLUMN_WIDTHS)

        status = items[self.wid("Status")]
        scan_btn = items[self.wid("Scan")]
        cancel_btn = items[self.wid("CancelScan")]
        convert_all_btn = items[self.wid("ConvertAll")]
        convert_sel_btn = items[self.wid("ConvertSel")]
        log_ctl = ui_kit.LogController(ctx.dispatcher, items[self.wid("Log")])

        def set_status(text):
            try:
                status.Text = text
            except Exception:
                pass
            ui_kit.pump(ctx.dispatcher)

        def set_scan_running(running):
            try:
                scan_btn.Enabled = not running
                scan_btn.Text = "Scanning..." if running else "Scan"
                cancel_btn.Enabled = running
                cancel_btn.Text = "Cancel"
                scope_combo.Enabled = not running
                convert_all_btn.Enabled = (not running) and bool(self._order)
                convert_sel_btn.Enabled = (not running) and bool(self._selected_key)
            except Exception:
                pass

        def set_convert_running(running):
            try:
                convert_all_btn.Enabled = not running and bool(self._order)
                convert_sel_btn.Enabled = not running and bool(self._selected_key)
                convert_all_btn.Text = "Converting..." if running else "Convert All Listed"
                cancel_btn.Enabled = running
                scan_btn.Enabled = not running
            except Exception:
                pass

        def on_scan():
            if self._run.running:
                return
            scope = "timeline" if scope_combo.CurrentIndex == 1 else "project"
            ui_kit.clear_tree(tree)
            self._by_key = {}
            self._order = []
            self._selected_key = ""

            if ctx.conn.get_project() is None:
                set_status("No project is open in Resolve.")
                return

            self._run.begin()
            set_scan_running(True)
            set_status("Scanning... (this can take a while on large projects)")

            def on_progress(count):
                try:
                    status.Text = f"Scanning... {count} clips checked (Cancel to stop)"
                except Exception:
                    pass
                ui_kit.pump(ctx.dispatcher)

            cancelled = False
            results = []
            try:
                results = api.find_odd_resolution(
                    scope, on_progress=on_progress,
                    should_cancel=self._run.should_cancel,
                )
            except ScanCancelled:
                cancelled = True
            except Exception as exc:
                self._run.end()
                set_scan_running(False)
                set_status(f"Error while scanning: {exc}")
                return

            for media in results:
                key = str(len(self._order))
                self._by_key[key] = media
                self._order.append(key)
                ui_kit.add_row(
                    tree,
                    [media["displayName"], media["binLocation"], media["resolution"],
                     media["filepath"], key],
                )

            self._run.end()
            set_scan_running(False)

            scope_label = "the current timeline" if scope == "timeline" else "this project"
            count = len(self._order)
            if cancelled:
                set_status(f"Scan cancelled. Showing {count} partial result(s).")
            elif count == 0:
                set_status(f"No odd-resolution images found in {scope_label}.")
            else:
                set_status(
                    f"Found {count} odd-resolution image(s) in {scope_label}. "
                    "Use Convert All Listed, or select a row and Convert Selected."
                )

        def on_cancel():
            if self._run.running:
                self._run.request_cancel()
                try:
                    cancel_btn.Text = "Cancelling..."
                    cancel_btn.Enabled = False
                except Exception:
                    pass

        def on_select(ev):
            item = ui_kit.get_event_item(ev)
            try:
                self._selected_key = item.Text[KEY_COL] if item is not None else ""
            except Exception:
                self._selected_key = ""
            try:
                convert_sel_btn.Enabled = (not self._run.running) and bool(self._selected_key)
            except Exception:
                pass

        def convert_records(records):
            if self._run.running:
                return
            if not records:
                return
            self._run.begin()
            set_convert_running(True)
            log_ctl.reset()
            log_ctl.log(f"Converting {len(records)} odd-resolution image(s)...")

            converted = 0
            failed = 0
            for media in records:
                if self._run.should_cancel():
                    log_ctl.log("Cancelled by user.")
                    break
                name = media["displayName"]
                media_obj = media.get("item")
                if media_obj is None:
                    try:
                        media_obj = api.get_media_object_from_bin_path(
                            media["binLocation"], media["mediaId"]
                        )
                    except Exception as exc:
                        media_obj = None
                        log_ctl.log(f"  [ERR]  {name}: lookup raised {exc}")
                if media_obj is None:
                    failed += 1
                    log_ctl.log(f"  [FAIL] {name}: could not locate the media item in the bin.")
                    log_ctl.pump()
                    continue

                output_path, err = convert_single_photo(media["filepath"])
                if output_path is None:
                    failed += 1
                    log_ctl.log(f"  [SKIP] {name}: {err}")
                    log_ctl.pump()
                    continue

                try:
                    replaced = bool(media_obj.ReplaceClip(output_path))
                except Exception as exc:
                    replaced = False
                    log_ctl.log(f"  [ERR]  {name}: ReplaceClip raised {exc}")

                if replaced:
                    converted += 1
                    log_ctl.log(f"  [OK]   {name}: replaced with even-resolution copy.")
                else:
                    failed += 1
                    log_ctl.log(
                        f"  [FAIL] {name}: converted file written ({output_path}) "
                        "but ReplaceClip returned false."
                    )
                log_ctl.pump()

            self._run.end()
            set_convert_running(False)
            log_ctl.log("")
            log_ctl.log(f"  Converted: {converted}    Failed/skipped: {failed}")
            log_ctl.log("  Re-scan to refresh the list.")
            set_status(f"Conversion finished: {converted} converted, {failed} failed/skipped.")

        def on_convert_all():
            convert_records([self._by_key[k] for k in self._order if k in self._by_key])

        def on_convert_sel():
            media = self._by_key.get(self._selected_key)
            if media is None:
                set_status("Select a row first, then Convert Selected.")
                return
            convert_records([media])

        win.On[self.wid("Scan")].Clicked = lambda ev: on_scan()
        win.On[self.wid("CancelScan")].Clicked = lambda ev: on_cancel()
        win.On[self.wid("ConvertAll")].Clicked = lambda ev: on_convert_all()
        win.On[self.wid("ConvertSel")].Clicked = lambda ev: on_convert_sel()
        win.On[self.wid("Tree")].ItemClicked = on_select
        win.On[self.wid("Tree")].CurrentItemChanged = on_select

    def on_show(self, ctx):
        try:
            names = ctx.api.project_and_timeline_names()
        except Exception:
            return
        if not names["timelineName"]:
            try:
                ctx.items[self.wid("Scope")].CurrentIndex = 0
            except Exception:
                pass
