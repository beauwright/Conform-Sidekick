"""Offline tests for ``app.event_loop`` (no Resolve, no UIManager).

The loop is one StepLoop + one remote poll per tick plus a periodic liveness
check; these drive it with fakes and a fake clock.
"""

from _harness import Results

from conform_sidekick import app


class Clock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, secs):
        self.t += secs


def _drive(closed_after=None, alive_pattern=None):
    clock = Clock()
    counts = {"step": 0, "poll": 0, "alive": 0}
    alive_pattern = list(alive_pattern or [])

    def step():
        counts["step"] += 1

    def poll():
        counts["poll"] += 1

    def alive():
        counts["alive"] += 1
        return alive_pattern.pop(0) if alive_pattern else True

    def closed():
        return closed_after is not None and counts["step"] >= closed_after

    result = app.event_loop(step, poll, alive, closed, sleep=clock.sleep, now=clock.now)
    return result, counts, clock


def run():
    r = Results("app loop")

    r.section("normal close")
    result, counts, _ = _drive(closed_after=5)
    r.check("returns closed", result, "closed")
    r.check("one step and one poll per tick", (counts["step"], counts["poll"]), (5, 5))
    r.check("no liveness check inside the first interval", counts["alive"], 0)

    r.section("liveness")
    ticks_per_interval = int(app.LIVENESS_INTERVAL / app.TICK_INTERVAL) + 1
    result, counts, _ = _drive(closed_after=ticks_per_interval * 3 + 5)
    r.check("checks about every LIVENESS_INTERVAL", counts["alive"], 3)

    result, counts, clock = _drive(alive_pattern=[False] * app.LIVENESS_FAILURES_TO_EXIT)
    r.check("Resolve gone -> loop exits", result, "resolve_gone")
    r.check("gave up after the configured failures", counts["alive"], app.LIVENESS_FAILURES_TO_EXIT)
    r.check("exit within a few intervals", clock.now() - 1000.0 < app.LIVENESS_INTERVAL * (app.LIVENESS_FAILURES_TO_EXIT + 1), True)

    result, counts, _ = _drive(closed_after=ticks_per_interval * 4 + 5, alive_pattern=[False, True, False, True])
    r.check("a single failed check is forgiven", result, "closed")

    r.section("step failure")
    clock = Clock()
    result = app.event_loop(lambda: False, lambda: None, lambda: True, lambda: False,
                            sleep=clock.sleep, now=clock.now)
    r.check("step() False -> resolve_gone at once", result, "resolve_gone")

    r.section("resolve_alive")
    class Conn:
        def __init__(self, version):
            self.resolve = self
            self._v = version
        def GetVersionString(self):
            if isinstance(self._v, Exception):
                raise self._v
            return self._v
    r.check("version string -> alive", app.resolve_alive(Conn("21.0.1")), True)
    r.check("None (dead proxy) -> not alive", app.resolve_alive(Conn(None)), False)
    r.check("exception -> not alive", app.resolve_alive(Conn(RuntimeError("x"))), False)
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
