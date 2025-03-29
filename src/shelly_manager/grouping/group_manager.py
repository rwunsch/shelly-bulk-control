"""
Group manager for handling device groups.
"""
import os
import yaml
import re
from typing import Dict, List, Optional, Set, Any
import logging
from pathlib import Path

from .models import DeviceGroup
from ..utils.logging import get_logger

# Get the logger for this module
logger = get_logger(__name__)

DEFAULT_GROUPS_DIR = "data/groups"

class GroupManager:
    """
    Manager for Shelly device groups.
    
    This class handles the creation, modification, and persistence of device groups.
    Groups are stored in individual YAML files in the specified directory.
    """
    
    def __init__(self, groups_dir: Optional[str] = None):
        """
        Initialize the group manager.
        
        Args:
            groups_dir: Directory to store group files. If None, uses the environment variable
                        SHELLY_GROUPS_DIR or the default directory.
        """
        # Check for environment variable first, then use argument, then default
        self.groups_dir = os.environ.get('SHELLY_GROUPS_DIR') or groups_dir or DEFAULT_GROUPS_DIR
        self.groups: Dict[str, DeviceGroup] = {}
        
        logger.debug(f"Initializing GroupManager with groups directory: {self.groups_dir}")
        
        # Load existing groups
        self._load_groups()
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a group name for use as a filename.
        
        Args:
            name: Group name to sanitize
            
        Returns:
            Sanitized name safe for use as a filename
        """
        # Replace invalid filename characters with underscores
        sanitized = re.sub(r'[\\/*?:"<>|]', '_', name)
        # Ensure no spaces in filename
        sanitized = sanitized.replace(' ', '_')
        return sanitized
    
    def _get_group_file_path(self, group_name: str) -> str:
        """
        Get the file path for a group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            Full path to the group's YAML file
        """
        filename = f"{self._sanitize_filename(group_name)}.yaml"
        return os.path.join(self.groups_dir, filename)
    
    def _load_groups(self) -> None:
        """
        Load all group definitions from YAML files in the groups directory.
        """
        self.groups = {}
        
        try:
            # Create the groups directory if it doesn't exist
            os.makedirs(self.groups_dir, exist_ok=True)
            
            # Find all YAML files in the directory
            for filename in os.listdir(self.groups_dir):
                # Skip the main groups.yaml file and any backup files
                if filename == 'groups.yaml' or filename.endswith('.bak'):
                    continue
                    
                if not filename.endswith('.yaml'):
                    continue
                    
                file_path = os.path.join(self.groups_dir, filename)
                
                try:
                    with open(file_path, 'r') as f:
                        group_data = yaml.safe_load(f) or {}
                    
                    if not isinstance(group_data, dict):
                        logger.warning(f"Invalid group data in {file_path}: not a dictionary")
                        continue
                    
                    # Get the group name - either from the data or from the filename
                    if "name" not in group_data:
                        # Extract name from filename (remove .yaml extension)
                        group_name = os.path.splitext(filename)[0]
                        group_data["name"] = group_name
                    
                    group = DeviceGroup.from_dict(group_data)
                    self.groups[group.name] = group
                    logger.debug(f"Loaded group '{group.name}' from {file_path}")
                except Exception as e:
                    logger.error(f"Failed to load group from {file_path}: {str(e)}")
            
            logger.info(f"Loaded {len(self.groups)} groups from {self.groups_dir}")
            
        except Exception as e:
            logger.error(f"Failed to load groups: {str(e)}")
            self.groups = {}
    
    def _save_group(self, group: DeviceGroup) -> bool:
        """
        Save a single group to its own YAML file.
        
        Args:
            group: The group to save
            
        Returns:
            bool: True if the save was successful, False otherwise
        """
        try:
            # Create the groups directory if it doesn't exist
            os.makedirs(self.groups_dir, exist_ok=True)
            
            # Get the file path
            file_path = self._get_group_file_path(group.name)
            
            # Convert the group to a dictionary
            group_dict = group.to_dict()
            
            # Save to YAML file
            with open(file_path, 'w') as f:
                yaml.dump(group_dict, f, sort_keys=False, default_flow_style=False)
            
            logger.debug(f"Saved group '{group.name}' to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save group '{group.name}': {str(e)}")
            return False
    
    def _delete_group_file(self, group_name: str) -> bool:
        """
        Delete a group's YAML file.
        
        Args:
            group_name: Name of the group to delete
            
        Returns:
            bool: True if the file was deleted, False otherwise
        """
        try:
            file_path = self._get_group_file_path(group_name)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted group file {file_path}")
                return True
            else:
                logger.warning(f"Group file {file_path} does not exist")
                return False
        except Exception as e:
            logger.error(f"Failed to delete group file for '{group_name}': {str(e)}")
            return False
    
    def _save_groups(self) -> None:
        """
        Save all groups to their individual YAML files.
        
        Note: This is provided for backward compatibility.
        New code should use _save_group for individual groups.
        """
        for group in self.groups.values():
            self._save_group(group)
    
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
        self._save_group(group)
        
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
        self._save_group(group)
        
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
        
        # Remove the group from memory
        del self.groups[group_name]
        
        # Delete the group file
        self._delete_group_file(group_name)
        
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
        self._save_group(group)
        
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
            self._save_group(group)
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
            all_devices.update(group.device_ids)
        
        return all_devices 