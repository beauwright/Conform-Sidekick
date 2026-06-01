"""Conform Sidekick application window.

Split layout: a left sidebar ``Tree`` lists categories (Conform / Edit / Color)
and their modes; the main area shows the active feature panel. Switching modes
hides all panels except the selected one.
"""

from . import resolve_conn
from . import ui_kit
from .resolve_api import ResolveAPI
from .features import build_features, features_by_category
from .features.base import AppContext

WINDOW_ID = "ConformSidekickWin"
NAV_TREE_ID = "NavTree"

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
    panels = []
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
    def show_panel(active):
        for feature in features:
            panel = ctx.items.get(feature.panel_id)
            if panel is None:
                continue
            try:
                panel.Hidden = feature.id != active.id
            except Exception:
                pass
        ui_kit.recalc_layout(ctx.win)
        ui_kit.pump(ctx.dispatcher)
        try:
            active.on_show(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: on_show failed for {active.id}: {exc}")

    return show_panel


def _make_nav_controller(ctx, grouped, features_by_id, show_panel):
    """Sidebar tree: mode rows switch panels; category rows pick last-used mode."""

    state = {
        "active": None,
        "last_in_category": {},
    }

    def select_feature(feature):
        state["active"] = feature
        state["last_in_category"][feature.category] = feature
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

    def on_nav_tree(ev):
        tree = ctx.items.get(NAV_TREE_ID)
        item = ui_kit.get_event_item(ev)
        if item is None and tree is not None:
            item = ui_kit.get_tree_current_item(tree)
        key = ui_kit.nav_tree_key(item, ctx.nav_tree_key_by_label)
        if not key:
            return
        if key.startswith(ui_kit.NAV_CATEGORY_PREFIX):
            select_category(key[len(ui_kit.NAV_CATEGORY_PREFIX) :])
            return
        feature = features_by_id.get(key)
        if feature is not None:
            select_feature(feature)

    return select_feature, on_nav_tree


def main(injected_globals=None):
    conn = resolve_conn.connect(injected_globals=injected_globals)
    api = ResolveAPI(conn)
    features = build_features()
    grouped = features_by_category(features)
    features_by_id = {f.id: f for f in features}

    ctx = AppContext(conn, api)

    win = _build_window(conn.ui, conn.dispatcher, features)
    ctx.win = win
    ctx.items = win.GetItems()

    nav_tree = ctx.items[NAV_TREE_ID]
    ui_kit.setup_nav_tree(nav_tree, SIDEBAR_WIDTH)
    ui_kit.populate_nav_tree(
        nav_tree, grouped, SIDEBAR_WIDTH, ctx.nav_tree_key_by_label
    )

    for feature in features:
        try:
            feature.bind(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: bind failed for {feature.id}: {exc}")

    show_panel = _make_show_panel(ctx, features)
    select_feature, on_nav_tree = _make_nav_controller(
        ctx, grouped, features_by_id, show_panel
    )

    win.On[NAV_TREE_ID].ItemClicked = on_nav_tree
    win.On[NAV_TREE_ID].CurrentItemChanged = on_nav_tree

    def on_close(ev):
        conn.dispatcher.ExitLoop()

    win.On[WINDOW_ID].Close = on_close

    win.Show()

    if features:
        first = grouped[0][2][0] if grouped else features[0]
        for feature in features:
            panel = ctx.items.get(feature.panel_id)
            if panel is None:
                continue
            try:
                panel.Hidden = True
            except Exception:
                pass
        active_panel = ctx.items.get(first.panel_id)
        if active_panel is not None:
            try:
                active_panel.Hidden = True
                active_panel.Hidden = False
            except Exception:
                pass
        select_feature(first)
        ui_kit.set_nav_tree_column_width(nav_tree, SIDEBAR_WIDTH)
        ui_kit.recalc_layout(win)
        ui_kit.pump(conn.dispatcher)

    conn.dispatcher.RunLoop()
    win.Hide()
