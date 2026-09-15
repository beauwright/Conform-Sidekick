"""Conform Sidekick application window.

Split layout: a left sidebar ``Tree`` lists categories (Conform / Edit / Color)
and their modes; the main area shows the active feature panel. Switching modes
hides all panels except the selected one.

Event loop
----------
The window is driven by one manual loop (:func:`event_loop`). Every tick
"kicks" the dispatcher - sets the text of a hidden widget in a never-shown
helper window and calls ``RunLoop()``, which drains every pending UI event and
returns as soon as the kick's own ``TextChanged`` handler calls ``ExitLoop()`` -
then serves the remote-control listener, and every couple of seconds checks
that Resolve is still there. Findings behind that (probed against Resolve
Studio 21; see ``tests/live_ui_events.py``):

- ``StepLoop()`` is non-blocking but delivers one queued message per call, and
  the full window generates a couple of hundred internal messages per fresh
  event. Polling it alone left clicks undelivered for seconds: the
  2.0.0-beta.9/10 "panel is dead while the Stream Deck works" bug. It is still
  what :func:`ui_kit.pump` uses *inside* a handler, where it delivers promptly.
- ``ExitLoop()`` is sticky: called before a ``RunLoop`` has run, it silences
  later ``StepLoop()`` calls too. A ``RunLoop`` with a kick queued always
  returns, stale flag or not. Nested ``RunLoop`` calls from inside a handler
  hang, so only the tick ever calls it.
- The UIManager window lives in Resolve's process. When Resolve crashes, this
  ``fuscript`` process survives with a dead connection and dead widget proxies
  (every ``.Text`` read returns None) but a live HTTP listener. The liveness
  check exits the loop so no such zombie is left holding the remote port or
  overwriting saved settings.
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


KICK_WINDOW_ID = "ConformSidekickKickWin"
KICK_EDIT_ID = "ConformSidekickKick"

# Seconds between loop ticks (one kick + RunLoop drain + one remote poll each);
# ~33 Hz costs about 1.5 % CPU idle, and a click waits at most one tick.
TICK_INTERVAL = 0.03
# Seconds between "is Resolve still there?" checks.
LIVENESS_INTERVAL = 2.0
# Consecutive failed liveness checks before the window gives up and exits.
LIVENESS_FAILURES_TO_EXIT = 2


def resolve_alive(conn):
    """True when the Resolve connection still answers.

    A crashed / quit Resolve leaves the scripting proxies in place but every
    call returns None (verified on a post-crash zombie), so a falsy version
    string is the signal.
    """
    try:
        return bool(conn.resolve.GetVersionString())
    except Exception:
        return False


def event_loop(step, poll, alive, closed, sleep=time.sleep, now=time.monotonic):
    """Drive the window until ``closed()`` is true or Resolve goes away.

    ``step`` drains pending UI events (returning False when the connection
    failed), ``poll`` serves pending remote requests, ``alive`` reports whether
    Resolve still answers. Returns ``"closed"`` or ``"resolve_gone"``. Pure
    apart from the injected callables so the offline tests can drive it.
    """
    next_check = now() + LIVENESS_INTERVAL
    failures = 0
    while not closed():
        if step() is False:
            print("Conform Sidekick: lost the Resolve connection - closing.")
            return "resolve_gone"
        poll()
        if now() >= next_check:
            next_check = now() + LIVENESS_INTERVAL
            if alive():
                failures = 0
            else:
                failures += 1
                if failures >= LIVENESS_FAILURES_TO_EXIT:
                    print("Conform Sidekick: Resolve is no longer reachable - closing.")
                    return "resolve_gone"
        sleep(TICK_INTERVAL)
    return "closed"


class App:
    """The built window plus everything the loop needs (see :func:`build`)."""

    def __init__(self, conn, ctx, win, remote, features, kick_win, kick_edit):
        self.conn = conn
        self.ctx = ctx
        self.win = win
        self.remote = remote
        self.features = features
        self.kick_win = kick_win
        self.kick_edit = kick_edit
        self.closed = False
        self._kicks = 0

    def step(self):
        """Drain every pending UI event. False when the connection is gone."""
        self._kicks += 1
        try:
            # A changed value is required: Qt emits TextChanged only on change.
            self.kick_edit.Text = str(self._kicks)
        except Exception as exc:
            print(f"Conform Sidekick: kick failed: {exc}")
            return False
        self.conn.dispatcher.RunLoop()
        return True

    def poll(self):
        if self.remote.listening:
            self.remote.poll()

    def alive(self):
        return resolve_alive(self.conn)

    def run(self):
        """Block until the window closes or Resolve disappears, then clean up."""
        try:
            return event_loop(self.step, self.poll, self.alive, lambda: self.closed)
        finally:
            self.shutdown()

    def shutdown(self):
        self.remote.stop()
        for window in (self.win, self.kick_win):
            try:
                window.Hide()
            except Exception:
                pass


def _build_kick_window(ui, dispatcher):
    """Never-shown helper window whose hidden LineEdit drives the tick.

    Returns ``(window, line_edit)``. The handler is bound here so ``RunLoop``
    can never be entered without a way out.
    """
    win = dispatcher.AddWindow(
        {"ID": KICK_WINDOW_ID, "WindowTitle": "Conform Sidekick", "Geometry": [0, 0, 10, 10]},
        [ui.VGroup({}, [ui.LineEdit({"ID": KICK_EDIT_ID, "Hidden": True})])],
    )
    win.On[KICK_EDIT_ID].TextChanged = lambda ev: dispatcher.ExitLoop()
    return win, win.GetItems()[KICK_EDIT_ID]


def build(injected_globals=None):
    """Connect, build and show the window. Returns an :class:`App` (not running)."""
    conn = resolve_conn.connect(injected_globals=injected_globals)
    api = ResolveAPI(conn)
    features = build_features()
    grouped = features_by_category(features)
    features_by_id = {f.id: f for f in features}

    ctx = AppContext(conn, api)
    remote = remote_mod.RemoteServer()
    ctx.remote = remote

    win = _build_window(conn.ui, conn.dispatcher, features)
    ctx.win = win
    ctx.items = win.GetItems()
    kick_win, kick_edit = _build_kick_window(conn.ui, conn.dispatcher)

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

    app = App(conn, ctx, win, remote, features, kick_win, kick_edit)

    def on_close(ev):
        app.closed = True

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
    return app


def main(injected_globals=None):
    return build(injected_globals=injected_globals).run()
