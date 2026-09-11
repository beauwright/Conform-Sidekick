"""Bypass / restore the color grade on the current clip in the Color page.

Bypass copies the current grade to a temporary local color version and
disables everything on that copy except the configured color input and output
nodes; the working grade is never modified. Restore switches back to the
original version and deletes the bypass version. Shared color group pre/post
graphs can't be versioned, so those are toggled in place (see
``ops.grade_bypass``).

The panel also hosts the Stream Deck / remote control switch (see ``remote``):
``bypass`` / ``restore`` / ``toggle`` / ``status`` are registered as remote
actions and run through the same :meth:`GradeBypassFeature.trigger` path as
the buttons, so a Stream Deck press behaves exactly like a click.
"""

import traceback

from .log_feature import LogFeature
from ..state import StateStore
from .. import remote as remote_mod
from .. import ui_kit
from .. import ui_strings as us
from ..ops.grade_bypass import (
    clip_on_bypass_version,
    current_clip_key,
    current_clip_label,
    grade_bypass,
    normalize_snapshots_by_clip,
    snapshot_can_restore,
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
    return snapshot_can_restore(by_clip.get(clip_key))


class GradeBypassFeature(LogFeature):
    id = "gradebypass"
    title = "Bypass Grade (Current Clip)"
    category = "color"

    def __init__(self):
        super().__init__()
        self._bound = None
        self._remote_dirty = False

    def state_store(self):
        return StateStore("grade_bypass", DEFAULTS)

    def form_rows(self, ui):
        return [
            ui_kit.note_block(ui, us.GRADE_BYPASS_INTRO),
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
            ui_kit.note_block(ui, us.GRADE_BYPASS_GROUP_NOTE),
            ui.CheckBox(
                {
                    "ID": self.wid("DryRun"),
                    "Text": us.CHECK_PREVIEW_ONLY,
                    "Checked": False,
                    "Weight": 0,
                }
            ),
        ] + self.remote_rows(ui)

    def remote_rows(self, ui):
        return [
            ui.VGap(4, 0.0),
            ui.Label(
                {
                    "Text": us.REMOTE_HEADER,
                    "Weight": 0,
                    "StyleSheet": "font-weight: bold;",
                }
            ),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.CheckBox(
                        {
                            "ID": self.wid("RemoteEnable"),
                            "Text": us.CHECK_REMOTE_ENABLE,
                            "Checked": False,
                            "Weight": 0,
                        }
                    ),
                    ui.HGap(12, 0.0),
                    ui.Label({"Text": us.LABEL_REMOTE_PORT, "Weight": 0}),
                    ui.LineEdit(
                        {
                            "ID": self.wid("RemotePort"),
                            "PlaceholderText": str(remote_mod.DEFAULT_PORT),
                            "Weight": 0,
                            "MinimumSize": [80, 0],
                            "MaximumSize": [90, 16777215],
                        }
                    ),
                    ui.HGap(0, 1.0),
                ],
            ),
            ui.Label(
                {
                    "ID": self.wid("RemoteStatus"),
                    "Text": us.REMOTE_STATUS_OFF,
                    "Weight": 0,
                }
            ),
            ui.HGroup(
                ui_kit.button_row_props(),
                [
                    ui_kit.action_button(
                        ui,
                        {
                            "ID": self.wid("RemoteFolder"),
                            "Text": us.BTN_REMOTE_FOLDER,
                            "MinimumSize": [150, 0],
                        },
                    ),
                    ui_kit.action_button(
                        ui,
                        {
                            "ID": self.wid("RemoteCopyUrl"),
                            "Text": us.BTN_REMOTE_COPY_URL,
                            "MinimumSize": [130, 0],
                        },
                    ),
                    ui.HGap(0, 1.0),
                ],
            ),
            ui_kit.note_block(ui, us.REMOTE_NOTE),
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
        rows.append(ui_kit.bottom_layout_pad(ui))
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
            enabled = _clip_has_bypass(store.load(), clip_key)
            if not enabled and conn is not None:
                # Orphaned bypass version (e.g. state lost): restore can still
                # recover it, so keep the button available.
                enabled = clip_on_bypass_version(conn)
            items[self.wid("Restore")].Enabled = enabled
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
                if self._remote_dirty:
                    self._apply_remote_settings(ctx)

        def on_cancel():
            if self._run.running:
                self._run.request_cancel()
                try:
                    cancel_btn.Text = "Cancelling..."
                    cancel_btn.Enabled = False
                except Exception:
                    pass

        self._bound = {
            "ctx": ctx,
            "items": items,
            "store": store,
            "log_ctl": log_ctl,
            "set_running": set_running,
        }

        win.On[self.wid("Bypass")].Clicked = lambda ev: self.trigger("bypass")
        win.On[self.wid("Restore")].Clicked = lambda ev: self.trigger("restore")
        win.On[self.wid("Cancel")].Clicked = lambda ev: on_cancel()

        self._bind_remote(ctx)

    # -- running -----------------------------------------------------------

    def _wants_restore(self, ctx, store):
        """True when the current clip is bypassed (toggle -> restore)."""
        try:
            clip_key = current_clip_key(ctx.conn)
            if store is not None and _clip_has_bypass(store.load(), clip_key):
                return True
        except Exception:
            pass
        return clip_on_bypass_version(ctx.conn)

    def trigger(self, action):
        """Run ``bypass`` / ``restore`` / ``toggle`` exactly as a button click would.

        Shared by the panel buttons and the remote control. Returns a dict for
        the remote reply: ``ok``, ``did`` (bypass/restore), ``message``,
        ``clip``.
        """
        bound = getattr(self, "_bound", None)
        if bound is None:
            return {"ok": False, "error": "not_ready", "message": "Window is not ready."}
        ctx, items, store = bound["ctx"], bound["items"], bound["store"]
        log_ctl, set_running = bound["log_ctl"], bound["set_running"]

        if self._run.running:
            return {
                "ok": False,
                "error": "busy",
                "message": "Bypass Grade is still running the previous action.",
            }

        action = (action or "").strip().lower()
        if action == "toggle":
            restore = self._wants_restore(ctx, store)
        elif action in ("bypass", "restore"):
            restore = action == "restore"
        else:
            return {"ok": False, "error": "unknown_action", "message": f"Unknown action '{action}'."}
        did = "restore" if restore else "bypass"

        # A remote trigger while another panel is showing: bring this one up
        # so the log is visible. A button click already has the panel shown.
        try:
            panel = items.get(self.panel_id) if hasattr(items, "get") else None
            if panel is not None and panel.Hidden and ctx.select_feature is not None:
                ctx.select_feature(self)
        except Exception:
            pass

        try:
            params, state = self.gather(items, restore=restore)
        except Exception as exc:
            log_ctl.reset()
            log_ctl.log(f"Check your settings: {exc}")
            return {"ok": False, "did": did, "message": f"Check your settings: {exc}"}
        if store is not None and state is not None:
            store.save(state)

        last_line = {"text": ""}

        def log(line):
            last_line["text"] = str(line)
            log_ctl.log(line)

        log_ctl.reset()
        self._run.begin()
        set_running(True, did)
        result = None
        try:
            result = self.run(ctx, params, log, log_ctl.pump, self._run.should_cancel)
        except Exception as exc:
            log(f"Unhandled error: {type(exc).__name__}: {exc}")
            log_ctl.log(traceback.format_exc())
            result = {"error": True}
        finally:
            self._run.end()
            set_running(False)

        return self._describe_result(result or {}, did, params.get("dry_run"), last_line["text"])

    @staticmethod
    def _describe_result(result, did, dry_run, last_line):
        clip = (result.get("clip_name") or "").strip()
        where = f" on {clip}" if clip else ""
        if result.get("error"):
            message = last_line or f"{did.capitalize()} grade failed."
            return {"ok": False, "did": did, "clip": clip, "message": message}
        if result.get("cancelled"):
            return {"ok": False, "did": did, "clip": clip, "error": "cancelled", "message": "Cancelled."}
        changed = int(result.get("nodes_changed") or 0)
        verb = "restored" if did == "restore" else "bypassed"
        message = f"Grade {verb}{where} ({changed} node{'s' if changed != 1 else ''})."
        if dry_run:
            message = "Preview only: " + message
        return {"ok": True, "did": did, "clip": clip, "nodes_changed": changed, "message": message}

    def remote_status(self, ctx):
        store = self.state_store()
        bypassed = self._wants_restore(ctx, store)
        return {
            "ok": True,
            "bypassed": bypassed,
            "clip": current_clip_label(ctx.conn),
            "running": self._run.running,
            "message": ("Grade is bypassed." if bypassed else "Grade is active."),
        }

    # -- remote control ----------------------------------------------------

    def _bind_remote(self, ctx):
        items = ctx.items
        win = ctx.win
        remote = ctx.remote
        if remote is None:
            return

        remote.register("bypass", lambda q: self.trigger("bypass"), "Bypass the grade on the current clip")
        remote.register("restore", lambda q: self.trigger("restore"), "Restore the grade on the current clip")
        remote.register("toggle", lambda q: self.trigger("toggle"), "Bypass if active, restore if bypassed")
        remote.register("status", lambda q: self.remote_status(ctx), "Report whether the current clip is bypassed")

        remote_store = remote_mod.remote_state_store()
        saved = remote_store.load()
        try:
            items[self.wid("RemoteEnable")].Checked = bool(saved.get("enabled"))
            port = saved.get("port") or remote_mod.DEFAULT_PORT
            items[self.wid("RemotePort")].Text = "" if port == remote_mod.DEFAULT_PORT else str(port)
        except Exception:
            pass

        def on_folder():
            folder = remote_mod.launcher_dir()
            if remote.listening:
                remote_mod.write_launchers(folder, remote.port, remote.token)
            if not remote_mod.reveal_folder(folder):
                self._set_remote_status(items, f"Launcher files: {folder}")

        def on_copy_url():
            token = remote_mod.ensure_token(remote_store)
            port = remote.port or self._remote_port_from_ui(items)[0] or remote_mod.DEFAULT_PORT
            url = remote_mod.endpoint_url(port, "toggle", token=token)
            if ui_kit.copy_to_clipboard(url):
                self._set_remote_status(items, f"Copied: {url}")
            else:
                self._set_remote_status(items, f"Toggle URL: {url}")

        win.On[self.wid("RemoteEnable")].Clicked = lambda ev: self._apply_remote_settings(ctx)
        win.On[self.wid("RemotePort")].EditingFinished = lambda ev: self._apply_remote_settings(ctx)
        win.On[self.wid("RemotePort")].ReturnPressed = lambda ev: self._apply_remote_settings(ctx)
        win.On[self.wid("RemoteFolder")].Clicked = lambda ev: on_folder()
        win.On[self.wid("RemoteCopyUrl")].Clicked = lambda ev: on_copy_url()

        self._apply_remote_settings(ctx)

    def _remote_port_from_ui(self, items):
        try:
            text = items[self.wid("RemotePort")].Text
        except Exception:
            text = ""
        return remote_mod.parse_port(text)

    def _set_remote_status(self, items, text):
        try:
            items[self.wid("RemoteStatus")].Text = text
        except Exception:
            pass

    def _apply_remote_settings(self, ctx):
        """Start / stop / re-port the listener to match the panel widgets."""
        items = ctx.items
        remote = ctx.remote
        if remote is None:
            return
        if self._run.running:
            # Never tear the listener down mid-request; set_running(False) retries.
            self._remote_dirty = True
            return
        self._remote_dirty = False

        try:
            enabled = bool(items[self.wid("RemoteEnable")].Checked)
        except Exception:
            enabled = False
        port, err = self._remote_port_from_ui(items)
        if err:
            self._set_remote_status(items, err)
            return

        remote_store = remote_mod.remote_state_store()
        remote_store.save({"enabled": enabled, "port": port})

        if not enabled:
            if remote.listening:
                remote.stop()
            self._set_remote_status(items, us.REMOTE_STATUS_OFF)
            return

        if remote.listening and remote.requested_port == port:
            return

        token = remote_mod.ensure_token(remote_store)
        try:
            actual = remote.start(port, token)
        except OSError as exc:
            self._set_remote_status(items, f"Could not start remote control: {exc}")
            return

        folder = remote_mod.launcher_dir()
        _written, errors = remote_mod.write_launchers(folder, actual, token)
        note = f" (port {port} was busy)" if actual != port else ""
        status = f"Listening on http://127.0.0.1:{actual}{note} - launcher files in {folder}"
        if errors:
            status += f" - {len(errors)} launcher file(s) failed: {errors[0]}"
        self._set_remote_status(items, status)

    def on_show(self, ctx):
        self._update_restore_enabled(ctx.items, self.state_store(), ctx.conn)
