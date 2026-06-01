"""Shared track-filter widgets for log features.

Resolve's UIManager has no multi-select ComboBox, so each video track gets a
small Include/Exclude dropdown plus a master checkbox to enable filtering.
"""

from __future__ import annotations

from . import timeline_filters as tf
from . import ui_strings as us

MAX_VIDEO_TRACKS = 24
_TRACK_COMBO_INCLUDE = 0
_TRACK_COMBO_EXCLUDE = 1


def track_select_wid(feature, index: int) -> str:
    return feature.wid(f"TrackSelect{index}")


def track_row_wid(feature, index: int) -> str:
    return feature.wid(f"TrackRow{index}")


def track_label_wid(feature, index: int) -> str:
    return feature.wid(f"TrackLabel{index}")


def build_track_filter_block(ui, feature, label_width=130):
    """Return UIManager widgets: enable checkbox + per-track dropdown rows."""
    track_rows = []
    for i in range(1, MAX_VIDEO_TRACKS + 1):
        track_rows.append(
            ui.HGroup(
                {
                    "Spacing": 8,
                    "Weight": 0,
                    "MinimumSize": [0, 28],
                    "ID": track_row_wid(feature, i),
                    "Hidden": True,
                },
                [
                    ui.Label(
                        {
                            "ID": track_label_wid(feature, i),
                            "Text": f"V{i}",
                            "Weight": 0,
                            "MinimumSize": [label_width, 0],
                        }
                    ),
                    ui.ComboBox(
                        {
                            "ID": track_select_wid(feature, i),
                            "Weight": 0,
                            "MinimumSize": [100, 0],
                            "MaximumSize": [120, 16777215],
                        }
                    ),
                ],
            )
        )

    return [
        ui.CheckBox(
            {
                "ID": feature.wid("UseTrackFilter"),
                "Text": us.TRACK_FILTER_ENABLE,
                "Checked": False,
                "Weight": 0,
            }
        ),
        ui.VGroup(
            {"Spacing": 4, "Weight": 0, "ID": feature.wid("TrackFilterRows")},
            track_rows,
        ),
    ]


def init_track_combos(items, feature):
    """Populate Include/Exclude items once per track dropdown."""
    for i in range(1, MAX_VIDEO_TRACKS + 1):
        combo = items[track_select_wid(feature, i)]
        combo.AddItem(us.TRACK_USE)
        combo.AddItem(us.TRACK_SKIP)
        combo.CurrentIndex = _TRACK_COMBO_INCLUDE


def refresh_track_filter_ui(ctx, feature, items):
    """Label each row from the current timeline's video tracks."""
    tracks = ctx.api.video_tracks()
    for i in range(1, MAX_VIDEO_TRACKS + 1):
        row = items.get(track_row_wid(feature, i))
        label = items.get(track_label_wid(feature, i))
        combo = items.get(track_select_wid(feature, i))
        if row is None or label is None or combo is None:
            continue
        if i <= len(tracks):
            track = tracks[i - 1]
            name = (track.get("name") or "").strip()
            label.Text = f"V{i}: {name}" if name else f"V{i}"
            row.Hidden = False
        else:
            row.Hidden = True
            combo.CurrentIndex = _TRACK_COMBO_EXCLUDE


def set_track_filter_enabled(items, feature, enabled: bool):
    """Enable or disable per-track dropdowns based on the master checkbox."""
    for i in range(1, MAX_VIDEO_TRACKS + 1):
        row = items.get(track_row_wid(feature, i))
        combo = items.get(track_select_wid(feature, i))
        if row is None or combo is None or row.Hidden:
            continue
        combo.Enabled = enabled


def apply_track_filter_state(items, feature, state: dict):
    """Restore master checkbox and per-track dropdowns from persisted state."""
    spec = (state.get("track_filter") or "").strip()
    use = state.get("use_track_filter")
    if use is None:
        use = bool(spec)
    else:
        use = bool(use)

    track_set, _err = tf.parse_int_spec(spec, what="track") if spec else (None, None)

    items[feature.wid("UseTrackFilter")].Checked = use
    for i in range(1, MAX_VIDEO_TRACKS + 1):
        row = items.get(track_row_wid(feature, i))
        combo = items[track_select_wid(feature, i)]
        if row is not None and row.Hidden:
            combo.CurrentIndex = _TRACK_COMBO_EXCLUDE
            continue
        if track_set is not None:
            combo.CurrentIndex = (
                _TRACK_COMBO_INCLUDE if i in track_set else _TRACK_COMBO_EXCLUDE
            )
        else:
            combo.CurrentIndex = _TRACK_COMBO_INCLUDE
    set_track_filter_enabled(items, feature, use)


def gather_track_filter(items, feature):
    """Return ``(track_filter_spec, use_track_filter, state_fragment)``."""
    use = bool(items[feature.wid("UseTrackFilter")].Checked)
    if not use:
        return "", False, {"use_track_filter": False, "track_filter": ""}

    selected = []
    for i in range(1, MAX_VIDEO_TRACKS + 1):
        row = items.get(track_row_wid(feature, i))
        if row is None or row.Hidden:
            continue
        combo = items[track_select_wid(feature, i)]
        if combo.CurrentIndex == _TRACK_COMBO_INCLUDE:
            selected.append(str(i))

    if not selected:
        raise ValueError(us.TRACK_FILTER_NONE_SELECTED)

    spec = ",".join(selected)
    return spec, True, {"use_track_filter": True, "track_filter": spec}


def bind_track_filter(ctx, feature, items, win):
    """Wire the master checkbox to enable/disable track dropdowns."""

    def on_toggle(_ev):
        enabled = bool(items[feature.wid("UseTrackFilter")].Checked)
        set_track_filter_enabled(items, feature, enabled)

    win.On[feature.wid("UseTrackFilter")].Clicked = on_toggle
