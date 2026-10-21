"""Offline tests for Color Groups from Avid LUTs (``ops.avid_lut_groups``).

Bin clips are built straight from ``_USER`` attribute dicts (the shape pyavb
hands back), and fake Resolve objects cover just enough of Project / Timeline /
TimelineItem / MediaPoolItem / ColorGroup for matching and assignment.

Set ``CS_AVID_TEST_BIN`` to a real ``.avb`` to also smoke-test the bin reader.
"""

import os

from _harness import Results

from conform_sidekick.ops import avid_lut_groups as alg


def _clip(name, column="", camera_id="", camera_file="", tape="", camera_custom=""):
    user = {"LUT": column, "lut3DID": camera_id, "clipName": camera_file}
    if camera_custom:
        user["lut3DFilename"] = camera_custom
    return alg.bin_clip_from_attrs(name, user, tape)


INT = "Quit-Clinic-Int_v01_65p_LogC4.cube"
EXT = "Quit-Clinic-Ext-Day_v01_65p_LogC4.cube"
REC709 = "arrimxf_llk_3d_lut_rec709"

BIN = [
    _clip("101 10-3_A", INT, REC709, "A_0018C003_260921_161258_p1CQI", "A_0018_1CQI"),
    _clip("101 10-4_A", INT, REC709, "A_0018C004_260921_162000_p1CQI", "A_0018_1CQI"),
    _clip("101 12-1_A", EXT, REC709, "A_0019C001_260921_170000_p1CQI", "A_0019_1CQI"),
    _clip("101 12-2_A", "", REC709, "A_0019C002_260921_171000_p1CQI", "A_0019_1CQI"),
    _clip("101 1-2_A", "", REC709, "A_0003C001_260910_110000_p1CQI", "A_0003_1CQI"),
    _clip("101 1 cart-1_D", "", "", "", "D001"),
]


class FakeGroup:
    def __init__(self, name):
        self.name = name

    def GetName(self):
        return self.name


class FakeMpi:
    def __init__(self, props):
        self.props = props

    def GetClipProperty(self, key):
        return self.props.get(key, "")


class FakeItem:
    def __init__(self, name, start, file_name="", clip_name="", reel="", group=None):
        self.name = name
        self.start = start
        self.group = group
        self.mpi = FakeMpi({"File Name": file_name, "Clip Name": clip_name or file_name,
                            "Reel Name": reel})

    def GetName(self):
        return self.name

    def GetStart(self):
        return self.start

    def GetMediaPoolItem(self):
        return self.mpi

    def GetColorGroup(self):
        return self.group

    def AssignToColorGroup(self, group):
        self.group = group
        return True


class FakeTimeline:
    def __init__(self, tracks):
        self.tracks = tracks

    def GetName(self):
        return "QTR 101 v12"

    def GetTrackCount(self, kind):
        return len(self.tracks) if kind == "video" else 0

    def GetItemListInTrack(self, kind, index):
        return self.tracks[index - 1]

    def GetSetting(self, key):
        return {"timelineFrameRate": "24", "timelineDropFrameTimecode": "0"}.get(key, "")


class FakeProject:
    def __init__(self, group_names):
        self.groups = [FakeGroup(n) for n in group_names]
        self.timeline = None

    def GetColorGroupsList(self):
        return list(self.groups)

    def AddColorGroup(self, name):
        group = FakeGroup(name)
        self.groups.append(group)
        return group

    def GetSetting(self, key):
        return self.timeline.GetSetting(key)


class FakeConn:
    def __init__(self, project, timeline):
        project.timeline = timeline
        self.project = project
        self.timeline = timeline

    def get_project(self):
        return self.project

    def get_timeline(self):
        return self.timeline


def _timeline_items(clinic_group):
    return [
        FakeItem("A_0018C003", 86400, "A_0018C003_260921_161258_p1CQI.mxf", reel="A_0018_1CQI"),
        FakeItem("A_0019C001", 86500, "A_0019C001_260921_170000_p1CQI.mxf", reel="A_0019_1CQI"),
        # Already graded into a group by hand: must be left alone.
        FakeItem("A_0018C004", 86600, "A_0018C004_260921_162000_p1CQI.mxf",
                 reel="A_0018_1CQI", group=clinic_group),
        # Dailies conform: only the Avid clip name lines up.
        FakeItem("101 1-2_A", 86700, "101 1-2_A.mov"),
        FakeItem("Pickup", 86800, "B_0099C001_261001_101010_p1C7U.mxf", reel="B_0099_1C7U"),
    ]


def run():
    r = Results("avid lut groups")
    every = list(alg.MATCH_METHODS)

    r.section("names")
    r.check("media extension stripped", alg.name_key("A_0018C003_p1CQI.MXF"), "a_0018c003_p1cqi")
    r.check("non-media dot kept", alg.name_key("101 10.5-1_A"), "101 10.5-1_a")
    r.check("lut stem", alg.lut_stem(INT), "Quit-Clinic-Int_v01_65p_LogC4")
    r.check("lut core drops version and tail", alg.lut_core(INT), "Quit-Clinic-Int")
    r.check("unversioned lut core is the stem", alg.lut_core("ShowLook.cube"), "ShowLook")

    r.section("group suggestions")
    groups = ["Clinic Int", "CLINIC EXT DAY", "Int", "Show"]
    r.check("contained, punctuation-insensitive", alg.suggest_group(INT, groups), "Clinic Int")
    r.check("case-insensitive", alg.suggest_group(EXT, groups), "CLINIC EXT DAY")
    r.check("short names never claim a LUT", alg.suggest_group(INT, ["Int"]), "")
    r.check("exact stem beats contained", alg.suggest_group(
        INT, ["Clinic Int", "Quit-Clinic-Int_v01_65p_LogC4"]), "Quit-Clinic-Int_v01_65p_LogC4")
    r.check("nothing close", alg.suggest_group(REC709, groups), "")

    r.section("LUT source priority")
    blank_column = BIN[3]
    custom = _clip("x", "", REC709, camera_custom="Quit-Clinic-Ext-Day_v01.cube")
    r.check("column first", alg.clip_lut(BIN[0], alg.LUT_SOURCE_COLUMN_THEN_CAMERA), (INT, "column"))
    r.check("falls back to camera", alg.clip_lut(blank_column, alg.LUT_SOURCE_COLUMN_THEN_CAMERA),
            (REC709, "camera"))
    r.check("camera first", alg.clip_lut(BIN[0], alg.LUT_SOURCE_CAMERA_THEN_COLUMN), (REC709, "camera"))
    r.check("column only, blank", alg.clip_lut(blank_column, alg.LUT_SOURCE_COLUMN_ONLY), ("", ""))
    r.check("camera only", alg.clip_lut(BIN[0], alg.LUT_SOURCE_CAMERA_ONLY), (REC709, "camera"))
    r.check("custom camera LUT beats stock id", custom["camera_lut"], "Quit-Clinic-Ext-Day_v01.cube")
    r.check("bin luts, column only", alg.bin_luts(BIN, alg.LUT_SOURCE_COLUMN_ONLY), [EXT, INT])

    r.section("matching")
    index = alg.BinIndex(BIN)
    col = alg.LUT_SOURCE_COLUMN_ONLY
    hit = alg.resolve_lut(index, {"file_name": "A_0018C003_260921_161258_p1CQI.mxf"}, every, col)
    r.check("camera file", (hit["status"], hit["method"], hit["lut"]), ("matched", "camera_file", INT))
    hit = alg.resolve_lut(index, {"file_name": "A_0018C003_260921_161258_p1CQI_S001.mxf"}, every, col)
    r.check("spanned segment matches its camera file", (hit["status"], hit["lut"]), ("matched", INT))
    r.check("segment keys", alg.camera_file_keys("X_p1CQI_S002.mxf"), ["x_p1cqi_s002", "x_p1cqi"])
    r.check("leading space in a name ignored", alg.name_key(" 101 1-2_B"), "101 1-2_b")
    hit = alg.resolve_lut(index, {"reel_name": "a_0018_1cqi"}, [alg.MATCH_CAMERA_ROLL], col)
    r.check("roll with one LUT", (hit["status"], hit["lut"]), ("matched", INT))
    hit = alg.resolve_lut(index, {"reel_name": "A_0019_1CQI"}, [alg.MATCH_CAMERA_ROLL],
                          alg.LUT_SOURCE_COLUMN_THEN_CAMERA)
    r.check("roll spanning LUTs is ambiguous", (hit["status"], hit["luts"]), ("ambiguous", sorted([EXT, REC709])))
    hit = alg.resolve_lut(index, {"reel_name": "A_0019_1CQI",
                                  "file_name": "A_0019C001_260921_170000_p1CQI.mov"},
                          [alg.MATCH_CAMERA_ROLL, alg.MATCH_CAMERA_FILE], col)
    r.check("ambiguous roll falls through to file", (hit["status"], hit["method"], hit["lut"]),
            ("matched", "camera_file", EXT))
    hit = alg.resolve_lut(index, {"clip_name": "101 1-2_A.mov"}, every, col)
    r.check("matched clip without LUT", (hit["status"], hit["bin_clip"]), ("no_lut", "101 1-2_A"))
    hit = alg.resolve_lut(index, {"clip_name": "101 1-2_A.mov"}, every, alg.LUT_SOURCE_COLUMN_THEN_CAMERA)
    r.check("...unless camera fallback is on", (hit["status"], hit["lut"]), ("matched", REC709))
    hit = alg.resolve_lut(index, {"file_name": "A_0018C003_260921_161258_p1CQI.mxf"},
                          [alg.MATCH_CLIP_NAME], col)
    r.check("disabled methods are not tried", hit["status"], "no_match")

    r.section("mapping targets")
    mapping = {INT: "Clinic Int", EXT: alg.NEW_GROUP, REC709: ""}
    r.check("existing group", alg.mapping_target(mapping, INT), ("Clinic Int", False))
    r.check("new group named after LUT", alg.mapping_target(mapping, EXT),
            ("Quit-Clinic-Ext-Day_v01_65p_LogC4", True))
    r.check("explicitly unassigned", alg.mapping_target(mapping, REC709), ("", False))

    r.section("group dropdown events")
    from conform_sidekick.features import avid_lut_groups as panel
    stem = alg.lut_stem(INT)
    r.check("no-group entry", panel.choice_value(panel.NO_GROUP), "")
    r.check("new-group entry", panel.choice_value(panel.NEW_GROUP_PREFIX + stem), alg.NEW_GROUP)
    r.check("existing group entry", panel.choice_value("Clinic Int"), "Clinic Int")
    r.check("echo of current choice ignored", panel.same_choice(INT, "Clinic Int", "Clinic Int"), True)
    r.check("echo of unassigned ignored", panel.same_choice(INT, "", ""), True)
    r.check("new group == existing group of that name",
            panel.same_choice(INT, alg.NEW_GROUP, stem), True)
    r.check("real change saves", panel.same_choice(INT, "Clinic Int", ""), False)

    r.section("assign (dry run)")
    project = FakeProject(["Clinic Int", "Night Ext"])
    clinic = project.groups[0]
    items = _timeline_items(clinic)
    conn = FakeConn(project, FakeTimeline([items]))
    lines = []
    result = alg.assign_color_groups(conn, BIN, mapping, every, col, dry_run=True, log=lines.append)
    log = "\n".join(lines)
    r.check("would assign two", result["assigned"], 2)
    r.check("would create one group", result["groups_created"], 1)
    r.check("nothing actually grouped", [i.group for i in items if i is not items[2]], [None] * 4)
    r.check("no group actually created", len(project.groups), 2)
    r.check("already grouped skipped", result["already_grouped"], 1)
    r.check("clip without LUT counted", result["no_lut"], 1)
    r.check("pickup not in bin", result["no_match"], 1)
    r.check("timecode in log", "V1 01:00:00:00 A_0018C003" in log, True)

    r.section("assign")
    project = FakeProject(["Clinic Int", "Night Ext"])
    clinic = project.groups[0]
    items = _timeline_items(clinic)
    conn = FakeConn(project, FakeTimeline([items]))
    result = alg.assign_color_groups(conn, BIN, mapping, every, col, log=lambda line: None)
    r.check("assigned", result["assigned"], 2)
    r.check("first clip in mapped group", items[0].group.GetName(), "Clinic Int")
    r.check("second clip in created group", items[1].group.GetName(), "Quit-Clinic-Ext-Day_v01_65p_LogC4")
    r.check("group created once", [g.GetName() for g in project.groups],
            ["Clinic Int", "Night Ext", "Quit-Clinic-Ext-Day_v01_65p_LogC4"])
    r.check("hand-grouped clip untouched", items[2].group is clinic, True)

    result = alg.assign_color_groups(conn, BIN, mapping, every, col, log=lambda line: None)
    r.check("re-run skips everything now grouped", (result["assigned"], result["already_grouped"]), (0, 3))

    project = FakeProject(["Clinic Int"])
    conn = FakeConn(project, FakeTimeline([_timeline_items(None)]))
    result = alg.assign_color_groups(conn, BIN, {INT: "Clinic Int"}, every, col, log=lambda line: None)
    r.check("unmapped LUT left alone", (result["assigned"], result["unmapped"]), (2, 1))
    result = alg.assign_color_groups(conn, BIN, {}, [], col, log=lambda line: None)
    r.check("no match method is an error", result["error"], True)

    r.section("real bin")
    path = os.environ.get("CS_AVID_TEST_BIN", "")
    if path and os.path.isfile(path):
        import conform_sidekick  # noqa: F401  (puts _vendor on sys.path)
        clips = alg.read_avid_bin(path)
        r.check("read some master clips", len(clips) > 0, True)
        r.check("camera file names present", any(c["camera_file"] for c in clips), True)
        r.check("tapes present", any(c["tape"] for c in clips), True)
    else:
        r.skip("read_avid_bin", "set CS_AVID_TEST_BIN to an .avb")
    return r.summary()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
