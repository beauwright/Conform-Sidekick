"""Bypass / restore the color grade on the current clip in the Color page.

Disables every node except the configured color input and output endpoints on
``Timeline.GetCurrentVideoItem()``. Optionally includes the clip's shared
Color Group pre-clip and post-clip node graphs (see ``TimelineItem.GetColorGroup``).

Restore re-enables only the nodes that were turned off by the last bypass
(stored in feature state), so nodes that were already disabled before bypass
are not touched on restore.

The Resolve scripting README documents ``Graph.SetNodeEnabled`` but not
``GetNodeEnabled``, so prior enabled state cannot be read from the API.
Collapsed node groups inside a single graph are not exposed by the API either;
only top-level nodes from ``Graph.GetNumNodes()`` are reachable.
"""

from .. import timeline_filters as tf
from .bulk_nodes import _target_indices_for_graph


def _noop():
    pass


def _clip_key(item):
    parts = []
    try:
        mpi = item.GetMediaPoolItem()
        if mpi is not None:
            pool_id = mpi.GetMediaPoolItemId()
            if pool_id:
                parts.append(f"pool:{pool_id}")
    except Exception:
        pass
    try:
        uid = item.GetUniqueId()
        if uid:
            parts.append(f"uid:{uid}")
    except Exception:
        pass
    if not parts:
        try:
            name = item.GetName() or ""
            start = item.GetStart()
            parts.append(f"name:{name}@{start}")
        except Exception:
            pass
    return "|".join(parts)


def _clip_label(item):
    try:
        name = item.GetName() or ""
    except Exception:
        name = ""
    try:
        start = item.GetStart()
        end = item.GetEnd()
        return f"{name} [{start}-{end}]"
    except Exception:
        return name or "(unnamed clip)"


def _color_group_name(color_group):
    try:
        return color_group.GetName() or "(unnamed group)"
    except Exception:
        return "(unnamed group)"


def _collect_graphs(item, layers, include_color_group, log):
    """Return ``[(graph_key, location_label, graph), ...]`` to visit."""
    graphs = []
    for layer_idx in layers:
        location = f"L{layer_idx} clip"
        try:
            graph = item.GetNodeGraph(layer_idx)
        except Exception as exc:
            log(f"  [SKIP] {location}: GetNodeGraph raised: {exc}")
            continue
        if graph is None:
            log(f"  [SKIP] {location}: no graph.")
            continue
        graphs.append((f"L{layer_idx}:clip", location, graph))

    if not include_color_group:
        return graphs

    color_group = None
    try:
        color_group = item.GetColorGroup()
    except Exception as exc:
        log(f"  [warn] GetColorGroup raised: {exc}")

    if color_group is None:
        log(
            "  [warn] Include color group is checked but this clip is not "
            "assigned to a color group."
        )
        return graphs

    group_name = _color_group_name(color_group)
    pre_graph = None
    post_graph = None
    try:
        pre_graph = color_group.GetPreClipNodeGraph()
    except Exception as exc:
        log(f"  [warn] Color group '{group_name}' GetPreClipNodeGraph raised: {exc}")
    try:
        post_graph = color_group.GetPostClipNodeGraph()
    except Exception as exc:
        log(f"  [warn] Color group '{group_name}' GetPostClipNodeGraph raised: {exc}")

    if pre_graph is not None:
        graphs.append(
            ("group_pre", f"Color group '{group_name}' pre-clip", pre_graph)
        )
    if post_graph is not None:
        graphs.append(
            ("group_post", f"Color group '{group_name}' post-clip", post_graph)
        )
    return graphs


def _snapshot_graph_entries(bypass_snapshot):
    """Normalize stored bypass data to ``{graph_key: layer_data}``."""
    graphs = bypass_snapshot.get("graphs")
    if isinstance(graphs, dict) and graphs:
        return graphs

    legacy_layers = bypass_snapshot.get("layers") or {}
    if not isinstance(legacy_layers, dict):
        return {}

    out = {}
    for layer_key, layer_data in legacy_layers.items():
        if not isinstance(layer_data, dict):
            continue
        if "disabled_indices" in layer_data:
            out[f"L{layer_key}:clip"] = layer_data
    return out


def _resolve_endpoint(
    graph,
    index_spec,
    label_regex,
    role,
    log,
    location,
    allow_no_match=False,
):
    index_set, index_err = tf.parse_int_spec(index_spec, what=f"{role} index")
    if index_err is not None:
        return None, 0, index_err

    label_pattern, label_err = tf.compile_regex(label_regex)
    if label_err is not None:
        return None, 0, f"Invalid {role} label regex: {label_err}"

    if index_set is None and label_pattern is None:
        if allow_no_match:
            try:
                total = int(graph.GetNumNodes() or 0)
            except Exception:
                total = 0
            return set(), total, None
        return None, 0, (
            f"No {role} node specified. Set either a node number or a label regex."
        )

    targets, total = _target_indices_for_graph(
        graph, index_set, label_pattern, log, location
    )
    if total <= 0:
        if allow_no_match:
            return set(), 0, None
        return None, 0, f"{location}: empty node graph."
    if not targets:
        if allow_no_match:
            return set(), total, None
        if label_pattern is not None:
            return None, total, (
                f"{location}: no node label matches /{label_regex}/ "
                f"(graph has {total} node(s))."
            )
        missing = sorted(i for i in (index_set or []) if i < 1 or i > total)
        return None, total, (
            f"{location}: requested {role} index(es) {sorted(index_set)} "
            f"but graph has only {total} node(s)."
            + (f" Out of range: {missing}." if missing else "")
        )

    if len(targets) > 1:
        log(
            f"  [warn] {location}: {role} matched {len(targets)} node(s) "
            f"{targets}; all will be kept enabled."
        )
    return set(targets), total, None


def _validate_bypass_endpoints(
    graphs,
    input_index_spec,
    input_label_regex,
    output_index_spec,
    output_label_regex,
    log,
):
    """Ensure input/output are specified and match somewhere across all graphs."""
    index_set, index_err = tf.parse_int_spec(input_index_spec, what="input index")
    if index_err is not None:
        return f"Color input index: {index_err}"

    label_pattern, label_err = tf.compile_regex(input_label_regex)
    if label_err is not None:
        return f"Invalid color input label regex: {label_err}"

    out_index_set, out_index_err = tf.parse_int_spec(
        output_index_spec, what="output index"
    )
    if out_index_err is not None:
        return f"Color output index: {out_index_err}"

    out_label_pattern, out_label_err = tf.compile_regex(output_label_regex)
    if out_label_err is not None:
        return f"Invalid color output label regex: {out_label_err}"

    has_input = index_set is not None or label_pattern is not None
    has_output = out_index_set is not None or out_label_pattern is not None
    if not has_input or not has_output:
        return (
            "Specify both a color input and a color output (node number and/or "
            "label regex for each)."
        )

    input_hits = 0
    output_hits = 0
    for _key, location, graph in graphs:
        input_set, _total, err = _resolve_endpoint(
            graph,
            input_index_spec,
            input_label_regex,
            "Color input",
            log,
            location,
            allow_no_match=True,
        )
        if err is not None:
            return err
        output_set, _total, err = _resolve_endpoint(
            graph,
            output_index_spec,
            output_label_regex,
            "Color output",
            log,
            location,
            allow_no_match=True,
        )
        if err is not None:
            return err
        input_hits += len(input_set)
        output_hits += len(output_set)

    if input_hits == 0:
        return (
            "Color input did not match any node on the graphs being visited. "
            "Node numbers are per graph (clip, pre-clip group, post-clip group); "
            "use label regex when endpoints live on different graphs."
        )
    if output_hits == 0:
        return (
            "Color output did not match any node on the graphs being visited. "
            "Node numbers are per graph (clip, pre-clip group, post-clip group); "
            "use label regex when endpoints live on different graphs."
        )
    return None


def _switch_to_color_page(resolve, log, dry_run):
    if dry_run:
        return None, False
    original_page = None
    page_switched = False
    try:
        original_page = resolve.GetCurrentPage()
    except Exception:
        original_page = None
    if original_page != "color":
        try:
            page_switched = bool(resolve.OpenPage("color"))
        except Exception:
            page_switched = False
        if page_switched:
            log("  Switched to Color page (required for SetNodeEnabled).")
        else:
            log(
                "  [warn] Could not switch to Color page; "
                "node changes may silently no-op."
            )
    return original_page, page_switched


def _restore_page(resolve, original_page, page_switched, log):
    if page_switched and original_page and original_page != "color":
        try:
            if resolve.OpenPage(original_page):
                log(f"  Restored {original_page} page.")
        except Exception:
            pass


def _restore_graph(graph, location, graph_data, dry_run, log, pump, result, should_cancel):
    disabled_indices = graph_data.get("disabled_indices") or []
    if not disabled_indices:
        log(f"  [SKIP] {location}: stored bypass list is empty.")
        return

    keep_indices = graph_data.get("keep_indices") or []
    log(
        f"  {location}: restoring {len(disabled_indices)} node(s) "
        f"disabled by bypass (keeping {sorted(keep_indices)})."
    )
    for node_idx in disabled_indices:
        if should_cancel():
            result["cancelled"] = True
            return
        try:
            node_label = graph.GetNodeLabel(node_idx) or ""
        except Exception:
            node_label = ""
        label_part = f" (label='{node_label}')" if node_label else ""
        if dry_run:
            result["nodes_changed"] += 1
            log(f"  [PLAN] {location}: node {node_idx}{label_part} -> Enabled")
            continue
        try:
            ok = bool(graph.SetNodeEnabled(node_idx, True))
        except Exception as exc:
            ok = False
            log(
                f"  [FAIL] {location}: node {node_idx}{label_part} "
                f"SetNodeEnabled raised: {exc}"
            )
        if ok:
            result["nodes_changed"] += 1
            log(f"  [OK]   {location}: node {node_idx}{label_part} -> Enabled")
        else:
            result["nodes_set_failed"] += 1
            log(
                f"  [FAIL] {location}: node {node_idx}{label_part} "
                "SetNodeEnabled returned False."
            )
        pump()


def _bypass_graph(
    graph,
    location,
    input_index_spec,
    input_label_regex,
    output_index_spec,
    output_label_regex,
    dry_run,
    log,
    pump,
    result,
    should_cancel,
):
    input_set, total_nodes, err = _resolve_endpoint(
        graph,
        input_index_spec,
        input_label_regex,
        "Color input",
        log,
        location,
        allow_no_match=True,
    )
    if err is not None:
        log(f"  [SKIP] {err}")
        return None

    output_set, total_nodes, err = _resolve_endpoint(
        graph,
        output_index_spec,
        output_label_regex,
        "Color output",
        log,
        location,
        allow_no_match=True,
    )
    if err is not None:
        log(f"  [SKIP] {err}")
        return None

    if total_nodes <= 0:
        log(f"  [SKIP] {location}: empty node graph.")
        return None

    keep_set = input_set | output_set
    disabled_by_bypass = []

    if not input_set and ((input_index_spec or "").strip() or (input_label_regex or "").strip()):
        log(f"  [info] {location}: color input not on this graph.")
    if not output_set and ((output_index_spec or "").strip() or (output_label_regex or "").strip()):
        log(f"  [info] {location}: color output not on this graph.")

    if keep_set:
        log(
            f"  {location}: keeping node(s) {sorted(keep_set)}; "
            f"disabling {total_nodes - len(keep_set)} other node(s) "
            f"(of {total_nodes} total)."
        )
    else:
        log(
            f"  {location}: input/output not on this graph; "
            f"disabling all {total_nodes} node(s)."
        )

    for node_idx in range(1, total_nodes + 1):
        if should_cancel():
            result["cancelled"] = True
            break
        if node_idx in keep_set:
            continue

        try:
            node_label = graph.GetNodeLabel(node_idx) or ""
        except Exception:
            node_label = ""
        label_part = f" (label='{node_label}')" if node_label else ""

        if dry_run:
            result["nodes_changed"] += 1
            disabled_by_bypass.append(node_idx)
            log(f"  [PLAN] {location}: node {node_idx}{label_part} -> Disabled")
            continue

        try:
            ok = bool(graph.SetNodeEnabled(node_idx, False))
        except Exception as exc:
            ok = False
            log(
                f"  [FAIL] {location}: node {node_idx}{label_part} "
                f"SetNodeEnabled raised: {exc}"
            )

        if ok:
            result["nodes_changed"] += 1
            disabled_by_bypass.append(node_idx)
            log(f"  [OK]   {location}: node {node_idx}{label_part} -> Disabled")
        else:
            result["nodes_set_failed"] += 1
            log(
                f"  [FAIL] {location}: node {node_idx}{label_part} "
                "SetNodeEnabled returned False."
            )
        pump()

    if not disabled_by_bypass:
        return None
    return {
        "disabled_indices": disabled_by_bypass,
        "keep_indices": sorted(keep_set),
    }


def grade_bypass(
    conn,
    restore,
    input_index_spec,
    input_label_regex,
    output_index_spec,
    output_label_regex,
    layer_spec,
    include_color_group=False,
    bypass_snapshot=None,
    dry_run=False,
    log=print,
    pump=_noop,
    should_cancel=lambda: False,
):
    result = {
        "nodes_changed": 0,
        "nodes_set_failed": 0,
        "graphs_visited": 0,
        "error": False,
        "cancelled": False,
        "snapshot": None,
    }

    bypass_snapshot = bypass_snapshot or {}

    project = conn.get_project()
    if project is None:
        log("No project is currently open.")
        result["error"] = True
        return result

    timeline = conn.get_timeline()
    if timeline is None:
        log("No timeline is currently loaded.")
        result["error"] = True
        return result

    try:
        item = timeline.GetCurrentVideoItem()
    except Exception as exc:
        log(f"GetCurrentVideoItem raised: {exc}")
        result["error"] = True
        return result

    if item is None:
        log(
            "No clip is selected on the current timeline. Select a clip on the "
            "timeline or open one in the Color page, then try again."
        )
        result["error"] = True
        return result

    clip_key = _clip_key(item)
    clip_name = _clip_label(item)

    try:
        max_layers = int(project.GetSetting("nodeStackLayers") or 1)
    except Exception:
        max_layers = 1

    layers, layer_err = tf.resolve_layer_spec(layer_spec, max_layers)
    if layer_err is not None:
        log(layer_err)
        result["error"] = True
        return result

    resolve = conn.resolve
    op_label = "Restore grade" if restore else "Bypass grade"
    header = f"{op_label} (current clip) - DRY RUN" if dry_run else op_label
    log(header)
    log(f"  Clip: {clip_name}")
    log(f"  Layers: {layers}  (project nodeStackLayers = {max_layers})")
    if include_color_group:
        log("  Color group: include pre-clip and post-clip node graphs")
    else:
        log("  Color group: clip node graph only")
    pump()

    original_page, page_switched = _switch_to_color_page(resolve, log, dry_run)

    stored_graphs = _snapshot_graph_entries(bypass_snapshot)
    if restore and not stored_graphs:
        log(
            "Nothing to restore. Run Bypass on this clip first "
            "(or preview was used last time)."
        )
        result["error"] = True
        _restore_page(resolve, original_page, page_switched, log)
        return result

    if restore:
        stored_key = (bypass_snapshot.get("clip_key") or "").strip()
        if stored_key and stored_key != clip_key:
            log(
                "  [warn] Stored bypass was for a different clip. "
                "Restore will still apply to matching graph data only."
            )
    else:
        log(f"  Color input:  index='{input_index_spec}'  label=/{input_label_regex}/")
        log(f"  Color output: index='{output_index_spec}'  label=/{output_label_regex}/")

    graphs_to_visit = _collect_graphs(
        item, layers, include_color_group if not restore else True, log=log
    )

    if not restore:
        endpoint_err = _validate_bypass_endpoints(
            graphs_to_visit,
            input_index_spec,
            input_label_regex,
            output_index_spec,
            output_label_regex,
            log,
        )
        if endpoint_err is not None:
            log(endpoint_err)
            result["error"] = True
            _restore_page(resolve, original_page, page_switched, log)
            return result

    if restore:
        graph_lookup = {
            key: (location, graph)
            for key, location, graph in graphs_to_visit
        }
        for graph_key, graph_data in stored_graphs.items():
            if should_cancel():
                result["cancelled"] = True
                break
            entry = graph_lookup.get(graph_key)
            if entry is None:
                log(f"  [SKIP] {graph_key}: graph not available on this clip.")
                continue
            location, graph = entry
            result["graphs_visited"] += 1
            _restore_graph(
                graph,
                location,
                graph_data,
                dry_run,
                log,
                pump,
                result,
                should_cancel,
            )
            if result["cancelled"]:
                break
    else:
        new_snapshot = {
            "clip_key": clip_key,
            "clip_label": clip_name,
            "include_color_group": bool(include_color_group),
            "graphs": {},
        }
        for graph_key, location, graph in graphs_to_visit:
            if should_cancel():
                result["cancelled"] = True
                break
            result["graphs_visited"] += 1
            graph_data = _bypass_graph(
                graph,
                location,
                input_index_spec,
                input_label_regex,
                output_index_spec,
                output_label_regex,
                dry_run,
                log,
                pump,
                result,
                should_cancel,
            )
            if graph_data and not dry_run:
                new_snapshot["graphs"][graph_key] = graph_data
            if result["cancelled"]:
                break

        if not dry_run and new_snapshot.get("graphs"):
            result["snapshot"] = new_snapshot

    if result["cancelled"]:
        log("Run cancelled by user. Showing partial results below.")

    _restore_page(resolve, original_page, page_switched, log)

    log("")
    log(f"  Graphs visited:          {result['graphs_visited']}")
    change_label = "Nodes that would change:" if dry_run else "Nodes changed:"
    log(f"  {change_label}         {result['nodes_changed']}")
    if result["nodes_set_failed"]:
        log(f"  SetNodeEnabled failures: {result['nodes_set_failed']}")
    if dry_run:
        log("  (Dry run: no changes were applied.)")
    elif restore and result["nodes_changed"] and not result["error"]:
        log("  Bypass snapshot cleared after restore.")
    pump()

    return result
