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
