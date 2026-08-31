"""Minimal test harness - no pytest, no third-party imports.

The in-Resolve package is deliberately dependency-free (pure-Python deps are
vendored, see ``ResolveScript/README.md``), and these tests are meant to run
under whatever interpreter is to hand - including Resolve's own bundled Python,
where installing pytest is not an option. So the harness is about thirty lines
rather than a framework.

Run everything with ``python3 ResolveScript/tests/run_tests.py``.
"""

import os
import sys
import time

# Make ``conform_sidekick`` importable: tests/ sits next to the package.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class Results:
    """Collects pass/fail/skip counts for one test module."""

    def __init__(self, title):
        self.title = title
        self.passed = 0
        self.failed = []
        self.skipped = []

    def section(self, name):
        print(f"\n-- {name}")

    def check(self, label, got, want):
        if got == want:
            self.passed += 1
            print(f"   PASS  {label}  -> {got!r}")
        else:
            self.failed.append(label)
            print(f"   FAIL  {label}\n           got  {got!r}\n          want  {want!r}")

    def skip(self, label, why):
        self.skipped.append(label)
        print(f"   SKIP  {label}  ({why})")

    def summary(self):
        bits = [f"{self.passed} passed"]
        if self.failed:
            bits.append(f"{len(self.failed)} FAILED")
        if self.skipped:
            bits.append(f"{len(self.skipped)} skipped")
        print(f"\n{self.title}: {', '.join(bits)}")
        if self.failed:
            for label in self.failed:
                print(f"   failed: {label}")
        return not self.failed


def pin_timezone(name="America/Denver"):
    """Pin the process timezone so local-time assertions are reproducible.

    Several checks assert on a *specific* local -> UTC conversion, which only
    means anything if the process timezone is known. ``time.tzset()`` is
    Unix-only, so on Windows the caller must skip those checks rather than
    assert against whatever zone the machine happens to be in.

    Returns True when the timezone was pinned.
    """
    if not hasattr(time, "tzset"):
        return False
    os.environ["TZ"] = name
    time.tzset()
    return True
