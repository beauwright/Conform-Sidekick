"""Conform Sidekick application window.

Split layout: a left sidebar ``Tree`` lists categories (Conform / Edit / Color)
and their modes; the main area shows the active feature panel. Switching modes
hides all panels except the selected one.
"""

import time

from . import remote as remote_mod
from . import resolve_conn
from . import ui_kit
from .resolve_api import ResolveAPI
from .features import build_features, features_by_category
from .features.base import AppContext
from .state import app_state_store

WINDOW_ID = "ConformSidekickWin"
NAV_TREE_ID = "NavTree"
EMPTY_PANEL_ID = "panel.empty"

# Padding (in px) applied on all four sides to inset all content uniformly.
EDGE_PAD = 28

# Sidebar: minimum width (px) and share of the horizontal split. UIManager often
# ignores MinimumSize alone; Weight gives a reliable fraction of the body width.
SIDEBAR_WIDTH = 440
SIDEBAR_WEIGHT = 0.38


def _pad(ui, content, pad):
    """Inset ``content`` by ``pad`` px on all four sides.

    Avoids the layout ``Margin`` property, which clips in UIManager (it offsets
    content without shrinking the content rect, so the right/bottom margin pushes
    content off the visible area). Spacer widgets are measured correctly by the
    layout and never clip.
    """
    return ui.VGroup(
        {"Spacing": 0, "Margin": 0, "Weight": 1},
        [
            ui.VGap(pad, 0.0),
            ui.HGroup(
                {"Spacing": 0, "Weight": 1},
                [
                    ui.HGap(pad, 0.0),
                    content,
                    ui.HGap(pad, 0.0),
                ],
            ),
            ui.VGap(pad, 0.0),
        ],
    )


def _build_window(ui, dispatcher, features):
    panels = [
        ui.VGroup(
            {
                "ID": EMPTY_PANEL_ID,
                "Weight": 1,
                "Hidden": False,
            },
            [],
        )
    ]
    for feature in features:
        panels.append(
            ui.VGroup(
                {
                    "ID": feature.panel_id,
                    "Weight": 1,
                    "Hidden": True,
                },
                [feature.build_layout(ui)],
            )
        )

    body = ui.HGroup(
        {"Spacing": 0, "Weight": 1},
        [
            ui.VGroup(
                {
                    "Spacing": 0,
                    "Weight": SIDEBAR_WEIGHT,
                    "MinimumSize": [SIDEBAR_WIDTH, 0],
                },
                [
                    ui.Tree(
                        {
                            "ID": NAV_TREE_ID,
                            "Weight": 1,
                            "SortingEnabled": False,
                        }
                    ),
                ],
            ),
            ui.HGap(12, 0.0),
            ui.VGroup({"Spacing": 0, "Weight": 1}, panels),
        ],
    )

    return dispatcher.AddWindow(
        {
            "ID": WINDOW_ID,
            "WindowTitle": "Conform Sidekick",
            "Geometry": [120, 80, 1320, 820],
            "Spacing": 8,
        },
        [
            _pad(
                ui,
                ui.VGroup(
                    {"Spacing": 10, "Margin": 0, "Weight": 1},
                    [
                        ui.Label(
                            {
                                "Text": "Conform Sidekick",
                                "Weight": 0,
                                "StyleSheet": "font-size: 18px; font-weight: bold;",
                            }
                        ),
                        body,
                    ],
                ),
                EDGE_PAD,
            )
        ],
    )


def _make_show_panel(ctx, features):
    empty_panel = ctx.items.get(EMPTY_PANEL_ID)

    def _set_hidden(panel, hidden):
        if panel is None:
            return
        try:
            panel.Hidden = hidden
        except Exception:
            pass

    def hide_all_panels():
        for feature in features:
            _set_hidden(ctx.items.get(feature.panel_id), True)
        _set_hidden(empty_panel, False)
        ui_kit.recalc_layout(ctx.win)
        ui_kit.pump(ctx.dispatcher)

    def show_panel(active):
        if active is None:
            hide_all_panels()
            return
        _set_hidden(empty_panel, True)
        for feature in features:
            _set_hidden(
                ctx.items.get(feature.panel_id),
                feature.id != active.id,
            )
        ui_kit.recalc_layout(ctx.win)
        ui_kit.pump(ctx.dispatcher)
        try:
            active.on_show(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: on_show failed for {active.id}: {exc}")

    show_panel.hide_all = hide_all_panels
    return show_panel


def _initial_feature(features_by_id, app_store):
    saved = app_store.load()
    last_id = (saved.get("last_feature_id") or "").strip()
    if not last_id:
        return None
    return features_by_id.get(last_id)


def _make_nav_controller(ctx, grouped, features_by_id, show_panel, app_store, nav_state):
    """Sidebar tree: mode rows switch panels; category rows pick last-used mode."""

    state = {
        "active": None,
        "last_in_category": {},
    }

    def select_feature(feature):
        state["active"] = feature
        state["last_in_category"][feature.category] = feature
        app_store.save({"last_feature_id": feature.id})
        show_panel(feature)

    def select_category(cat_id):
        last = state["last_in_category"].get(cat_id)
        cat_features = None
        for cid, _label, feats in grouped:
            if cid == cat_id:
                cat_features = feats
                break
        if not cat_features:
            return
        if last is None or last not in cat_features:
            last = cat_features[0]
        select_feature(last)

    def nav_event_key(ev):
        tree = ctx.items.get(NAV_TREE_ID)
        item = ui_kit.get_event_item(ev)
        if item is None and tree is not None:
            item = ui_kit.get_tree_current_item(tree)
        return ui_kit.nav_tree_key(item, ctx.nav_tree_key_by_label)

    def on_nav_item_clicked(ev):
        if nav_state.get("bootstrapping"):
            return
        key = nav_event_key(ev)
        if not key:
            return
        if key.startswith(ui_kit.NAV_CATEGORY_PREFIX):
            select_category(key[len(ui_kit.NAV_CATEGORY_PREFIX) :])
            return
        feature = features_by_id.get(key)
        if feature is not None:
            select_feature(feature)

    return select_feature, on_nav_item_clicked


def _poll_until(conn, remote, stop):
    """Manual event loop: StepLoop + remote poll until ``stop()`` is true."""
    while not stop():
        ui_kit.pump(conn.dispatcher)
        remote.poll()
        time.sleep(remote_mod.POLL_INTERVAL)


def _event_loop(conn, remote, closed):
    """Run the window's event loop until the window closes.

    ``RunLoop`` is the proven path and stays the default. It blocks natively,
    so nothing else can run while the window idles; when the remote listener
    is on we need to poll it, and ``StepLoop`` (non-blocking, sub-millisecond
    when idle - see ``remote``) is used instead. Starting the remote calls
    ``ExitLoop`` (via ``remote.on_started``) so this loop can switch modes.
    """
    while not closed():
        if remote.listening:
            _poll_until(conn, remote, lambda: closed() or not remote.listening)
            continue
        started = time.monotonic()
        conn.dispatcher.RunLoop()
        if closed() or remote.listening:
            continue
        if time.monotonic() - started < 0.05:
            # RunLoop bounced straight out (a stale ExitLoop from a start /
            # stop before the loop began). Polling handles every case.
            _poll_until(conn, remote, closed)


def main(injected_globals=None):
    conn = resolve_conn.connect(injected_globals=injected_globals)
    api = ResolveAPI(conn)
    features = build_features()
    grouped = features_by_category(features)
    features_by_id = {f.id: f for f in features}

    ctx = AppContext(conn, api)
    remote = remote_mod.RemoteServer()
    remote.on_started = lambda: conn.dispatcher.ExitLoop()
    ctx.remote = remote

    win = _build_window(conn.ui, conn.dispatcher, features)
    ctx.win = win
    ctx.items = win.GetItems()

    nav_tree = ctx.items[NAV_TREE_ID]
    ui_kit.setup_nav_tree(nav_tree, SIDEBAR_WIDTH)
    ui_kit.populate_nav_tree(
        nav_tree, grouped, SIDEBAR_WIDTH, ctx.nav_tree_key_by_label
    )

    app_store = app_state_store()
    nav_state = {"bootstrapping": True}
    show_panel = _make_show_panel(ctx, features)
    select_feature, on_nav_item_clicked = _make_nav_controller(
        ctx, grouped, features_by_id, show_panel, app_store, nav_state
    )

    def select_feature_and_nav(feature):
        select_feature(feature)
        try:
            ui_kit.select_nav_tree_for_feature(
                nav_tree, feature.id, ctx.nav_tree_key_by_label
            )
        except Exception:
            pass

    ctx.select_feature = select_feature_and_nav

    for feature in features:
        try:
            feature.bind(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: bind failed for {feature.id}: {exc}")

    closed = {"value": False}

    def on_close(ev):
        closed["value"] = True
        conn.dispatcher.ExitLoop()

    win.On[WINDOW_ID].Close = on_close

    initial = _initial_feature(features_by_id, app_store)

    win.Show()

    if initial is not None:
        select_feature(initial)
    else:
        show_panel.hide_all()
        ui_kit.clear_nav_tree_selection(nav_tree)

    ui_kit.set_nav_tree_column_width(nav_tree, SIDEBAR_WIDTH)
    ui_kit.recalc_layout(win)
    ui_kit.pump(conn.dispatcher)

    if initial is not None:
        ui_kit.select_nav_tree_for_feature(
            nav_tree, initial.id, ctx.nav_tree_key_by_label
        )
        ui_kit.pump(conn.dispatcher)

    nav_state["bootstrapping"] = False
    win.On[NAV_TREE_ID].ItemClicked = on_nav_item_clicked

    try:
        _event_loop(conn, remote, lambda: closed["value"])
    finally:
        remote.stop()
        win.Hide()
