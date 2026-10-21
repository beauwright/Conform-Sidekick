"""Offline tests for Recolor Markers (``ops.recolor_markers``).

Fake marker owners mimic Resolve: ``GetMarkers`` returns float frame keys,
``AddMarker`` refuses a frame that already holds a marker, and colors can be
made to fail so the restore / lost paths run.
"""

from _harness import Results

from conform_sidekick.ops import recolor_markers as rm


class FakeOwner:
    def __init__(self, markers, refuse_colors=(), refuse_delete=False):
        self.markers = {
            float(frame): dict({"duration": 1.0, "note": "", "name": "", "customData": ""}, **info)
            for frame, info in markers.items()
        }
        self.refuse_colors = set(refuse_colors)
        self.refuse_delete = refuse_delete
        self.calls = []

    def GetMarkers(self):
        return {frame: dict(info) for frame, info in self.markers.items()}

    def DeleteMarkerAtFrame(self, frame):
        self.calls.append(("delete", frame))
        if self.refuse_delete or float(frame) not in self.markers:
            return False
        del self.markers[float(frame)]
        return True

    def AddMarker(self, frame, color, name, note, duration, custom_data=""):
        self.calls.append(("add", frame, color))
        if float(frame) in self.markers or color in self.refuse_colors:
            return False
        self.markers[float(frame)] = {"color": color, "name": name, "note": note,
                                      "duration": float(duration), "customData": custom_data}
        return True

    def colors(self):
        return {int(f): m["color"] for f, m in sorted(self.markers.items())}


class FakeItem(FakeOwner):
    def __init__(self, name, start, end, markers):
        super().__init__(markers)
        self.name, self.start, self.end = name, start, end

    def GetName(self):
        return self.name

    def GetStart(self):
        return self.start

    def GetEnd(self):
        return self.end


class FakeTimeline(FakeOwner):
    def __init__(self, markers, video=(), audio=(), inout=None, start=86400):
        super().__init__(markers)
        self.video, self.audio, self.inout, self.start = list(video), list(audio), inout, start

    def GetName(self):
        return "Reel 1"

    def GetSetting(self, key):
        return ""

    def GetStartFrame(self):
        return self.start

    def GetMarkInOut(self):
        return {"video": {"in": self.inout[0], "out": self.inout[1]}} if self.inout else {}

    def GetTrackCount(self, kind):
        return len(self.video if kind == "video" else self.audio)

    def GetItemListInTrack(self, kind, index):
        return (self.video if kind == "video" else self.audio)[index - 1]


class FakeConn:
    def __init__(self, timeline):
        self.timeline = timeline

    def get_timeline(self):
        return self.timeline

    def get_project(self):
        return FakeProject()


class FakeProject:
    def GetSetting(self, key):
        return {"timelineFrameRate": "24", "timelineDropFrameTimecode": "0"}.get(key, "")


def _run(timeline, **kwargs):
    lines = []
    kwargs.setdefault("from_color", "Blue")
    kwargs.setdefault("to_color", "Green")
    result = rm.recolor_markers(FakeConn(timeline), log=lines.append, **kwargs)
    return result, "\n".join(lines)


def run():
    r = Results("recolor markers")

    r.section("selection")
    r.check("matching color", rm.wanted({"color": "Blue"}, "Blue", "Green"), True)
    r.check("other color", rm.wanted({"color": "Red"}, "Blue", "Green"), False)
    r.check("any color", rm.wanted({"color": "Red"}, rm.ANY_COLOR, "Green"), True)
    r.check("already target color", rm.wanted({"color": "Green"}, rm.ANY_COLOR, "Green"), False)
    r.check("float frame key back to int", rm._frame_arg(96.0), 96)

    r.section("timeline markers")
    tl = FakeTimeline({
        10: {"color": "Blue", "name": "VFX 01", "note": "sky", "duration": 24.0, "customData": "id7"},
        20: {"color": "Red", "name": "keep"},
        30: {"color": "Blue"},
    })
    result, log = _run(tl)
    r.check("blue -> green, red untouched", tl.colors(), {10: "Green", 20: "Red", 30: "Green"})
    r.check("name/note/duration/customData kept",
            {k: tl.markers[10.0][k] for k in ("name", "note", "duration", "customData")},
            {"name": "VFX 01", "note": "sky", "duration": 24.0, "customData": "id7"})
    r.check("counts", (result["markers_scanned"], result["recolored"], result["failed"]), (3, 2, 0))
    r.check("deleted before adding", tl.calls[:2], [("delete", 10), ("add", 10, "Green")])
    r.check("absolute frame in log", "Timeline marker 01:00:00:10 Blue -> Green 'VFX 01'" in log, True)

    tl = FakeTimeline({10: {"color": "Blue"}})
    result, log = _run(tl, dry_run=True)
    r.check("dry run changes nothing", (tl.colors(), tl.calls), ({10: "Blue"}, []))
    r.check("dry run counts", result["recolored"], 1)

    r.section("scope")
    tl = FakeTimeline({10: {"color": "Blue"}, 100: {"color": "Blue"}}, inout=(86400, 86450))
    result, _log = _run(tl, use_inout=True)
    r.check("only markers inside In/Out", tl.colors(), {10: "Green", 100: "Blue"})
    r.check("out of scope counted", result["skipped_out_of_scope"], 1)
    result, log = _run(FakeTimeline({}), use_inout=True)
    r.check("In/Out required when asked", (result["error"], "no In/Out range" in log), (True, True))

    r.section("clip markers")
    v1 = FakeItem("A001", 86400, 86500, {5: {"color": "Blue"}})
    v2 = FakeItem("B001", 86400, 86500, {5: {"color": "Blue"}})
    a1 = FakeItem("A001", 86400, 86500, {5: {"color": "Blue"}})
    late = FakeItem("A002", 90000, 90100, {5: {"color": "Blue"}})
    tl = FakeTimeline({10: {"color": "Blue"}}, video=[[v1, late], [v2]], audio=[[a1]])
    result, log = _run(tl, timeline_markers=False, clip_markers=True, track_filter_spec="1")
    r.check("timeline markers left alone", tl.colors(), {10: "Blue"})
    r.check("V1 recolored", (v1.colors(), late.colors()), ({5: "Green"}, {5: "Green"}))
    r.check("V2 filtered out", v2.colors(), {5: "Blue"})
    r.check("audio skipped by default", a1.colors(), {5: "Blue"})
    r.check("clip marker log", "V1 01:00:00:00 'A001' clip marker @5 Blue -> Green" in log, True)
    tl.inout = (86400, 86600)
    result, _log = _run(tl, timeline_markers=False, clip_markers=True, include_audio=True,
                        from_color="Green", to_color="Red", use_inout=True)
    r.check("audio included on request", a1.colors(), {5: "Blue"})
    r.check("In/Out scopes clips by overlap", (v1.colors(), late.colors()), ({5: "Red"}, {5: "Green"}))
    result, _log = _run(tl, timeline_markers=False, clip_markers=True, include_audio=True)
    r.check("audio clip recolored", a1.colors(), {5: "Green"})

    r.section("failures")
    tl = FakeTimeline({10: {"color": "Blue", "name": "n"}})
    tl.refuse_colors = {"Green"}
    result, log = _run(tl)
    r.check("refused color restores original", tl.colors(), {10: "Blue"})
    r.check("...counted as failure, not lost", (result["failed"], result["lost"]), (1, 0))
    tl = FakeTimeline({10: {"color": "Blue", "name": "n"}})
    tl.refuse_colors = {"Green", "Blue"}
    result, log = _run(tl)
    r.check("lost marker reported", (result["lost"], "[LOST]" in log, "name 'n'" in log), (1, True, True))
    tl = FakeTimeline({10: {"color": "Blue"}})
    tl.refuse_delete = True
    result, _log = _run(tl)
    r.check("undeletable marker left alone", (tl.colors(), result["failed"]), ({10: "Blue"}, 1))

    r.section("validation")
    r.check("same colors refused", _run(FakeTimeline({}), to_color="Blue")[0]["error"], True)
    r.check("nothing selected refused",
            _run(FakeTimeline({}), timeline_markers=False, clip_markers=False)[0]["error"], True)
    r.check("unknown color refused", _run(FakeTimeline({}), to_color="Orange")[0]["error"], True)
    return r.summary()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
