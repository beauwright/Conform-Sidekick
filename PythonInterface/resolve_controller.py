from typing import Dict, Union
from get_resolve import GetResolve, ResolveConnectionFailed
import convert_photos
from timecode import Timecode


class ResolveController:
    def __init__(self, project, timeline):
        self.project = project
        self.timeline = timeline

    class MediaFolder:
        def __init__(self, folder, bin_location):
            self.folder = folder
            self.bin_location = bin_location

    class MediaClip:
        def __init__(self, clip, timecode: str, track: int):
            self.clip = clip
            self.timecode = timecode
            self.track = track


    def get_all_media_in_media_pool(self) -> dict[str, str]:
        all_folders = self.get_all_folders_in_project()
        all_media = {"scope": "project", "media": []}
        clips_in_timeline = self.get_all_timeline_clips_with_timecode()
        
        for folder in all_folders:
            clips = folder.folder.GetClipList()
            for clip in clips:
                timecodes = []
                if clips_in_timeline:
                    for item in clips_in_timeline:
                        try:
                            if clip.GetMediaId() == item.clip.GetMediaId():
                                timecodes.append({"timecode": item.timecode, "track": item.track})
                        except:
                            pass
                
                all_media["media"].append({
                    "displayName": clip.GetName(),
                    "binLocation": folder.bin_location + clip.GetName(),
                    "resolution": clip.GetClipProperty("resolution"),
                    "timecodes": timecodes,
                    "filepath": clip.GetClipProperty("File Path"),
                    "mediaId": clip.GetMediaId(),
                    "clipType": clip.GetClipProperty("Type"),
                    "fieldType": clip.GetClipProperty("Field Dominance")
                })
        return all_media

    def get_all_odd_res_in_media_pool(self) -> dict[str, str]:
        all_media = self.get_all_media_in_media_pool()
        odd_res_media = {"scope": "project", "selectedMedia": []}
        
        for media in all_media["media"]:
            if self.is_resolution_odd(media["resolution"]):
                odd_res_media["selectedMedia"].append(media)
        
        return odd_res_media
    
    def get_all_folders_in_project(self):
        # Iterate through the MediaPool to get every piece of media from the root folder
        # What Resolve calls bins in the GUI are called Folders in the API
        media_pool = self.project.GetMediaPool()
        folders_to_explore = [self.MediaFolder(media_pool.GetRootFolder(), "/")]
        all_folders = []

        while folders_to_explore:
            folder_obj = folders_to_explore.pop(0)
            all_folders.append(folder_obj)
            for subfolder in folder_obj.folder.GetSubFolderList():
                new_bin_location = ''
                if folder_obj.bin_location != '/':
                    new_bin_location = f"{folder_obj.bin_location}/{subfolder.GetName()}"
                else:
                    new_bin_location = f"/{subfolder.GetName()}"
                folders_to_explore.append(self.MediaFolder(subfolder, new_bin_location))
        return all_folders

    def get_all_timeline_clips_with_timecode(self) -> list[MediaClip]:
        clips_in_timeline = []

        if self.timeline:
            tuples = self.get_all_media_objects_in_timeline()

            frame_rate = self.project.GetSetting('timelineFrameRate')
            drop_frame = self.project.GetSetting('timelineDropFrameTimecode')
            timeline_frame_rate = self.timeline.GetSetting("timelineFrameRate")
            if (timeline_frame_rate is not None):
                if (timeline_frame_rate != ""):
                    frame_rate = timeline_frame_rate
                    drop_frame = self.project.GetSetting('timelineDropFrameTimecode')

            # Resolve returns a string of '0' if drop frames are not used and '1' if drop frames are used
            if drop_frame == '1':
                drop_frame = True
            else:
                drop_frame = False

            for tuple in tuples:
                item = tuple[0]
                mediaPoolItem = item.GetMediaPoolItem()
                if mediaPoolItem is not None:
                    mediaClip = self.MediaClip(clip=mediaPoolItem, timecode=self.frame_id_to_timecode(frame_rate, drop_frame, item.GetStart()), track=tuple[1]['track'])
                    clips_in_timeline.append(mediaClip)
        return clips_in_timeline


    def get_all_media_objects_in_timeline(self):
        timeline_media = []
        for i in range(self.timeline.GetTrackCount("video")):
            cur_track = self.timeline.GetItemListInTrack("video", i + 1)
            for j in range(len(cur_track)):
                timeline_media.append((self.timeline.GetItemListInTrack("video", i + 1)[j], {"track": i + 1}))
        # Ignore audio tracks for now as there's no use cases for it, if audio is added,
        # get_all_timeline_clips_with_timecode will need to be updated to prevent two timeecodes 
        return timeline_media

    def get_all_interlaced_in_media_pool(self):
        all_media = self.get_all_media_in_media_pool()
        interlaced_media = {"scope": "project", "selectedMedia": []}
        for media in all_media["media"]:
            if self.is_interlaced(media["fieldType"]):
                interlaced_media["selectedMedia"].append(media)
        return interlaced_media
    
    def get_all_interlaced_in_timeline(self):
        all_media = self.get_all_media_in_media_pool()
        interlaced_media = {"scope": "timeline", "selectedMedia": []}
        for media in all_media["media"]:
            if self.is_interlaced(media["fieldType"]) and media["timecodes"] != []:
                interlaced_media["selectedMedia"].append(media)
        return interlaced_media

    def get_all_compound_clips_in_media_pool(self):
        all_media = self.get_all_media_in_media_pool()
        compound_clips = {"scope": "project", "selectedMedia": []}
        for media in all_media["media"]:
            if media["clipType"] == "Compound":
                compound_clips["selectedMedia"].append(media)
        return compound_clips
    
    def get_all_compound_clips_in_timeline(self):
        all_media = self.get_all_media_in_media_pool()
        compound_clips = {"scope": "timeline", "selectedMedia": []}
        for media in all_media["media"]:
            if media["clipType"] == "Compound" and media["timecodes"] != []:
                compound_clips["selectedMedia"].append(media)
        return compound_clips

    def is_interlaced(self, fieldType: str):
        if fieldType == "Upper Field" or fieldType == "Lower Field":
            return True
        return False

    def get_all_odd_res_in_timeline(self) -> dict[str, str]:
        all_media = self.get_all_media_in_media_pool()
        odd_res_media = {"scope": "timeline", "selectedMedia": []}
        
        for media in all_media["media"]:
            if self.is_resolution_odd(media["resolution"]) and media["timecodes"] != []:
                odd_res_media["selectedMedia"].append(media)
        
        return odd_res_media

    def frame_id_to_timecode(self, frame_rate, drop_frame, number_of_frames):
        """Converts frame number to a timecode string.

        Args:
            frame_rate (float): The frame rate of the video.
            drop_frame (bool): True if using drop frame timecode; False otherwise.
            number_of_frames (int): The total number of frames.

        Returns:
            str: The timecode string.
        """
        # The `timecode` library expects a string for the frame rate if drop frame timecode is used
        if drop_frame:
            # NTSC drop frame rates
            if frame_rate == 29.97:
                frame_rate_str = '29.97'
            elif frame_rate == 59.94:
                frame_rate_str = '59.94'
            else:
                raise ValueError("Unsupported drop frame rate. Supported rates: 29.97, 59.94")
        else:
            frame_rate_str = str(frame_rate)

        # Create a Timecode instance
        tc = Timecode(frame_rate_str, frames=number_of_frames + 1)
        return str(tc)


    def is_resolution_odd(self, resolution: str) -> bool:
        resolution = resolution.split("x")
        
        is_odd = False
        for axis in resolution:
            # If there are audio files in the MediaPool they return empty string for res
            if axis == '':
                return False
            if int(axis) % 2 != 0:
                is_odd = True
        return is_odd

    """
    returns None or DaVinci Resolve MediaPoolItem
    """
    def get_media_object_from_bin_path(self, bin_location, media_id):
        folders = self.get_all_folders_in_project()

        # Split the bin path and initialize the directory and file name
        bin_location_parts = bin_location.split('/')
        if len(bin_location_parts) < 2:  # Need at least a folder and a file
            return None

        bin_directory = ""
        for index, sub_path in enumerate(bin_location_parts):
            if index != len(bin_location_parts) - 1:
                bin_directory = bin_directory + "/" + sub_path
        file_name = bin_location_parts[-1]

        # Search through all folders for matching bin paths
        for folder in folders:
            if folder.bin_location == bin_directory:
                clips = folder.folder.GetClipList()
                for clip in clips:
                    if clip.GetName() == file_name and clip.GetMediaId() == media_id:
                            return clip

        return None

                    
    def go_to_timecode(self, target_timecode: str) -> None:
        self.timeline.SetCurrentTimecode(target_timecode)

    """
    media_object is a DaVinci Resolve MediaPoolItem
    """
    def replace_single_odd_resolution_file(
        self,
        file_path: str, 
        media_object
    ) -> Dict[str, Union[bool, str]]:    # Get each key from the dict, which are the filepaths
        converted_photo_filepath = convert_photos.convert_single_photo(file_path)
        if convert_photos is not None:
            is_replaced = media_object.ReplaceClip(converted_photo_filepath)
            if not is_replaced:
                return{"success": False, "error_message": f"Failed to replace {file_path} with converted photo at {converted_photo_filepath}."}
            return{"success": True, "file_path": converted_photo_filepath}
        else:
            return{"success": False, "error_message": f"Failed to replace {file_path} because file conversion failed."}