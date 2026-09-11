"""Local HTTP remote control (Stream Deck, Companion, Keyboard Maestro, curl).

Resolve cannot bind a keyboard shortcut to a script, and a Stream Deck
"Hotkey" action only types into whichever app has focus - exactly the
collision with Resolve's own shortcuts we want to avoid. So instead the running
window listens on ``127.0.0.1:<port>`` and any controller that can open a file
or send an HTTP request drives it directly.

Threading is deliberately avoided. The script runs in Resolve's ``fuscript``
process, where ``UIDispatcher.RunLoop()`` holds the GIL, so a background
thread never gets scheduled while the window idles (verified by probe). The
``Timer`` UIManager element exists but its ``Timeout`` event never reaches
Python either. What *does* work is ``StepLoop()``: it returns in well under a
millisecond when idle, so while the remote is on the app swaps ``RunLoop`` for
a small ``StepLoop`` + :meth:`RemoteServer.poll` loop (see ``app``), and every
request is accepted and answered on the UI thread with a zero-timeout select.

Security model: loopback only, and every action needs a random per-install
token (header ``X-Sidekick-Token`` or ``?token=``). Without the token a web
page could fire an action through an ``<img>`` tag pointed at localhost.

The launcher files written by :func:`write_launchers` bake the port and token
in, so the user can drag them onto a Stream Deck "System: Open" action without
ever seeing either.
"""

import hashlib
import json
import os
import secrets
import select
import stat
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import TCPServer
from urllib.parse import parse_qs, urlsplit

from . import paths
from .state import StateStore

DEFAULT_PORT = 41451
PORT_MIN = 1024
PORT_MAX = 65535
# When the configured port is taken, try the next few before giving up.
PORT_SEARCH_SPAN = 10
TOKEN_HEADER = "X-Sidekick-Token"
# Seconds between StepLoop passes while the remote is on (~33 Hz).
POLL_INTERVAL = 0.03
# Requests handled per poll pass; keeps a burst from starving the UI.
MAX_REQUESTS_PER_POLL = 4
# A client that connects but never sends a request line stalls the UI thread
# for at most this long.
CLIENT_TIMEOUT = 2.0
LAUNCHER_FOLDER = "streamdeck"

DEFAULTS = {
    "enabled": False,
    "port": DEFAULT_PORT,
    "token": "",
}

# (action, launcher display name) - order is the order files are written.
LAUNCHER_ACTIONS = (
    ("bypass", "Bypass Grade"),
    ("restore", "Restore Grade"),
    ("toggle", "Toggle Grade"),
)

NOT_RUNNING_MESSAGE = (
    "Conform Sidekick is not running. Open it from Workspace > Scripts > Utility."
)


def remote_state_store():
    return StateStore("remote", DEFAULTS)


def ensure_token(store):
    """Return the persisted token, generating and saving one on first use."""
    state = store.load()
    token = (state.get("token") or "").strip()
    if not token:
        token = secrets.token_hex(16)
        store.save({"token": token})
    return token


def parse_port(text):
    """Return ``(port, error)`` for a user-typed port; blank means the default."""
    text = (text or "").strip()
    if not text:
        return DEFAULT_PORT, None
    try:
        port = int(text)
    except ValueError:
        return None, f"Port must be a number between {PORT_MIN} and {PORT_MAX}."
    if port < PORT_MIN or port > PORT_MAX:
        return None, f"Port must be between {PORT_MIN} and {PORT_MAX}."
    return port, None


def launcher_dir():
    return os.path.join(paths.get_support_home(), LAUNCHER_FOLDER)


def endpoint_url(port, action, token=None, plain=False):
    url = f"http://127.0.0.1:{int(port)}/{action}"
    query = []
    if token:
        query.append(f"token={token}")
    if plain:
        query.append("plain=1")
    if query:
        url += "?" + "&".join(query)
    return url


def reveal_folder(path):
    """Open ``path`` in Finder / Explorer / the desktop file manager."""
    try:
        os.makedirs(path, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


class _Server(HTTPServer):
    # Windows' SO_REUSEADDR lets a second listener silently share a port that
    # another program already owns; we want EADDRINUSE there instead.
    allow_reuse_address = not sys.platform.startswith("win")
    timeout = 0

    def __init__(self, address, handler, remote):
        self.remote = remote
        super().__init__(address, handler)

    def server_bind(self):
        # HTTPServer.server_bind reverse-resolves the bind address via
        # getfqdn(), which can stall for seconds on a bad DNS setup.
        TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(CLIENT_TIMEOUT)
        return request, client_address

    def handle_error(self, request, client_address):
        print("Conform Sidekick: remote request failed (see console).")

    def handle_timeout(self):
        return None


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 => one request per connection; no keep-alive loop on the UI thread.
    protocol_version = "HTTP/1.0"
    server_version = "ConformSidekick"
    sys_version = ""

    def log_message(self, fmt, *args):  # quiet
        return None

    def do_GET(self):
        self._serve()

    def do_POST(self):
        self._serve()

    def _serve(self):
        parts = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(min(length, 65536))

        status, payload = self.server.remote.dispatch(
            parts.path, self.headers.get(TOKEN_HEADER), query
        )
        plain = str(query.get("plain", "")).lower() in ("1", "true", "yes")
        if plain:
            body = (payload.get("message") or "") + "\n"
            ctype = "text/plain; charset=utf-8"
        else:
            body = json.dumps(payload) + "\n"
            ctype = "application/json; charset=utf-8"
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


class RemoteServer:
    """Action registry + loopback HTTP listener polled from the UI thread.

    Features register callables with :meth:`register`; each receives the query
    dict and returns a JSON-serialisable dict (``ok`` / ``message`` at least).
    """

    def __init__(self):
        self.actions = {}
        self.descriptions = {}
        self.server = None
        self.port = None
        self.requested_port = None
        self.token = ""
        self.busy = False
        # app hooks: called after a successful start / stop.
        self.on_started = None
        self.on_stopped = None

    # -- registry ----------------------------------------------------------

    def register(self, name, fn, description=""):
        name = (name or "").strip().lower()
        if not name:
            raise ValueError("action name is required")
        self.actions[name] = fn
        self.descriptions[name] = description

    # -- lifecycle ---------------------------------------------------------

    @property
    def listening(self):
        return self.server is not None

    def start(self, port, token):
        """Listen on ``port`` (or the next free one nearby). Returns the port."""
        if self.server is not None:
            self.stop()
        self.token = token or ""
        self.requested_port = int(port)
        last_error = None
        for candidate in range(self.requested_port, self.requested_port + PORT_SEARCH_SPAN):
            if candidate > PORT_MAX:
                break
            try:
                self.server = _Server(("127.0.0.1", candidate), _Handler, self)
            except OSError as exc:
                last_error = exc
                continue
            # Report the bound port (``candidate`` may be 0 = ephemeral).
            self.port = int(self.server.server_address[1])
            break
        if self.server is None:
            raise OSError(
                f"could not listen on ports {self.requested_port}-"
                f"{self.requested_port + PORT_SEARCH_SPAN - 1}: {last_error}"
            )
        if self.on_started is not None:
            try:
                self.on_started()
            except Exception:
                pass
        return self.port

    def stop(self):
        server, self.server = self.server, None
        self.port = None
        if server is not None:
            try:
                server.server_close()
            except Exception:
                pass
            if self.on_stopped is not None:
                try:
                    self.on_stopped()
                except Exception:
                    pass

    # -- request handling --------------------------------------------------

    def poll(self):
        """Handle pending requests without blocking. Returns the count served."""
        if self.server is None or self.busy:
            return 0
        handled = 0
        for _ in range(MAX_REQUESTS_PER_POLL):
            try:
                ready, _, _ = select.select([self.server], [], [], 0)
            except (OSError, ValueError):
                break
            if not ready:
                break
            try:
                self.server.handle_request()
            except Exception as exc:
                print(f"Conform Sidekick: remote handler error: {exc}")
            handled += 1
            if self.server is None:
                break
        return handled

    def dispatch(self, path, header_token, query):
        """Route one request. Returns ``(http_status, payload_dict)``."""
        action = (path or "").strip("/").split("/")[0].lower()
        if action in ("", "help"):
            return 200, {
                "ok": True,
                "message": "Conform Sidekick is listening.",
                "actions": sorted(self.actions),
                "token_header": TOKEN_HEADER,
            }

        token = header_token or query.get("token") or ""
        if not token or not self.token or not secrets.compare_digest(token, self.token):
            return 401, {
                "ok": False,
                "error": "unauthorized",
                "message": (
                    "Missing or wrong token. Use the launcher files Conform "
                    "Sidekick writes, or copy the URL from its window."
                ),
            }

        fn = self.actions.get(action)
        if fn is None:
            return 404, {
                "ok": False,
                "error": "unknown_action",
                "message": f"Unknown action '{action}'. Known: {', '.join(sorted(self.actions))}.",
            }

        if self.busy:
            return 409, {
                "ok": False,
                "error": "busy",
                "message": "Conform Sidekick is still running the previous action.",
            }

        self.busy = True
        try:
            payload = fn(query) or {}
        except Exception as exc:
            return 500, {
                "ok": False,
                "error": "exception",
                "message": f"{type(exc).__name__}: {exc}",
            }
        finally:
            self.busy = False

        payload = dict(payload)
        payload.setdefault("ok", True)
        payload.setdefault("action", action)
        payload.setdefault("message", "Done." if payload["ok"] else "Failed.")
        if payload["ok"]:
            return 200, payload
        if payload.get("error") == "busy":
            return 409, payload
        return 422, payload


# ---------------------------------------------------------------------------
# Launcher files
# ---------------------------------------------------------------------------


def _curl_command(port, token, action, quote):
    """Build the curl invocation with ``quote`` as the shell quote character."""
    url = endpoint_url(port, action, plain=True)
    header = f"{TOKEN_HEADER}: {token}"
    return (
        f"curl -s -m 60 -X POST -H {quote}{header}{quote} {quote}{url}{quote}"
    )


def launcher_sources(port, token):
    """Return ``{filename: text}`` for every launcher on this platform.

    Pure function so tests can check the generated content without touching
    the filesystem. AppleScript applets are compiled separately (see
    :func:`write_launchers`); their source is included here under ``.applescript``.
    """
    files = {}
    if sys.platform == "darwin":
        for action, name in LAUNCHER_ACTIONS:
            cmd = _curl_command(port, token, action, "'")
            files[f"{name}.applescript"] = (
                "try\n"
                f'\tset msg to do shell script "{cmd}"\n'
                "on error\n"
                f'\tset msg to "{NOT_RUNNING_MESSAGE}"\n'
                "end try\n"
                "try\n"
                '\tdisplay notification msg with title "Conform Sidekick"\n'
                "end try\n"
            )
            files[f"{name}.command"] = _shell_launcher(cmd)
    elif sys.platform.startswith("win"):
        for action, name in LAUNCHER_ACTIONS:
            cmd = _curl_command(port, token, action, '"').replace("curl ", "curl.exe ", 1)
            vbs_cmd = cmd.replace('"', '""')
            files[f"{name}.vbs"] = (
                'Set sh = CreateObject("WScript.Shell")\n'
                f'rc = sh.Run("{vbs_cmd}", 0, True)\n'
                f'If rc <> 0 Then MsgBox "{NOT_RUNNING_MESSAGE}", 48, "Conform Sidekick"\n'
            )
            files[f"{name}.bat"] = "@echo off\r\n" + cmd + "\r\n"
    else:
        for action, name in LAUNCHER_ACTIONS:
            cmd = _curl_command(port, token, action, "'")
            files[f"{name}.sh"] = _shell_launcher(cmd)
    files["README.txt"] = _readme_text(port, token)
    return files


def _shell_launcher(cmd):
    return (
        "#!/bin/sh\n"
        "# Generated by Conform Sidekick - re-created whenever remote control starts.\n"
        f"{cmd} || echo \"{NOT_RUNNING_MESSAGE}\"\n"
    )


def _readme_text(port, token):
    lines = [
        "Conform Sidekick - Stream Deck / remote control launchers",
        "",
        "These files trigger the Bypass Grade mode of the running Conform Sidekick",
        "window. Conform Sidekick must be open in Resolve with remote control",
        "enabled (Color > Bypass Grade > Enable remote control).",
        "",
        "Stream Deck:",
        "  Add a 'System: Open' action and drag one of these files onto it:",
    ]
    if sys.platform == "darwin":
        lines += [
            "    Bypass Grade.app / Restore Grade.app / Toggle Grade.app (silent, shows a notification)",
            "    *.command files do the same from Terminal if the .app versions are missing.",
        ]
    elif sys.platform.startswith("win"):
        lines += [
            "    Bypass Grade.vbs / Restore Grade.vbs / Toggle Grade.vbs (silent)",
            "    *.bat files do the same but briefly show a console window.",
        ]
    else:
        lines += ["    Bypass Grade.sh / Restore Grade.sh / Toggle Grade.sh"]
    lines += [
        "",
        "Any HTTP client (Stream Deck 'Web Requests' plugin, Bitfocus Companion,",
        "Keyboard Maestro, curl) can call the endpoint directly:",
        "",
        f"  POST {endpoint_url(port, 'toggle')}",
        f"  header  {TOKEN_HEADER}: {token}",
        f"  or      {endpoint_url(port, 'toggle', token=token)}",
        "",
        "Actions: bypass, restore, toggle, status. Add ?plain=1 for a one-line",
        "text reply instead of JSON. Requests are accepted from this computer only.",
        "",
        "These files are rewritten whenever the port changes; do not edit them.",
        "",
    ]
    return "\n".join(lines)


def _stamp(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_launchers(folder, port, token, compile_applets=True):
    """Write launcher files into ``folder``. Returns ``(written, errors)``.

    macOS applets are compiled with ``osacompile`` only when their source
    changed (a stamp file sits next to each app), so normal startups skip the
    ~1 s per applet compile.
    """
    written, errors = [], []
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as exc:
        return written, [f"could not create {folder}: {exc}"]

    for filename, text in launcher_sources(port, token).items():
        path = os.path.join(folder, filename)
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            if filename.endswith((".command", ".sh")):
                mode = os.stat(path).st_mode
                os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            written.append(path)
        except OSError as exc:
            errors.append(f"{filename}: {exc}")

    if sys.platform == "darwin" and compile_applets:
        for filename in list(launcher_sources(port, token)):
            if not filename.endswith(".applescript"):
                continue
            src_path = os.path.join(folder, filename)
            app_path = os.path.join(folder, filename[: -len(".applescript")] + ".app")
            stamp_path = os.path.join(folder, "." + filename[: -len(".applescript")] + ".stamp")
            try:
                with open(src_path, "r", encoding="utf-8") as fh:
                    stamp = _stamp(fh.read())
                current = ""
                if os.path.isdir(app_path) and os.path.isfile(stamp_path):
                    with open(stamp_path, "r", encoding="utf-8") as fh:
                        current = fh.read().strip()
                if current == stamp:
                    continue
                proc = subprocess.run(
                    ["osacompile", "-o", app_path, src_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if proc.returncode != 0:
                    errors.append(f"{os.path.basename(app_path)}: {proc.stderr.strip() or 'osacompile failed'}")
                    continue
                with open(stamp_path, "w", encoding="utf-8") as fh:
                    fh.write(stamp)
                written.append(app_path)
            except Exception as exc:
                errors.append(f"{os.path.basename(app_path)}: {exc}")
    return written, errors
