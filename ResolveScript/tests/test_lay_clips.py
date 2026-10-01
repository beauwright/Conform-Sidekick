"""Offline tests for Lay Matching Bin Clips (``ops.lay_clips``).

A fake timeline / media pool stands in for Resolve: enough of the item, clip
and ``AppendToTimeline`` surface for the source-range remap, the clamp to the
new clip's extents and the lay-track bookkeeping. The fake ``resolve`` has no
``EXPORT_TEXT_CSV``, so every run takes the scripting-API path rather than the
Edit Index one.

The clamp cases pin the sync rule: a new clip that starts later than the
range in use (shorter head handles) must be laid that many frames later on the
record side, or every remaining frame lands early.
"""

from _harness import Results

from conform_sidekick.ops import lay_clips

REC = 86400  # 01:00:00:00 at 24 fps


class FakeClip:
    """MediaPoolItem: ``frames`` long, numbered from 0, starting at ``start_tc``."""

    def __init__(self, name, frames, start_tc):
        self.name = name
        self.props = {
            "Type": "Video",
            "Start": 0,
            "End": frames - 1,
            "Frames": frames,
            "FPS": 24.0,
            "Start TC": start_tc,
        }

    def GetName(self):
        return self.name

    def GetClipProperty(self, key):
        return self.props.get(key)


class FakeItem:
    """TimelineItem covering record ``[start, end)`` from source ``[src_in, src_out)``."""

    def __init__(self, name, start, end, src_in=0, src_out=0, clip=None):
        self.name = name
        self.start, self.end = start, end
        self.src_in, self.src_out = src_in, src_out
        self.clip = clip

    def GetName(self):
        return self.name

    def GetStart(self):
        return self.start

    def GetEnd(self):
        return self.end

    def GetSourceStartFrame(self):
        return self.src_in

    def GetSourceEndFrame(self):
        return self.src_out

    def GetMediaPoolItem(self):
        return self.clip

    def GetClipEnabled(self):
        return True

    def GetUniqueId(self):
        return f"item-{id(self)}"


class FakeTimeline:
    def __init__(self, items):
        self.tracks = {1: list(items)}
        self.names = {}

    def GetName(self):
        return "Reel 1"

    def GetSetting(self, key):
        return {"timelineFrameRate": "24", "timelineDropFrameTimecode": "0"}.get(key)

    def GetTrackCount(self, kind):
        return len(self.tracks)

    def GetItemListInTrack(self, kind, index):
        return list(self.tracks.get(index, []))

    def AddTrack(self, kind):
        self.tracks[len(self.tracks) + 1] = []
        return True

    def SetTrackName(self, kind, index, name):
        self.names[index] = name
        return True


class FakeFolder:
    def __init__(self, clips):
        self.clips = clips

    def GetName(self):
        return "VFX"

    def GetClipList(self):
        return list(self.clips)


class FakeMediaPool:
    def __init__(self, folder, timeline):
        self.folder, self.timeline = folder, timeline
        self.appended = []

    def GetCurrentFolder(self):
        return self.folder

    def AppendToTimeline(self, infos):
        out = []
        for info in infos:
            self.appended.append(info)
            length = info["endFrame"] - info["startFrame"]
            item = FakeItem(
                info["mediaPoolItem"].GetName(),
                info["recordFrame"],
                info["recordFrame"] + length,
            )
            self.timeline.tracks[info["trackIndex"]].append(item)
            out.append(item)
        return out


class FakeProject:
    def __init__(self, media_pool):
        self.media_pool = media_pool

    def GetSetting(self, key):
        return {"timelineFrameRate": "24", "timelineDropFrameTimecode": "0"}.get(key)

    def GetMediaPool(self):
        return self.media_pool


class FakeConn:
    resolve = object()

    def __init__(self, items, bin_clips):
        self.timeline = FakeTimeline(items)
        self.media_pool = FakeMediaPool(FakeFolder(bin_clips), self.timeline)
        self.project = FakeProject(self.media_pool)

    def get_project(self):
        return self.project

    def get_timeline(self):
        return self.timeline


def _lay(items, bin_clips, dry_run=False):
    conn = FakeConn(items, bin_clips)
    lines = []
    result = lay_clips.lay_matching_bin_clips(
        conn,
        pattern_str=r"(SH\d+)",
        new_track_name="Reconform",
        clip_color="",
        copy_grade=False,
        copy_attrs=False,
        disable_originals=False,
        skip_disabled_tlis=True,
        dry_run=dry_run,
        log=lines.append,
    )
    placed = [
        (i["mediaPoolItem"].GetName(), i["trackIndex"], i["recordFrame"],
         i["startFrame"], i["endFrame"])
        for i in conn.media_pool.appended
    ]
    return conn, result, placed, "\n".join(lines)


def run():
    r = Results("lay clips")
    plate = FakeClip("A001_C003.mov", 200, "01:00:00:00")

    r.section("new clip covers the range in use")
    # Same Start TC and length: the range carries over unchanged.
    comp = FakeClip("SH010_comp_v002.mov", 200, "01:00:00:00")
    item = FakeItem("SH010_plate", REC, REC + 100, 10, 110, plate)
    conn, result, placed, log = _lay([item], [comp])
    r.check("laid at the original record start", placed,
            [("SH010_comp_v002.mov", 2, REC, 10, 110)])
    r.check("not counted as clamped", result["clamped"], 0)
    r.check("lay track named", conn.timeline.names, {2: "Reconform"})

    # The comp starts 20 frames into the plate: frame numbers shift, sync holds.
    comp = FakeClip("SH010_comp_v002.mov", 150, "01:00:00:20")
    item = FakeItem("SH010_plate", REC, REC + 100, 30, 130, plate)
    _, result, placed, log = _lay([item], [comp])
    r.check("Start TC delta remaps the source range", placed,
            [("SH010_comp_v002.mov", 2, REC, 10, 110)])

    r.section("head clamp (new clip has shorter head handles)")
    # Plate frames 10-109 are in use, but the comp only begins at plate frame
    # 20. Its first frame belongs 10 frames after the original record start.
    comp = FakeClip("SH010_comp_v002.mov", 100, "01:00:00:20")
    item = FakeItem("SH010_plate", REC, REC + 100, 10, 110, plate)
    _, result, placed, log = _lay([item], [comp])
    r.check("record start moves by the clamped frames", placed,
            [("SH010_comp_v002.mov", 2, REC + 10, 0, 90)])
    r.check("counted as clamped", (result["clamped"], result["laid"]), (1, 1))
    r.check("log says how much is missing",
            "missing 10f at the head and 0f at the tail" in log, True)
    r.check("...and where it lands",
            f"covers record [{REC + 10}-{REC + 100}]" in log, True)
    r.check("summary line", "Laid short (missing handles):   1" in log, True)

    r.section("tail clamp (new clip ends early)")
    # Plate frames 100-139 in use; the comp ends at plate frame 119.
    item = FakeItem("SH010_plate", REC, REC + 40, 100, 140, plate)
    _, result, placed, log = _lay([item], [comp])
    r.check("record start unchanged, tail shortened", placed,
            [("SH010_comp_v002.mov", 2, REC, 80, 100)])
    r.check("log says how much is missing",
            "missing 0f at the head and 20f at the tail" in log, True)

    r.section("no overlap at all")
    item = FakeItem("SH010_plate", REC, REC + 40, 150, 190, plate)
    _, result, placed, log = _lay([item], [comp])
    r.check("nothing laid", (placed, result["range_failures"], result["clamped"]),
            ([], 1, 0))

    r.section("dry run")
    item = FakeItem("SH010_plate", REC, REC + 100, 10, 110, plate)
    conn, result, placed, log = _lay([item], [comp], dry_run=True)
    r.check("nothing appended, no track added",
            (placed, len(conn.timeline.tracks)), ([], 1))
    r.check("clamp still reported", (result["clamped"], result["laid"]), (1, 1))
    r.check("planned position in the log",
            f"covers record [{REC + 10}-{REC + 100}]" in log, True)

    r.section("lay-track occupancy follows what was actually laid")
    comps = [
        FakeClip("SH010_comp.mov", 200, "01:00:00:00"),
        FakeClip("SH020_comp.mov", 200, "01:00:00:00"),
    ]
    items = [
        FakeItem("SH010_plate", REC, REC + 50, 0, 50, plate),
        FakeItem("SH020_plate", REC + 50, REC + 100, 100, 150, plate),
    ]
    _, result, placed, log = _lay(items, comps)
    r.check("adjacent clips share one lay track",
            [(name, track) for name, track, *_ in placed],
            [("SH010_comp.mov", 2), ("SH020_comp.mov", 2)])

    # A 200% retime is laid at 100% speed, so it runs 100 frames from a
    # 50-frame slot; the next clip must not be stacked onto it.
    items = [
        FakeItem("SH010_plate", REC, REC + 50, 0, 100, plate),
        FakeItem("SH020_plate", REC + 50, REC + 100, 100, 150, plate),
    ]
    _, result, placed, log = _lay(items, comps)
    r.check("clip after an over-long lay spills to a new track",
            [(name, track, rec) for name, track, rec, *_ in placed],
            [("SH010_comp.mov", 2, REC), ("SH020_comp.mov", 3, REC + 50)])
    r.check("second lay track added", result["tracks_added"], 2)
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
