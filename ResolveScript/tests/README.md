# Tests

Offline tests for the in-Resolve package. **No Resolve, no network, no
third-party packages** — they run anywhere, including Resolve's own bundled
Python.

```bash
python3 ResolveScript/tests/run_tests.py
```

Exits non-zero if anything fails. 246 checks across nine suites. The one
exception to "no third-party packages" is `test_odd_res.py`, which needs
Pillow like the feature it covers and reports `SKIP` without it.

## Why not pytest

The shipped package is deliberately dependency-free (pure-Python dependencies
are vendored — see the main [README](../README.md)), and these tests are meant
to be runnable under whichever interpreter Resolve happens to be using, where
`pip install pytest` is not always an option. [`_harness.py`](_harness.py) is
about thirty lines and does the job. If the suite ever grows past what that can
carry, pytest is the obvious next step.

## Suites

**[`test_source_tc_pure.py`](test_source_tc_pure.py)** — date parsing, timezone
conversion, timecode derivation and collision assignment. Every assertion is
pinned to something observed on a real project rather than an invented example:

- `Date Created` does not zero-pad the day (`'Mon May 4 2026 13:42:28'`) and
  `Date Modified` puts the year last, so the `[-8:]` slice found in community
  scripts is correct for one and silently wrong for the other.
- Local → UTC conversions are asserted against **real embedded values read out
  of the media with ffprobe**, spanning both MST and MDT so a fixed offset
  cannot pass.
- Collisions are normal-path behaviour: roughly half of a real project's
  zero-TC clips shared a timestamp to the second.
- A clip created at 23:59:59 must never wrap onto `00:00:00:00` — that would
  make it a candidate again on the next run.

**[`test_source_tc_ops.py`](test_source_tc_ops.py)** — scanning, filtering,
applying, verifying and reverting against a fake media pool. The fakes
reproduce two behaviours seen on real projects:

- `SetClipProperty` can return `True` without the value sticking, so the op
  re-reads and reports a mismatch rather than trusting the return value.
- The `Usage` clip property only reflects the **currently open** timeline. With
  no timeline open it read `'0'` for 5248 of 5249 clips on a 48-timeline
  project while 75 zero-TC clips were genuinely in use. The fake `inuse.mov`
  therefore carries `Usage == '0'` while sitting in a fake timeline, so the
  exclusion has to come from the computed usage map or the test fails.

**[`test_lay_clips.py`](test_lay_clips.py)** — Lay Matching Bin Clips against a
fake timeline and media pool: the Start TC remap, the clamp to the new clip's
extents, and lay-track occupancy. The rule it pins: when the new clip starts
later than the range in use (shorter head handles), it is laid that many frames
later on the record side. Laid at the original record start, every remaining
frame would land early.

**[`test_odd_res.py`](test_odd_res.py)** — the 1px stretch on real image files
written to a temp folder. The converted file replaces the original in the
project, so it must match the source in everything but the extra pixel:

- A JPEG keeps its quantization tables, chroma subsampling, ICC profile, EXIF
  orientation and DPI. A bare `Image.save()` recompresses at quality 75 / 4:2:0
  and drops all the metadata.
- 16-bit RGB(A) is refused, because Pillow has no such mode and hands back
  8-bit.
- Big-endian 16-bit greyscale (the usual TIFF byte order) keeps its pixel
  values. Pillow's resampling filters read `I;16B` as little-endian and
  scramble it, so the op re-reads the bytes in native order first.

## Platform note

Assertions on specific local → UTC conversions need a pinned process timezone,
and `time.tzset()` is Unix-only. On Windows those four checks report `SKIP`
rather than asserting against whatever zone the machine happens to be in; the
rest run everywhere.

## Not included

Scripts that drive a live Resolve are kept out of the repo on purpose — they
write to whatever project is open, which is too easy to run by accident.
