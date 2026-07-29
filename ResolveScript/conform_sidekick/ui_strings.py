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
# Longer notes are pre-broken into lines (see ui_kit.note_block): UIManager
# clips WordWrap labels to a single line of height.
GRADE_BYPASS_INTRO = (
    "Bypass copies the current grade to a temporary local version ('Conform Sidekick Bypass')\n"
    "and disables everything on that copy except the color input/output and leave-alone nodes.\n"
    "Your working grade — including nodes you disabled by hand — is not touched.\n"
    "Restore switches back to your original version and deletes the bypass version."
)
GRADE_BYPASS_GROUP_NOTE = (
    "Note: group pre/post nodes are shared across the whole group and can't be captured\n"
    "by the bypass version, so they are toggled off in place. Resolve's API can't read\n"
    "whether a node was already off, so Restore may re-enable group nodes you had\n"
    "disabled yourself — list those under the leave-alone regex."
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

LABEL_GRADE_BYPASS_IGNORE = "Also leave nodes alone (regex):"
PLACEHOLDER_GRADE_BYPASS_IGNORE = (
    "Optional — nodes to skip (e.g. already off); use ^ and $ for exact labels"
)

VERSION_AUDIT_INTRO = (
    "Compare a VFX delivery file to the current timeline. "
    "Flag missing deliveries, newer/older versions vs the sheet, disabled clips, and cover warnings."
)
LABEL_VFX_CSV = "VFX delivery file:"
PLACEHOLDER_VFX_CSV = "Full path to CSV or .xlsx from VFX"
LABEL_VFX_KEY_COLUMN = "VFX key column:"
PLACEHOLDER_VFX_KEY_COLUMN = "Header name or 1-based column index (e.g. shot_id or 1)"
CHECK_VFX_HAS_HEADER = "First row is a header (uncheck for a single key column)"
CHECK_STRIP_EXTENSION = "Ignore file extensions (.mov, .exr, etc.)"
CHECK_NORMALIZE_NUMERIC = "Normalize numeric segments (ignore leading zeros)"
CHECK_DETECT_VERSION_DRIFT = (
    "Detect newer / older versions in project (when sheet key is missing)"
)
LABEL_VERSION_PRESET = "Version naming:"
PLACEHOLDER_VERSION_PATTERN = (
    r"Custom regex with base + ver groups — e.g. ^(?P<base>.+)_v(?P<ver>\d+)$"
)
LABEL_TIMELINE_KEY = "Match timeline by:"
CHECK_WARN_COVER = (
    "Warn when higher tracks (within track filter) cover a match"
)
VERSION_AUDIT_STATUS_IDLE = (
    "Set the VFX CSV path and key column, then click Audit."
)
VERSION_AUDIT_NO_TIMELINE = "Open a timeline in Resolve first."
VERSION_AUDIT_NO_CSV = "Enter the path to the VFX delivery file (CSV or .xlsx)."
VERSION_AUDIT_NO_KEY_COLUMN = "Enter the VFX key column name or index."
LABEL_EXPORT_CSV = "Export CSV to:"
PLACEHOLDER_EXPORT_CSV = "Path for audit results (auto-filled after Audit)"
VERSION_AUDIT_NO_RESULTS = "Run an audit first, then export."
VERSION_AUDIT_NO_EXPORT_PATH = "Enter a path for the export CSV."


def scope_area_label(scope: str) -> str:
    """Human label for status messages ('project' or 'timeline' scope key)."""
    return "the current timeline" if scope == "timeline" else "this project"
