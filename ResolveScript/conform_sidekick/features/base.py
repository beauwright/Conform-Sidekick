"""Feature interface + shared application context.

Each feature contributes one panel to the single tabbed window. The app builds
every panel up front, stacks them in the content area, and shows exactly one at
a time (the others are hidden). Features namespace their widget IDs with their
``id`` so the flat UIManager id space stays collision-free.
"""


class AppContext:
    """Handles shared across every feature for the lifetime of the window."""

    def __init__(self, conn, api):
        self.conn = conn
        self.api = api
        self.ui = conn.ui
        self.dispatcher = conn.dispatcher
        self.win = None
        self.items = None


class Feature:
    """Base class. Subclasses set ``id``/``title`` and implement the panel."""

    id = ""
    title = ""

    def wid(self, name: str) -> str:
        """Namespace a widget id to this feature."""
        return f"{self.id}.{name}"

    @property
    def panel_id(self) -> str:
        return f"panel.{self.id}"

    def build_layout(self, ui):
        """Return the UIManager element for this feature's panel."""
        raise NotImplementedError

    def bind(self, ctx: AppContext):
        """Wire up event handlers after the window exists. Optional."""
        return None

    def on_show(self, ctx: AppContext):
        """Called each time this panel becomes the active tab. Optional."""
        return None
