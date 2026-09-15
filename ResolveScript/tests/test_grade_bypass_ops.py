"""Offline tests for the Bypass Grade endpoint rules (``ops.grade_bypass``).

Fake node graphs stand in for Resolve's: enough of ``GetNumNodes`` /
``GetNodeLabel`` / ``SetNodeEnabled`` for endpoint resolution and the
per-graph disable pass.
"""

from _harness import Results

from conform_sidekick.ops import grade_bypass as gb


class FakeGraph:
    def __init__(self, labels):
        self.labels = list(labels)
        self.enabled = {i: True for i in range(1, len(self.labels) + 1)}

    def GetNumNodes(self):
        return len(self.labels)

    def GetNodeLabel(self, idx):
        return self.labels[idx - 1]

    def SetNodeEnabled(self, idx, enabled):
        self.enabled[idx] = enabled
        return True


def _bypass(graph, inp_idx="", inp_re="", out_idx="", out_re="", ignore_re=""):
    lines = []
    result = {"nodes_changed": 0, "nodes_set_failed": 0, "cancelled": False}
    snapshot = gb._bypass_graph(
        graph, "L1:clip", inp_idx, inp_re, out_idx, out_re, ignore_re,
        False, lines.append, lambda: None, result, lambda: False,
    )
    return snapshot, result, "\n".join(lines)


def run():
    r = Results("grade bypass ops")
    labels = ["XFORM", "Balance", "Look", "Deflicker", "Output"]

    r.section("validation")
    graphs = [("L1:clip", "L1:clip", FakeGraph(labels))]
    lines = []
    err = gb._validate_bypass_endpoints(graphs, "", "", "", "", lines.append)
    r.check("all blank -> allowed (disable everything)", err, None)
    r.check("...and says so", any("disable every node" in l for l in lines), True)
    err = gb._validate_bypass_endpoints(graphs, "1", "", "", "", lines.append)
    r.check("input only -> refused", "leave all four blank" in (err or ""), True)
    err = gb._validate_bypass_endpoints(graphs, "", "", "", "Output", lines.append)
    r.check("output only -> refused", "Specify both" in (err or ""), True)
    err = gb._validate_bypass_endpoints(graphs, "1", "", "", "Nope", lines.append)
    r.check("output matches nothing -> refused", "did not match" in (err or ""), True)
    err = gb._validate_bypass_endpoints(graphs, "", "XFORM", "5", "", lines.append)
    r.check("input regex + output index -> ok", err, None)
    r.check("endpoints_blank treats whitespace as blank", gb.endpoints_blank(" ", None, "", "\t"), True)

    r.section("disable everything")
    g = FakeGraph(labels)
    snap, result, log = _bypass(g)
    r.check("every node disabled", [i for i, on in g.enabled.items() if not on], [1, 2, 3, 4, 5])
    r.check("snapshot records all five", (snap["disabled_indices"], snap["keep_indices"]), ([1, 2, 3, 4, 5], []))
    r.check("log explains why", "no color input/output set; disabling all 5" in log, True)

    g = FakeGraph(labels)
    snap, result, log = _bypass(g, ignore_re="Deflicker")
    r.check("leave-alone still honoured", [i for i, on in g.enabled.items() if not on], [1, 2, 3, 5])
    r.check("kept node in snapshot", (snap["keep_indices"], snap["ignore_indices"]), ([4], [4]))

    r.section("normal endpoints unchanged")
    g = FakeGraph(labels)
    snap, result, log = _bypass(g, inp_re="XFORM", out_idx="5")
    r.check("only the middle nodes go off", [i for i, on in g.enabled.items() if not on], [2, 3, 4])
    r.check("keeps input and output", snap["keep_indices"], [1, 5])
    r.check("nodes_changed counted", result["nodes_changed"], 3)
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
