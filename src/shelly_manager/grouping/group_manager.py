"""
Group manager for handling device groups.
"""
import os
import yaml
from typing import Dict, List, Optional, Set, Any
import logging
from pathlib import Path

from .models import DeviceGroup
from ..utils.logging import get_logger

# Get the logger for this module
logger = get_logger(__name__)

DEFAULT_GROUPS_DIR = "data/groups"
DEFAULT_GROUPS_FILE = "groups.yaml"

class GroupManager:
    """
    Manager for Shelly device groups.
    
    This class handles the creation, modification, and persistence of device groups.
    Groups are stored in YAML files in the specified directory.
    """
    
    def __init__(self, groups_file: Optional[str] = None):
        """
        Initialize the group manager.
        
        Args:
            groups_file: Path to the groups YAML file. If None, uses the default path.
        """
        self.groups_file = groups_file or os.path.join(DEFAULT_GROUPS_DIR, DEFAULT_GROUPS_FILE)
        self.groups: Dict[str, DeviceGroup] = {}
        
        # Load existing groups
        self._load_groups()
    
    def _load_groups(self) -> None:
        """
        Load all group definitions from YAML files in the groups directory.
        """
        self.groups = {}
        
        try:
            # Create the groups directory if it doesn't exist
            os.makedirs(os.path.dirname(self.groups_file), exist_ok=True)
            
            # Check if the file exists
            if not os.path.exists(self.groups_file):
                logger.info(f"Groups file not found at {self.groups_file}. Creating new file.")
                self._save_groups()
                return
            
            # Load the groups from the file
            with open(self.groups_file, 'r') as f:
                groups_data = yaml.safe_load(f) or {}
            
            # Parse the groups
            if "groups" in groups_data and isinstance(groups_data["groups"], dict):
                for group_name, group_data in groups_data["groups"].items():
                    # Add name to the group data
                    group_data["name"] = group_name
                    self.groups[group_name] = DeviceGroup.from_dict(group_data)
            
            logger.info(f"Loaded {len(self.groups)} groups from {self.groups_file}")
        except Exception as e:
            logger.error(f"Failed to load groups: {str(e)}")
            self.groups = {}
    
    def _save_groups(self) -> None:
        """
        Save all groups to the groups.yaml file.
        """
        try:
            # Create the groups directory if it doesn't exist
            os.makedirs(os.path.dirname(self.groups_file), exist_ok=True)
            
            # Create the data structure
            groups_data = {"groups": {}}
            
            # Add groups to the data structure
            for group_name, group in self.groups.items():
                group_dict = group.to_dict()
                # Remove the name from the dict since it's used as the key
                if "name" in group_dict:
                    del group_dict["name"]
                groups_data["groups"][group_name] = group_dict
            
            # Save the data to the file
            with open(self.groups_file, 'w') as f:
                yaml.dump(groups_data, f, sort_keys=False, default_flow_style=False)
                
            logger.info(f"Saved {len(self.groups)} groups to {self.groups_file}")
        except Exception as e:
            logger.error(f"Failed to save groups: {str(e)}")
    
    def create_group(
        self, 
        name: str, 
        description: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> DeviceGroup:
        """
        Create a new device group.
        
        Args:
            name: Name of the group
            description: Optional description
            device_ids: List of device IDs to include
            tags: Optional list of tags
            config: Optional configuration dictionary
        
        Returns:
            DeviceGroup: The newly created group
            
        Raises:
            ValueError: If a group with this name already exists
        """
        if name in self.groups:
            raise ValueError(f"Group '{name}' already exists")
        
        # Create new group
        group = DeviceGroup(
            name=name,
            description=description or "",
            device_ids=device_ids or [],
            tags=tags or [],
            config=config or {}
        )
        
        # Add to collection and save
        self.groups[name] = group
        self._save_groups()
        
        logger.info(f"Created group '{name}' with {len(group.device_ids)} devices")
        return group
    
    def update_group(self, group: DeviceGroup) -> None:
        """
        Update an existing group.
        
        Args:
            group: The group to update
            
        Raises:
            ValueError: If the group doesn't exist
        """
        if group.name not in self.groups:
            raise ValueError(f"Group '{group.name}' doesn't exist")
        
        # Update the group
        self.groups[group.name] = group
        
        # Save changes
        self._save_groups()
        
        logger.info(f"Updated group '{group.name}'")
    
    def delete_group(self, group_name: str) -> bool:
        """
        Delete a group.
        
        Args:
            group_name: Name of the group to delete
            
        Returns:
            bool: True if the group was deleted, False if it didn't exist
        """
        if group_name not in self.groups:
            return False
        
        # Remove the group
        del self.groups[group_name]
        
        # Save changes
        self._save_groups()
        
        logger.info(f"Deleted group '{group_name}'")
        return True
    
    def get_group(self, group_name: str) -> Optional[DeviceGroup]:
        """
        Get a group by name.
        
        Args:
            group_name: Name of the group to retrieve
            
        Returns:
            Optional[DeviceGroup]: The group, or None if not found
        """
        return self.groups.get(group_name)
    
    def list_groups(self) -> List[DeviceGroup]:
        """
        List all groups.
        
        Returns:
            List of all groups
        """
        return list(self.groups.values())
    
    # Alias for backward compatibility
    get_all_groups = list_groups
    
    def add_device_to_group(self, group_name: str, device_id: str) -> bool:
        """
        Add a device to a group.
        
        Args:
            group_name: Name of the group
            device_id: ID of the device to add
            
        Returns:
            bool: True if the device was added, False if the group doesn't exist
            
        Raises:
            KeyError: If the group doesn't exist
        """
        group = self.get_group(group_name)
        if not group:
            raise KeyError(f"Group '{group_name}' does not exist")
        
        # Check if device already in group
        if device_id in group.device_ids:
            logger.debug(f"Device {device_id} already in group '{group_name}'")
            return True
        
        # Add device to group
        group.add_device(device_id)
        self._save_groups()
        
        logger.info(f"Added device {device_id} to group '{group_name}'")
        return True
    
    def remove_device_from_group(self, group_name: str, device_id: str) -> bool:
        """
        Remove a device from a group.
        
        Args:
            group_name: Name of the group
            device_id: ID of the device to remove
            
        Returns:
            bool: True if the device was removed, False if the group or device doesn't exist
        """
        group = self.get_group(group_name)
        if not group:
            logger.warning(f"Attempted to remove device from non-existent group '{group_name}'")
            return False
        
        # Remove device from group
        if group.remove_device(device_id):
            self._save_groups()
            logger.info(f"Removed device {device_id} from group '{group_name}'")
            return True
        
        logger.debug(f"Device {device_id} not found in group '{group_name}'")
        return False
    
    def get_groups_for_device(self, device_id: str) -> List[DeviceGroup]:
        """
        Get all groups that contain a specific device.
        
        Args:
            device_id: ID of the device
            
        Returns:
            List[DeviceGroup]: List of groups containing the device
        """
        return [group for group in self.groups.values() if group.has_device(device_id)]
    
    def get_devices_in_group(self, group_name: str) -> List[str]:
        """
        Get all device IDs in a specific group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List[str]: List of device IDs in the group
            
        Raises:
            KeyError: If the group doesn't exist
        """
        group = self.get_group(group_name)
        if not group:
            raise KeyError(f"Group '{group_name}' does not exist")
        
        return group.device_ids.copy()
    
    def get_all_devices(self) -> Set[str]:
        """
        Get all device IDs across all groups.
        
        Returns:
            Set[str]: Set of all unique device IDs
        """
        all_devices = set()
        for group in self.groups.values():
            all_devices.update(group.devices)
        
        return all_devices 