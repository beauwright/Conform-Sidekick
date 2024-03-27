import argparse
import json
import tempfile
import sys
import os
from get_resolve import GetResolve, ResolveConnectionFailed
from resolve_controller import ResolveController

class ResolveHelper:
    def __init__(self):
        self.resolve = self.get_resolve()
        self.project = self.get_current_project()
        self.timeline = self.get_current_timeline()
        self.controller = ResolveController(self.project, self.timeline)

    def get_resolve(self):
        try:
            return GetResolve()
        except AttributeError:
            raise ResolveConnectionFailed

    def get_current_project(self):
        try:
            project_manager = self.resolve.GetProjectManager()
            return project_manager.GetCurrentProject()
        except AttributeError:
            raise ResolveConnectionFailed

    def get_current_timeline(self):
        try:
            return self.project.GetCurrentTimeline()
        except AttributeError:
            raise ResolveConnectionFailed

    def project_and_timeline_info(self):
        if self.project is None:
            raise ValueError("Unable to connect to DaVinci Resolve or fetch project/timeline information")

        return {
            "projectName": self.project.GetName(),
            "timelineName": self.timeline.GetName() if self.timeline else ""
        }
    
def currentMediaPoolToJSON(resolve_helper: ResolveHelper) -> None:
    try:
        # Access ResolveController directly from resolve_helper
        output_json(resolve_helper.controller.get_all_odd_res_in_media_pool())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def current_timeline_json(resolve_helper: ResolveHelper) -> None:
    try:
        # Access ResolveController directly from resolve_helper
        output_json(resolve_helper.controller.get_all_odd_res_in_timeline())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def convert_bin_path_json(resolve_helper: ResolveHelper, bin_location: str, media_id: str) -> None:
    try:
        # Use resolve_helper's attributes and methods
        media = resolve_helper.controller.get_media_object_from_bin_path(bin_location, media_id)
        if media is None:
            output_json({"success": False, "error_message": f"Failed to find the file from the specified binLocation: {bin_location}."})
        else:
            result = resolve_helper.controller.replace_single_odd_resolution_file(media.GetClipProperty("File Path"), media)
            output_json(result)
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

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
        sys.exit(1)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process Resolve controls.')
    parser.add_argument('operation', type=str, choices=['projectAndTimeline', 'oddResInProject', 'oddResInTimeline', 'convertOddResPhoto', 'jumpToTimecode'],
                        help='Operation to perform')
    parser.add_argument('--binLocation', type=str, help='Bin location for the odd resolution photo to convert', required=False)
    parser.add_argument('--mediaId', type=str, help='MediaId for the odd resolution photo to convert', required=False)
    parser.add_argument('--tc', type=str, help='Timecode to jump playhead to', required=False)
    return parser.parse_args()

def main():
    args = parse_arguments()
    resolve_helper = ResolveHelper()

    try:
        if args.operation == 'projectAndTimeline':
            info = resolve_helper.project_and_timeline_info()
            output_json(info)

        elif args.operation == 'oddResInProject':
            currentMediaPoolToJSON(resolve_helper)

        elif args.operation == 'oddResInTimeline':
            current_timeline_json(resolve_helper)

        elif args.operation == 'convertOddResPhoto':
            if not args.binLocation or not args.mediaId:
                print("Error: --binLocation and --mediaId are required for 'convertBinLocation'")
                sys.exit(1)
            convert_bin_path_json(resolve_helper, args.binLocation, args.mediaId)

        elif args.operation == 'jumpToTimecode':
            if not args.tc:
                print("Error: --tc is required for 'jumpToTimecode'")
                sys.exit(1)
            # Now handled within the helper
            resolve_helper.controller.go_to_timecode(args.tc)
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()