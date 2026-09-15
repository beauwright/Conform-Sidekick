"""Offline tests for ``state.StateStore``: None is never persisted over a value.

Background: when Resolve crashes under a running Conform Sidekick, the script
process survives with dead widget proxies whose ``.Text`` reads back as None. A
Stream Deck press on that zombie used to write ``null`` for every Bypass Grade
setting. The store now drops such values on save and ignores them on load.
"""

import json
import os
import shutil
import tempfile

from _harness import Results


def run():
    r = Results("state")
    home = tempfile.mkdtemp(prefix="cs-state-")
    previous = os.environ.get("CONFORM_SIDEKICK_HOME")
    os.environ["CONFORM_SIDEKICK_HOME"] = home
    try:
        from conform_sidekick.state import StateStore

        defaults = {"text": "", "flag": False, "count": 3, "optional": None, "table": {}}
        store = StateStore("unit", defaults)

        r.section("save")
        store.save({"text": "XFORM", "flag": True, "count": 30})
        r.check("values written", store.load(), {**defaults, "text": "XFORM", "flag": True, "count": 30})

        store.save({"text": None, "flag": None, "count": None, "table": None})
        r.check("None never overwrites a concrete value", store.load(),
                {**defaults, "text": "XFORM", "flag": True, "count": 30})

        store.save({"optional": None})
        r.check("None allowed where the default is None", store.load()["optional"], None)
        store.save({"optional": "x"})
        store.save({"optional": None})
        r.check("None can clear a None-default key", store.load()["optional"], None)

        r.section("load heals a damaged file")
        with open(store.path, "w", encoding="utf-8") as fh:
            json.dump({"text": None, "flag": None, "count": 7, "table": {"a": 1}}, fh)
        r.check("nulls fall back to defaults, others kept", store.load(),
                {**defaults, "count": 7, "table": {"a": 1}})
        store.save({"count": 8})
        with open(store.path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        r.check("rewrite drops the nulls from disk", (on_disk["text"], on_disk["flag"], on_disk["count"]),
                ("", False, 8))

        r.section("unknown keys")
        store.save({"nope": 1})
        r.check("keys outside defaults are ignored on load", "nope" in store.load(), False)
    finally:
        if previous is None:
            os.environ.pop("CONFORM_SIDEKICK_HOME", None)
        else:
            os.environ["CONFORM_SIDEKICK_HOME"] = previous
        shutil.rmtree(home, ignore_errors=True)
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
