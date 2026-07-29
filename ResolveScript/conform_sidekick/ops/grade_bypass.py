"""Bypass / restore the color grade on the current clip in the Color page.

Bypass creates a temporary local color version (``BYPASS_VERSION_NAME``) on
``Timeline.GetCurrentVideoItem()``. ``TimelineItem.AddVersion`` copies the
current grade into the new version and switches to it (verified empirically);
every node on that copy is then disabled except the configured color input and
output endpoints, plus any nodes matching an optional leave-alone label regex.
Restore switches back to the original version (``LoadVersionByName``) and
deletes the bypass version — the working grade, including nodes the user had
disabled by hand, is never modified.

Color group pre-clip / post-clip graphs (``TimelineItem.GetColorGroup``) are
shared across the group and are not captured by local versions, so those are
still bypassed in place with ``Graph.SetNodeEnabled`` and restored from the
node list recorded at bypass time. The API has no ``GetNodeEnabled`` and
``SetNodeEnabled`` always returns ``True`` even when the node is already off,
so group nodes disabled before bypass cannot be detected and may be re-enabled
on restore. Collapsed node groups inside a single graph are not exposed by the
API either; only top-level nodes from ``Graph.GetNumNodes()`` are reachable.

Snapshots persisted by older builds (clip-graph node lists without an
``original_version``) are still restored the legacy way, by re-enabling the
recorded nodes.
"""

from .. import timeline_filters as tf
from .bulk_nodes import _target_indices_for_graph

BYPASS_VERSION_NAME = "Conform Sidekick Bypass"
_GROUP_GRAPH_KEYS = ("group_pre", "group_post")


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


def current_clip_key(conn):
    """Return the snapshot key for ``Timeline.GetCurrentVideoItem()``, or ``""``."""
    timeline = conn.get_timeline()
    if timeline is None:
        return ""
    try:
        item = timeline.GetCurrentVideoItem()
    except Exception:
        return ""
    if item is None:
        return ""
    return _clip_key(item)


def normalize_snapshots_by_clip(raw):
    """Return ``{clip_key: snapshot}`` from persisted state, migrating legacy data."""
    if not isinstance(raw, dict):
        return {}
    by_clip = raw.get("bypass_snapshots_by_clip")
    if not isinstance(by_clip, dict):
        by_clip = {}
    else:
        by_clip = dict(by_clip)
    legacy = raw.get("bypass_snapshot") or {}
    if isinstance(legacy, dict):
        legacy_key = (legacy.get("clip_key") or "").strip()
        if legacy_key and legacy_key not in by_clip:
            by_clip[legacy_key] = legacy
    return by_clip


def snapshot_can_restore(snapshot):
    """True when ``snapshot`` contains bypass data that restore can apply."""
    snapshot = snapshot or {}
    if _snapshot_graph_entries(snapshot):
        return True
    original = snapshot.get("original_version") or {}
    return bool((original.get("name") or "").strip())


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


def _collect_clip_graphs(item, layers, log):
    """Return ``[(graph_key, location_label, graph), ...]`` for the clip layers."""
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
    return graphs


def _collect_group_graphs(item, log):
    """Return the clip's shared color group pre/post graphs, if any."""
    graphs = []
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


def _collect_graphs(item, layers, include_color_group, log):
    """Return ``[(graph_key, location_label, graph), ...]`` to visit."""
    graphs = _collect_clip_graphs(item, layers, log)
    if include_color_group:
        graphs.extend(_collect_group_graphs(item, log))
    return graphs


def _current_version_info(item, log):
    """Return ``TimelineItem.GetCurrentVersion()`` as a dict (may be empty)."""
    try:
        return item.GetCurrentVersion() or {}
    except Exception as exc:
        log(f"  [warn] GetCurrentVersion raised: {exc}")
        return {}


def _local_versions(item, log):
    try:
        return list(item.GetVersionNameList(0) or [])
    except Exception as exc:
        log(f"  [warn] GetVersionNameList raised: {exc}")
        return []


def _delete_bypass_version(item, log, reason=""):
    """Delete the bypass version if present. True when absent or deleted."""
    if BYPASS_VERSION_NAME not in _local_versions(item, log):
        return True
    try:
        ok = bool(item.DeleteVersionByName(BYPASS_VERSION_NAME, 0))
    except Exception as exc:
        log(
            f"  [warn] DeleteVersionByName('{BYPASS_VERSION_NAME}') raised: {exc}"
        )
        return False
    if ok:
        log(f"  Deleted bypass version '{BYPASS_VERSION_NAME}'{reason}.")
    else:
        log(
            f"  [warn] Could not delete bypass version "
            f"'{BYPASS_VERSION_NAME}'{reason}; remove it by hand if it lingers."
        )
    return ok


def clip_on_bypass_version(conn):
    """True when the current clip is parked on the bypass version."""
    try:
        timeline = conn.get_timeline()
        item = timeline.GetCurrentVideoItem() if timeline is not None else None
        if item is None:
            return False
        info = item.GetCurrentVersion() or {}
        return info.get("versionName") == BYPASS_VERSION_NAME
    except Exception:
        return False


def _restore_original_version(item, bypass_snapshot, has_stored_graphs, dry_run, log, result):
    """Switch back to the pre-bypass version and delete the bypass version.

    Returns True when the caller should continue with graph restore, False on
    a fatal condition (already logged, ``result['error']`` set).
    """
    original = bypass_snapshot.get("original_version") or {}
    original_name = (original.get("name") or "").strip()
    original_type = int(original.get("type") or 0)

    info = _current_version_info(item, log)
    current_name = info.get("versionName") or ""

    if not original_name:
        if current_name != BYPASS_VERSION_NAME:
            if has_stored_graphs:
                # Legacy snapshot: nothing version-related to undo.
                return True
            log(
                "Nothing to restore for this clip. Bypass it first "
                "(or preview was used last time)."
            )
            result["error"] = True
            return False
        # On the bypass version with no stored original (state was lost):
        # recover with the first other local version.
        candidates = [
            name for name in _local_versions(item, log)
            if name != BYPASS_VERSION_NAME
        ]
        if not candidates:
            log(
                "  [FAIL] Clip is on the bypass version but no other local "
                "version exists to switch back to."
            )
            result["error"] = True
            return False
        original_name = candidates[0]
        original_type = 0
        log(
            "  No stored original version for this clip; recovering by "
            f"switching to '{original_name}'."
        )

    if dry_run:
        log(f"  [PLAN] Switch back to version '{original_name}'.")
        log(f"  [PLAN] Delete bypass version '{BYPASS_VERSION_NAME}'.")
        return True

    if current_name != original_name:
        try:
            loaded = bool(item.LoadVersionByName(original_name, original_type))
        except Exception as exc:
            loaded = False
            log(f"  [FAIL] LoadVersionByName('{original_name}') raised: {exc}")
        if not loaded:
            log(
                f"  [FAIL] Could not switch back to version '{original_name}'; "
                "leaving the clip as-is."
            )
            result["error"] = True
            return False
        log(f"  Switched back to version '{original_name}'.")
    else:
        log(f"  Already on version '{original_name}'.")

    _delete_bypass_version(item, log)
    return True


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


def _ignore_indices_for_graph(graph, label_regex, log, location):
    """Return node indices whose labels match ``label_regex``, or ``set()``."""
    label_pattern, label_err = tf.compile_regex(label_regex)
    if label_err is not None:
        return None, f"Invalid ignore label regex: {label_err}"
    if label_pattern is None:
        return set(), None
    targets, total = _target_indices_for_graph(
        graph, None, label_pattern, log, location
    )
    if total <= 0:
        return set(), None
    if not targets:
        log(
            f"  [info] {location}: no node label matches ignore regex "
            f"/{label_regex}/ (graph has {total} node(s))."
        )
    elif len(targets) > 1:
        log(
            f"  [info] {location}: ignore regex matched {len(targets)} node(s) "
            f"{targets}; all will be left alone."
        )
    return set(targets), None


def _bypass_graph(
    graph,
    location,
    input_index_spec,
    input_label_regex,
    output_index_spec,
    output_label_regex,
    ignore_label_regex,
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

    ignore_set, ignore_err = _ignore_indices_for_graph(
        graph, ignore_label_regex, log, location
    )
    if ignore_err is not None:
        log(f"  [SKIP] {ignore_err}")
        return None

    keep_set = input_set | output_set | ignore_set
    disabled_by_bypass = []

    if not input_set and ((input_index_spec or "").strip() or (input_label_regex or "").strip()):
        log(f"  [info] {location}: color input not on this graph.")
    if not output_set and ((output_index_spec or "").strip() or (output_label_regex or "").strip()):
        log(f"  [info] {location}: color output not on this graph.")

    if keep_set:
        parts = [f"keeping node(s) {sorted(keep_set)}"]
        if ignore_set:
            parts.append(f"{len(ignore_set)} ignored")
        log(
            f"  {location}: {parts[0]}; "
            f"disabling {total_nodes - len(keep_set)} other node(s) "
            f"(of {total_nodes} total)."
            + (f" ({parts[1]})" if ignore_set else "")
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
        "ignore_indices": sorted(ignore_set),
    }


def grade_bypass(
    conn,
    restore,
    input_index_spec,
    input_label_regex,
    output_index_spec,
    output_label_regex,
    layer_spec,
    ignore_label_regex="",
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

    result["clip_key"] = clip_key
    stored_graphs = _snapshot_graph_entries(bypass_snapshot)

    if restore:
        stored_label = (bypass_snapshot.get("clip_label") or "").strip()
        if stored_label:
            log(f"  Restoring bypass stored for: {stored_label}")

        proceed = _restore_original_version(
            item, bypass_snapshot, bool(stored_graphs), dry_run, log, result
        )
        if not proceed:
            _restore_page(resolve, original_page, page_switched, log)
            return result

        # Collect graphs after the version switch so clip-graph handles (used
        # by legacy snapshots) refer to the restored version.
        graph_lookup = {
            key: (location, graph)
            for key, location, graph in _collect_graphs(item, layers, True, log=log)
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
        log(f"  Color input:  index='{input_index_spec}'  label=/{input_label_regex}/")
        log(f"  Color output: index='{output_index_spec}'  label=/{output_label_regex}/")
        if (ignore_label_regex or "").strip():
            log(f"  Leave alone:  label=/{ignore_label_regex}/")

        # Validate against the current version's graphs; the bypass version is
        # a copy of them, so endpoint matches carry over.
        graphs_current = _collect_graphs(item, layers, include_color_group, log=log)

        _, ignore_err = tf.compile_regex(ignore_label_regex)
        if ignore_err is not None:
            log(f"Invalid leave-alone label regex: {ignore_err}")
            result["error"] = True
            _restore_page(resolve, original_page, page_switched, log)
            return result

        endpoint_err = _validate_bypass_endpoints(
            graphs_current,
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

        if dry_run:
            log(
                f"  [PLAN] Create local version '{BYPASS_VERSION_NAME}' (a copy "
                "of the current grade), switch to it, and disable the clip "
                "nodes below on that copy only."
            )
            log(
                "  [PLAN] Restore will switch back to the current version and "
                "delete the bypass version."
            )
            graphs_to_bypass = graphs_current
        else:
            if should_cancel():
                result["cancelled"] = True
                _restore_page(resolve, original_page, page_switched, log)
                return result

            info = _current_version_info(item, log)
            original_name = (info.get("versionName") or "").strip()
            original_type = int(info.get("versionType") or 0)
            if original_name == BYPASS_VERSION_NAME:
                log(
                    f"  This clip is already on '{BYPASS_VERSION_NAME}'. "
                    "Use Restore grade instead."
                )
                result["error"] = True
                _restore_page(resolve, original_page, page_switched, log)
                return result
            if not original_name:
                log("  [FAIL] Could not read the clip's current version; not bypassing.")
                result["error"] = True
                _restore_page(resolve, original_page, page_switched, log)
                return result

            _delete_bypass_version(item, log, reason=" left over from an earlier run")

            try:
                added = bool(item.AddVersion(BYPASS_VERSION_NAME, 0))
            except Exception as exc:
                added = False
                log(f"  [FAIL] AddVersion raised: {exc}")
            if not added:
                log(
                    f"  [FAIL] Could not create bypass version "
                    f"'{BYPASS_VERSION_NAME}'."
                )
                result["error"] = True
                _restore_page(resolve, original_page, page_switched, log)
                return result
            log(
                f"  Created bypass version '{BYPASS_VERSION_NAME}' as a copy "
                f"of '{original_name}' and switched to it."
            )

            after = _current_version_info(item, log)
            if (after.get("versionName") or "") != BYPASS_VERSION_NAME:
                try:
                    loaded = bool(item.LoadVersionByName(BYPASS_VERSION_NAME, 0))
                except Exception as exc:
                    loaded = False
                    log(f"  [FAIL] LoadVersionByName raised: {exc}")
                if not loaded:
                    log("  [FAIL] Could not switch to the bypass version; undoing.")
                    _delete_bypass_version(item, log)
                    result["error"] = True
                    _restore_page(resolve, original_page, page_switched, log)
                    return result

            new_snapshot = {
                "clip_key": clip_key,
                "clip_label": clip_name,
                "include_color_group": bool(include_color_group),
                "original_version": {"name": original_name, "type": original_type},
                "graphs": {},
            }
            # Recorded immediately so restore works even if the run is
            # cancelled mid-way through the node loop below.
            result["snapshot"] = new_snapshot

            # Clip graph handles must be re-fetched on the bypass version.
            graphs_to_bypass = _collect_clip_graphs(item, layers, log)
            if include_color_group:
                log(
                    "  Group pre/post graphs are shared (not versioned); "
                    "toggling those nodes off in place."
                )
                graphs_to_bypass.extend(_collect_group_graphs(item, log))

        for graph_key, location, graph in graphs_to_bypass:
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
                ignore_label_regex,
                dry_run,
                log,
                pump,
                result,
                should_cancel,
            )
            if graph_data and not dry_run and graph_key in _GROUP_GRAPH_KEYS:
                result["snapshot"]["graphs"][graph_key] = graph_data
            if result["cancelled"]:
                break

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
    elif restore and not result["error"]:
        log("  Bypass data cleared for this clip after restore.")
    elif not restore and not result["error"]:
        log(
            f"  Bypass is active on version '{BYPASS_VERSION_NAME}'; the "
            "original grade is untouched. Use Restore grade to switch back."
        )
    pump()

    return result
