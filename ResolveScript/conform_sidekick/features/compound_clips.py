"""Identify Compound Clips.

Same scan/table/jump pattern as Identify Interlaced, differing only in the
classifier (``clipType == 'Compound'`` via ``ResolveAPI.find_compound_clips``).
"""

from .table_scan import TableScanFeature


class CompoundClipsFeature(TableScanFeature):
    id = "compound"
    title = "Identify Compound Clips"
    category = "conform"
    intro = "List compound clips in the project (or current timeline) and jump to them."
    noun_plural = "compound clip(s)"
    columns = ["Name", "Bin Location", "Resolution", "Track", "Timecode"]
    column_widths = [240, 320, 120, 80, 150]
    tc_column = 4

    def find(self, api, scope, on_progress, should_cancel):
        return api.find_compound_clips(
            scope, on_progress=on_progress, should_cancel=should_cancel
        )

    def row_values(self, media, inst):
        return [
            media["displayName"],
            media["binLocation"],
            media["resolution"],
            inst.get("track", ""),
            inst.get("timecode", ""),
        ]
