"""User-facing labels and messages for the Resolve UIManager panels."""

# Scope selector (combo index 0 = project, 1 = timeline)
SCOPE_ENTIRE_PROJECT = "Entire project"
SCOPE_CURRENT_TIMELINE = "Current timeline only"

LABEL_SEARCH_IN = "Search in:"

CHECK_TIMELINE_INOUT = "Only clips inside the timeline In/Out range"
CHECK_PREVIEW_ONLY = "Preview only — don't change anything"

OUTPUT_HEADER = "Results:"
OUTPUT_PLACEHOLDER = "Results will appear here after you run."

TRACK_FILTER_ENABLE = "Only run on specific timeline tracks"
TRACK_USE = "Use this track"
TRACK_SKIP = "Skip this track"

TRACK_FILTER_NONE_SELECTED = (
    "No tracks are selected. Choose at least one track to use, "
    "or turn off 'Only run on specific timeline tracks'."
)

CHECK_INCLUDE_COLOR_GROUP = (
    "Include shared color group nodes (pre-clip & post-clip)"
)
STATUS_CHOOSE_SCOPE = "Choose where to search, then click Scan."
STATUS_NO_PROJECT = "Open a project in Resolve first."

# Pattern / name matching (supports regular expressions)
LABEL_MARKER_PATTERN = (
    "Find in each marker's name or note (supports regex):"
)
PLACEHOLDER_MARKER_PATTERN = (
    "Regex — e.g. SHOT_101 or ^[A-Z]{2,4}_\\d+"
)

LABEL_CLIP_NAME_PATTERN = (
    "Match timeline and bin clip names (supports regex):"
)
PLACEHOLDER_CLIP_NAME_PATTERN = (
    r"Regex — e.g. ^(SHOT_\d+); same pattern must match both names"
)

LABEL_NODE_LABEL_PATTERN = "Or match node label (supports regex):"
PLACEHOLDER_NODE_LABEL_PATTERN = "Optional regex — e.g. denoise"

LABEL_CLIP_NAME_FILTER = "Clip name filter (supports regex):"
PLACEHOLDER_CLIP_NAME_FILTER = "Optional regex — part of the clip name to match"


def scope_area_label(scope: str) -> str:
    """Human label for status messages ('project' or 'timeline' scope key)."""
    return "the current timeline" if scope == "timeline" else "this project"
