from abc import ABC, abstractmethod

class Clip:
    def __init__(self, clip_id: str, clip_name: str, scaling_type: str, scaling_x: str, scaling_y:str, pos_x: str, pos_y: str, anchor_x: str, anchor_y: str):
        self.clip_id = clip_id
        self.clip_name = clip_name
        self.scaling_type = scaling_type
        self.scaling_x = scaling_x
        self.scaling_y = scaling_y
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y

    def __str__(self):
        return f"Clip ID: {self.clip_id}, Clip Name: {self.clip_name}, Scaling Type: {self.scaling_type}, Scaling Value: {self.scaling_value}, Pos X: {self.pos_x}, Pos Y: {self.pos_y}"

class AbstractXMLScaleModifier(ABC):
    @abstractmethod
    def load(self, file_path: str) -> None:
        """Load an XML file. Returns True if the load was successful, False otherwise."""
        pass

    @abstractmethod
    def get_supported_scaling_types(self) -> list[str]:
        """Returns the supported scaling types of an XML format. For example, "fit" or "fill". If the XML format doesn't support multiple scaling types, returns a list with a single element of the only supported type."""
        pass

    @abstractmethod
    def get_all_clips(self) -> Clip:
        """Returns all clip IDs in the XML."""
        pass

    @abstractmethod
    def multiply_all_scaling_and_pos_values(self, multiply_value: str) -> None:
        """Multiplies every clip's scaling and positioning values with the user's provided value."""
        pass

    @abstractmethod
    def multiply_all_scaling_and_pos_values_of_scaling_type(self, multiply_value: str, scaling_type: str) -> None:
        """Multiplies the scaling and positioning values for all clips of a given scaling type with the user's provided value."""
        pass

    @abstractmethod
    def multiply_scaling_and_pos_value_for_clip_ids(self, multiply_value: str, clip_ids: list[str]) -> None:
        """Modify a specific value within the XML."""
        pass

    @abstractmethod
    def update_scaling_and_pos_value_for_clip_id(self, clip_id: str, new_clip_values: Clip) -> None:
        """Replace the clip values within the XML with those provided in the new_clip_values object."""
        pass

    @abstractmethod
    def save(self, file_path: str) -> None:
        """Save the modified XML to a file. Returns True if the save was successful, False otherwise."""
        pass
