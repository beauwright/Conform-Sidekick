"""Feature registry.

Order here is the order the tabs appear in the window. The first entry is the
default visible panel.
"""

from .interlaced import InterlacedFeature
from .compound_clips import CompoundClipsFeature
from .odd_res_photos import OddResPhotosFeature
from .rename_from_markers import RenameFromMarkersFeature
from .lay_matching_clips import LayMatchingClipsFeature
from .bulk_node_enable import BulkNodeEnableFeature


def build_features():
    return [
        InterlacedFeature(),
        CompoundClipsFeature(),
        OddResPhotosFeature(),
        RenameFromMarkersFeature(),
        LayMatchingClipsFeature(),
        BulkNodeEnableFeature(),
    ]
