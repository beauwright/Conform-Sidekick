"""Identify Interlaced Footage.

The original proof-of-concept, now expressed on top of the shared
:class:`TableScanFeature`: find interlaced (Upper/Lower field) media across the
project or current timeline, list each instance, and jump the playhead to it.
"""

from .table_scan import TableScanFeature


class InterlacedFeature(TableScanFeature):
    id = "interlaced"
    title = "Identify Interlaced"
    intro = "Find interlaced (Upper/Lower field) media."
    noun_plural = "interlaced instance(s)"
    columns = ["Name", "Bin Location", "Resolution", "Field", "Track", "Timecode"]
    column_widths = [200, 260, 100, 100, 70, 140]
    tc_column = 5

    def find(self, api, scope, on_progress, should_cancel):
        return api.find_interlaced(
            scope, on_progress=on_progress, should_cancel=should_cancel
        )

    def row_values(self, media, inst):
        return [
            media["displayName"],
            media["binLocation"],
            media["resolution"],
            media["fieldType"],
            inst.get("track", ""),
            inst.get("timecode", ""),
        ]
