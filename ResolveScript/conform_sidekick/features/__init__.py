"""Feature registry.

Categories drive the two-level nav (category strip + mode row). The first
feature in the first category is the default panel on launch.
"""

from .interlaced import InterlacedFeature
from .compound_clips import CompoundClipsFeature
from .odd_res_photos import OddResPhotosFeature
from .rename_from_markers import RenameFromMarkersFeature
from .lay_matching_clips import LayMatchingClipsFeature
from .bulk_node_enable import BulkNodeEnableFeature
from .grade_bypass import GradeBypassFeature
from .version_audit import VersionAuditFeature

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
