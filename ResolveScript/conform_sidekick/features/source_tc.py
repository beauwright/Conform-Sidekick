"""Set Source TC From Date Created.

Finds media pool clips sitting at a source TC of ``00:00:00:00`` and gives each
one an invented timecode derived from its ``Date Created``, so TC-driven tools
have something unique to work with. See :mod:`conform_sidekick.ops.source_tc`
for the verified Resolve behaviour this relies on.

Shaped like :mod:`conform_sidekick.features.grade_bypass`: a log feature with a
second action button (Revert) whose enabled state depends on whether this
workstation has recorded changes for the currently open project.
"""

import traceback

from .log_feature import LogFeature
from ..state import StateStore
from .. import ui_kit
from .. import ui_strings as us
from ..ops.source_tc import (
    CURATED_ZONES,
    ZONE_LOCAL,
    revert_source_tc,
    set_source_tc,
)


DEFAULTS = {
    "scope_index": 0,      # 0 = entire project, 1 = current bin
    "zone_index": 0,       # 0 = machine local, 1 = UTC, 2+ = CURATED_ZONES
    "zone_override": "",
    "include_images": False,
    "include_audio": False,
    "include_in_timeline": False,
    "dry_run": True,       # this mode writes to the project; preview by default
    "applied_by_project": {},
}

APPLY_LABEL = "Set Source TC"
REVERT_LABEL = "Revert"

# Combo entries ahead of the curated IANA list.
_ZONE_LOCAL_INDEX = 0
_ZONE_UTC_INDEX = 1


def _row(ui, label, widget):
    return ui.HGroup(
        {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
        [ui.Label({"Text": label, "Weight": 0, "MinimumSize": [130, 0]}), widget],
    )


def _zone_name_for_index(index):
    """Map a combo index to the zone name understood by ``ops.source_tc``."""
    if index == _ZONE_LOCAL_INDEX:
        return ZONE_LOCAL
    if index == _ZONE_UTC_INDEX:
        return "UTC"
    offset = index - (_ZONE_UTC_INDEX + 1)
    if 0 <= offset < len(CURATED_ZONES):
        return CURATED_ZONES[offset]
    return ZONE_LOCAL


def _project_key(conn):
    """Stable per-project key for the applied-clip record."""
    project = conn.get_project()
    if project is None:
        return ""
    for getter in ("GetUniqueId", "GetName"):
        try:
            value = getattr(project, getter)()
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def _applied_ids(state, project_key):
    by_project = state.get("applied_by_project")
    if not isinstance(by_project, dict) or not project_key:
        return []
    ids = by_project.get(project_key)
    return list(ids) if isinstance(ids, list) else []


class SourceTcFeature(LogFeature):
    id = "sourcetc"
    title = "Set Source TC From Date Created"
    category = "conform"
    run_label = APPLY_LABEL

    def state_store(self):
        return StateStore("source_tc", DEFAULTS)

    # -- layout ------------------------------------------------------------

    def form_rows(self, ui):
        return [
            ui_kit.note_block(ui, us.SOURCE_TC_INTRO),
            _row(
                ui,
                us.LABEL_SEARCH_IN,
                ui.ComboBox({"ID": self.wid("Scope"), "Weight": 1}),
            ),
            _row(
                ui,
                us.LABEL_SOURCE_TC_ZONE,
                ui.ComboBox({"ID": self.wid("Zone"), "Weight": 1}),
            ),
            _row(
                ui,
                us.LABEL_SOURCE_TC_ZONE_OVERRIDE,
                ui.LineEdit(
                    {
                        "ID": self.wid("ZoneOverride"),
                        "PlaceholderText": us.PLACEHOLDER_SOURCE_TC_ZONE,
                        "Weight": 1,
                    }
                ),
            ),
            ui_kit.note_block(ui, us.SOURCE_TC_ZONE_NOTE),
            ui.CheckBox(
                {
                    "ID": self.wid("IncludeImages"),
                    "Text": us.CHECK_SOURCE_TC_INCLUDE_IMAGES,
                    "Checked": False,
                    "Weight": 0,
                }
            ),
            ui.CheckBox(
                {
                    "ID": self.wid("IncludeAudio"),
                    "Text": us.CHECK_SOURCE_TC_INCLUDE_AUDIO,
                    "Checked": False,
                    "Weight": 0,
                }
            ),
            ui_kit.note_block(ui, us.SOURCE_TC_TIMELINE_NOTE),
            ui.CheckBox(
                {
                    "ID": self.wid("IncludeInTimeline"),
                    "Text": us.CHECK_SOURCE_TC_INCLUDE_IN_TIMELINE,
                    "Checked": False,
                    "Weight": 0,
                }
            ),
            ui.CheckBox(
                {
                    "ID": self.wid("DryRun"),
                    "Text": us.CHECK_PREVIEW_ONLY,
                    "Checked": True,
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
                            "ID": self.wid("Apply"),
                            "Text": APPLY_LABEL,
                            "Default": True,
                            "MinimumSize": [130, 0],
                        },
                    ),
                    ui_kit.action_button(
                        ui,
                        {
                            "ID": self.wid("Revert"),
                            "Text": REVERT_LABEL,
                            "Enabled": False,
                            "MinimumSize": [100, 0],
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

    # -- state -------------------------------------------------------------

    def apply_state(self, items, state):
        scope = items[self.wid("Scope")]
        scope.AddItem(us.SCOPE_ENTIRE_PROJECT)
        scope.AddItem(us.SOURCE_TC_SCOPE_BIN)
        scope_index = state.get("scope_index", 0)
        scope.CurrentIndex = scope_index if scope_index in (0, 1) else 0

        zone = items[self.wid("Zone")]
        zone.AddItem(us.SOURCE_TC_ZONE_LOCAL)
        zone.AddItem("UTC")
        for name in CURATED_ZONES:
            zone.AddItem(name)
        zone_index = state.get("zone_index", 0)
        if not isinstance(zone_index, int) or not 0 <= zone_index < 2 + len(CURATED_ZONES):
            zone_index = 0
        zone.CurrentIndex = zone_index

        items[self.wid("ZoneOverride")].Text = state.get("zone_override", "") or ""
        items[self.wid("IncludeImages")].Checked = bool(state.get("include_images"))
        items[self.wid("IncludeAudio")].Checked = bool(state.get("include_audio"))
        items[self.wid("IncludeInTimeline")].Checked = bool(
            state.get("include_in_timeline")
        )
        items[self.wid("DryRun")].Checked = bool(state.get("dry_run", True))

    def gather(self, items, revert=False):
        zone_index = items[self.wid("Zone")].CurrentIndex
        override = (items[self.wid("ZoneOverride")].Text or "").strip()
        scope_index = items[self.wid("Scope")].CurrentIndex
        params = {
            "revert": revert,
            "scope": "bin" if scope_index == 1 else "project",
            "zone_name": override or _zone_name_for_index(zone_index),
            "include_images": bool(items[self.wid("IncludeImages")].Checked),
            "include_audio": bool(items[self.wid("IncludeAudio")].Checked),
            "include_in_timeline": bool(items[self.wid("IncludeInTimeline")].Checked),
            "dry_run": bool(items[self.wid("DryRun")].Checked),
        }
        state = {
            "scope_index": scope_index,
            "zone_index": zone_index,
            "zone_override": override,
            "include_images": params["include_images"],
            "include_audio": params["include_audio"],
            "include_in_timeline": params["include_in_timeline"],
            "dry_run": params["dry_run"],
        }
        return params, state

    # -- run ---------------------------------------------------------------

    def run(self, ctx, params, log, pump, should_cancel):
        store = self.state_store()
        project_key = _project_key(ctx.conn)
        if not project_key:
            log(us.SOURCE_TC_NO_PROJECT)
            return None
        state = store.load()

        if params["revert"]:
            result = revert_source_tc(
                ctx.conn,
                ctx.api,
                _applied_ids(state, project_key),
                log=log,
                pump=pump,
                should_cancel=should_cancel,
            )
            # Drop the record only once everything came back cleanly, so a
            # partial revert stays retryable.
            if result["reverted"] and not result["failed"] and not result["cancelled"]:
                by_project = dict(state.get("applied_by_project") or {})
                by_project.pop(project_key, None)
                store.save({"applied_by_project": by_project})
            return result

        result = set_source_tc(
            ctx.conn,
            ctx.api,
            scope=params["scope"],
            zone_name=params["zone_name"],
            include_images=params["include_images"],
            include_audio=params["include_audio"],
            include_in_timeline=params["include_in_timeline"],
            dry_run=params["dry_run"],
            log=log,
            pump=pump,
            should_cancel=should_cancel,
        )
        if result.get("applied_ids"):
            by_project = dict(state.get("applied_by_project") or {})
            merged = list(by_project.get(project_key) or [])
            known = set(merged)
            merged.extend(uid for uid in result["applied_ids"] if uid not in known)
            by_project[project_key] = merged
            store.save({"applied_by_project": by_project})
        return result

    # -- wiring ------------------------------------------------------------

    def _update_revert_enabled(self, items, store, conn):
        if store is None or conn is None:
            return
        try:
            enabled = bool(_applied_ids(store.load(), _project_key(conn)))
            items[self.wid("Revert")].Enabled = enabled
        except Exception:
            pass

    def bind(self, ctx):
        items = ctx.items
        win = ctx.win

        log_ctl = ui_kit.LogController(ctx.dispatcher, items[self.wid("Log")])
        apply_btn = items[self.wid("Apply")]
        revert_btn = items[self.wid("Revert")]
        cancel_btn = items[self.wid("Cancel")]

        store = self.state_store()
        if store is not None:
            try:
                self.apply_state(items, store.load())
            except Exception as exc:
                print(f"Conform Sidekick: {self.id} apply_state failed: {exc}")

        self._update_revert_enabled(items, store, ctx.conn)

        def set_running(running, active=None):
            try:
                apply_btn.Enabled = not running
                apply_btn.Text = (
                    "Running..." if running and active == "apply" else APPLY_LABEL
                )
                revert_btn.Enabled = not running and revert_btn.Enabled
                revert_btn.Text = (
                    "Running..." if running and active == "revert" else REVERT_LABEL
                )
                cancel_btn.Enabled = running
                cancel_btn.Text = "Cancel"
            except Exception:
                pass
            if not running:
                self._update_revert_enabled(items, store, ctx.conn)

        def on_action(revert):
            if self._run.running:
                return
            try:
                params, state = self.gather(items, revert=revert)
            except Exception as exc:
                log_ctl.reset()
                log_ctl.log(f"Check your settings: {exc}")
                return
            if store is not None and state is not None:
                store.save(state)

            log_ctl.reset()
            self._run.begin()
            set_running(True, "revert" if revert else "apply")
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

        win.On[self.wid("Apply")].Clicked = lambda ev: on_action(revert=False)
        win.On[self.wid("Revert")].Clicked = lambda ev: on_action(revert=True)
        win.On[self.wid("Cancel")].Clicked = lambda ev: on_cancel()

    def on_show(self, ctx):
        # The open project can change between visits, and the record of applied
        # clips is per-project.
        self._update_revert_enabled(ctx.items, self.state_store(), ctx.conn)
