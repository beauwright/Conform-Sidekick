from typing import Dict, Union
from get_resolve import GetResolve, ResolveConnectionFailed
import convert_photos


class ResolveController:
    def __init__(self, project, timeline):
        self.project = project
        self.timeline = timeline

    class MediaFolder:
        def __init__(self, folder, bin_location):
            self.folder = folder
            self.bin_location = bin_location


    def get_all_odd_res_in_media_pool(self) -> dict[str, str]:
        all_folders = self.get_all_folders_in_project()

        all_media = {"scope": "project",
                    "oddResMedia": []
                    }
        
        clips_in_timeline = self.get_all_timeline_clips_with_timecode()
        
        for folder in all_folders:
            clips = folder.folder.GetClipList()
            for clip in clips:
                timecodes = []
                if clips_in_timeline:
                    for item in clips_in_timeline:
                        try:
                            if clip.GetMediaId() == item[0].GetMediaId():
                                timecodes.append(item[1])
                        except:
                            pass
                
                resolution = clip.GetClipProperty("resolution")
                if self.is_resolution_odd(resolution):
                    all_media["oddResMedia"].append({"displayName": clip.GetName(), "binLocation": folder.bin_location + clip.GetName(), "resolution": clip.GetClipProperty("resolution"), "timecodes":timecodes, "filepath": clip.GetClipProperty("File Path")})
        return all_media

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

    def get_all_timeline_clips_with_timecode(self):
        clips_in_timeline = []

        if self.timeline:
            items = self.get_all_media_objects_in_timeline()

            frame_rate = self.project.GetSetting('timelineFrameRate')
            timeline_frame_rate = self.timeline.GetSetting("timelineFrameRate")
            if (timeline_frame_rate is not None):
                if (timeline_frame_rate != ""):
                    frame_rate = timeline_frame_rate
            for item in items:
                mediaPoolItem = item.GetMediaPoolItem()
                if mediaPoolItem is not None:
                    clips_in_timeline.append((mediaPoolItem, self.frame_id_to_timecode(item.GetStart(), frame_rate)))
        return clips_in_timeline


    def get_all_media_objects_in_timeline(self):
        timeline_media = []
        for i in range(self.timeline.GetTrackCount("video")):
                timeline_media.extend(self.timeline.GetItemListInTrack("video", i + 1))
        for i in range(self.timeline.GetTrackCount("audio")):
                timeline_media.extend(self.timeline.GetItemListInTrack("audio", i + 1))
        return timeline_media


    def get_all_odd_res_in_timeline(self) -> dict[str, str]:
        all_folders = self.get_all_folders_in_project()

        all_media = {"scope": "timeline",
                    "oddResMedia": []
                    }
        
        clips_in_timeline = self.get_all_timeline_clips_with_timecode()
        
        for folder in all_folders:
            clips = folder.folder.GetClipList()
            for clip in clips:
                timecodes = []
                if clips_in_timeline:
                    for item in clips_in_timeline:
                        if clip.GetMediaId() == item[0].GetMediaId():
                            timecodes.append(item[1])
                resolution = clip.GetClipProperty("resolution")
                if self.is_resolution_odd(resolution) and len(timecodes):
                    all_media["oddResMedia"].append({"displayName": clip.GetName(), "binLocation": folder.bin_location + clip.GetName(), "resolution": clip.GetClipProperty("resolution"), "timecodes":timecodes, "filepath": clip.GetClipProperty("File Path")})
        return all_media

    def frame_id_to_timecode(self, frame_id, frame_rate) -> str:
        frames = int(frame_id % frame_rate)
        seconds = int((frame_id // frame_rate) % 60)
        minutes = int((frame_id // (frame_rate * 60)) % 60)
        hours = int((frame_id // (frame_rate * 3600)) % 24)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

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
    def get_media_object_from_bin_path(self):
        folders = self.get_all_folders_in_project()

        bin_path = bin_path.split('/')
        bin_directory = ""

        if len(bin_path) == 0:
            return None

        file_name = bin_path[len(bin_path) - 1]

        for index, sub_path in enumerate(bin_path):
            if index != len(bin_path) - 1:
                bin_directory = bin_directory + "/" + sub_path

        clips = None
        for folder in folders:
            if(folder.bin_location == bin_directory):
                clips = folder.folder.GetClipList()
        
        if clips is None:
            return None
        
        found_clip = None

        for clip in clips:
            if clip.GetName() == file_name:
                found_clip = clip

        return found_clip
                    
    def go_to_timecode(self, target_timecode: str) -> None:
        self.timeline.SetCurrentTimecode(target_timecode)

    """
    media_object is a DaVinci Resolve MediaPoolItem
    """
    def replace_single_odd_resolution_file(
        file_path: str, 
        media_object
    ) -> Dict[str, Union[bool, str]]:    # Get each key from the dict, which are the filepaths
        converted_photo_filepath = convert_photos.convert_single_photo(file_path)
        if convert_photos is not None:
            is_replaced = media_object.ReplaceClip(converted_photo_filepath)
            if not is_replaced:
                return{"success": False, "file_path": file_path, "message": f"Failed to replace {file_path} with converted photo at {converted_photo_filepath}."}
            return{"success": True, "file_path": file_path, "message": f"Converted photo located at {converted_photo_filepath}."}
        else:
            return{"success": False, "file_path": file_path, "message": f"Failed to replace {file_path} because file conversion failed."}