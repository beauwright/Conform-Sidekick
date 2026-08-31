"""End-to-end checks for ``ops.source_tc`` against a fake media pool.

Stands in enough of the Resolve API to exercise scanning, filtering, applying,
verifying and reverting without a running Resolve. The fakes deliberately
reproduce two behaviours observed on real projects:

* ``SetClipProperty`` can return ``True`` without the value sticking, so the op
  re-reads and reports a mismatch instead of trusting the return value.
* The ``Usage`` clip property only reflects the *currently open* timeline. With
  no timeline open it read ``'0'`` for 5248 of 5249 clips on a 48-timeline
  project while 75 zero-TC clips were genuinely in use. ``inuse.mov`` below
  therefore carries ``Usage == '0'`` while living in a fake timeline: the
  exclusion has to come from the computed usage map, not the property.
"""

from _harness import Results, pin_timezone

from conform_sidekick.ops import source_tc as st

QUIET = lambda *a, **k: None  # noqa: E731


class FakeItem:
    def __init__(self, name, uid, props, write_ok=True, sticky=True):
        self.name, self.uid, self.props = name, uid, dict(props)
        self.write_ok, self.sticky = write_ok, sticky
        self.writes = []

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetClipProperty(self, key=None):
        return dict(self.props) if key is None else self.props.get(key, "")

    def SetClipProperty(self, key, value):
        self.writes.append((key, value))
        if self.write_ok and self.sticky:
            self.props[key] = value
        return self.write_ok


class FakeFolder:
    def __init__(self, clips):
        self._clips = clips

    def GetClipList(self):
        return self._clips

    def GetSubFolderList(self):
        return []

    def GetUniqueId(self):
        return "folder-root"

    def GetName(self):
        return "Master"


class FakeMediaFolder:
    def __init__(self, folder):
        self.folder, self.bin_location = folder, "/"


class FakeTimelineItem:
    def __init__(self, media):
        self._media = media

    def GetMediaPoolItem(self):
        return self._media


class FakeTimeline:
    def __init__(self, items):
        self._items = items

    def GetTrackCount(self, kind):
        return 1 if kind == "video" else 0

    def GetItemListInTrack(self, kind, index):
        return self._items if kind == "video" else []


class FakePool:
    def __init__(self, folder):
        self._folder = folder

    def GetCurrentFolder(self):
        return self._folder


class FakeProject:
    def __init__(self, folder, timelines=()):
        self._pool = FakePool(folder)
        self._timelines = list(timelines)

    def GetMediaPool(self):
        return self._pool

    def GetUniqueId(self):
        return "proj-1"

    def GetName(self):
        return "Fake Project"

    def GetTimelineCount(self):
        return len(self._timelines)

    def GetTimelineByIndex(self, index):
        return self._timelines[index - 1]


class FakeConn:
    def __init__(self, project):
        self._project = project

    def get_project(self):
        return self._project


class FakeApi:
    def __init__(self, folder):
        self._entries = [FakeMediaFolder(folder)]

    def get_all_folders(self, project):
        return self._entries


def build():
    """A pool covering every filter branch. Returns (conn, api, {uid: item})."""
    zero, created = st.ZERO_TC, "Tue Dec 02 2025 05:44:53"
    items = [
        FakeItem("video.mov", "u-video", {
            "Start TC": zero, "File Path": "/x/video.mov", "Type": "Video + Audio",
            "Usage": "0", "Date Created": created, "FPS": 24.0}),
        FakeItem("still.jpg", "u-still", {
            "Start TC": zero, "File Path": "/x/still.jpg", "Type": "Still",
            "Usage": "0", "Date Created": created, "FPS": 24.0}),
        FakeItem("sound.wav", "u-audio", {
            "Start TC": zero, "File Path": "/x/sound.wav", "Type": "Audio",
            "Usage": "0", "Date Created": created, "FPS": 24.0}),
        FakeItem("compound", "u-comp", {
            "Start TC": zero, "File Path": "", "Type": "Compound",
            "Usage": "0", "Date Created": created, "FPS": 24.0}),
        # In a timeline, but Usage reports 0 - see the module docstring.
        FakeItem("inuse.mov", "u-inuse", {
            "Start TC": zero, "File Path": "/x/inuse.mov", "Type": "Video",
            "Usage": "0", "Date Created": created, "FPS": 24.0}),
        FakeItem("nodate.mov", "u-nodate", {
            "Start TC": zero, "File Path": "/x/nodate.mov", "Type": "Video",
            "Usage": "0", "Date Created": "", "FPS": 24.0}),
        FakeItem("hasTC.mov", "u-hastc", {
            "Start TC": "01:00:00:00", "File Path": "/x/hasTC.mov", "Type": "Video",
            "Usage": "0", "Date Created": created, "FPS": 24.0}),
    ]
    folder = FakeFolder(items)
    by_uid = {i.uid: i for i in items}
    timeline = FakeTimeline([FakeTimelineItem(by_uid["u-inuse"])])
    return FakeConn(FakeProject(folder, [timeline])), FakeApi(folder), by_uid


def run():
    r = Results("source_tc ops")
    pinned = pin_timezone()

    r.section("scanning and filters")
    conn, api, by_uid = build()
    res = st.set_source_tc(conn, api, dry_run=True, log=QUIET)
    r.check("scans every clip", res["scanned"], 7)
    r.check("finds the zero-TC ones", res["zero_tc"], 6)
    r.check("defaults leave only real footage", res["candidates"], 1)
    r.check("dry run plans it", res["planned"], 1)
    r.check("dry run writes nothing", [i.writes for i in by_uid.values()], [[]] * 7)

    conn, api, by_uid = build()
    res = st.set_source_tc(conn, api, dry_run=True, include_images=True,
                           include_audio=True, include_in_timeline=True, log=QUIET)
    r.check("opt-ins widen the set", res["candidates"], 4)
    r.check("in-timeline clips are counted for the warning",
            res["in_timeline_touched"], 1)

    r.section("timeline usage is computed, not read from Usage")
    conn, api, by_uid = build()
    r.check("the property claims it is unused", by_uid["u-inuse"].props["Usage"], "0")
    r.check("the computed map finds it anyway",
            st.timeline_usage_ids(conn, log=QUIET), {"u-inuse"})
    r.check("so it is excluded by default",
            st.set_source_tc(conn, api, dry_run=True, log=QUIET)["candidates"], 1)
    r.check("and included on opt-in",
            st.set_source_tc(conn, api, dry_run=True, include_in_timeline=True,
                             log=QUIET)["candidates"], 2)

    r.section("applying")
    conn, api, by_uid = build()
    res = st.set_source_tc(conn, api, dry_run=False, log=QUIET)
    r.check("applies the candidate", res["applied"], 1)
    r.check("records the id for revert", res["applied_ids"], ["u-video"])
    r.check("leaves filtered clips alone",
            by_uid["u-still"].props["Start TC"], st.ZERO_TC)
    if not pinned:
        r.skip("derived value", "time.tzset() unavailable on this platform")
    else:
        r.check("writes the derived timecode",
                by_uid["u-video"].props["Start TC"], "05:44:53:00")
        conn, api, by_uid = build()
        st.set_source_tc(conn, api, dry_run=False, zone_name="UTC", log=QUIET)
        r.check("timezone changes what is written",
                by_uid["u-video"].props["Start TC"], "12:44:53:00")

    r.section("failure handling")
    conn, api, by_uid = build()
    by_uid["u-video"].write_ok = False
    res = st.set_source_tc(conn, api, dry_run=False, log=QUIET)
    r.check("a False return counts as failure", (res["applied"], res["failed"]), (0, 1))
    r.check("nothing is recorded for revert", res["applied_ids"], [])

    conn, api, by_uid = build()
    by_uid["u-video"].sticky = False  # returns True, value does not stick
    res = st.set_source_tc(conn, api, dry_run=False, log=QUIET)
    r.check("read-back mismatch is caught",
            (res["applied"], res["verify_mismatch"]), (0, 1))

    conn, api, by_uid = build()
    res = st.set_source_tc(conn, api, dry_run=False, zone_name="Mars/Olympus", log=QUIET)
    r.check("an unusable timezone aborts", res["error"], True)
    r.check("and writes nothing first", by_uid["u-video"].writes, [])

    r.section("revert and cancel")
    conn, api, by_uid = build()
    applied = st.set_source_tc(conn, api, dry_run=False, log=QUIET)["applied_ids"]
    rev = st.revert_source_tc(conn, api, applied, log=QUIET)
    r.check("reverts what was applied", rev["reverted"], len(applied))
    r.check("restores the sentinel", by_uid["u-video"].props["Start TC"], st.ZERO_TC)
    r.check("reports ids missing from the project",
            st.revert_source_tc(conn, api, ["not-here"], log=QUIET)["not_found"], 1)

    conn, api, by_uid = build()
    res = st.set_source_tc(conn, api, dry_run=False, log=QUIET,
                           should_cancel=lambda: True)
    r.check("cancelling writes nothing",
            (res["cancelled"], by_uid["u-video"].writes), (True, []))

    return r.summary()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
