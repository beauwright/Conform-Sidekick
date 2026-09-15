"""Live check (needs a running Resolve with external scripting enabled).

Builds the real window in a throw-away support home with remote control saved
as *enabled* - the startup path that 2.0.0-beta.9/10 left dead to clicks - and
verifies that while the loop polls: a UI event reaches its handler, the
save-on-edit path writes the file, and the remote listener answers.

    python3 ResolveScript/tests/live_ui_events.py

Not part of ``run_tests.py`` (it needs Resolve).
"""

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _harness import Results  # noqa: E402

PORT = 41499


def tick(app, n=15):
    for _ in range(n):
        app.step()
        app.poll()
        time.sleep(0.02)


def run():
    r = Results("live UI events")
    home = tempfile.mkdtemp(prefix="cs-live-")
    os.environ["CONFORM_SIDEKICK_HOME"] = home
    # Package import must come after the env var so paths resolve into ``home``.
    from conform_sidekick import app as app_mod
    from conform_sidekick import remote as remote_mod

    remote_mod.remote_state_store().save({"enabled": True, "port": PORT})
    app = None
    try:
        app = app_mod.build()
        r.section("startup with remote saved as enabled")
        r.check("listener started during bind", app.remote.listening, True)
        r.check("Resolve answers the liveness probe", app.alive(), True)
        tick(app)

        r.section("UI events are delivered while polling")
        items = app.ctx.items
        feature = next(f for f in app.features if f.id == "gradebypass")
        hits = []
        app.win.On[feature.wid("InputIndexSpec")].TextChanged = (
            lambda ev: hits.append(ev.get("Text")) or feature.save_settings()
        )
        items[feature.wid("InputIndexSpec")].Text = "7"
        tick(app)
        r.check("TextChanged handler ran", hits, ["7"])
        saved = feature.state_store().load()
        r.check("save-on-edit persisted the value", saved.get("input_index_spec"), "7")

        r.section("remote keeps working in the same loop")
        token = remote_mod.ensure_token(remote_mod.remote_state_store())
        url = remote_mod.endpoint_url(app.remote.port, "status", token=token)
        req = urllib.request.Request(url, method="POST")
        got = {}

        def fetch():
            with urllib.request.urlopen(req, timeout=5) as resp:
                got.update(json.loads(resp.read().decode("utf-8")))

        import threading
        th = threading.Thread(target=fetch)
        th.start()
        for _ in range(100):
            tick(app, 1)
            if not th.is_alive():
                break
        th.join(timeout=1)
        r.check("status answered", got.get("ok"), True)

        r.section("close")
        app.closed = True
        r.check("loop exits on close", app.run(), "closed")
    finally:
        if app is not None and app.remote.listening:
            app.shutdown()
        shutil.rmtree(home, ignore_errors=True)
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
