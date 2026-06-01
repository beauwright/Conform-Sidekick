"""Conform Sidekick application window.

Builds a single window with a row of "tab" buttons and a stacked content area
holding every feature's panel. Switching tabs hides all panels except the
selected one. This keeps the "one tool, switch modes" experience users liked in
the Tauri app while running natively inside Resolve.

Tab switching relies on toggling each panel's ``Hidden`` attribute. That works
on current Resolve builds; if a future build changes the behaviour, the toggle
is isolated to :func:`_make_show_panel` and can be swapped for a rebuild.
"""

from . import resolve_conn
from . import ui_kit
from .resolve_api import ResolveAPI
from .features import build_features
from .features.base import AppContext

WINDOW_ID = "ConformSidekickWin"

# Padding (in px) applied on all four sides to inset all content uniformly.
EDGE_PAD = 28


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
    nav_row = [ui.HGap(0, 0.0)]
    for feature in features:
        nav_row.append(
            ui.Button(
                {
                    "ID": f"nav.{feature.id}",
                    "Text": feature.title,
                    "Weight": 0,
                    # Min width 0 lets the button size to its label so the text
                    # isn't clipped. Height is reserved by the row's MinimumSize
                    # (below) so the buttons sit fully inside it.
                    "MinimumSize": [0, 30],
                }
            )
        )
    nav_row.append(ui.HGap(0, 1.0))

    panels = []
    for feature in features:
        # Build every panel hidden. The active one is revealed after Show() with
        # an explicit hidden->visible transition, which is what forces UIManager
        # to actually lay the panel out (revealing an already-"visible" panel is
        # a no-op and leaves it blank until the window is resized).
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

    return dispatcher.AddWindow(
        {
            "ID": WINDOW_ID,
            "WindowTitle": "Conform Sidekick",
            "Geometry": [120, 80, 1180, 820],
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
                        # The nav row needs an explicit MinimumSize height. Without
                        # it the HGroup keeps its default height and the buttons
                        # (drawn taller via their own MinimumSize) overflow downward
                        # and get clipped by the content below. Sizing the row
                        # reserves the space so the content area shifts down.
                        ui.HGroup(
                            {"Spacing": 6, "Weight": 0, "MinimumSize": [0, 44]},
                            nav_row,
                        ),
                        ui.VGroup({"Spacing": 0, "Weight": 1}, panels),
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
        # UIManager doesn't relayout on a Hidden flip by itself; force it so the
        # newly-shown panel fills the content area immediately.
        ui_kit.recalc_layout(ctx.win)
        ui_kit.pump(ctx.dispatcher)
        try:
            active.on_show(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: on_show failed for {active.id}: {exc}")

    return show_panel


def main(injected_globals=None):
    conn = resolve_conn.connect(injected_globals=injected_globals)
    api = ResolveAPI(conn)
    features = build_features()

    ctx = AppContext(conn, api)

    win = _build_window(conn.ui, conn.dispatcher, features)
    ctx.win = win
    ctx.items = win.GetItems()

    for feature in features:
        try:
            feature.bind(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: bind failed for {feature.id}: {exc}")

    show_panel = _make_show_panel(ctx, features)

    def make_nav_handler(feature):
        def handler(ev):
            show_panel(feature)
        return handler

    for feature in features:
        win.On[f"nav.{feature.id}"].Clicked = make_nav_handler(feature)

    def on_close(ev):
        conn.dispatcher.ExitLoop()

    win.On[WINDOW_ID].Close = on_close

    win.Show()

    # Reveal the initial tab AFTER Show(). We force a clean hidden->visible
    # transition on the active panel because that transition is what triggers
    # the layout pass; without it the default panel renders blank. A single
    # pump flushes the layout. We deliberately do NOT run heavy work (e.g. a
    # scan) before RunLoop() - that's what previously wedged the dispatcher.
    if features:
        first = features[0]
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
        ui_kit.recalc_layout(win)
        ui_kit.pump(conn.dispatcher)
        try:
            first.on_show(ctx)
        except Exception as exc:
            print(f"Conform Sidekick: on_show failed for {first.id}: {exc}")

    conn.dispatcher.RunLoop()
    win.Hide()
