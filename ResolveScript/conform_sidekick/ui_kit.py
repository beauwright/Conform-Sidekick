"""Reusable Fusion UIManager helpers.

Lifted and generalised from the three davinci-resolve-scripts: a live-updating
log panel, an event ``pump`` so long runs repaint, run/cancel button-state
management, and a small set of helpers for the ``Tree`` widget (the closest
native equivalent to Conform Sidekick's web data tables).

None of this depends on a specific feature; features compose these helpers
around their own widgets.
"""

import subprocess
import sys

# Compact action buttons (Resolve's UIManager defaults are tall and wide).
BTN_HEIGHT = 26
BTN_ROW_HEIGHT = 32
BTN_STYLE = "font-size: 12px;"


def button_row_props():
    """HGroup props for a row that contains action buttons."""
    return {"Spacing": 8, "Weight": 0, "MinimumSize": [0, BTN_ROW_HEIGHT]}


def action_button(ui, props):
    """Build a ``Button`` with shared compact height and font size."""
    spec = dict(props)
    spec.setdefault("Weight", 0)
    style = spec.get("StyleSheet") or ""
    if BTN_STYLE not in style:
        spec["StyleSheet"] = (BTN_STYLE + style).strip()
    min_size = list(spec.get("MinimumSize") or [0, BTN_HEIGHT])
    if len(min_size) == 1:
        min_size = [min_size[0], BTN_HEIGHT]
    else:
        min_size[1] = BTN_HEIGHT
    spec["MinimumSize"] = min_size
    max_size = spec.get("MaximumSize")
    if max_size is None:
        # Cap height only so labels like "Scanning..." can grow wider at runtime.
        spec["MaximumSize"] = [16777215, BTN_HEIGHT]
    else:
        max_size = list(max_size)
        if len(max_size) >= 2:
            max_size[1] = BTN_HEIGHT
            spec["MaximumSize"] = max_size
    return ui.Button(spec)


def get_event_item(ev):
    """Return the Tree item from a UIManager item event, tolerating shapes.

    Different events (ItemClicked, CurrentItemChanged, ...) and Resolve builds
    expose the item under different keys, so try the common ones.
    """
    for key in ("item", "current", "currentItem"):
        try:
            value = ev[key]
            if value is not None:
                return value
        except Exception:
            pass
    for attr in ("item", "current", "currentItem"):
        value = getattr(ev, attr, None)
        if value is not None:
            return value
    return None


def copy_to_clipboard(text):
    """Best-effort copy ``text`` to the OS clipboard. Returns True on success.

    UIManager exposes no clipboard API, so shell out to the platform tool
    (pbcopy / clip / xclip). On Windows we suppress the console window flash.
    """
    text = "" if text is None else str(text)
    try:
        if sys.platform == "darwin":
            args, data = ["pbcopy"], text.encode("utf-8")
            kwargs = {}
        elif sys.platform.startswith("win"):
            args, data = ["clip"], text.encode("utf-16-le")
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs = {
                "startupinfo": startupinfo,
                "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            }
        else:
            args, data = ["xclip", "-selection", "clipboard"], text.encode("utf-8")
            kwargs = {}
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, **kwargs)
        proc.communicate(data)
        return proc.returncode == 0
    except Exception:
        return False


def pump(dispatcher):
    """Process pending UI events so the window repaints during/after work."""
    for method_name in ("StepLoop", "ProcessEvents", "Execute"):
        method = getattr(dispatcher, method_name, None)
        if callable(method):
            try:
                method()
                return
            except Exception:
                continue


def recalc_layout(win):
    """Best-effort: force the window to re-run its layout.

    UIManager does not reliably relayout when a child's ``Hidden`` flag flips,
    which leaves stacked panels drawn on top of one another until the user
    resizes the window. Calling this after toggling visibility avoids that.
    """
    for method_name in ("RecalcLayout", "Recalc", "UpdateGeometry"):
        method = getattr(win, method_name, None)
        if callable(method):
            try:
                method()
                return True
            except Exception:
                continue
    return False


class LogController:
    """Owns a read-only TextEdit and exposes ``log`` / ``pump`` callbacks.

    These are exactly the callbacks the ported core operations expect, so the
    UI-agnostic logic can stream progress into the panel and stay responsive.
    """

    def __init__(self, dispatcher, log_widget):
        self.dispatcher = dispatcher
        self.widget = log_widget

    def reset(self):
        for attr in ("PlainText", "Text"):
            try:
                setattr(self.widget, attr, "")
                return
            except Exception:
                continue

    def _scroll_to_end(self):
        try:
            sb_accessor = getattr(self.widget, "VerticalScrollBar", None)
            sb = sb_accessor() if callable(sb_accessor) else sb_accessor
            if sb is not None:
                sb.Value = sb.Maximum
                return
        except Exception:
            pass
        for method_name in ("MoveCursor", "ScrollToBottom"):
            method = getattr(self.widget, method_name, None)
            if callable(method):
                try:
                    method("End") if method_name == "MoveCursor" else method()
                    return
                except Exception:
                    continue

    def log(self, line):
        """Append one line to the panel and mirror to the Fusion console."""
        text = str(line)
        print(text)
        appended = False
        for method_name in ("AppendPlainText", "Append"):
            method = getattr(self.widget, method_name, None)
            if callable(method):
                try:
                    method(text)
                    appended = True
                    break
                except Exception:
                    continue
        if not appended:
            try:
                current = self.widget.PlainText or ""
                self.widget.PlainText = (current + text + "\n") if current else (text + "\n")
            except Exception:
                pass
        self._scroll_to_end()

    def pump(self):
        """Process pending UI events so the panel repaints during long runs."""
        for method_name in ("StepLoop", "ProcessEvents", "Execute"):
            method = getattr(self.dispatcher, method_name, None)
            if callable(method):
                try:
                    method()
                    return
                except Exception:
                    continue


class RunState:
    """Track whether a feature is mid-run and coordinate cooperative cancel."""

    def __init__(self):
        self.running = False
        self.cancel_requested = False

    def begin(self):
        self.running = True
        self.cancel_requested = False

    def end(self):
        self.running = False
        self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True

    def should_cancel(self) -> bool:
        return self.cancel_requested


# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------

def setup_tree(tree, headers, column_widths=None):
    """Configure a Tree's columns and header row."""
    try:
        tree.ColumnCount = len(headers)
    except Exception:
        pass
    try:
        header = tree.NewItem()
        for i, text in enumerate(headers):
            header.Text[i] = str(text)
        tree.SetHeaderItem(header)
    except Exception:
        pass
    if column_widths:
        for i, width in enumerate(column_widths):
            if width is None:
                continue
            try:
                tree.SetColumnWidth(i, int(width))
            except Exception:
                pass


def clear_tree(tree):
    try:
        tree.Clear()
    except Exception:
        pass


def add_row(tree, values):
    """Append a top-level row of string values; returns the created item."""
    item = tree.NewItem()
    for i, value in enumerate(values):
        item.Text[i] = "" if value is None else str(value)
    try:
        tree.AddTopLevelItem(item)
    except Exception:
        pass
    return item


# ---------------------------------------------------------------------------
# Navigation sidebar tree (category -> mode hierarchy)
# ---------------------------------------------------------------------------

NAV_CATEGORY_PREFIX = "@"


def setup_nav_tree(tree, sidebar_width=440):
    """Single column for labels; row keys live in ``nav_tree_key_by_label``."""
    try:
        tree.ColumnCount = 1
    except Exception:
        pass
    try:
        header = tree.NewItem()
        header.Text[0] = "Tools"
        tree.SetHeaderItem(header)
    except Exception:
        pass
    set_nav_tree_column_width(tree, sidebar_width)
    try:
        tree.SortingEnabled = False
    except Exception:
        pass


def set_nav_tree_column_width(tree, sidebar_width):
    """Set the label column wide enough that mode titles are not ellipsized."""
    width = int(sidebar_width)
    label_w = max(320, width - 24)
    for _ in range(2):
        try:
            tree.SetColumnWidth(0, label_w)
        except Exception:
            pass


def _tree_item_text(item, index, default=""):
    if item is None:
        return default
    try:
        return item.Text[index] or default
    except Exception:
        return default


def _nav_register_label(key_by_label, text, key):
    """Map visible tree text to a feature id or ``@category`` key."""
    if key_by_label is None or not text or not key:
        return
    key_by_label[text] = key
    stripped = text.strip()
    if stripped and stripped != text:
        key_by_label[stripped] = key


def get_tree_current_item(tree):
    """Return the tree's current row (event payloads often omit the item)."""
    if tree is None:
        return None
    for name in ("CurrentItem", "GetCurrentItem"):
        method = getattr(tree, name, None)
        if callable(method):
            try:
                item = method()
                if item is not None:
                    return item
            except Exception:
                continue
    return None


def populate_nav_tree(tree, grouped, sidebar_width=440, key_by_label=None):
    """Fill the sidebar: Conform / Edit / Color parents with mode children.

    ``grouped`` is the list from :func:`features.features_by_category`. Row keys
    (feature id or ``@<category_id>``) are stored in ``key_by_label`` by the
    visible ``Text[0]`` string — UIManager click events use different item
    objects than those created at populate time, so ``id(item)`` lookup fails.
    """
    clear_tree(tree)
    if key_by_label is not None:
        key_by_label.clear()
    for cat_id, label, cat_features in grouped:
        parent = tree.NewItem()
        parent.Text[0] = label
        _nav_register_label(key_by_label, label, NAV_CATEGORY_PREFIX + cat_id)

        parent_added = False
        try:
            tree.AddTopLevelItem(parent)
            parent_added = True
        except Exception:
            pass

        for feature in cat_features:
            child = tree.NewItem()
            child.Text[0] = feature.title
            _nav_register_label(key_by_label, feature.title, feature.id)

            if parent_added:
                attached = False
                for method_name in ("AddChild", "InsertChild", "AddItem"):
                    method = getattr(parent, method_name, None)
                    if callable(method):
                        try:
                            method(child)
                            attached = True
                            break
                        except Exception:
                            continue
                if not attached:
                    flat = "    " + feature.title
                    child.Text[0] = flat
                    _nav_register_label(key_by_label, flat, feature.id)
                    try:
                        tree.AddTopLevelItem(child)
                    except Exception:
                        pass
            else:
                flat = label + " — " + feature.title
                child.Text[0] = flat
                _nav_register_label(key_by_label, flat, feature.id)
                try:
                    tree.AddTopLevelItem(child)
                except Exception:
                    pass

        if parent_added:
            for expand_name in ("SetExpanded", "Expand"):
                method = getattr(parent, expand_name, None)
                if callable(method):
                    try:
                        if expand_name == "SetExpanded":
                            method(True)
                        else:
                            method()
                        break
                    except Exception:
                        continue

    set_nav_tree_column_width(tree, sidebar_width)


def nav_tree_key(item, key_by_label=None):
    """Return the key for a nav row (feature id or @category)."""
    if item is None:
        return ""
    text = _tree_item_text(item, 0, "")
    if not text:
        return ""
    if key_by_label is None:
        return ""
    key = key_by_label.get(text)
    if key:
        return key
    stripped = text.strip()
    key = key_by_label.get(stripped)
    if key:
        return key
    if " — " in stripped:
        suffix = stripped.split(" — ", 1)[-1].strip()
        key = key_by_label.get(suffix)
        if key:
            return key
    return ""


def _walk_tree_items(tree):
    """Yield top-level nav rows and their children."""
    try:
        top_count = int(tree.TopLevelItemCount())
    except Exception:
        return
    for index in range(top_count):
        top = None
        for method_name in ("TopLevelItem", "GetTopLevelItem"):
            method = getattr(tree, method_name, None)
            if callable(method):
                try:
                    top = method(index)
                    break
                except Exception:
                    continue
        if top is None:
            continue
        yield top
        child_count = None
        for method_name in ("ChildCount", "GetChildCount"):
            method = getattr(top, method_name, None)
            if callable(method):
                try:
                    child_count = int(method())
                    break
                except Exception:
                    continue
        if child_count is None:
            continue
        for child_index in range(child_count):
            child = None
            for method_name in ("Child", "GetChild"):
                method = getattr(top, method_name, None)
                if callable(method):
                    try:
                        child = method(child_index)
                        break
                    except Exception:
                        continue
            if child is not None:
                yield child


def select_nav_tree_for_feature(tree, feature_id, key_by_label=None):
    """Highlight the sidebar row for ``feature_id``. Returns True if found."""
    if tree is None or not feature_id:
        return False
    for item in _walk_tree_items(tree):
        if nav_tree_key(item, key_by_label) != feature_id:
            continue
        for target, method_name in (
            (tree, "SetCurrentItem"),
            (item, "SetSelected"),
            (tree, "SetSelected"),
        ):
            method = getattr(target, method_name, None)
            if not callable(method):
                continue
            try:
                if method_name == "SetSelected":
                    method(True)
                else:
                    method(item)
                return True
            except Exception:
                try:
                    if method_name == "SetSelected":
                        method(0, True)
                    else:
                        method(item)
                    return True
                except Exception:
                    continue
    return False
