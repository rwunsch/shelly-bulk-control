"""
Group service for managing device groups with higher-level operations.
"""
import asyncio
from typing import List, Dict, Any, Optional

from .group_manager import GroupManager
from .models import DeviceGroup
from ..models.device_registry import device_registry


class GroupService:
    """
    High-level service for managing device groups.
    
    This service wraps the GroupManager and provides additional
    functionality for working with groups and devices.
    """
    
    def __init__(self):
        """Initialize the group service."""
        self.group_manager = GroupManager()
    
    async def list_groups(self) -> List[DeviceGroup]:
        """
        List all available groups.
        
        Returns:
            List of device groups
        """
        return self.group_manager.list_groups()
    
    async def get_group(self, group_name: str) -> Optional[DeviceGroup]:
        """
        Get a group by name.
        
        Args:
            group_name: Name of the group
            
        Returns:
            DeviceGroup or None if not found
        """
        return self.group_manager.get_group(group_name)
    
    async def create_group(self, name: str, description: Optional[str] = None, 
                         device_ids: Optional[List[str]] = None, 
                         tags: Optional[List[str]] = None) -> DeviceGroup:
        """
        Create a new group.
        
        Args:
            name: Name for the new group
            description: Optional description
            device_ids: Optional list of device IDs to include
            tags: Optional list of tags
            
        Returns:
            The created DeviceGroup
        """
        return self.group_manager.create_group(
            name=name,
            description=description,
            device_ids=device_ids or [],
            tags=tags or []
        )
    
    async def update_group(self, group: DeviceGroup) -> DeviceGroup:
        """
        Update an existing group.
        
        Args:
            group: Group to update
            
        Returns:
            Updated DeviceGroup
        """
        return self.group_manager.update_group(group)
    
    async def delete_group(self, group_name: str) -> bool:
        """
        Delete a group.
        
        Args:
            group_name: Name of the group to delete
            
        Returns:
            True if deleted, False if not found
        """
        return self.group_manager.delete_group(group_name)
    
    async def add_device_to_group(self, group_name: str, device_id: str) -> bool:
        """
        Add a device to a group.
        
        Args:
            group_name: Name of the group
            device_id: ID of the device to add
            
        Returns:
            True if successful, False if group not found
        """
        return self.group_manager.add_device_to_group(group_name, device_id)
    
    async def remove_device_from_group(self, group_name: str, device_id: str) -> bool:
        """
        Remove a device from a group.
        
        Args:
            group_name: Name of the group
            device_id: ID of the device to remove
            
        Returns:
            True if removed, False if not found
        """
        return self.group_manager.remove_device_from_group(group_name, device_id)
    
    async def get_devices_in_group(self, group_name: str) -> List[Dict[str, Any]]:
        """
        Get all devices in a group with their details.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List of device details
        """
        group = self.group_manager.get_group(group_name)
        if not group:
            return []
        
        # Get devices from registry
        devices = device_registry.get_devices(group.device_ids)
        
        # Convert to dictionaries for easier serialization
        return [device.to_dict() for device in devices] 