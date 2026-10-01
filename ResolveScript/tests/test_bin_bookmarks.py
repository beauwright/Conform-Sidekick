"""Offline tests for ``ops.bin_bookmarks`` against a fake bin tree.

The fakes model what was observed on Resolve Studio 21.0.4: a bin keeps its
unique id through a rename or a move, and ``SetCurrentFolder`` returns True.
"""

from _harness import Results

from conform_sidekick.ops import bin_bookmarks as bb


class FakeFolder:
    def __init__(self, name, uid, subs=()):
        self.name, self.uid, self.subs = name, uid, list(subs)

    def GetName(self):
        return self.name

    def GetUniqueId(self):
        return self.uid

    def GetSubFolderList(self):
        return self.subs


class FakeMediaPool:
    def __init__(self, root):
        self.root, self.current = root, root

    def GetRootFolder(self):
        return self.root

    def GetCurrentFolder(self):
        return self.current

    def SetCurrentFolder(self, folder):
        self.current = folder
        return True


def _pool():
    day1 = FakeFolder("Day 01", "d1")
    day2 = FakeFolder("Day 02", "d2")
    footage = FakeFolder("FOOTAGE", "f", [day1, day2])
    seq = FakeFolder("_SEQ", "s")
    root = FakeFolder("Master", "r", [footage, seq])
    return FakeMediaPool(root), root, footage, seq, day1, day2


def run():
    r = Results("bin bookmarks")
    pool, root, footage, seq, day1, day2 = _pool()

    r.section("walk")
    bins = bb.walk_bins(pool)
    r.check("paths, parents first", [p for _f, p in bins],
            ["/", "/FOOTAGE", "/_SEQ", "/FOOTAGE/Day 01", "/FOOTAGE/Day 02"])
    r.check("names", [bb.bin_name(p) for p in ("/", "/_SEQ", "/FOOTAGE/Day 01")],
            ["Master", "_SEQ", "Day 01"])

    r.section("current bin")
    r.check("root", bb.current_bin(pool)[1], "/")
    pool.current = day2
    r.check("nested", bb.current_bin(pool, bins)[1], "/FOOTAGE/Day 02")

    r.section("list edits")
    marks, added = bb.add([], "d2", "/FOOTAGE/Day 02")
    marks, _ = bb.add(marks, "s", "/_SEQ")
    marks, _ = bb.add(marks, "r", "/")
    r.check("added", (added, [b["id"] for b in marks]), (True, ["d2", "s", "r"]))
    r.check("no duplicate", bb.add(marks, "s", "/_SEQ")[1], False)
    r.check("move up", [b["id"] for b in bb.move(marks, "r", -1)], ["d2", "r", "s"])
    r.check("move down", [b["id"] for b in bb.move(marks, "d2", 1)], ["s", "d2", "r"])
    r.check("move past the end is a no-op", bb.move(marks, "r", 1), marks)
    r.check("remove", [b["id"] for b in bb.remove(marks, "s")], ["d2", "r"])

    r.section("go to")
    r.check("jumps", bb.go_to(pool, marks[1]), (True, "/_SEQ"))
    r.check("media pool moved", pool.current is seq, True)

    r.section("rename and move keep the bookmark")
    day2.name = "Day 02 Selects"
    footage.subs.remove(day2)
    seq.subs.append(day2)
    bins = bb.walk_bins(pool)
    refreshed, missing = bb.refresh(marks, bins)
    r.check("path follows the bin", refreshed[0], {"id": "d2", "path": "/_SEQ/Day 02 Selects"})
    r.check("nothing missing", missing, set())
    r.check("go to finds it by id", bb.go_to(pool, marks[0]), (True, "/_SEQ/Day 02 Selects"))
    r.check("media pool moved to it", pool.current is day2, True)

    r.section("ids changed (restored archive): path fallback")
    stale = [{"id": "old-id", "path": "/FOOTAGE/Day 01"}]
    refreshed, missing = bb.refresh(stale, bins)
    r.check("re-keyed onto the live bin", (refreshed, missing),
            ([{"id": "d1", "path": "/FOOTAGE/Day 01"}], set()))

    r.section("deleted bin")
    seq.subs.remove(day2)
    pool.current = root
    bins = bb.walk_bins(pool)
    gone = {"id": "d2", "path": "/_SEQ/Day 02 Selects"}
    refreshed, missing = bb.refresh([gone, marks[1]], bins)
    r.check("kept in the list, flagged missing", (refreshed[0], missing), (gone, {"d2"}))
    r.check("go to reports it", bb.go_to(pool, gone, bins), (False, None))
    r.check("media pool left alone", pool.current is root, True)

    r.section("loading saved state")
    r.check("junk tolerated", bb.clean(None), [])
    r.check("bad entries and duplicates dropped",
            bb.clean([{"id": "a", "path": "/A"}, "x", {"id": "", "path": "/B"},
                      {"id": "a", "path": "/A2"}, {"id": "c"}]),
            [{"id": "a", "path": "/A"}])
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
