"""Timecode conversion helpers backed by the vendored ``timecode`` library.

The previous davinci-resolve-scripts hand-rolled SMPTE / drop-frame math
(``_tc_to_frames`` and friends), which was a suspected source of off-by-one and
drop-frame bugs in the reconform feature. Conform Sidekick standardises on the
``timecode`` library for everything that touches an ``HH:MM:SS:FF`` string or an
fps-dependent frame conversion. Pure integer frame logic (record positions,
marker frame ids) stays as plain ints elsewhere.

``timecode`` counts frames 1-based, so a Resolve 0-based frame index ``n`` maps
to ``Timecode(..., frames=n + 1)`` and back with a ``- 1``.
"""

from timecode import Timecode


def get_timeline_framerate_and_dropframe(project, timeline):
    """Return ``(frame_rate_str, drop_frame_bool)`` for the active timeline.

    Mirrors the resolution order used by the original ResolveController: start
    from the project setting, then override with the timeline-specific setting
    when present. Resolve reports drop frame as the string ``'1'`` / ``'0'``.
    """
    frame_rate = project.GetSetting("timelineFrameRate")
    drop_frame = project.GetSetting("timelineDropFrameTimecode")

    if timeline is not None:
        timeline_frame_rate = timeline.GetSetting("timelineFrameRate")
        if timeline_frame_rate is not None and timeline_frame_rate != "":
            frame_rate = timeline_frame_rate
            drop_frame = timeline.GetSetting("timelineDropFrameTimecode")

    return str(frame_rate), (drop_frame == "1")


def frame_to_timecode(frame_rate, drop_frame: bool, number_of_frames: int) -> str:
    """Convert a 0-based Resolve frame index to a timecode string."""
    frame_rate_str = str(frame_rate)
    tc = Timecode(
        frame_rate_str,
        frames=int(number_of_frames) + 1,
        force_non_drop_frame=not drop_frame,
    )
    return str(tc)


def timecode_to_frames(frame_rate, drop_frame: bool, timecode_str: str) -> int:
    """Convert a timecode string back to a 0-based Resolve frame index."""
    frame_rate_str = str(frame_rate)
    tc = Timecode(
        frame_rate_str,
        timecode_str,
        force_non_drop_frame=not drop_frame,
    )
    return int(tc.frames) - 1
