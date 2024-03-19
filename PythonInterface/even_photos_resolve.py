import argparse
import json
import tempfile
import sys
import os
import time
from python_get_resolve import GetResolve, ResolveConnectionFailed
import convert_photos

media = {}

def get_all_media_in_media_pool(project):
    # Iterate through the MediaPool to get every piece of media from the root folder
    # What Resolve calls bins in the GUI are called Folders in the API
    media_pool = project.GetMediaPool()

    folders_to_explore = [{"folder": media_pool.GetRootFolder(), "binLocation": ""}]
    all_folders = []

    while len(folders_to_explore):
        folder = folders_to_explore.pop(0)
        all_folders.append(folder)
        for subfolder in folder["folder"].GetSubFolderList():
            folders_to_explore.append({"folder": subfolder, "binLocation":(folder["binLocation"] + "/" + subfolder.GetName())})

    all_media = {"scope": "project",
                 "oddResMedia": []
                 }
    
    cur_timeline = get_resolve_current_timeline()
    clips_in_timeline = []

    if cur_timeline:
        items = get_all_media_items_in_timeline(cur_timeline)
        #print("items is ", items)

        frame_rate = project.GetSetting('timelineFrameRate')
        #print("project frame rate is ", frame_rate)
        timeline = get_resolve_current_timeline()
        timeline_frame_rate = timeline.GetSetting("timelineFrameRate")
        if (timeline_frame_rate is not None):
            if (timeline_frame_rate != ""):
                #print("timeline frame rate", timeline_frame_rate)
                frame_rate = timeline_frame_rate
        for item in items:
            clips_in_timeline.append((item.GetMediaPoolItem(), frame_id_to_timecode(item.GetStart(), frame_rate)))
    #print("frame rate is", frame_rate)
    for folder in all_folders:
        clips = folder["folder"].GetClipList()
        #print(clips)
        for clip in clips:
            timecodes = []
            if clips_in_timeline:
                for item in clips_in_timeline:
                    if clip.GetMediaId() == item[0].GetMediaId():
                        timecodes.append(item[1])
            all_media["oddResMedia"].append({"displayName": clip.GetName(), "binLocation": folder["binLocation"] + "/" + clip.GetName(), "resolution": clip.GetClipProperty("resolution"), "timecodes":timecodes, "filepath": clip.GetClipProperty("File Path")})
    #print("all media", all_media)
    return all_media

def get_all_media_items_in_timeline(timeline):
    timeline_media = []
    for i in range(timeline.GetTrackCount("video")):
            timeline_media.extend(timeline.GetItemListInTrack("video", i + 1))
    for i in range(timeline.GetTrackCount("audio")):
            timeline_media.extend(timeline.GetItemListInTrack("audio", i + 1))
    return timeline_media


def get_all_media_in_timeline(timeline):
    all_media = {"scope": "project",
                "oddResMedia": []
                }
    clips = get_all_media_items_in_timeline(timeline)
    for clip in clips:
        #TODO: merge different instances of clips from the same media pool
        #TODO: get bin location
        all_media["oddResMedia"].append({"displayName": clip.GetName(), "binLocation": "", "resolution": clip.GetClipProperty("resolution"), "timecodes":"", "filepath": clip.GetClipProperty("File Path")})

def frame_id_to_timecode(frame_id, frame_rate):
    frames = int(frame_id % frame_rate)
    seconds = int((frame_id // frame_rate) % 60)
    minutes = int((frame_id // (frame_rate * 60)) % 60)
    hours = int((frame_id // (frame_rate * 3600)) % 24)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

def get_all_odd_resolution_media(selected_media):
    # Store the Resolve MediaPoolItems in a dict with the filepath as the key so
    # we can find the objects later to manipulate
    odd_res_media = []
    for media in selected_media:
        resolution = media["resolution"]
        # Resolve outputs resolution as a string with the two values separated by
        # an 'x', so we need to split by 'x' and then typecast as int
        resolution = resolution.split("x")
        
        is_even = True
        for axis in resolution:
            # If there are audio files in the MediaPool they return empty string for res
            if axis == '':
                continue
            if int(axis) % 2 != 0:
                is_even = False
        
        if not is_even:
            odd_res_media.append(media)
    return odd_res_media

def replace_all_odd_resolution_media(all_odd_media) -> None:
    # Get each key from the dict, which are the filepaths
    for entry in all_odd_media:
        # Try to convert every odd resolution file, replace the MediaPoolItem with the
        # converted one if successful
        replace_single_odd_resolution_file(entry, all_odd_media[entry])


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
    
    

def convert_photos_in_media_pool() -> None:
    # Open current Resolve project
    project = get_resolve_current_project()

    # Find the odd res media
    media = get_all_media_in_media_pool(project)
    odd_res_media = get_all_odd_resolution_media(media)
    replace_all_odd_resolution_media(odd_res_media)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('operation', type=str, choices=['projectAndTimeline'],
                        help='Operation to perform')
    return parser.parse_args()

def currentMediaPoolToJSON():
    try:
        project = get_resolve_current_project()
        outputJSON(get_all_media_in_media_pool(project))
    except Exception as e:
        sys.stderr.write(str(e))
        exit()

def projectAndTimelineToJSON():
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
        
        outputJSON(output_data=output_data)

    except Exception as e:
        sys.stderr.write(str(e))
        exit()

def outputJSON(output_data: str):
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

def main():
    args = parse_arguments()

    if args.operation == 'projectAndTimeline':
        projectAndTimelineToJSON()
    
if __name__ == "__main__":
    main()