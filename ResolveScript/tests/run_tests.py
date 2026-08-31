#!/usr/bin/env python3
"""Run every Conform Sidekick test module. Exits non-zero on failure.

    python3 ResolveScript/tests/run_tests.py

No third-party dependencies, so this also runs under Resolve's bundled Python.
Each module exposes ``run()`` returning True on success.
"""

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

MODULES = (
    "test_source_tc_pure",
    "test_source_tc_ops",
)


def main():
    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    ok = True
    for name in MODULES:
        print(f"\n{'=' * 68}\n{name}\n{'=' * 68}")
        module = importlib.import_module(name)
        ok = module.run() and ok
    print(f"\n{'=' * 68}")
    print("ALL SUITES PASSED" if ok else "FAILURES - see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
