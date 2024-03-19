import argparse
import json
import tempfile
import sys
import os
from get_resolve import GetResolve, ResolveConnectionFailed
import convert_photos

class MediaFolder:
    def __init__(self, folder, bin_location):
        self.folder = folder
        self.bin_location = bin_location


def get_all_odd_res_in_media_pool(project, timeline) -> dict[str, str]:
    all_folders = get_all_folders_in_project(project=project)

    all_media = {"scope": "project",
                 "oddResMedia": []
                 }
    
    clips_in_timeline = get_all_timeline_clips_with_timecode(project, timeline)
    
    for folder in all_folders:
        clips = folder.folder.GetClipList()
        for clip in clips:
            timecodes = []
            if clips_in_timeline:
                for item in clips_in_timeline:
                    if clip.GetMediaId() == item[0].GetMediaId():
                        timecodes.append(item[1])
            
            resolution = clip.GetClipProperty("resolution")
            if is_resolution_odd(resolution):
                all_media["oddResMedia"].append({"displayName": clip.GetName(), "binLocation": folder.bin_location + clip.GetName(), "resolution": clip.GetClipProperty("resolution"), "timecodes":timecodes, "filepath": clip.GetClipProperty("File Path")})
    return all_media

def get_all_folders_in_project(project):
    # Iterate through the MediaPool to get every piece of media from the root folder
    # What Resolve calls bins in the GUI are called Folders in the API
    media_pool = project.GetMediaPool()
    folders_to_explore = [MediaFolder(media_pool.GetRootFolder(), "/")]
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
            folders_to_explore.append(MediaFolder(subfolder, new_bin_location))
    return all_folders

def get_all_timeline_clips_with_timecode(project, timeline):
    clips_in_timeline = []

    if timeline:
        items = get_all_media_objects_in_timeline(timeline)

        frame_rate = project.GetSetting('timelineFrameRate')
        timeline = get_resolve_current_timeline()
        timeline_frame_rate = timeline.GetSetting("timelineFrameRate")
        if (timeline_frame_rate is not None):
            if (timeline_frame_rate != ""):
                frame_rate = timeline_frame_rate
        for item in items:
            clips_in_timeline.append((item.GetMediaPoolItem(), frame_id_to_timecode(item.GetStart(), frame_rate)))
    return clips_in_timeline


def get_all_media_objects_in_timeline(timeline):
    timeline_media = []
    for i in range(timeline.GetTrackCount("video")):
            timeline_media.extend(timeline.GetItemListInTrack("video", i + 1))
    for i in range(timeline.GetTrackCount("audio")):
            timeline_media.extend(timeline.GetItemListInTrack("audio", i + 1))
    return timeline_media


def get_all_odd_res_in_timeline(project, timeline) -> dict[str, str]:
    all_folders = get_all_folders_in_project(project=project)

    all_media = {"scope": "timeline",
                 "oddResMedia": []
                 }
    
    clips_in_timeline = get_all_timeline_clips_with_timecode(project, timeline)
    
    for folder in all_folders:
        clips = folder.folder.GetClipList()
        for clip in clips:
            timecodes = []
            if clips_in_timeline:
                for item in clips_in_timeline:
                    if clip.GetMediaId() == item[0].GetMediaId():
                        timecodes.append(item[1])
            resolution = clip.GetClipProperty("resolution")
            if is_resolution_odd(resolution) and len(timecodes):
                all_media["oddResMedia"].append({"displayName": clip.GetName(), "binLocation": folder.bin_location + clip.GetName(), "resolution": clip.GetClipProperty("resolution"), "timecodes":timecodes, "filepath": clip.GetClipProperty("File Path")})
    return all_media

def frame_id_to_timecode(frame_id, frame_rate) -> str:
    frames = int(frame_id % frame_rate)
    seconds = int((frame_id // frame_rate) % 60)
    minutes = int((frame_id // (frame_rate * 60)) % 60)
    hours = int((frame_id // (frame_rate * 3600)) % 24)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

def is_resolution_odd(resolution: str) -> bool:
    resolution = resolution.split("x")
    
    is_odd = False
    for axis in resolution:
        # If there are audio files in the MediaPool they return empty string for res
        if axis == '':
            return False
        if int(axis) % 2 != 0:
            is_odd = True
    return is_odd

def get_media_object_from_bin_path(project, bin_path: str):
    folders = get_all_folders_in_project(project=project)

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
                

def replace_single_odd_resolution_file(file_path, media_object):
    # Get each key from the dict, which are the filepaths
    converted_photo_filepath = convert_photos.convert_single_photo(file_path)
    if convert_photos is not None:
        is_replaced = media_object.ReplaceClip(converted_photo_filepath)
        if not is_replaced:
            return{"success": False, "file_path": file_path, "message": f"Failed to replace {file_path} with converted photo at {converted_photo_filepath}."}
        return{"success": True, "file_path": file_path, "message": f"Converted photo located at {converted_photo_filepath}."}
    else:
        return{"success": False, "file_path": file_path, "message": f"Failed to replace {file_path} because file conversion failed."}

def get_resolve_current_project():
    # Get current Resolve project
    try:
        resolve = GetResolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        return project
    except AttributeError:
        raise ResolveConnectionFailed

def get_resolve_current_timeline():
    # Get current Resolve timeline
    try:
        resolve = GetResolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        timeline = project.GetCurrentTimeline()
        return timeline
    except AttributeError:
        raise ResolveConnectionFailed

def currentMediaPoolToJSON() -> None:
    try:
        project = get_resolve_current_project()
        timeline = get_resolve_current_timeline()
        output_json(get_all_odd_res_in_media_pool(project, timeline))
    except Exception as e:
        sys.stderr.write(str(e))
        exit()

def current_timeline_json() -> None:
    try:
        project = get_resolve_current_project()
        timeline = get_resolve_current_timeline()
        output_json(get_all_odd_res_in_timeline(project, timeline))
    except Exception as e:
        sys.stderr.write(str(e))
        exit()

def project_and_timeline_json() -> None:
    try:
        project = get_resolve_current_project()
        timeline = get_resolve_current_timeline()
        if project is None:
            raise ValueError("Unable to connect to DaVinci Resolve")
        timelineName = "" if timeline is None else timeline.GetName()

        # Standard JSON format for output
        output_data = {
            "projectName": project.GetName(),
            "timelineName": timelineName
        }
        
        output_json(output_data=output_data)

    except Exception as e:
        sys.stderr.write(str(e))
        exit()

def convert_bin_path_json(bin_path: str) -> None:
    project = get_resolve_current_project()
    media = get_media_object_from_bin_path(project, bin_path)
    if media is None:
        output_json({"success": False, "file_path": None, "message": f"Failed to find the file from the specified binPath: {bin_path}."})
    else:
        result = replace_single_odd_resolution_file(media.GetClipProperty("File Path"), media)
        output_json(result)

def output_json(output_data: str) -> None:
    try:
        # Ensure the ConformSidekick subfolder exists
        temp_dir = tempfile.gettempdir()  # Get the system temporary directory
        conform_sidekick_dir = os.path.join(temp_dir, 'ConformSidekick')  # Path to your specific temp dir
        os.makedirs(conform_sidekick_dir, exist_ok=True)  # Create the directory if it does not exist

        # Create a temp file in the specified subdirectory
        tempfile_output = {"path": ""}
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', dir=conform_sidekick_dir) as temp_file:
            json.dump(output_data, temp_file, indent=4)  # Make the JSON output pretty
            tempfile_output["path"] = temp_file.name
        print(json.dumps(tempfile_output, indent=4))  # Print the path to the temp file
    except Exception as e:
        sys.stderr.write(str(e))
        exit()

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process Resolve controls.')
    parser.add_argument('operation', type=str, choices=['projectAndTimeline', 'oddResInProject', 'oddResInTimeline', 'convertBinLocation'],
                        help='Operation to perform')
    parser.add_argument('--binPath', type=str, help='Convert media from a specific bin location', required=False)
    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.operation == 'projectAndTimeline':
        project_and_timeline_json()

    elif args.operation == 'oddResInProject':
        currentMediaPoolToJSON()

    elif args.operation == 'oddResInTimeline':
        current_timeline_json()

    elif args.operation == 'convertBinLocation':
        if not args.binPath:  # Ensure the second argument is provided.
            print("Error: --binPath is required when using 'convertBinLocation'")
            sys.exit(1)
        convert_bin_path_json(args.binPath)
    
if __name__ == "__main__":
    main()