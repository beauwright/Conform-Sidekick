"""Feature registry.

Categories drive the two-level nav (category strip + mode row). On first
launch (no saved mode), the main area stays empty until the user picks a mode.
"""

from .interlaced import InterlacedFeature
from .compound_clips import CompoundClipsFeature
from .odd_res_photos import OddResPhotosFeature
from .rename_from_markers import RenameFromMarkersFeature
from .lay_matching_clips import LayMatchingClipsFeature
from .bulk_node_enable import BulkNodeEnableFeature
from .grade_bypass import GradeBypassFeature
from .version_audit import VersionAuditFeature
from .source_tc import SourceTcFeature

# (category_id, label shown on the category button)
CATEGORIES = (
    ("conform", "Conform"),
    ("edit", "Edit"),
    ("color", "Color"),
)


def build_features():
    return [
        InterlacedFeature(),
        CompoundClipsFeature(),
        OddResPhotosFeature(),
        VersionAuditFeature(),
        SourceTcFeature(),
        RenameFromMarkersFeature(),
        LayMatchingClipsFeature(),
        BulkNodeEnableFeature(),
        GradeBypassFeature(),
    ]


def features_by_category(features):
    """Return ``[(category_id, label, [features...]), ...]`` in ``CATEGORIES`` order."""
    buckets = {cat_id: [] for cat_id, _ in CATEGORIES}
    for feature in features:
        buckets.setdefault(feature.category, []).append(feature)
    return [
        (cat_id, label, buckets[cat_id])
        for cat_id, label in CATEGORIES
        if buckets.get(cat_id)
    ]
