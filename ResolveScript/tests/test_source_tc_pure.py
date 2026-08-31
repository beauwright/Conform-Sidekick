"""Pure-function checks for ``ops.source_tc`` - date parsing, timezones, timecode.

These cover the parts that were easiest to get subtly wrong, each pinned to a
real observation rather than an invented example:

* ``Date Created`` does not zero-pad the day, and ``Date Modified`` uses a
  different field order, so the ``[-8:]`` slice found in community scripts is
  wrong for one of them.
* Resolve renders creation dates in the workstation's local timezone, so the
  local -> UTC conversion is asserted against real embedded values read out of
  the media with ffprobe.
* Half of a real project's zero-TC clips share a timestamp to the second, so
  collision handling is normal-path behaviour, not an edge case.
"""

import datetime as dt

from _harness import Results, pin_timezone

from conform_sidekick.ops.source_tc import (
    ZERO_TC,
    assign_timecodes,
    derive_tc,
    parse_date_created,
    resolve_zone,
    to_zone,
)

# Resolve's local rendering -> the UTC value actually embedded in the file,
# read with ffprobe. Spans both MST and MDT to pin DST handling.
GROUND_TRUTH = (
    ("Tue Mar 30 2021 08:45:03", "2021-03-30T14:45:03"),
    ("Sun Jan 12 2025 23:10:33", "2025-01-13T06:10:33"),   # crosses midnight
    ("Wed Mar 26 2025 12:15:45", "2025-03-26T18:15:45"),
    ("Thu May 21 2026 15:54:03", "2026-05-21T21:54:03"),
)


def _clip(name, created, fps=24):
    return {"name": name, "uid": name,
            "created_dt": parse_date_created(created), "fps": fps}


def run():
    r = Results("source_tc pure")
    pinned = pin_timezone()

    r.section("parse_date_created")
    r.check("standard shape", parse_date_created("Thu Feb 12 2026 16:47:29"),
            dt.datetime(2026, 2, 12, 16, 47, 29))
    r.check("day is not zero-padded", parse_date_created("Mon May 4 2026 13:42:28"),
            dt.datetime(2026, 5, 4, 13, 42, 28))
    r.check("Date Modified order, accepted defensively",
            parse_date_created("Thu Jul 11 12:19:32 2024"),
            dt.datetime(2024, 7, 11, 12, 19, 32))
    r.check("collapses repeated whitespace",
            parse_date_created("Mon  May   4  2026  13:42:28"),
            dt.datetime(2026, 5, 4, 13, 42, 28))
    r.check("unparseable -> None", parse_date_created("not a date"), None)
    r.check("empty -> None", parse_date_created(""), None)
    r.check("non-string -> None", parse_date_created(271984384), None)

    r.section("local -> UTC against embedded ground truth")
    if not pinned:
        r.skip("ground-truth conversions", "time.tzset() unavailable on this platform")
    else:
        utc = resolve_zone("UTC")
        for local_s, want in GROUND_TRUTH:
            r.check(f"{local_s} -> UTC",
                    to_zone(parse_date_created(local_s), utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    want)

    r.section("zones")
    r.check("machine local is identity",
            to_zone(dt.datetime(2025, 1, 12, 23, 10, 33), resolve_zone("")),
            dt.datetime(2025, 1, 12, 23, 10, 33))
    if not pinned:
        r.skip("named-zone DST handling", "time.tzset() unavailable on this platform")
    else:
        # A captured offset would shift one of these by an hour; a named zone
        # carries the transition rules and leaves both untouched.
        r.check("named zone, winter clip",
                to_zone(dt.datetime(2025, 1, 12, 23, 10, 33), resolve_zone("America/Denver")),
                dt.datetime(2025, 1, 12, 23, 10, 33))
        r.check("named zone, summer clip",
                to_zone(dt.datetime(2020, 7, 1, 18, 52, 28), resolve_zone("America/Denver")),
                dt.datetime(2020, 7, 1, 18, 52, 28))
        r.check("cross-zone conversion",
                to_zone(dt.datetime(2020, 7, 1, 18, 52, 28), resolve_zone("America/New_York")),
                dt.datetime(2020, 7, 1, 20, 52, 28))
    try:
        resolve_zone("Mars/Olympus_Mons")
        r.check("unknown zone raises", "no exception", "ValueError")
    except ValueError as exc:
        r.check("unknown zone raises a helpful ValueError",
                "America/Denver" in str(exc), True)

    r.section("derive_tc")
    moment = dt.datetime(2026, 5, 21, 15, 54, 3)
    r.check("frame 0", derive_tc(moment, 0, 24), "15:54:03:00")
    r.check("frame 5", derive_tc(moment, 5, 24), "15:54:03:05")
    r.check("rolls into the next second at fps", derive_tc(moment, 24, 24), "15:54:04:00")
    r.check("rolls twice", derive_tc(moment, 49, 24), "15:54:05:01")
    r.check("unusable fps falls back to 24", derive_tc(moment, 24, None), "15:54:04:00")

    r.section("assign_timecodes")
    # The real collision observed on the reference project.
    pair = [_clip("WDW_Monorail_4k.mp4", "Thu Dec 05 2024 22:47:08"),
            _clip("WDW_Epcot Night_4k.mp4", "Thu Dec 05 2024 22:47:08")]
    assigned = [(c["name"], tc) for c, tc, _ in assign_timecodes(pair)]
    r.check("collision resolved by frame, ordered by name", assigned,
            [("WDW_Epcot Night_4k.mp4", "22:47:08:00"),
             ("WDW_Monorail_4k.mp4", "22:47:08:01")])
    r.check("input order does not change the result",
            [(c["name"], tc) for c, tc, _ in assign_timecodes(list(reversed(pair)))],
            assigned)

    # Spilling must not land on a clip that genuinely occupies the next second.
    crowd = [_clip(f"c{i:02d}", "Thu Dec 05 2024 22:47:08") for i in range(26)]
    crowd.append(_clip("zz_next_second", "Thu Dec 05 2024 22:47:09"))
    spilled = assign_timecodes(crowd)
    tcs = [tc for _, tc, _ in spilled]
    r.check("every assignment is unique across the spill", len(set(tcs)), 27)
    r.check("overflow lands in the following second",
            sorted(t for t in tcs if t.startswith("22:47:09")),
            ["22:47:09:00", "22:47:09:01", "22:47:09:02"])
    r.check("spill is flagged for the log", sum(1 for _, _, sp in spilled if sp), 2)

    # A clip created at 23:59:59 must never wrap onto the sentinel, or it would
    # be picked up as a candidate again on the next run.
    midnight = [_clip(f"m{i:02d}", "Wed Dec 31 2025 23:59:59") for i in range(26)]
    m_tcs = [tc for _, tc, _ in assign_timecodes(midnight)]
    r.check("00:00:00:00 is never assigned", ZERO_TC in m_tcs, False)
    r.check("it wraps past the sentinel instead",
            sorted(t for t in m_tcs if t.startswith("00:")),
            ["00:00:00:01", "00:00:00:02"])

    r.section("timezone reaches the assigned timecode")
    if not pinned:
        r.skip("zone applied end to end", "time.tzset() unavailable on this platform")
    else:
        r.check("UTC shifts the result",
                assign_timecodes([_clip("a.mov", "Sun Jan 12 2025 23:10:33")],
                                 resolve_zone("UTC"))[0][1],
                "06:10:33:00")

    return r.summary()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
