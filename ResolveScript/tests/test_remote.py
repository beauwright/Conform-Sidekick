"""Offline tests for the Stream Deck / remote control layer (``remote``).

No Resolve needed: the server is a plain loopback HTTP listener polled from
the caller's thread, so the tests spin one up on an ephemeral port, fire
requests at it from a helper thread and drive ``poll()`` by hand.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request

from _harness import Results

from conform_sidekick import remote
from conform_sidekick.features.grade_bypass import GradeBypassFeature


def _request(url, token=None, method="POST", header=True):
    """Return ``(status, payload_dict_or_text)`` for one request."""
    req = urllib.request.Request(url, method=method)
    if token and header:
        req.add_header(remote.TOKEN_HEADER, token)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        status = exc.code
    try:
        return status, json.loads(body)
    except ValueError:
        return status, body


def _served(server, url, **kwargs):
    """Fire a request from a thread while the caller polls the server."""
    out = {}

    def worker():
        out["result"] = _request(url, **kwargs)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    for _ in range(500):
        server.poll()
        thread.join(0.01)
        if not thread.is_alive():
            break
    thread.join(2)
    return out.get("result", (None, None))


def run():
    r = Results("test_remote")

    # -- dispatch -------------------------------------------------------------
    r.section("dispatch: auth, routing, busy")
    srv = remote.RemoteServer()
    srv.token = "abc123"
    calls = []
    srv.register("bypass", lambda q: calls.append(("bypass", dict(q))) or {"message": "did it"})
    srv.register("fail", lambda q: {"ok": False, "message": "nope"})
    srv.register("boom", lambda q: 1 / 0)

    status, payload = srv.dispatch("/", None, {})
    r.check("help needs no token", (status, payload["ok"]), (200, True))
    r.check("help lists actions", payload["actions"], ["boom", "bypass", "fail"])

    status, payload = srv.dispatch("/bypass", None, {})
    r.check("missing token -> 401", (status, payload["error"]), (401, "unauthorized"))
    status, _ = srv.dispatch("/bypass", "wrong", {})
    r.check("wrong header token -> 401", status, 401)
    status, _ = srv.dispatch("/bypass", None, {"token": "wrong"})
    r.check("wrong query token -> 401", status, 401)
    r.check("no action ran on bad auth", calls, [])

    status, payload = srv.dispatch("/bypass", "abc123", {"x": "1"})
    r.check("header token -> 200", (status, payload["ok"], payload["action"]), (200, True, "bypass"))
    r.check("action got the query", calls[-1], ("bypass", {"x": "1"}))
    r.check("action message kept", payload["message"], "did it")
    status, _ = srv.dispatch("/bypass/", None, {"token": "abc123"})
    r.check("query token + trailing slash -> 200", status, 200)
    status, _ = srv.dispatch("/BYPASS", "abc123", {})
    r.check("action is case-insensitive", status, 200)

    status, payload = srv.dispatch("/nope", "abc123", {})
    r.check("unknown action -> 404", (status, payload["error"]), (404, "unknown_action"))
    status, payload = srv.dispatch("/fail", "abc123", {})
    r.check("action reporting ok=False -> 422", (status, payload["ok"]), (422, False))
    status, payload = srv.dispatch("/boom", "abc123", {})
    r.check("raising action -> 500", (status, payload["error"]), (500, "exception"))
    r.check("busy flag cleared after exception", srv.busy, False)

    srv.busy = True
    status, payload = srv.dispatch("/bypass", "abc123", {})
    r.check("busy -> 409", (status, payload["error"]), (409, "busy"))
    srv.busy = False

    empty = remote.RemoteServer()
    status, _ = empty.dispatch("/bypass", "", {"token": ""})
    r.check("empty server token never matches", status, 401)

    # -- live loopback round trip -------------------------------------------
    r.section("live listener via poll()")
    srv = remote.RemoteServer()
    seen = []
    srv.register("toggle", lambda q: seen.append(q) or {"message": "toggled", "did": "bypass"})
    started = []
    srv.on_started = lambda: started.append(True)
    port = srv.start(0, "tok")
    r.check("start returns a real port", port > 0, True)
    r.check("listening", srv.listening, True)
    r.check("on_started hook fired", started, [True])
    r.check("idle poll handles nothing", srv.poll(), 0)

    base = f"http://127.0.0.1:{port}"
    status, payload = _served(srv, base + "/toggle", token="tok")
    r.check("POST with header -> 200", (status, payload and payload["ok"]), (200, True))
    r.check("handler ran once", len(seen), 1)

    status, payload = _served(srv, base + "/toggle?token=tok", method="GET")
    r.check("GET with query token works", (status, payload and payload["did"]), (200, "bypass"))

    status, text = _served(srv, base + "/toggle?token=tok&plain=1")
    r.check("plain=1 returns the message text", (status, text), (200, "toggled\n"))

    status, payload = _served(srv, base + "/toggle")
    r.check("no token over HTTP -> 401", status, 401)

    status, text = _served(srv, base + "/toggle?plain=1")
    r.check("plain 401 still has a message", "token" in (text or ""), True)

    status, payload = _served(srv, base + "/", method="GET")
    r.check("root help over HTTP", (status, payload and payload["message"]), (200, "Conform Sidekick is listening."))

    # Port collision: a second server on the same requested port moves along.
    other = remote.RemoteServer()
    other_port = other.start(port, "tok2")
    r.check("busy port -> next free port", other_port != port and other_port > port, True)
    other.stop()

    stopped = []
    srv.on_stopped = lambda: stopped.append(True)
    srv.stop()
    r.check("stop clears listener", (srv.listening, srv.port, stopped), (False, None, [True]))
    r.check("poll after stop is a no-op", srv.poll(), 0)
    try:
        _request(base + "/toggle", token="tok")
        r.check("port closed after stop", False, True)
    except (urllib.error.URLError, OSError):
        r.check("port closed after stop", True, True)

    # -- helpers ---------------------------------------------------------------
    r.section("helpers")
    r.check("parse_port blank -> default", remote.parse_port(""), (remote.DEFAULT_PORT, None))
    r.check("parse_port number", remote.parse_port(" 5000 "), (5000, None))
    r.check("parse_port junk", remote.parse_port("abc")[0], None)
    r.check("parse_port too low", remote.parse_port("80")[0], None)
    r.check("parse_port too high", remote.parse_port("70000")[0], None)
    r.check(
        "endpoint_url with token + plain",
        remote.endpoint_url(41451, "toggle", token="t", plain=True),
        "http://127.0.0.1:41451/toggle?token=t&plain=1",
    )
    r.check("endpoint_url bare", remote.endpoint_url(41451, "status"), "http://127.0.0.1:41451/status")

    # -- launcher files --------------------------------------------------------
    r.section("launcher files")
    sources = remote.launcher_sources(41451, "deadbeef")
    r.check("README always written", "README.txt" in sources, True)
    r.check("README carries the token header", remote.TOKEN_HEADER + ": deadbeef" in sources["README.txt"], True)
    names = [n for _, n in remote.LAUNCHER_ACTIONS]
    for name in names:
        if sys.platform == "darwin":
            r.check(f"{name}: applescript + command", (f"{name}.applescript" in sources, f"{name}.command" in sources), (True, True))
            src = sources[f"{name}.applescript"]
            r.check(f"{name}: applet notifies", "display notification msg" in src, True)
            r.check(f"{name}: applet POSTs with token", "-X POST -H 'X-Sidekick-Token: deadbeef'" in src, True)
        elif sys.platform.startswith("win"):
            r.check(f"{name}: vbs + bat", (f"{name}.vbs" in sources, f"{name}.bat" in sources), (True, True))
            r.check(f"{name}: vbs hidden run", ", 0, True)" in sources[f"{name}.vbs"], True)
            r.check(f"{name}: vbs escapes quotes", '""X-Sidekick-Token: deadbeef""' in sources[f"{name}.vbs"], True)
        else:
            r.check(f"{name}: sh", f"{name}.sh" in sources, True)
    joined = "\n".join(sources.values())
    for action, _ in remote.LAUNCHER_ACTIONS:
        r.check(f"launchers hit /{action}?plain=1", f"http://127.0.0.1:41451/{action}?plain=1" in joined, True)

    tmp = tempfile.mkdtemp(prefix="cs-remote-")
    try:
        folder = os.path.join(tmp, "streamdeck")
        written, errors = remote.write_launchers(folder, 41451, "deadbeef", compile_applets=False)
        r.check("write_launchers: no errors", errors, [])
        r.check("write_launchers: every source written", sorted(os.path.basename(p) for p in written), sorted(sources))
        for path in written:
            if path.endswith((".command", ".sh")):
                r.check(f"{os.path.basename(path)} executable", os.access(path, os.X_OK), True)
                break
        # Re-running overwrites in place without error.
        written2, errors2 = remote.write_launchers(folder, 41452, "deadbeef", compile_applets=False)
        r.check("rewrite on port change", (errors2, len(written2)), ([], len(written)))
        with open(os.path.join(folder, "README.txt"), encoding="utf-8") as fh:
            r.check("rewritten README has new port", ":41452/" in fh.read(), True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # -- feature reply shaping -----------------------------------------------
    r.section("GradeBypassFeature._describe_result")
    describe = GradeBypassFeature._describe_result
    r.check(
        "success bypass",
        describe({"clip_name": "A001", "nodes_changed": 3}, "bypass", False, ""),
        {"ok": True, "did": "bypass", "clip": "A001", "nodes_changed": 3, "message": "Grade bypassed on A001 (3 nodes)."},
    )
    r.check(
        "success restore single node",
        describe({"clip_name": "A001", "nodes_changed": 1}, "restore", False, "")["message"],
        "Grade restored on A001 (1 node).",
    )
    r.check(
        "dry run prefix",
        describe({"nodes_changed": 0}, "bypass", True, "")["message"],
        "Preview only: Grade bypassed (0 nodes).",
    )
    r.check(
        "error uses last log line",
        describe({"error": True}, "bypass", False, "No clip is selected."),
        {"ok": False, "did": "bypass", "clip": "", "message": "No clip is selected."},
    )
    r.check("cancelled", describe({"cancelled": True}, "restore", False, "")["error"], "cancelled")

    feature = GradeBypassFeature()
    r.check(
        "trigger before bind reports not_ready",
        feature.trigger("bypass")["error"],
        "not_ready",
    )

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
