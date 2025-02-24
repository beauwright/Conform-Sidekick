import argparse
import json
import tempfile
import sys
import os
from get_resolve import GetResolve, ResolveConnectionFailed
from resolve_controller import ResolveController
from xml_scale_modifier.fcpxml_scale_modifier import FcpxmlScaleModifier

TEMP_DIR = tempfile.gettempdir()  # Get the system temporary directory
CONFORM_SIDEKICK_DIR = os.path.join(TEMP_DIR, 'ConformSidekick')

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
    
def current_odd_res_in_mediapool_to_json(resolve_helper: ResolveHelper) -> None:
    try:
        output_json(resolve_helper.controller.get_all_odd_res_in_media_pool())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)
def current_interlaced_in_project_to_json(resolve_helper: ResolveHelper) -> None:
    try:
        output_json(resolve_helper.controller.get_all_interlaced_in_media_pool())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def current_interlaced_in_timeline_to_json(resolve_helper: ResolveHelper) -> None:
    try:
        output_json(resolve_helper.controller.get_all_interlaced_in_timeline())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def current_compound_clips_in_project_to_json(resolve_helper: ResolveHelper) -> None:
    try:
        output_json(resolve_helper.controller.get_all_compound_clips_in_media_pool())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)  

def current_compound_clips_in_timeline_to_json(resolve_helper: ResolveHelper) -> None:
    try:
        output_json(resolve_helper.controller.get_all_compound_clips_in_timeline())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)  

def current_odd_res_in_timeline_json(resolve_helper: ResolveHelper) -> None:
    try:
        output_json(resolve_helper.controller.get_all_odd_res_in_timeline())
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def convert_bin_path_json(resolve_helper: ResolveHelper, bin_location: str, media_id: str) -> None:
    try:
        media = resolve_helper.controller.get_media_object_from_bin_path(bin_location, media_id)
        if media is None:
            output_json({"success": False, "error_message": f"Failed to find the file from the specified binLocation: {bin_location}."})
        else:
            result = resolve_helper.controller.replace_single_odd_resolution_file(media.GetClipProperty("File Path"), media)
            output_json(result)
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def export_timeline_fcpxml(resolve_helper: ResolveHelper) -> None:
    try:
        # Ensure the ConformSidekick subfolder exists
        os.makedirs(CONFORM_SIDEKICK_DIR, exist_ok=True)  # Create the directory if it does not exist
        timeline_name = resolve_helper.timeline.GetName() # Get the timeline name
        if not timeline_name or timeline_name == "":
            raise ValueError("No timeline found to export")
        # We're using a FCPXML file to export the timeline to modify it in ways the Python API doesn't support since it's the most accurate way to represent the timeline
        # More recent FCPXML files are wrapped in a bundle, hence the .fcpxmld extension for the file
        file_path = os.path.join(CONFORM_SIDEKICK_DIR, f"{timeline_name}.fcpxmld")
        # We're using a FXPXML 1.10 export since it's the most recent version of the FCPXML format supported by Resolve's scripting API currently even though it's not the most recent version of the FCPXML format that the Resolve GUI supports
        export_success = resolve_helper.timeline.Export(file_path, resolve_helper.resolve.EXPORT_FCPXML_1_10)
        if not export_success:
            raise ValueError("Resolve reported it has failed to export the timeline to FCPXML")
        output_json({"success": True, "path": file_path})
    
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def import_fcpxml(resolve_helper: ResolveHelper, fcpxml_path: str) -> None:
    try:
        if not os.path.exists(fcpxml_path):
            raise ValueError(f"File not found: {fcpxml_path}")
        # Import the FCPXML file
        import_success = resolve_helper.project.GetMediaPool().ImportTimelineFromFile(fcpxml_path)
        if import_success is None:
            raise ValueError("Resolve reported it has failed to import the FCPXML file")
        output_json({"success": True})
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def output_json(output_data: str) -> None:
    try:
        # Ensure the ConformSidekick subfolder exists
        os.makedirs(CONFORM_SIDEKICK_DIR, exist_ok=True)  # Create the directory if it does not exist

        # Create a temp file
        tempfile_output = {"path": ""}
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', dir=CONFORM_SIDEKICK_DIR) as temp_file:
            json.dump(output_data, temp_file, indent=4)
            tempfile_output["path"] = temp_file.name
        print(json.dumps(tempfile_output, indent=4))  # Print the path to the temp file
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process Resolve controls.')
    parser.add_argument('operation', type=str, choices=['projectAndTimeline', 'oddResInProject', 'oddResInTimeline', 'interlacedInProject', 'interlacedInTimeline', 'compoundClipsInProject', 'compoundClipsInTimeline', 'convertOddResPhoto', 'jumpToTimecode', 'exportCurrentTimelineFCPXML', 'importFCPXML', 'modifyFCPXMLScaling'],
                        help='Operation to perform')
    parser.add_argument('--binLocation', type=str, help='Bin location for the odd resolution photo to convert', required=False)
    parser.add_argument('--mediaId', type=str, help='MediaId for the odd resolution photo to convert', required=False)
    parser.add_argument('--tc', type=str, help='Timecode to jump playhead to', required=False)
    parser.add_argument('--fcpxmld', type=str, help='Path to the FCPXMLD bundle containing an FCPXML file to import', required=False)
    parser.add_argument('--scalingValue', type=str, help='Scaling value to multiply the FCPXML file with', required=False)
    parser.add_argument('--scalingType', type=str, help='Scaling type to multiply the FCPXML file with', required=False)
    parser.add_argument('--saveScaledFCPXMLDPath', type=str, help='Path to save the new FCPXMLD bundle containing a modified FCPXML file at', required=False)
    parser.add_argument('--saveScaledFCPXMLDName', type=str, help='Name of the new FCPXMLD bundle containing a modified FCPXML file to save', required=False)
    return parser.parse_args()

def main():
    args = parse_arguments()
    resolve_helper = ResolveHelper()

    try:
        if args.operation == 'projectAndTimeline':
            info = resolve_helper.project_and_timeline_info()
            output_json(info)

        elif args.operation == 'oddResInProject':
            current_odd_res_in_mediapool_to_json(resolve_helper)

        elif args.operation == 'oddResInTimeline':
            current_odd_res_in_timeline_json(resolve_helper)

        elif args.operation == 'interlacedInProject':
            current_interlaced_in_project_to_json(resolve_helper)

        elif args.operation == 'interlacedInTimeline':
            current_interlaced_in_timeline_to_json(resolve_helper)

        elif args.operation == 'compoundClipsInProject':
            current_compound_clips_in_project_to_json(resolve_helper)

        elif args.operation == 'compoundClipsInTimeline':
            current_compound_clips_in_timeline_to_json(resolve_helper)

        elif args.operation == 'convertOddResPhoto':
            if not args.binLocation or not args.mediaId:
                print("Error: --binLocation and --mediaId are required for 'convertBinLocation'")
                sys.exit(1)
            convert_bin_path_json(resolve_helper, args.binLocation, args.mediaId)

        elif args.operation == 'jumpToTimecode':
            if not args.tc:
                print("Error: --tc is required for 'jumpToTimecode'")
                sys.exit(1)
            resolve_helper.controller.go_to_timecode(args.tc)

        elif args.operation == 'exportCurrentTimelineFCPXML':
            export_timeline_fcpxml(resolve_helper)

        elif args.operation == 'importFCPXML':
            if not args.fcpxmld:
                print("Error: --fcpxmld is required for 'importFCPXML'")
                sys.exit(1)
            import_fcpxml(resolve_helper, args.fcpxmld)

        elif args.operation == 'modifyFCPXMLScaling':
            if not args.scalingValue or not args.saveScaledFCPXMLDPath or not args.saveScaledFCPXMLDName or not args.fcpxmld:
                print("Error: --scalingValue, --saveScaledFCPXMLDPath, --saveScaledFCPXMLDName, and --fcpxmld are required for 'modifyFCPXMLScaling'")
                sys.exit(1)
            scaler = FcpxmlScaleModifier()
            scaler.load(args.fcpxmld)
            if args.scalingType:
                if args.scalingType not in scaler.get_supported_scaling_types():
                    print(f"Error: scalingType {args.scalingType} is not supported.")
                    sys.exit(1)
                scaler.multiply_all_scaling_and_pos_values_of_scaling_type(args.scalingValue, args.scalingType)
            else:
                scaler.multiply_all_scaling_and_pos_values(args.scalingValue)
            scaler.save(args.saveScaledFCPXMLDPath, args.saveScaledFCPXMLDName)
                

    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()