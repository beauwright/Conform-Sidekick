"""Bulk Enable / Disable Color Nodes - core operation.

Ported from davinci-resolve-scripts/Color/BulkEnableDisableNodes.py. No timecode
math. The module-global ``resolve`` of the original is replaced by the passed-in
connection (``conn.resolve`` for page switching, ``conn.get_project`` /
``conn.get_timeline`` for context).
"""

from .. import timeline_filters as tf


def _noop():
    pass


def _target_indices_for_graph(graph, index_set, label_pattern, log, location):
    try:
        n = int(graph.GetNumNodes() or 0)
    except Exception as exc:
        log(f"  [SKIP] {location}: GetNumNodes raised: {exc}")
        return [], 0

    if n <= 0:
        return [], 0

    if label_pattern is not None:
        hits = []
        for i in range(1, n + 1):
            try:
                label = graph.GetNodeLabel(i) or ""
            except Exception:
                label = ""
            if label_pattern.search(label):
                hits.append(i)
        return hits, n

    if index_set is not None:
        return sorted(i for i in index_set if 1 <= i <= n), n

    return [], n


def _color_group_name(color_group):
    try:
        return color_group.GetName() or "(unnamed group)"
    except Exception:
        return "(unnamed group)"


def _process_graph_targets(
    graph,
    location,
    clip_name,
    enabled,
    index_set,
    label_pattern,
    label_regex,
    index_spec,
    dry_run,
    log,
    maybe_pump,
    result,
):
    """Enable/disable target nodes on one graph. Returns True if any node changed."""
    targets, total_nodes = _target_indices_for_graph(
        graph, index_set, label_pattern, log, location
    )

    if total_nodes <= 0:
        log(f"  [SKIP] {location} '{clip_name}': empty graph.")
        return False

    if not targets:
        if label_pattern is not None:
            log(
                f"  [SKIP] {location} '{clip_name}': no node label matches /{label_regex}/ "
                f"(graph has {total_nodes} node(s))."
            )
        else:
            missing = sorted(i for i in index_set if i < 1 or i > total_nodes)
            result["nodes_skipped_short_graph"] += len(missing)
            log(
                f"  [SKIP] {location} '{clip_name}': requested {sorted(index_set)} "
                f"but graph has only {total_nodes} node(s)."
            )
        return False

    changed = False
    for node_idx in targets:
        try:
            node_label = graph.GetNodeLabel(node_idx) or ""
        except Exception:
            node_label = ""
        label_part = f" (label='{node_label}')" if node_label else ""

        if dry_run:
            result["nodes_changed"] += 1
            log(
                f"  [PLAN] {location} '{clip_name}': node {node_idx}{label_part} -> "
                f"{'Enabled' if enabled else 'Disabled'}"
            )
            maybe_pump()
            changed = True
            continue

        try:
            ok = bool(graph.SetNodeEnabled(node_idx, enabled))
        except Exception as exc:
            ok = False
            log(
                f"  [FAIL] {location} '{clip_name}': node {node_idx}{label_part} "
                f"SetNodeEnabled raised: {exc}"
            )

        if ok:
            result["nodes_changed"] += 1
            log(
                f"  [OK]   {location} '{clip_name}': node {node_idx}{label_part} -> "
                f"{'Enabled' if enabled else 'Disabled'}"
            )
            changed = True
        else:
            result["nodes_set_failed"] += 1
            log(
                f"  [FAIL] {location} '{clip_name}': node {node_idx}{label_part} "
                "SetNodeEnabled returned False."
            )

        maybe_pump()

    return changed


def _process_color_group_graphs(
    item,
    location_base,
    clip_name,
    enabled,
    index_set,
    label_pattern,
    label_regex,
    index_spec,
    dry_run,
    log,
    maybe_pump,
    result,
    processed_group_graphs,
    should_cancel,
):
    """Visit shared pre/post graphs once per color group per run."""
    if should_cancel():
        result["cancelled"] = True
        return False

    color_group = None
    try:
        color_group = item.GetColorGroup()
    except Exception as exc:
        log(f"  [warn] {location_base}: GetColorGroup raised: {exc}")
        return False

    if color_group is None:
        return False

    group_name = _color_group_name(color_group)
    changed = False

    for graph_kind, method_name in (
        ("pre-clip", "GetPreClipNodeGraph"),
        ("post-clip", "GetPostClipNodeGraph"),
    ):
        if should_cancel():
            result["cancelled"] = True
            return changed

        dedupe_key = (group_name, graph_kind)
        if dedupe_key in processed_group_graphs:
            result["color_group_graphs_deduped"] += 1
            continue

        get_graph = getattr(color_group, method_name, None)
        if not callable(get_graph):
            continue
        try:
            graph = get_graph()
        except Exception as exc:
            log(
                f"  [warn] Color group '{group_name}' {method_name} raised: {exc}"
            )
            continue
        if graph is None:
            continue

        processed_group_graphs.add(dedupe_key)
        result["layers_visited"] += 1
        location = f"{location_base} Color group '{group_name}' {graph_kind}"
        if _process_graph_targets(
            graph,
            location,
            clip_name,
            enabled,
            index_set,
            label_pattern,
            label_regex,
            index_spec,
            dry_run,
            log,
            maybe_pump,
            result,
        ):
            changed = True

    return changed


def bulk_set_node_enabled(
    conn,
    enabled,
    index_spec,
    label_regex,
    name_filter,
    layer_spec,
    all_versions,
    use_inout,
    track_filter_spec,
    clip_color_filter="",
    include_color_group=False,
    dry_run=False,
    log=print,
    pump=_noop,
    pump_every=5,
    should_cancel=lambda: False,
):
    result = {
        "tli_scanned": 0,
        "tli_skipped_out_of_scope": 0,
        "tli_skipped_name_filter": 0,
        "tli_skipped_clip_color": 0,
        "tli_processed": 0,
        "nodes_changed": 0,
        "nodes_skipped_short_graph": 0,
        "nodes_set_failed": 0,
        "versions_visited": 0,
        "layers_visited": 0,
        "color_group_graphs_deduped": 0,
        "error": False,
        "cancelled": False,
    }

    pump_state = {"n": 0}
    effective_pump_every = max(1, int(pump_every))

    def maybe_pump():
        pump_state["n"] += 1
        if pump_state["n"] >= effective_pump_every:
            pump_state["n"] = 0
            pump()

    index_set, index_err = tf.parse_int_spec(index_spec, what="index")
    if index_err is not None:
        log(f"Index: {index_err}")
        result["error"] = True
        return result

    label_pattern, label_err = tf.compile_regex(label_regex)
    if label_err is not None:
        log(f"Invalid label regex: {label_err}")
        result["error"] = True
        return result

    if index_set is None and label_pattern is None:
        log(
            "No target specified. Set either an index (e.g. '2' or '2,5') "
            "or a label regex."
        )
        result["error"] = True
        return result

    name_pattern, name_err = tf.compile_regex(name_filter)
    if name_err is not None:
        log(f"Invalid TimelineItem name regex: {name_err}")
        result["error"] = True
        return result

    resolve = conn.resolve
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
        max_layers = int(project.GetSetting("nodeStackLayers") or 1)
    except Exception:
        max_layers = 1

    layers, layer_err = tf.resolve_layer_spec(layer_spec, max_layers)
    if layer_err is not None:
        log(f"{layer_err}")
        result["error"] = True
        return result

    video_track_count = timeline.GetTrackCount("video") or 0
    track_set, track_err = tf.parse_track_filter(track_filter_spec, video_track_count)
    if track_err:
        log(f"Tracks: {track_err}")
        result["error"] = True
        return result

    scope_range = None
    if use_inout:
        scope_range = tf.get_inout_range(timeline)
        if scope_range is None:
            log(
                "Use timeline In/Out is checked but no In/Out range is set on the "
                "current timeline. Set one with I/O (or uncheck the option) and re-run."
            )
            result["error"] = True
            return result

    color_filter = (clip_color_filter or "").strip()
    color_filter_active = bool(color_filter)
    color_target_uncolored = color_filter == tf.UNCOLORED_SENTINEL

    op_label = "Enable" if enabled else "Disable"
    header = (
        f"Bulk {op_label} Color Nodes - DRY RUN"
        if dry_run
        else f"Bulk {op_label} Color Nodes"
    )
    log(header)
    if label_pattern is not None:
        log(f"  Target: nodes matching label regex /{label_regex}/")
    else:
        log(f"  Target: node index spec '{index_spec}' -> {sorted(index_set)}")
    log(f"  Layers: {layers}  (project nodeStackLayers = {max_layers})")
    log(f"  Versions: {'all local + restore' if all_versions else 'active version only'}")
    if name_pattern is not None:
        log(f"  TimelineItem name filter: /{name_filter}/")
    if color_filter_active:
        if color_target_uncolored:
            log("  Clip color filter: only uncolored clips")
        else:
            log(f"  Clip color filter: only clips tagged '{color_filter}'")
    if scope_range is not None:
        log(f"  Scope: In/Out range [{scope_range[0]}-{scope_range[1]}] (absolute timeline frames)")
    if track_set is not None:
        log(f"  Tracks: V{sorted(track_set)} (filtered)")
    else:
        log(f"  Tracks: all {video_track_count} video track(s)")
    if include_color_group:
        log("  Color group: include pre-clip and post-clip node graphs (once per group)")
    else:
        log("  Color group: clip node graphs only")
    pump()

    # SetNodeEnabled needs the Color page active to actually take effect.
    original_page = None
    page_switched = False
    if not dry_run:
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
                log("  [warn] Could not switch to Color page; node-enable changes may silently no-op.")
        pump()

    track_indices = (
        sorted(track_set)
        if track_set is not None
        else list(range(1, video_track_count + 1))
    )
    processed_group_graphs = set()

    for track_idx in track_indices:
        if should_cancel():
            result["cancelled"] = True
            break
        items = timeline.GetItemListInTrack("video", track_idx) or []
        for item in items:
            if should_cancel():
                result["cancelled"] = True
                break
            result["tli_scanned"] += 1

            try:
                item_start = item.GetStart()
                item_end = item.GetEnd()
            except Exception:
                item_start = None
                item_end = None

            if scope_range is not None and item_start is not None and item_end is not None:
                scope_in, scope_out = scope_range
                if not (item_start < scope_out and scope_in < item_end):
                    result["tli_skipped_out_of_scope"] += 1
                    continue

            name = ""
            try:
                name = item.GetName() or ""
            except Exception:
                name = ""

            if not tf.match_name(name_pattern, name):
                result["tli_skipped_name_filter"] += 1
                continue

            if color_filter_active:
                try:
                    clip_color = item.GetClipColor() or ""
                except Exception:
                    clip_color = ""
                if color_target_uncolored:
                    color_match = clip_color == ""
                else:
                    color_match = clip_color == color_filter
                if not color_match:
                    result["tli_skipped_clip_color"] += 1
                    continue

            location_base = (
                f"V{track_idx} {item_start}-{item_end}"
                if item_start is not None and item_end is not None
                else f"V{track_idx} {name}"
            )

            saved_version = None
            if all_versions and not dry_run:
                try:
                    saved_version = item.GetCurrentVersion()
                except Exception as exc:
                    saved_version = None
                    log(f"  [warn] {location_base}: GetCurrentVersion raised: {exc}")

            if all_versions:
                try:
                    version_names = item.GetVersionNameList(0) or []
                except Exception:
                    version_names = []
                if not version_names:
                    versions_to_visit = [None]
                else:
                    versions_to_visit = list(version_names)
            else:
                versions_to_visit = [None]

            processed_this_clip = False

            for version_marker in versions_to_visit:
                if should_cancel():
                    result["cancelled"] = True
                    break

                if version_marker is not None and not dry_run:
                    try:
                        loaded_ok = bool(item.LoadVersionByName(version_marker, 0))
                    except Exception as exc:
                        loaded_ok = False
                        log(f"  [warn] {location_base} v='{version_marker}': LoadVersionByName raised: {exc}")
                    if not loaded_ok:
                        log(f"  [warn] {location_base} v='{version_marker}': LoadVersionByName returned False; skipping this version.")
                        continue
                    result["versions_visited"] += 1
                else:
                    result["versions_visited"] += 1

                version_label = (
                    f" v='{version_marker}'"
                    if version_marker is not None
                    else ""
                )

                for layer_idx in layers:
                    if should_cancel():
                        result["cancelled"] = True
                        break
                    try:
                        graph = item.GetNodeGraph(layer_idx)
                    except Exception as exc:
                        log(f"  [SKIP] {location_base}{version_label} L{layer_idx}: GetNodeGraph raised: {exc}")
                        continue
                    if graph is None:
                        log(f"  [SKIP] {location_base}{version_label} L{layer_idx}: no graph.")
                        continue

                    result["layers_visited"] += 1

                    location = f"{location_base}{version_label} L{layer_idx}"
                    if _process_graph_targets(
                        graph,
                        location,
                        name,
                        enabled,
                        index_set,
                        label_pattern,
                        label_regex,
                        index_spec,
                        dry_run,
                        log,
                        maybe_pump,
                        result,
                    ):
                        processed_this_clip = True

                if result["cancelled"]:
                    break

            if include_color_group:
                if _process_color_group_graphs(
                    item,
                    location_base,
                    name,
                    enabled,
                    index_set,
                    label_pattern,
                    label_regex,
                    index_spec,
                    dry_run,
                    log,
                    maybe_pump,
                    result,
                    processed_group_graphs,
                    should_cancel,
                ):
                    processed_this_clip = True

            if saved_version and saved_version.get("versionName") and not dry_run:
                try:
                    item.LoadVersionByName(
                        saved_version["versionName"],
                        saved_version.get("versionType", 0),
                    )
                except Exception:
                    pass

            if processed_this_clip:
                result["tli_processed"] += 1

            if result["cancelled"]:
                break

        if result["cancelled"]:
            break

    if result["cancelled"]:
        log("Run cancelled by user. Showing partial results below.")
        pump()

    if page_switched and original_page and original_page != "color":
        try:
            if resolve.OpenPage(original_page):
                log(f"  Restored {original_page} page.")
        except Exception:
            pass
        pump()

    log("")
    log(f"  Timeline clips scanned:         {result['tli_scanned']}")
    if result["tli_skipped_out_of_scope"]:
        log(f"  Out-of-scope TLIs skipped:      {result['tli_skipped_out_of_scope']}")
    if result["tli_skipped_name_filter"]:
        log(f"  Name-filtered TLIs skipped:     {result['tli_skipped_name_filter']}")
    if result["tli_skipped_clip_color"]:
        log(f"  Color-filtered TLIs skipped:    {result['tli_skipped_clip_color']}")
    log(f"  Timeline clips processed:       {result['tli_processed']}")
    log(f"  Layers visited:                 {result['layers_visited']}")
    if result["color_group_graphs_deduped"]:
        log(
            f"  Color group graphs deduped:     {result['color_group_graphs_deduped']} "
            "(shared group already processed for another clip)"
        )
    if all_versions:
        log(f"  Versions visited:               {result['versions_visited']}")
    change_label = "Nodes that would be changed:" if dry_run else "Nodes changed:                 "
    log(f"  {change_label} {result['nodes_changed']}")
    if result["nodes_skipped_short_graph"]:
        log(f"  Indices outside graph extents:  {result['nodes_skipped_short_graph']}")
    if result["nodes_set_failed"]:
        log(f"  SetNodeEnabled failures:        {result['nodes_set_failed']}")
    if dry_run:
        log("  (Dry run: no changes were applied.)")
    pump()

    return result
