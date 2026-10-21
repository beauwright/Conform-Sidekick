"""Color Groups from Avid LUTs.

Load an Avid bin, map each shot LUT logged in it to one of the project's
existing color groups, and drop the timeline's clips into those groups. See
:mod:`conform_sidekick.ops.avid_lut_groups` for how clips are matched.

The LUT -> group mapping is remembered per project. LUTs the user has not
mapped yet fall back to a suggested group whose name resembles the LUT.
"""

import os

from .log_feature import TrackFilterLogFeature
from .bin_bookmarks import _project_key
from ..state import StateStore
from .. import track_filter_ui
from .. import ui_kit
from .. import ui_strings as us
from ..ops import avid_lut_groups as alg

LUT_SOURCE_CHOICES = (
    (alg.LUT_SOURCE_COLUMN_THEN_CAMERA, "Bin LUT column, then camera LUT"),
    (alg.LUT_SOURCE_CAMERA_THEN_COLUMN, "Camera LUT, then bin LUT column"),
    (alg.LUT_SOURCE_COLUMN_ONLY, "Bin LUT column only"),
    (alg.LUT_SOURCE_CAMERA_ONLY, "Camera LUT only"),
)

DEFAULTS = {
    "bin_path": "",
    "lut_column": "LUT",
    "lut_source_index": 0,
    "match_camera_file": True,
    "match_camera_roll": True,
    "match_clip_name": True,
    "use_track_filter": False,
    "track_filter": "",
    "dry_run": True,
    # project unique id -> {lut: group name | "" (don't assign) | alg.NEW_GROUP}
    "by_project": {},
}

INTRO = (
    "Assigns timeline clips to your existing color groups by the LUT each shot\n"
    "was logged with in an Avid bin. Clips already in a color group are skipped."
)

COLUMNS = ["LUT", "Timeline clips", "Color group"]
COLUMN_WIDTHS = [330, 100, 260]
# LUT name, stored on the row past ColumnCount (see bin_bookmarks.ID_COLUMN).
LUT_COLUMN = 3

NO_GROUP = "— Don't assign —"
NEW_GROUP_PREFIX = "+ New empty group: "


def choice_value(choice):
    """Mapping value stored for a group dropdown entry."""
    if choice == NO_GROUP:
        return ""
    if choice.startswith(NEW_GROUP_PREFIX):
        return alg.NEW_GROUP
    return choice


def same_choice(lut, current, value):
    """True when ``value`` would send ``lut`` to the group it already maps to.

    A new-group choice and picking the existing group of that name are the
    same target.
    """
    return alg.mapping_target({lut: current}, lut)[0] == alg.mapping_target({lut: value}, lut)[0]


def _row(ui, label, widget):
    return ui.HGroup(
        {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
        [ui.Label({"Text": label, "Weight": 0, "MinimumSize": [130, 0]}), widget],
    )


class AvidLutGroupsFeature(TrackFilterLogFeature):
    id = "avidlutgroups"
    title = "Color Groups from Avid LUTs"
    category = "color"
    run_label = "Assign Groups"

    def __init__(self):
        super().__init__()
        self._clips = []
        self._clips_key = None
        self._counts = {}
        self._group_names = []
        self._selected_lut = ""
        self._combo_choices = []
        self._filling_combo = False

    def state_store(self):
        return StateStore("avid_lut_groups", DEFAULTS)

    # -- layout ------------------------------------------------------------

    def form_rows(self, ui):
        return [
            ui_kit.note_block(ui, INTRO),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Avid bin (.avb):", "Weight": 0,
                              "MinimumSize": [130, 0]}),
                    ui.LineEdit({"ID": self.wid("BinPath"), "Weight": 1,
                                 "PlaceholderText": "Path to the turnover bin"}),
                    ui_kit.action_button(
                        ui, {"ID": self.wid("Browse"), "Text": "Browse...",
                             "MinimumSize": [88, 0]}),
                    ui_kit.action_button(
                        ui, {"ID": self.wid("Load"), "Text": "Load & Scan",
                             "MinimumSize": [110, 0]}),
                ],
            ),
            _row(ui, "Bin LUT column:", ui.LineEdit(
                {"ID": self.wid("LutColumn"), "Weight": 1,
                 "PlaceholderText": "Custom bin column holding the shot LUT (e.g. LUT)"})),
            _row(ui, "Use LUT from:", ui.ComboBox({"ID": self.wid("LutSource"), "Weight": 1})),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Match clips by:", "Weight": 0,
                              "MinimumSize": [130, 0]}),
                    ui.CheckBox({"ID": self.wid("MatchCameraFile"),
                                 "Text": "Camera file name", "Weight": 0}),
                    ui.CheckBox({"ID": self.wid("MatchCameraRoll"),
                                 "Text": "Camera roll", "Weight": 0}),
                    ui.CheckBox({"ID": self.wid("MatchClipName"),
                                 "Text": "Clip name", "Weight": 0}),
                    ui.HGap(0, 1.0),
                ],
            ),
        ] + self.track_filter_rows(ui) + [
            ui.Label({"ID": self.wid("Status"), "Text": "", "Weight": 0,
                      "StyleSheet": "font-weight: bold;"}),
            ui.Tree({"ID": self.wid("Tree"), "Weight": 1, "SortingEnabled": False,
                     "MinimumSize": [0, 140]}),
            ui.HGroup(
                {"Spacing": 8, "Weight": 0, "MinimumSize": [0, 30]},
                [
                    ui.Label({"Text": "Group for selected LUT:", "Weight": 0,
                              "MinimumSize": [170, 0]}),
                    ui.ComboBox({"ID": self.wid("Group"), "Weight": 1,
                                 "Enabled": False}),
                    ui_kit.action_button(
                        ui, {"ID": self.wid("RefreshGroups"), "Text": "Refresh Groups",
                             "MinimumSize": [120, 0]}),
                ],
            ),
            ui.CheckBox({"ID": self.wid("DryRun"), "Text": us.CHECK_PREVIEW_ONLY,
                         "Checked": True, "Weight": 0}),
        ]

    # -- persisted form state ----------------------------------------------

    def apply_state(self, items, state):
        source = items[self.wid("LutSource")]
        for _key, label in LUT_SOURCE_CHOICES:
            source.AddItem(label)
        index = state.get("lut_source_index", 0)
        source.CurrentIndex = index if 0 <= index < len(LUT_SOURCE_CHOICES) else 0
        items[self.wid("BinPath")].Text = state.get("bin_path", "")
        items[self.wid("LutColumn")].Text = state.get("lut_column", "LUT")
        items[self.wid("MatchCameraFile")].Checked = bool(state.get("match_camera_file", True))
        items[self.wid("MatchCameraRoll")].Checked = bool(state.get("match_camera_roll", True))
        items[self.wid("MatchClipName")].Checked = bool(state.get("match_clip_name", True))
        track_filter_ui.apply_track_filter_state(items, self, state)
        items[self.wid("DryRun")].Checked = bool(state.get("dry_run", True))

    def _settings(self, items):
        """Form values shared by Load & Scan and Assign."""
        index = items[self.wid("LutSource")].CurrentIndex
        if not (0 <= index < len(LUT_SOURCE_CHOICES)):
            index = 0
        methods = [
            method
            for method, wid in (
                (alg.MATCH_CAMERA_FILE, "MatchCameraFile"),
                (alg.MATCH_CAMERA_ROLL, "MatchCameraRoll"),
                (alg.MATCH_CLIP_NAME, "MatchClipName"),
            )
            if items[self.wid(wid)].Checked
        ]
        track_spec, _use, track_state = track_filter_ui.gather_track_filter(items, self)
        settings = {
            "bin_path": (items[self.wid("BinPath")].Text or "").strip().strip('"'),
            "lut_column": (items[self.wid("LutColumn")].Text or "").strip(),
            "lut_source": LUT_SOURCE_CHOICES[index][0],
            "methods": methods,
            "track_filter_spec": track_spec,
        }
        state = {
            "bin_path": settings["bin_path"],
            "lut_column": settings["lut_column"],
            "lut_source_index": index,
            "match_camera_file": alg.MATCH_CAMERA_FILE in methods,
            "match_camera_roll": alg.MATCH_CAMERA_ROLL in methods,
            "match_clip_name": alg.MATCH_CLIP_NAME in methods,
            **track_state,
        }
        return settings, state

    def gather(self, items):
        settings, state = self._settings(items)
        settings["dry_run"] = bool(items[self.wid("DryRun")].Checked)
        state["dry_run"] = settings["dry_run"]
        return settings, state

    # -- bin + mapping -----------------------------------------------------

    def _load_bin(self, path, lut_column):
        """Read the bin unless the same file (and column) is already loaded."""
        if not path:
            raise ValueError("Choose an Avid bin (.avb) first.")
        if not os.path.isfile(path):
            raise ValueError(f"Bin not found: {path}")
        key = (path, os.path.getmtime(path), lut_column)
        if key != self._clips_key:
            self._clips = alg.read_avid_bin(path, lut_column)
            self._clips_key = key
        return self._clips

    def _saved_mapping(self, project):
        by_project = self.state_store().load().get("by_project")
        if not isinstance(by_project, dict):
            return {}
        saved = by_project.get(_project_key(project))
        return dict(saved) if isinstance(saved, dict) else {}

    def _save_choice(self, project, lut, value):
        key = _project_key(project)
        if not key:
            return
        store = self.state_store()
        by_project = store.load().get("by_project")
        by_project = dict(by_project) if isinstance(by_project, dict) else {}
        saved = dict(by_project.get(key) or {})
        saved[lut] = value
        by_project[key] = saved
        store.save({"by_project": by_project})

    def _effective_mapping(self, project, luts):
        """Saved choices, with unmapped LUTs falling back to a suggestion.

        Returns ``(mapping, suggested_luts)``.
        """
        saved = self._saved_mapping(project)
        mapping, suggested = {}, set()
        for lut in luts:
            if lut in saved:
                mapping[lut] = saved[lut]
            else:
                guess = alg.suggest_group(lut, self._group_names)
                mapping[lut] = guess
                if guess:
                    suggested.add(lut)
        return mapping, suggested

    def _group_label(self, value, lut, suggested):
        if value == alg.NEW_GROUP:
            name = alg.lut_stem(lut)
            if name in self._group_names:
                return name
            return f"(new) {name}"
        if not value:
            return "—"
        if value not in self._group_names:
            return f"{value} (missing)"
        return f"{value} (suggested)" if suggested else value

    # -- behaviour ---------------------------------------------------------

    def bind(self, ctx):
        super().bind(ctx)
        items = ctx.items
        win = ctx.win
        tree = items[self.wid("Tree")]
        status = items[self.wid("Status")]
        group_combo = items[self.wid("Group")]
        log_ctl = ui_kit.LogController(ctx.dispatcher, items[self.wid("Log")])
        ui_kit.setup_tree(tree, COLUMNS, COLUMN_WIDTHS)

        def set_status(text):
            try:
                status.Text = text
            except Exception:
                pass

        def current_luts(settings):
            return alg.bin_luts(self._clips, settings["lut_source"]) if self._clips else []

        def refresh_groups(project):
            self._group_names = sorted(alg.color_groups(project), key=str.casefold) \
                if project is not None else []

        def fill_combo(project, lut):
            """Point the group dropdown at the selected LUT's current choice."""
            self._filling_combo = True
            try:
                group_combo.Clear()
                if not lut or project is None:
                    group_combo.Enabled = False
                    return
                choices = [NO_GROUP] + self._group_names
                new_name = alg.lut_stem(lut)
                if new_name not in self._group_names:
                    choices.append(NEW_GROUP_PREFIX + new_name)
                self._combo_choices = choices
                for choice in choices:
                    group_combo.AddItem(choice)
                mapping, _suggested = self._effective_mapping(project, [lut])
                value = mapping.get(lut, "")
                if value == alg.NEW_GROUP:
                    index = (choices.index(new_name) if new_name in self._group_names
                             else len(choices) - 1)
                elif value in self._group_names:
                    index = choices.index(value)
                else:
                    index = 0
                group_combo.CurrentIndex = index
                group_combo.Enabled = True
            except Exception:
                pass
            finally:
                self._filling_combo = False

        def render(project, settings):
            luts = current_luts(settings)
            mapping, suggested = self._effective_mapping(project, luts) \
                if project is not None else ({}, set())
            ui_kit.clear_tree(tree)
            for lut in luts:
                count = self._counts.get(lut)
                item = ui_kit.add_row(tree, [
                    lut,
                    "" if count is None else str(count),
                    self._group_label(mapping.get(lut, ""), lut, lut in suggested),
                ])
                try:
                    item.Text[LUT_COLUMN] = lut
                    if lut == self._selected_lut:
                        item.Selected = True
                except Exception:
                    pass
            if self._selected_lut not in luts:
                self._selected_lut = ""
            fill_combo(project, self._selected_lut)

        def read_settings():
            try:
                return self._settings(items)
            except Exception as exc:
                set_status(f"Check your settings: {exc}")
                return None, None

        def load_and_scan():
            if self._run.running:
                return
            settings, state = read_settings()
            if settings is None:
                return
            self.state_store().save(state)
            project = ctx.conn.get_project()
            refresh_groups(project)
            try:
                clips = self._load_bin(settings["bin_path"], settings["lut_column"])
            except Exception as exc:
                self._counts = {}
                render(project, settings)
                return set_status(f"Could not read the bin: {exc}")
            set_status(f"Read {len(clips)} clips from the bin. Scanning the timeline...")
            ui_kit.pump(ctx.dispatcher)

            timeline = ctx.conn.get_timeline()
            self._counts = {}
            if timeline is None:
                render(project, settings)
                return set_status(f"Read {len(clips)} clips from the bin. "
                                  "Open a timeline to count matching clips.")
            records, err = alg.scan_timeline(
                timeline, alg.BinIndex(clips), settings["methods"],
                settings["lut_source"], settings["track_filter_spec"],
                log_ctl.log, log_ctl.pump,
            )
            if err:
                render(project, settings)
                return set_status(err)
            self._counts = alg.lut_counts(records)
            matched = sum(self._counts.values())
            grouped = sum(1 for r in records if r["group"])
            render(project, settings)
            set_status(
                f"{len(records)} timeline clips: {matched} matched to a LUT, "
                f"{grouped} already in a group. Click a LUT to choose its group."
            )

        def refresh_view():
            settings, _state = read_settings()
            if settings is None:
                return
            project = ctx.conn.get_project()
            refresh_groups(project)
            render(project, settings)

        def on_browse():
            start = (items[self.wid("BinPath")].Text or "").strip()
            start = os.path.dirname(start) if start else os.path.expanduser("~")
            try:
                picked = ctx.conn.fusion.RequestFile(start)
            except Exception as exc:
                return set_status(f"File dialog unavailable ({exc}); paste the path instead.")
            if picked:
                items[self.wid("BinPath")].Text = str(picked)
                load_and_scan()

        def on_tree_click(ev):
            item = ui_kit.get_event_item(ev)
            lut = ""
            if item is not None:
                try:
                    lut = item.Text[LUT_COLUMN] or item.Text[0] or ""
                except Exception:
                    lut = ""
            self._selected_lut = lut
            fill_combo(ctx.conn.get_project(), lut)

        def on_group_choice():
            if self._filling_combo or not self._selected_lut:
                return
            project = ctx.conn.get_project()
            if project is None:
                return
            try:
                index = int(group_combo.CurrentIndex)
            except Exception:
                return
            if not (0 <= index < len(self._combo_choices)):
                return
            value = choice_value(self._combo_choices[index])
            lut = self._selected_lut
            current, _suggested = self._effective_mapping(project, [lut])
            # fill_combo's Clear/AddItem/CurrentIndex queue CurrentIndexChanged
            # events that UIManager delivers after it returns (so the
            # _filling_combo guard is already off). They land here with the
            # choice the LUT already has; saving and re-rendering on them
            # rebuilds the dropdown, which queues more events: an endless
            # flicker. Only a real change may save.
            if same_choice(lut, current.get(lut, ""), value):
                return
            self._save_choice(project, lut, value)
            refresh_view()

        def on_lut_source_change():
            if self._clips:
                load_and_scan()

        self._refresh_view = refresh_view
        win.On[self.wid("Load")].Clicked = lambda ev: load_and_scan()
        win.On[self.wid("Browse")].Clicked = lambda ev: on_browse()
        win.On[self.wid("RefreshGroups")].Clicked = lambda ev: refresh_view()
        win.On[self.wid("Tree")].ItemClicked = on_tree_click
        win.On[self.wid("Group")].CurrentIndexChanged = lambda ev: on_group_choice()
        win.On[self.wid("LutSource")].CurrentIndexChanged = lambda ev: on_lut_source_change()

    def on_show(self, ctx):
        super().on_show(ctx)
        refresh = getattr(self, "_refresh_view", None)
        if refresh is not None:
            refresh()

    # -- run ---------------------------------------------------------------

    def run(self, ctx, params, log, pump, should_cancel):
        project = ctx.conn.get_project()
        try:
            clips = self._load_bin(params["bin_path"], params["lut_column"])
        except Exception as exc:
            log(f"Could not read the bin: {exc}")
            return None
        log(f"Avid bin: {params['bin_path']} ({len(clips)} clips)")
        self._group_names = sorted(alg.color_groups(project), key=str.casefold) \
            if project is not None else []
        luts = alg.bin_luts(clips, params["lut_source"])
        mapping, _suggested = self._effective_mapping(project, luts) \
            if project is not None else ({}, set())
        log("  LUT -> color group:")
        for lut in luts:
            name, create = alg.mapping_target(mapping, lut)
            label = f"{name} (new, empty)" if create and name not in self._group_names \
                else (name or "— not assigned")
            log(f"    {lut} -> {label}")
        result = alg.assign_color_groups(
            ctx.conn, clips, mapping, params["methods"], params["lut_source"],
            params["track_filter_spec"], params["dry_run"], log, pump, should_cancel,
        )
        refresh = getattr(self, "_refresh_view", None)
        if refresh is not None and not params["dry_run"]:
            refresh()
        return result
