"""Resolve media-pool / timeline queries.

Ported from Conform Sidekick's ``ResolveController`` (PythonInterface/
resolve_controller.py), adapted to run in-process and to use the vendored
``timecode`` library via :mod:`conform_sidekick.timecode_utils` instead of any
hand-rolled timecode math.

Scan strategy (see the Resolve scripting README):

* **Timeline scope** iterates the timeline's own items and never walks the media
  pool. Each item already knows its track and record frame, so we only touch the
  ``MediaPoolItem`` of clips actually in the cut. This is the big win over the
  old "walk the whole project, then throw away anything not in the timeline".
* **Project scope** walks every bin once, but builds a ``mediaId -> instances``
  map up front (one pass over the timeline) so attaching record timecodes is an
  O(1) dict lookup instead of the old O(clips x timeline-instances) cross
  product.
* In both scopes we read only the *single* classifying property for each clip
  (the README notes specific-key reads are faster than a full snapshot) and
  fetch the remaining display properties only for clips that actually match.
"""

from . import timecode_utils


class ScanCancelled(Exception):
    """Raised inside a scan when the user requests an abort."""


class MediaFolder:
    def __init__(self, folder, bin_location):
        self.folder = folder
        self.bin_location = bin_location


class ResolveAPI:
    """Stateless-ish wrapper; project/timeline are re-fetched on each scan so
    results always reflect what the user currently has open."""

    def __init__(self, conn):
        self.conn = conn

    # -- context -----------------------------------------------------------

    def project_and_timeline_names(self) -> dict:
        project = self.conn.get_project()
        timeline = self.conn.get_timeline()
        return {
            "projectName": project.GetName() if project else "",
            "timelineName": timeline.GetName() if (project and timeline) else "",
        }

    def video_tracks(self) -> list:
        """Return ``[{index, name}, ...]`` for each video track on the current timeline."""
        timeline = self.conn.get_timeline()
        if timeline is None:
            return []
        try:
            count = int(timeline.GetTrackCount("video") or 0)
        except (TypeError, ValueError):
            count = 0
        tracks = []
        for index in range(1, count + 1):
            name = ""
            try:
                name = timeline.GetTrackName("video", index) or ""
            except Exception:
                pass
            tracks.append({"index": index, "name": name})
        return tracks

    # -- media pool traversal ---------------------------------------------

    def get_all_folders(self, project):
        media_pool = project.GetMediaPool()
        folders_to_explore = [MediaFolder(media_pool.GetRootFolder(), "/")]
        all_folders = []
        while folders_to_explore:
            folder_obj = folders_to_explore.pop(0)
            all_folders.append(folder_obj)
            for subfolder in folder_obj.folder.GetSubFolderList():
                if folder_obj.bin_location != "/":
                    new_bin_location = f"{folder_obj.bin_location}/{subfolder.GetName()}"
                else:
                    new_bin_location = f"/{subfolder.GetName()}"
                folders_to_explore.append(MediaFolder(subfolder, new_bin_location))
        return all_folders

    def _timeline_video_items(self, timeline):
        items = []
        for i in range(timeline.GetTrackCount("video")):
            track_index = i + 1
            for item in (timeline.GetItemListInTrack("video", track_index) or []):
                items.append((item, track_index))
        return items

    def _instances_by_media(self, project, timeline):
        """Map ``mediaId -> [{timecode, track}, ...]`` for every video timeline
        item, in one pass. Used to attach record positions during a project
        scan without re-scanning the timeline per clip."""
        out = {}
        if timeline is None:
            return out
        frame_rate, drop_frame = timecode_utils.get_timeline_framerate_and_dropframe(
            project, timeline
        )
        for item, track_index in self._timeline_video_items(timeline):
            media_pool_item = item.GetMediaPoolItem()
            if media_pool_item is None:
                continue
            try:
                media_id = media_pool_item.GetMediaId()
            except Exception:
                continue
            try:
                timecode = timecode_utils.frame_to_timecode(
                    frame_rate, drop_frame, item.GetStart()
                )
            except Exception:
                timecode = ""
            out.setdefault(media_id, []).append(
                {"timecode": timecode, "track": track_index}
            )
        return out

    # -- record construction ----------------------------------------------

    @staticmethod
    def _prop(clip, key):
        """Read one clip property, tolerating API errors. Querying a single key
        is faster than a full-snapshot ``GetClipProperty()`` per the README."""
        try:
            return clip.GetClipProperty(key)
        except Exception:
            return ""

    def _build_record(self, clip, name, media_id, bin_location, instances):
        """Build the full display record for a matched clip. Only called for
        matches, so the extra property reads stay off the hot path."""
        return {
            "displayName": name,
            "binLocation": bin_location,
            "resolution": self._prop(clip, "resolution"),
            "clips": instances,
            "filepath": self._prop(clip, "File Path"),
            "mediaId": media_id,
            "clipType": self._prop(clip, "Type"),
            "fieldType": self._prop(clip, "Field Dominance"),
            # Live MediaPoolItem handle so actions (e.g. ReplaceClip) don't have
            # to re-find the clip by bin path. Not used for display.
            "item": clip,
        }

    # -- classification ----------------------------------------------------

    @staticmethod
    def is_interlaced(field_type: str) -> bool:
        return field_type in ("Upper Field", "Lower Field")

    @staticmethod
    def is_resolution_odd(resolution: str) -> bool:
        if not resolution:
            return False
        parts = resolution.split("x")
        for axis in parts:
            if axis == "":
                return False
            try:
                if int(axis) % 2 != 0:
                    return True
            except ValueError:
                return False
        return False

    # -- scan engine -------------------------------------------------------

    def _scan(self, scope, classify, on_progress=None, should_cancel=None):
        project = self.conn.get_project()
        timeline = self.conn.get_timeline()
        if scope == "timeline":
            return self._scan_timeline(
                project, timeline, classify, on_progress, should_cancel
            )
        return self._scan_project(
            project, timeline, classify, on_progress, should_cancel
        )

    def _scan_timeline(self, project, timeline, classify, on_progress, should_cancel):
        """Only inspect clips that are actually in the current timeline."""
        records = []
        if project is None or timeline is None:
            return records

        frame_rate, drop_frame = timecode_utils.get_timeline_framerate_and_dropframe(
            project, timeline
        )
        record_by_media = {}  # media_id -> record, to merge repeated instances
        count = 0
        for item, track_index in self._timeline_video_items(timeline):
            if should_cancel is not None and should_cancel():
                raise ScanCancelled()
            count += 1
            if on_progress is not None and count % 25 == 0:
                on_progress(count)

            mpi = item.GetMediaPoolItem()
            if mpi is None or not classify(mpi):
                continue

            try:
                timecode = timecode_utils.frame_to_timecode(
                    frame_rate, drop_frame, item.GetStart()
                )
            except Exception:
                timecode = ""
            instance = {"timecode": timecode, "track": track_index}

            try:
                media_id = mpi.GetMediaId()
            except Exception:
                media_id = None

            record = record_by_media.get(media_id) if media_id is not None else None
            if record is None:
                record = self._build_record(mpi, mpi.GetName(), media_id, "", [])
                records.append(record)
                if media_id is not None:
                    record_by_media[media_id] = record
            record["clips"].append(instance)

        if on_progress is not None:
            on_progress(count)
        return records

    def _scan_project(self, project, timeline, classify, on_progress, should_cancel):
        """Walk every bin, but attach timeline positions via a prebuilt map."""
        records = []
        if project is None:
            return records

        instances_by_media = self._instances_by_media(project, timeline)
        count = 0
        for folder in self.get_all_folders(project):
            bin_base = folder.bin_location
            for clip in (folder.folder.GetClipList() or []):
                if should_cancel is not None and should_cancel():
                    raise ScanCancelled()
                count += 1
                if on_progress is not None and count % 25 == 0:
                    on_progress(count)

                if not classify(clip):
                    continue

                name = clip.GetName()
                if bin_base == "/":
                    bin_location = bin_base + name
                else:
                    bin_location = bin_base + "/" + name
                try:
                    media_id = clip.GetMediaId()
                except Exception:
                    media_id = ""
                instances = list(instances_by_media.get(media_id, []))
                records.append(
                    self._build_record(clip, name, media_id, bin_location, instances)
                )

        if on_progress is not None:
            on_progress(count)
        return records

    # -- feature queries ---------------------------------------------------

    def find_interlaced(self, scope="project", on_progress=None, should_cancel=None):
        return self._scan(
            scope,
            lambda c: self.is_interlaced(self._prop(c, "Field Dominance")),
            on_progress,
            should_cancel,
        )

    def find_compound_clips(self, scope="project", on_progress=None, should_cancel=None):
        return self._scan(
            scope,
            lambda c: self._prop(c, "Type") == "Compound",
            on_progress,
            should_cancel,
        )

    def find_odd_resolution(self, scope="project", on_progress=None, should_cancel=None):
        return self._scan(
            scope,
            lambda c: self.is_resolution_odd(self._prop(c, "resolution")),
            on_progress,
            should_cancel,
        )

    # -- actions -----------------------------------------------------------

    def go_to_timecode(self, target_timecode: str) -> bool:
        timeline = self.conn.get_timeline()
        if timeline is None or not target_timecode:
            return False
        try:
            timeline.SetCurrentTimecode(target_timecode)
            return True
        except Exception:
            return False

    def get_media_object_from_bin_path(self, bin_location, media_id):
        project = self.conn.get_project()
        folders = self.get_all_folders(project)

        bin_location_parts = bin_location.split("/")
        if len(bin_location_parts) < 2:
            return None

        bin_directory = ""
        for index, sub_path in enumerate(bin_location_parts):
            if index != len(bin_location_parts) - 1:
                if bin_directory == "/" or sub_path == "/":
                    bin_directory = bin_directory + sub_path
                else:
                    bin_directory = bin_directory + "/" + sub_path
        file_name = bin_location_parts[-1]

        for folder in folders:
            if folder.bin_location == bin_directory:
                for clip in (folder.folder.GetClipList() or []):
                    if clip.GetName() == file_name and clip.GetMediaId() == media_id:
                        return clip
        return None
