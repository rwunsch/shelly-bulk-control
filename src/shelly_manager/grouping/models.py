"""
Models for defining device groups.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class DeviceGroup:
    """
    Represents a group of Shelly devices.
    """
    name: str
    description: Optional[str] = None
    device_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)

    def add_device(self, device_id: str) -> None:
        """
        Add a device to the group.
        
        Args:
            device_id: The ID of the device to add (MAC address or device identifier)
        """
        if device_id not in self.device_ids:
            self.device_ids.append(device_id)
    
    def remove_device(self, device_id: str) -> bool:
        """
        Remove a device from the group.
        
        Args:
            device_id: The ID of the device to remove
            
        Returns:
            bool: True if the device was removed, False if it wasn't in the group
        """
        if device_id in self.device_ids:
            self.device_ids.remove(device_id)
            return True
        return False
    
    def has_device(self, device_id: str) -> bool:
        """
        Check if a device is in the group.
        
        Args:
            device_id: The ID of the device to check
            
        Returns:
            bool: True if the device is in the group, False otherwise
        """
        return device_id in self.device_ids
    
    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the group.
        
        Args:
            tag: The tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> bool:
        """
        Remove a tag from the group.
        
        Args:
            tag: The tag to remove
            
        Returns:
            bool: True if the tag was removed, False if it wasn't in the group
        """
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the group to a dictionary for serialization.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the group
        """
        result = {
            "name": self.name,
            "device_ids": self.device_ids,
        }
        
        if self.description:
            result["description"] = self.description
        
        if self.tags:
            result["tags"] = self.tags
            
        if self.config:
            result["config"] = self.config
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceGroup':
        """
        Create a DeviceGroup from a dictionary.
        
        Args:
            data: Dictionary containing group data
            
        Returns:
            DeviceGroup: A new DeviceGroup instance
        """
        return cls(
            name=data["name"],
            description=data.get("description"),
            device_ids=data.get("device_ids", []),
            tags=data.get("tags", []),
            config=data.get("config", {})
        ) 