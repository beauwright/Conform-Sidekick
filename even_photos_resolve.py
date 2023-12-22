from python_get_resolve import GetResolve, ResolveConnectionFailed
import sys
import convert_photos

def get_all_media_paths(project):
    # Iterate through the mediapool to get every piece of media from the root folder
    # What Resolve calls bins in the GUI are called Folders in the API
    media_pool = project.GetMediaPool()

    folders_to_explore = [media_pool.GetRootFolder()]
    all_folders = []

    while len(folders_to_explore):
        folder = folders_to_explore.pop(0)
        all_folders.append(folder)
        for subfolder in folder.GetSubFolderList():
            folders_to_explore.append(subfolder)

    all_media = []

    for folder in all_folders:
        clips = folder.GetClipList()
        for clip in clips:
            all_media.append(clip)
    
    return all_media

def get_all_odd_resolution_media(all_media):
    # Store the Resolve MediaPoolItems in a dict with the filepath as the key so
    # we can find the objects later to manipulate
    resolve_media_path_and_object = {}
    for media in all_media:
        resolution = media.GetClipProperty("Resolution")
        # Resolve outputs resolution as a string with the two values seperated by
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
            resolve_media_path_and_object[media.GetClipProperty("File Path")] = media
    return resolve_media_path_and_object

def replace_all_odd_resolution_media(all_odd_media) -> None:
    # Get each key from the dict, which are the filepaths
    for entry in all_odd_media:
        # Try to convert every odd resolution file, replace the MediaPoolItem with the
        # converted one if successful
        replace_single_odd_resolution_file(entry, all_odd_media[entry])


def replace_single_odd_resolution_file(file_path, media_object) -> None:
    # Get each key from the dict, which are the filepaths
    converted_photo_filepath = convert_photos.convert_single_photo(file_path)
    if convert_photos is not None:
        is_replaced = media_object.ReplaceClip(converted_photo_filepath)
        if not is_replaced:
            print("Failed to replace ", file_path, 
                    "with converted photo at ", converted_photo_filepath)
    else:
        print("Failed to replace ", file_path, "because file conversion failed")


def get_resolve_current_project():
    # Open current Resolve project
    try:
        resolve = GetResolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        return project
    except AttributeError:
        raise ResolveConnectionFailed



def convert_photos_in_media_pool() -> None:
    # Open current Resolve project
    project = get_resolve_current_project()

    # Find the odd res media
    media = get_all_media_paths(project)
    odd_res_media = get_all_odd_resolution_media(media)
    replace_all_odd_resolution_media(odd_res_media)