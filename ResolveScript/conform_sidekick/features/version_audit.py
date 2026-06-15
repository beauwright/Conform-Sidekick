"""VFX Version Audit.

Compare a VFX delivery CSV against clips on the current timeline. Unmatched
rows show deliveries missing from the edit; optional version-drift detection
flags when the project has a newer or older comp than the spreadsheet lists.
"""

from .base import Feature
from ..state import StateStore
from .. import track_filter_ui
from .. import ui_kit
from .. import ui_strings as us
from ..ops.version_audit import (
    run_version_audit,
    TIMELINE_KEY_FIELDS,
    VERSION_PATTERN_PRESETS,
    DEFAULT_VERSION_PRESET,
    default_audit_export_path,
    write_results_csv,
)
from ..resolve_api import ScanCancelled


TIMELINE_KEY_LABELS = {
    "clip_name": "Timeline clip name",
    "media_name": "Media pool clip name",
    "file_path": "File path",
}

SHOW_FILTERS = (
    ("all", "All results"),
    ("unmatched", "Not in edit only"),
    ("matched", "Matched only"),
    ("normalized", "Matched (normalized) only"),
    ("newer", "Newer in project only"),
    ("older", "Older in project only"),
    ("covered", "Warnings only"),
)

STATUS_LABELS = {
    "not_in_edit": "Not in edit",
    "matched": "Matched",
    "matched_covered": "Matched (covered)",
    "matched_disabled": "Matched (disabled)",
    "matched_covered_disabled": "Matched (covered, disabled)",
    "matched_normalized": "Matched (normalized)",
    "matched_normalized_covered": "Matched (normalized, covered)",
    "matched_normalized_disabled": "Matched (normalized, disabled)",
    "matched_normalized_covered_disabled": "Matched (normalized, covered, disabled)",
    "newer_in_project": "Newer in project",
    "newer_in_project_disabled": "Newer in project (disabled)",
    "older_in_project": "Older in project",
    "older_in_project_disabled": "Older in project (disabled)",
}

MATCHED_STATUSES = (
    "matched",
    "matched_covered",
    "matched_disabled",
    "matched_covered_disabled",
)
NORMALIZED_STATUSES = (
    "matched_normalized",
    "matched_normalized_covered",
    "matched_normalized_disabled",
    "matched_normalized_covered_disabled",
)
WARNING_STATUSES = (
    "matched_covered",
    "matched_disabled",
    "matched_covered_disabled",
    "matched_normalized_covered",
    "matched_normalized_disabled",
    "matched_normalized_covered_disabled",
    "newer_in_project_disabled",
    "older_in_project_disabled",
)

COLUMNS = [
    "Status",
    "VFX Key",
    "Version",
    "Track",
    "Timecode",
    "Clip Name",
    "Warnings",
]
COLUMN_WIDTHS = [150, 150, 96, 48, 108, 130, 110]
VFX_KEY_COLUMN = 1
TC_COLUMN = 4

_FORM_LABEL_WIDTH = 96
_CUSTOM_PRESET_ID = "custom"

DEFAULTS = {
    "vfx_csv_path": "",
    "vfx_key_column": "",
    "vfx_has_header": False,
    "timeline_key_field": "clip_name",
    "trim": True,
    "case_insensitive": True,
    "strip_extension": True,
    "normalize_numeric": False,
    "skip_empty_keys": True,
    "detect_version_drift": True,
    "version_preset": DEFAULT_VERSION_PRESET,
    "version_pattern": "",
    "use_inout": False,
    "use_track_filter": False,
    "track_filter": "",
    "warn_cover": True,
    "show_filter": "all",
    "export_csv_path": "",
}


class VersionAuditFeature(Feature):
    id = "version_audit"
    title = "VFX Version Audit"
    category = "conform"
    track_filter_label_width = 130

    def __init__(self):
        self._run = ui_kit.RunState()
        self._selected_tc = ""
        self._selected_vfx_key = ""
        self._all_results = []

    def state_store(self):
        return StateStore("version_audit", DEFAULTS)

    def _version_pattern_rows(self, ui):
        return [
            ui.CheckBox(
                {
                    "ID": self.wid("DetectVersionDrift"),
                    "Text": us.CHECK_DETECT_VERSION_DRIFT,
                    "Checked": True,
                    "Weight": 0,
                }
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0},
                [
                    ui.Label(
                        {
                            "Text": us.LABEL_VERSION_PRESET,
                            "Weight": 0,
                            "MinimumSize": [_FORM_LABEL_WIDTH, 0],
                        }
                    ),
                    ui.ComboBox(
                        {
                            "ID": self.wid("VersionPreset"),
                            "Weight": 1,
                        }
                    ),
                ],
            ),
            ui.LineEdit(
                {
                    "ID": self.wid("VersionPattern"),
                    "PlaceholderText": us.PLACEHOLDER_VERSION_PATTERN,
                    "Text": "",
                    "Weight": 0,
                }
            ),
        ]

    def build_layout(self, ui):
        return ui.VGroup(
            {"Spacing": 8, "Weight": 1},
            [
                ui.Label(
                    {
                        "Text": us.VERSION_AUDIT_INTRO,
                        "Weight": 0,
                    }
                ),
                ui.HGroup(
                    {"Spacing": 8, "Weight": 0},
                    [
                        ui.Label(
                            {
                                "Text": us.LABEL_VFX_CSV,
                                "Weight": 0,
                                "MinimumSize": [_FORM_LABEL_WIDTH, 0],
                            }
                        ),
                        ui.LineEdit(
                            {
                                "ID": self.wid("VfxCsv"),
                                "PlaceholderText": us.PLACEHOLDER_VFX_CSV,
                                "Text": "",
                                "Weight": 1,
                            }
                        ),
                    ],
                ),
                ui.HGroup(
                    {"Spacing": 8, "Weight": 0},
                    [
                        ui.Label(
                            {
                                "Text": us.LABEL_VFX_KEY_COLUMN,
                                "Weight": 0,
                                "MinimumSize": [_FORM_LABEL_WIDTH, 0],
                            }
                        ),
                        ui.LineEdit(
                            {
                                "ID": self.wid("VfxKeyCol"),
                                "PlaceholderText": us.PLACEHOLDER_VFX_KEY_COLUMN,
                                "Text": "",
                                "Weight": 1,
                                "MaximumSize": [180, 16777215],
                            }
                        ),
                    ],
                ),
                ui.HGroup(
                    {"Spacing": 8, "Weight": 0},
                    [
                        ui.Label(
                            {
                                "Text": us.LABEL_TIMELINE_KEY,
                                "Weight": 0,
                                "MinimumSize": [_FORM_LABEL_WIDTH, 0],
                            }
                        ),
                        ui.ComboBox(
                            {
                                "ID": self.wid("TimelineKey"),
                                "Weight": 1,
                            }
                        ),
                    ],
                ),
                ui.VGroup(
                    {"Spacing": 2, "Weight": 0},
                    [
                        ui.CheckBox(
                            {
                                "ID": self.wid("VfxHasHeader"),
                                "Text": us.CHECK_VFX_HAS_HEADER,
                                "Checked": False,
                                "Weight": 0,
                            }
                        ),
                        ui.CheckBox(
                            {
                                "ID": self.wid("Trim"),
                                "Text": "Trim whitespace",
                                "Checked": True,
                                "Weight": 0,
                            }
                        ),
                        ui.CheckBox(
                            {
                                "ID": self.wid("CaseInsensitive"),
                                "Text": "Case-insensitive match",
                                "Checked": True,
                                "Weight": 0,
                            }
                        ),
                        ui.CheckBox(
                            {
                                "ID": self.wid("StripExtension"),
                                "Text": us.CHECK_STRIP_EXTENSION,
                                "Checked": True,
                                "Weight": 0,
                            }
                        ),
                        ui.CheckBox(
                            {
                                "ID": self.wid("NormalizeNumeric"),
                                "Text": us.CHECK_NORMALIZE_NUMERIC,
                                "Checked": False,
                                "Weight": 0,
                            }
                        ),
                        ui.CheckBox(
                            {
                                "ID": self.wid("SkipEmpty"),
                                "Text": "Skip empty VFX keys",
                                "Checked": True,
                                "Weight": 0,
                            }
                        ),
                    ],
                ),
            ]
            + self._version_pattern_rows(ui)
            + track_filter_ui.build_track_filter_block(
                ui, self, label_width=self.track_filter_label_width
            )
            + [
                ui.CheckBox(
                    {
                        "ID": self.wid("UseInOut"),
                        "Text": us.CHECK_TIMELINE_INOUT,
                        "Checked": False,
                        "Weight": 0,
                    }
                ),
                ui.CheckBox(
                    {
                        "ID": self.wid("WarnCover"),
                        "Text": us.CHECK_WARN_COVER,
                        "Checked": True,
                        "Weight": 0,
                    }
                ),
                ui.HGroup(
                    {"Spacing": 8, "Weight": 0},
                    [
                        ui.Label({"Text": "Show:", "Weight": 0}),
                        ui.ComboBox(
                            {
                                "ID": self.wid("ShowFilter"),
                                "Weight": 1,
                            }
                        ),
                    ],
                ),
                ui.HGroup(
                    {"Spacing": 8, "Weight": 0},
                    [
                        ui.Label(
                            {
                                "Text": us.LABEL_EXPORT_CSV,
                                "Weight": 0,
                                "MinimumSize": [_FORM_LABEL_WIDTH, 0],
                            }
                        ),
                        ui.LineEdit(
                            {
                                "ID": self.wid("ExportCsv"),
                                "PlaceholderText": us.PLACEHOLDER_EXPORT_CSV,
                                "Text": "",
                                "Weight": 1,
                            }
                        ),
                        ui_kit.action_button(
                            ui,
                            {
                                "ID": self.wid("ExportCsvBtn"),
                                "Text": "Export CSV",
                                "Enabled": False,
                                "MinimumSize": [96, 0],
                            },
                        ),
                    ],
                ),
                ui.HGroup(
                    ui_kit.button_row_props(),
                    [
                        ui_kit.action_button(
                            ui,
                            {
                                "ID": self.wid("Scan"),
                                "Text": "Audit",
                                "Default": True,
                                "MinimumSize": [88, 0],
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
                ),
                ui.VGroup(
                    {"Spacing": 8, "Weight": 1},
                    [
                        ui.Label(
                            {
                                "ID": self.wid("Status"),
                                "Text": us.VERSION_AUDIT_STATUS_IDLE,
                                "Weight": 0,
                                "StyleSheet": "font-weight: bold;",
                            }
                        ),
                        ui.Tree(
                            {
                                "ID": self.wid("Tree"),
                                "Weight": 1,
                                "SortingEnabled": True,
                            }
                        ),
                        ui.HGroup(
                            ui_kit.button_row_props(),
                            [
                                ui.Label(
                                    {
                                        "Text": "Selected:",
                                        "Weight": 0,
                                        "MinimumSize": [70, 0],
                                    }
                                ),
                                ui.Label(
                                    {
                                        "ID": self.wid("SelTC"),
                                        "Text": "\u2014",
                                        "Weight": 0,
                                        "MinimumSize": [130, 0],
                                        "StyleSheet": "font-weight: bold;",
                                    }
                                ),
                                ui_kit.action_button(
                                    ui,
                                    {
                                        "ID": self.wid("GoTC"),
                                        "Text": "Jump to Clip",
                                        "Enabled": False,
                                        "MinimumSize": [120, 0],
                                    },
                                ),
                                ui_kit.action_button(
                                    ui,
                                    {
                                        "ID": self.wid("CopyTC"),
                                        "Text": "Copy Timecode",
                                        "Enabled": False,
                                        "MinimumSize": [120, 0],
                                    },
                                ),
                                ui_kit.action_button(
                                    ui,
                                    {
                                        "ID": self.wid("CopyVfxKey"),
                                        "Text": "Copy VFX Key",
                                        "Enabled": False,
                                        "MinimumSize": [110, 0],
                                    },
                                ),
                                ui.HGap(0, 1.0),
                            ],
                        ),
                        ui_kit.bottom_layout_pad(ui),
                    ],
                ),
            ],
        )

    def _preset_index(self, preset_id):
        for index, (pid, _label, _pattern) in enumerate(VERSION_PATTERN_PRESETS):
            if pid == preset_id:
                return index
        return 0

    def _apply_version_preset_combo(self, items, preset_id):
        combo = items[self.wid("VersionPreset")]
        for _pid, label, _pattern in VERSION_PATTERN_PRESETS:
            combo.AddItem(label)
        combo.CurrentIndex = self._preset_index(preset_id)

    def _set_version_pattern_ui_enabled(self, items, enabled):
        preset_custom = (
            items[self.wid("VersionPreset")].CurrentIndex
            == self._preset_index(_CUSTOM_PRESET_ID)
        )
        try:
            items[self.wid("VersionPreset")].Enabled = enabled
            items[self.wid("VersionPattern")].Enabled = enabled and preset_custom
        except Exception:
            pass

    def _apply_state(self, items, state):
        items[self.wid("VfxCsv")].Text = state.get("vfx_csv_path", "")
        items[self.wid("VfxKeyCol")].Text = state.get("vfx_key_column", "")
        items[self.wid("ExportCsv")].Text = state.get("export_csv_path", "")

        key_combo = items[self.wid("TimelineKey")]
        key_field = state.get("timeline_key_field", "clip_name")
        selected_index = 0
        for i, field in enumerate(TIMELINE_KEY_FIELDS):
            key_combo.AddItem(TIMELINE_KEY_LABELS[field])
            if field == key_field:
                selected_index = i
        key_combo.CurrentIndex = selected_index

        items[self.wid("VfxHasHeader")].Checked = bool(
            state.get("vfx_has_header", False)
        )
        items[self.wid("Trim")].Checked = bool(state.get("trim", True))
        items[self.wid("CaseInsensitive")].Checked = bool(
            state.get("case_insensitive", True)
        )
        items[self.wid("StripExtension")].Checked = bool(
            state.get("strip_extension", True)
        )
        items[self.wid("NormalizeNumeric")].Checked = bool(
            state.get("normalize_numeric", False)
        )
        items[self.wid("SkipEmpty")].Checked = bool(
            state.get("skip_empty_keys", True)
        )
        items[self.wid("DetectVersionDrift")].Checked = bool(
            state.get("detect_version_drift", True)
        )
        self._apply_version_preset_combo(
            items, state.get("version_preset", DEFAULT_VERSION_PRESET)
        )
        items[self.wid("VersionPattern")].Text = state.get("version_pattern", "")
        self._set_version_pattern_ui_enabled(
            items, bool(items[self.wid("DetectVersionDrift")].Checked)
        )
        items[self.wid("UseInOut")].Checked = bool(state.get("use_inout", False))
        items[self.wid("WarnCover")].Checked = bool(state.get("warn_cover", True))

        show_combo = items[self.wid("ShowFilter")]
        show_filter = state.get("show_filter", "all")
        show_index = 0
        for i, (key, label) in enumerate(SHOW_FILTERS):
            show_combo.AddItem(label)
            if key == show_filter:
                show_index = i
        show_combo.CurrentIndex = show_index

    def _gather_state(self, items):
        key_idx = items[self.wid("TimelineKey")].CurrentIndex
        if key_idx < 0 or key_idx >= len(TIMELINE_KEY_FIELDS):
            key_idx = 0
        timeline_key_field = TIMELINE_KEY_FIELDS[key_idx]

        show_idx = items[self.wid("ShowFilter")].CurrentIndex
        if show_idx < 0 or show_idx >= len(SHOW_FILTERS):
            show_idx = 0
        show_filter = SHOW_FILTERS[show_idx][0]

        preset_idx = items[self.wid("VersionPreset")].CurrentIndex
        if preset_idx < 0 or preset_idx >= len(VERSION_PATTERN_PRESETS):
            preset_idx = 0
        version_preset = VERSION_PATTERN_PRESETS[preset_idx][0]

        track_spec, use_tracks, track_state = track_filter_ui.gather_track_filter(
            items, self
        )

        state = {
            "vfx_csv_path": items[self.wid("VfxCsv")].Text.strip(),
            "vfx_key_column": items[self.wid("VfxKeyCol")].Text.strip(),
            "export_csv_path": items[self.wid("ExportCsv")].Text.strip(),
            "vfx_has_header": bool(items[self.wid("VfxHasHeader")].Checked),
            "timeline_key_field": timeline_key_field,
            "trim": bool(items[self.wid("Trim")].Checked),
            "case_insensitive": bool(items[self.wid("CaseInsensitive")].Checked),
            "strip_extension": bool(items[self.wid("StripExtension")].Checked),
            "normalize_numeric": bool(items[self.wid("NormalizeNumeric")].Checked),
            "skip_empty_keys": bool(items[self.wid("SkipEmpty")].Checked),
            "detect_version_drift": bool(
                items[self.wid("DetectVersionDrift")].Checked
            ),
            "version_preset": version_preset,
            "version_pattern": items[self.wid("VersionPattern")].Text.strip(),
            "use_inout": bool(items[self.wid("UseInOut")].Checked),
            "warn_cover": bool(items[self.wid("WarnCover")].Checked),
            "show_filter": show_filter,
            **track_state,
        }
        params = {
            **state,
            "track_filter_spec": track_spec,
            "use_track_filter": use_tracks,
        }
        return params, state

    def _row_passes_filter(self, row, show_filter):
        status = row.get("status", "")
        if show_filter == "all":
            return True
        if show_filter == "unmatched":
            return status == "not_in_edit"
        if show_filter == "matched":
            return status in MATCHED_STATUSES
        if show_filter == "normalized":
            return status in NORMALIZED_STATUSES
        if show_filter == "newer":
            return status.startswith("newer_in_project")
        if show_filter == "older":
            return status.startswith("older_in_project")
        if show_filter == "covered":
            return status in WARNING_STATUSES or bool(row.get("cover_warning"))
        return True

    def _row_values(self, row):
        track = row.get("track", "")
        track_text = f"V{track}" if track != "" else ""
        return [
            STATUS_LABELS.get(row.get("status", ""), row.get("status", "")),
            row.get("vfx_key", ""),
            row.get("version_note", "") or "\u2014",
            track_text,
            row.get("timecode", ""),
            row.get("clip_name", ""),
            row.get("cover_warning", ""),
        ]

    def _filtered_rows(self, results, show_filter):
        return [
            row for row in results if self._row_passes_filter(row, show_filter)
        ]

    def _populate_tree(self, tree, results, show_filter):
        ui_kit.clear_tree(tree)
        filtered = self._filtered_rows(results, show_filter)
        for row in filtered:
            ui_kit.add_row(tree, self._row_values(row))
        return len(filtered)

    def _suggest_export_path(self, vfx_source_path, show_filter):
        return default_audit_export_path(vfx_source_path, show_filter)

    def _set_export_enabled(self, export_btn, enabled):
        try:
            export_btn.Enabled = bool(enabled)
        except Exception:
            pass

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win
        api = ctx.api

        tree = items[self.wid("Tree")]
        ui_kit.setup_tree(tree, COLUMNS, COLUMN_WIDTHS)

        status = items[self.wid("Status")]
        scan_btn = items[self.wid("Scan")]
        cancel_btn = items[self.wid("Cancel")]
        sel_tc_label = items[self.wid("SelTC")]
        go_tc_btn = items[self.wid("GoTC")]
        copy_tc_btn = items[self.wid("CopyTC")]
        copy_vfx_btn = items[self.wid("CopyVfxKey")]
        export_csv_edit = items[self.wid("ExportCsv")]
        export_btn = items[self.wid("ExportCsvBtn")]
        show_combo = items[self.wid("ShowFilter")]

        store = self.state_store()
        loaded_state = store.load()
        try:
            self._apply_state(items, loaded_state)
        except Exception as exc:
            print(f"Conform Sidekick: {self.id} apply_state failed: {exc}")

        track_filter_ui.wire_track_filter(
            ctx, self, items, win, loaded_state
        )

        def set_status(text):
            try:
                status.Text = text
            except Exception:
                pass
            ui_kit.pump(ctx.dispatcher)

        def cell_of(item, column):
            if item is None:
                return ""
            try:
                return item.Text[column] or ""
            except Exception:
                return ""

        def set_selected_row(item):
            self._selected_tc = cell_of(item, TC_COLUMN)
            self._selected_vfx_key = cell_of(item, VFX_KEY_COLUMN)
            try:
                sel_tc_label.Text = self._selected_tc or "\u2014"
                go_tc_btn.Enabled = bool(self._selected_tc)
                copy_tc_btn.Enabled = bool(self._selected_tc)
                copy_vfx_btn.Enabled = bool(self._selected_vfx_key)
            except Exception:
                pass

        def update_export_path_suggestion():
            show_idx = show_combo.CurrentIndex
            if show_idx < 0 or show_idx >= len(SHOW_FILTERS):
                show_idx = 0
            show_filter = SHOW_FILTERS[show_idx][0]
            vfx_path = items[self.wid("VfxCsv")].Text.strip()
            if vfx_path:
                try:
                    export_csv_edit.Text = self._suggest_export_path(
                        vfx_path, show_filter
                    )
                except Exception:
                    pass

        def set_running(running):
            form_ids = (
                "VfxCsv", "VfxKeyCol", "ExportCsv", "VfxHasHeader", "TimelineKey",
                "Trim", "CaseInsensitive", "StripExtension", "NormalizeNumeric",
                "SkipEmpty", "DetectVersionDrift", "VersionPreset",
                "VersionPattern", "UseInOut", "WarnCover", "UseTrackFilter",
            )
            try:
                scan_btn.Enabled = not running
                scan_btn.Text = "Auditing..." if running else "Audit"
                cancel_btn.Enabled = running
                cancel_btn.Text = "Cancel"
                show_combo.Enabled = not running
                for wid in form_ids:
                    items[self.wid(wid)].Enabled = not running
                self._set_export_enabled(
                    export_btn, (not running) and bool(self._all_results)
                )
                if not running:
                    self._set_version_pattern_ui_enabled(
                        items,
                        bool(items[self.wid("DetectVersionDrift")].Checked),
                    )
                track_filter_ui.set_track_filter_enabled(
                    items,
                    self,
                    bool(items[self.wid("UseTrackFilter")].Checked) and not running,
                )
            except Exception:
                pass

        def on_version_drift_toggle(_ev):
            self._set_version_pattern_ui_enabled(
                items,
                bool(items[self.wid("DetectVersionDrift")].Checked),
            )

        def on_version_preset_change(_ev):
            self._set_version_pattern_ui_enabled(
                items,
                bool(items[self.wid("DetectVersionDrift")].Checked),
            )

        def refresh_table():
            show_idx = show_combo.CurrentIndex
            if show_idx < 0 or show_idx >= len(SHOW_FILTERS):
                show_idx = 0
            show_filter = SHOW_FILTERS[show_idx][0]
            set_selected_row(None)
            count = self._populate_tree(tree, self._all_results, show_filter)
            self._set_export_enabled(export_btn, bool(self._all_results))
            update_export_path_suggestion()
            return count

        def on_show_filter_change(_ev):
            if self._run.running:
                return
            count = refresh_table()
            if self._all_results:
                set_status(f"Showing {count} row(s) with the current filter.")

        def on_export():
            if self._run.running:
                return
            if not self._all_results:
                set_status(us.VERSION_AUDIT_NO_RESULTS)
                return

            show_idx = show_combo.CurrentIndex
            if show_idx < 0 or show_idx >= len(SHOW_FILTERS):
                show_idx = 0
            show_filter = SHOW_FILTERS[show_idx][0]

            export_path = export_csv_edit.Text.strip()
            if not export_path:
                vfx_path = items[self.wid("VfxCsv")].Text.strip()
                export_path = self._suggest_export_path(vfx_path, show_filter)
            if not export_path:
                set_status(us.VERSION_AUDIT_NO_EXPORT_PATH)
                return

            filtered = self._filtered_rows(self._all_results, show_filter)
            rows = [self._row_values(row) for row in filtered]
            try:
                write_results_csv(export_path, COLUMNS, rows)
            except OSError as exc:
                set_status(f"Could not write export CSV: {exc}")
                return

            try:
                export_csv_edit.Text = export_path
            except Exception:
                pass
            try:
                store.save({**store.load(), "export_csv_path": export_path})
            except Exception:
                pass
            set_status(
                f"Exported {len(rows)} row(s) to {export_path} "
                f"(current Show filter: {SHOW_FILTERS[show_idx][1]})."
            )

        def on_scan():
            if self._run.running:
                return

            if ctx.conn.get_project() is None:
                set_status(us.STATUS_NO_PROJECT)
                return
            if ctx.conn.get_timeline() is None:
                set_status(us.VERSION_AUDIT_NO_TIMELINE)
                return

            try:
                params, state = self._gather_state(items)
            except Exception as exc:
                set_status(str(exc))
                return

            if not params["vfx_csv_path"]:
                set_status(us.VERSION_AUDIT_NO_CSV)
                return
            if not params["vfx_key_column"]:
                set_status(us.VERSION_AUDIT_NO_KEY_COLUMN)
                return

            store.save(state)
            self._all_results = []
            ui_kit.clear_tree(tree)
            set_selected_row(None)
            self._set_export_enabled(export_btn, False)

            self._run.begin()
            set_running(True)
            set_status("Auditing… scanning timeline clips.")

            def on_progress(count):
                try:
                    status.Text = (
                        f"Auditing… {count} timeline clip(s) checked "
                        "(click Cancel to stop)"
                    )
                except Exception:
                    pass
                ui_kit.pump(ctx.dispatcher)

            cancelled = False
            summary = None
            try:
                summary = run_version_audit(
                    ctx.conn,
                    vfx_csv_path=params["vfx_csv_path"],
                    vfx_key_column=params["vfx_key_column"],
                    timeline_key_field=params["timeline_key_field"],
                    vfx_has_header=params["vfx_has_header"],
                    trim=params["trim"],
                    case_insensitive=params["case_insensitive"],
                    strip_extension=params["strip_extension"],
                    normalize_numeric=params["normalize_numeric"],
                    skip_empty_keys=params["skip_empty_keys"],
                    detect_version_drift=params["detect_version_drift"],
                    version_preset=params["version_preset"],
                    version_pattern=params["version_pattern"],
                    track_filter_spec=params["track_filter_spec"],
                    use_track_filter=params["use_track_filter"],
                    use_inout=params["use_inout"],
                    warn_cover=params["warn_cover"],
                    should_cancel=self._run.should_cancel,
                    on_progress=on_progress,
                )
                self._all_results = summary["results"]
            except ScanCancelled:
                cancelled = True
            except Exception as exc:
                self._run.end()
                set_running(False)
                set_status(f"Error while auditing: {exc}")
                return

            row_count = refresh_table()

            self._run.end()
            set_running(False)

            if cancelled:
                set_status(
                    f"Audit stopped early. Showing {row_count} row(s) so far."
                )
                return

            if summary is None:
                set_status("Audit produced no results.")
                return

            parts = [
                f"{summary['vfx_rows']} VFX row(s)",
                f"{summary['unmatched_count']} not in edit",
                f"{summary['matched_count']} matched",
            ]
            if params["normalize_numeric"]:
                parts.append(f"{summary['normalized_count']} matched (normalized)")
            if params["detect_version_drift"]:
                parts.append(f"{summary['newer_count']} newer in project")
                parts.append(f"{summary['older_count']} older in project")
            if params["warn_cover"]:
                parts.append(f"{summary['covered_count']} covered")
            if summary.get("disabled_count"):
                parts.append(f"{summary['disabled_count']} disabled")
            msg = (
                f"Audited {', '.join(parts)} "
                f"({summary['clips_scanned']} timeline clip(s) scanned). "
                f"Showing {row_count} row(s). "
                "Select a row, then Jump to Clip, Copy Timecode, or Copy VFX Key "
                "(double-click a row to jump)."
            )
            set_status(msg)

        def on_cancel():
            if self._run.running:
                self._run.request_cancel()
                try:
                    cancel_btn.Text = "Cancelling..."
                    cancel_btn.Enabled = False
                except Exception:
                    pass

        def jump_to(tc):
            if not tc:
                return
            if api.go_to_timecode(tc):
                set_status(f"Playhead moved to {tc}.")
            else:
                set_status(f"Could not jump to {tc} — open the timeline first.")

        def on_select(ev):
            set_selected_row(ui_kit.get_event_item(ev))

        def on_double(ev):
            jump_to(cell_of(ui_kit.get_event_item(ev), TC_COLUMN))

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

        def on_copy_vfx_key():
            vfx_key = self._selected_vfx_key
            if not vfx_key:
                return
            if ui_kit.copy_to_clipboard(vfx_key):
                set_status(f"Copied VFX key {vfx_key} to the clipboard.")
            else:
                set_status(f"Could not copy {vfx_key} to the clipboard.")

        win.On[self.wid("Scan")].Clicked = lambda ev: on_scan()
        win.On[self.wid("Cancel")].Clicked = lambda ev: on_cancel()
        win.On[self.wid("ExportCsvBtn")].Clicked = lambda ev: on_export()
        win.On[self.wid("GoTC")].Clicked = lambda ev: on_go()
        win.On[self.wid("CopyTC")].Clicked = lambda ev: on_copy()
        win.On[self.wid("CopyVfxKey")].Clicked = lambda ev: on_copy_vfx_key()
        win.On[self.wid("DetectVersionDrift")].Clicked = on_version_drift_toggle
        win.On[self.wid("VersionPreset")].CurrentIndexChanged = on_version_preset_change
        win.On[self.wid("VersionPreset")].ItemClicked = on_version_preset_change
        win.On[self.wid("ShowFilter")].CurrentIndexChanged = on_show_filter_change
        win.On[self.wid("ShowFilter")].ItemClicked = on_show_filter_change
        win.On[self.wid("Tree")].ItemDoubleClicked = on_double
        win.On[self.wid("Tree")].ItemClicked = on_select
        win.On[self.wid("Tree")].CurrentItemChanged = on_select

    def on_show(self, ctx):
        track_filter_ui.refresh_track_filter_ui(ctx, self, ctx.items)
        track_filter_ui.set_track_filter_enabled(
            ctx.items,
            self,
            bool(ctx.items[self.wid("UseTrackFilter")].Checked),
        )
        self._set_version_pattern_ui_enabled(
            ctx.items,
            bool(ctx.items[self.wid("DetectVersionDrift")].Checked),
        )
        ui_kit.recalc_layout(ctx.win)
        ui_kit.pump(ctx.dispatcher)
