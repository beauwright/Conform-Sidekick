from .base import AbstractXMLScaleModifier, Clip
import xml.etree.ElementTree as ET
import os

class FcpxmlScaleModifier(AbstractXMLScaleModifier):
    def __init__(self):
        self.clips = []
        # none is the equivalent of Premiere's standard scaling type and DaVinci's crop scaling type
        # unknown is used when the scaling type is not specified in the XML, will be treated as "fit" unless otherwise specified by the project scaling type
        self.supported_scaling_types = ["fit", "fill", "none", "unknown"]
        self._xml_tree = None
        self.timeline_name = None
        self.project_scaling_type = "fit"

    def _pull_fcpxml_from_bundle(self, file_path: str) -> str:
        """Pull the fcpxml file from the bundle."""
        # In every bundle, there is a fcpxml file titled "Info.fcpxml"
        return os.path.join(file_path, "Info.fcpxml")

    def _ingest_fcpxml(self, fcpxml: str) -> None:
        """Parse the fcpxml file."""
        # Parse the XML file
        self._xml_tree = ET.parse(fcpxml)
        # Get the root of the XML tree
        root = self._xml_tree.getroot()
        # Verify that the XML is a fcpxml file
        if root.tag != "fcpxml":
            raise ValueError("The XML file is not a FCPXML file.")
        # Verify that the XML version is 1.10
        if root.attrib["version"] != "1.10":
            raise ValueError("The FCPXML version is not 1.10. Only 1.10 is currently supported.")

        # Populate self.clips
        self._populate_clips(root)

    def _get_xml_sequences(self, root: ET.Element) -> list[ET.Element]:
        """Get all sequence elements in the XML."""
        # Find all sequence elements in the XML
        sequences = root.findall(".//library/event/project/sequence")
        if len(sequences) == 0:
            raise ValueError("No sequences found in the XML file.")
        return sequences

    def _populate_timeline_name(self, root: ET.Element) -> None:
        """Get the timeline name from the XML."""
        # Find all sequence elements in the XML
        sequences = self._get_xml_sequences(root)
        # Get the timeline name from the first sequence 
        self.timeline_name = sequences[0].attrib["name"]

    def _get_xml_clips(self, root: ET.Element) -> list[ET.Element]:
        """Get all clip elements in the XML."""
        # Find all clip elements in the XML
        sequences = self._get_xml_sequences(root)

        # Find all clip elements in the first sequence
        clips = sequences[0].findall(".//asset-clip")
        clips.extend(sequences[0].findall(".//clip"))
        if len(clips) == 0:
            raise ValueError("No clips found in the XML file.")
        
        return clips

    def _populate_clips(self, root: ET.Element) -> None:
        """Populate the clips list with Clip objects."""
        # Find all clip elements in the first sequence
        clips = self._get_xml_clips(root)
        if len(clips) == 0:
            raise ValueError("No clips found in the XML file.")
        # Populate self.clips with Clip objects
        for clip in clips:
            clip_id = self._generate_clip_id(clip)
            clip_name = clip.attrib["name"]
            try:
                scaling_type = clip.find(".//adjust-conform").attrib["type"]
            except AttributeError:
                # Scaling is only specified for clips not using the project scaling type
                scaling_type = "unknown"
            _pos_string = clip.find(".//adjust-transform").attrib["position"]
            pos_x, pos_y = _pos_string.split()
            
            _anchor_string = clip.find(".//adjust-transform").attrib["anchor"]
            anchor_x, anchor_y = _anchor_string.split()

            _scaling_string = clip.find(".//adjust-transform").attrib["scale"]
            scaling_x, scaling_y = _scaling_string.split()

            self.clips.append(Clip(clip_id, clip_name, scaling_type, scaling_x, scaling_y, pos_x, pos_y, anchor_x, anchor_y))

    def _generate_clip_id(self, Element: ET.Element) -> str:
        return f"{Element.attrib["offset"]} {Element.attrib["format"]} {Element.attrib["start"]} {Element.attrib["duration"]}"

    def load(self, file_path: str) -> None:
        fcpxml = self._pull_fcpxml_from_bundle(file_path)
        self._ingest_fcpxml(fcpxml)

    def get_supported_scaling_types(self) -> list[str]:
        return self.supported_scaling_types
    
    def set_project_scaling_type(self, scaling_type: str) -> None:
        if scaling_type not in self.supported_scaling_types:
            raise ValueError(f"Scaling type {scaling_type} is not supported.")
        self.project_scaling_type = scaling_type

    def get_project_scaling_type(self) -> str:
        return self.project_scaling_type

    def get_all_clips(self) -> Clip:
        """Returns all clip IDs in the XML."""
        return self.clips
    
    def _multiply_xml_clip_scaling_and_pos_values(self, clip: ET.Element, multiply_value: str) -> None:
            _pos_string = clip.find(".//adjust-transform").attrib["position"]
            pos_x, pos_y = _pos_string.split()
            pos_x = str(float(pos_x) * float(multiply_value))
            pos_y = str(float(pos_y) * float(multiply_value))
            
            _anchor_string = clip.find(".//adjust-transform").attrib["anchor"]
            anchor_x, anchor_y = _anchor_string.split()
            anchor_x = str(float(anchor_x) * float(multiply_value))
            anchor_y = str(float(anchor_y) * float(multiply_value))

            _scaling_string = clip.find(".//adjust-transform").attrib["scale"]
            scaling_x, scaling_y = _scaling_string.split()
            scaling_x = str(float(scaling_x) * float(multiply_value))
            scaling_y = str(float(scaling_y) * float(multiply_value))

            clip.find(".//adjust-transform").attrib["position"] = f"{pos_x} {pos_y}"
            clip.find(".//adjust-transform").attrib["anchor"] = f"{anchor_x} {anchor_y}"
            clip.find(".//adjust-transform").attrib["scale"] = f"{scaling_x} {scaling_y}"


    def multiply_all_scaling_and_pos_values(self, multiply_value: str) -> None:
        clips = self._get_xml_clips(self._xml_tree.getroot())        
        for clip in clips:
            self._multiply_xml_clip_scaling_and_pos_values(clip, multiply_value)

    def _find_xml_clip_from_clip_id(self, clip_id: str) -> ET.Element:
        clips = self._get_xml_clips(self._xml_tree.getroot())
        for clip in clips:
            current_clip_id = self._generate_clip_id(clip)
            if current_clip_id == clip_id:
                return clip
        raise ValueError(f"Clip with ID {clip_id} not found.")

    def multiply_all_scaling_and_pos_values_of_scaling_type(self, multiply_value: str, scaling_type: str) -> None:
        # Check given scaling type is supported
        if scaling_type not in self.supported_scaling_types:
            raise ValueError(f"Scaling type {scaling_type} is not supported.")
        
        clips = self.get_all_clips()
        for clip in clips:
            # If the clip scaling type matches
            if clip.scaling_type == scaling_type:
                xml_clip = self._find_xml_clip_from_clip_id(clip.clip_id)
                self._multiply_xml_clip_scaling_and_pos_values(xml_clip, multiply_value)
            # If the clip is using the project scaling type and the project scaling type matches
            elif scaling_type == "unknown" and self.project_scaling_type == scaling_type:
                self._multiply_xml_clip_scaling_and_pos_values(xml_clip, multiply_value)

    def multiply_scaling_and_pos_value_for_clip_ids(self, multiply_value: str, clip_ids: list[str]) -> None:
        clips = self._get_xml_clips(self._xml_tree.getroot())
        for clip in clips:
            current_clip_id = self._generate_clip_id(clip)
            if current_clip_id in clip_ids:
                self._multiply_xml_clip_scaling_and_pos_values(clip, multiply_value)

    def update_scaling_and_pos_value_for_clip_id(self, clip_id: str, new_clip_values: Clip) -> None:
        clips = self._get_xml_clips(self._xml_tree.getroot())
        for clip in clips:
            current_clip_id = self._generate_clip_id(clip)
            if current_clip_id == clip_id:
                clip.find(".//adjust-transform").attrib["position"] = f"{new_clip_values.pos_x} {new_clip_values.pos_y}"
                clip.find(".//adjust-transform").attrib["anchor"] = f"{new_clip_values.anchor_x} {new_clip_values.anchor_y}"
                clip.find(".//adjust-transform").attrib["scale"] = f"{new_clip_values.scaling_x} {new_clip_values.scaling_y}"

    def save(self, save_dir_path: str, file_name: str) -> str:
        bundle_dir = os.path.join(save_dir_path, f"{file_name}.fcpxmld")
        os.mkdir(bundle_dir)
        new_file = os.path.join(bundle_dir, "Info.fcpxml")
        self._xml_tree.write(new_file)