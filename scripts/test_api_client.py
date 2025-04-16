#!/usr/bin/env python3
"""
Test client for the Shelly Device Manager API

This script provides a simple command-line interface to test the API endpoints.
"""

import argparse
import json
import sys
from typing import Dict, List, Any, Optional
import httpx

class ShellyManagerClient:
    """Client for the Shelly Device Manager API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client
        
        Args:
            base_url: Base URL of the API
        """
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)
    
    def _make_request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        """Make an HTTP request to the API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path
            data: Request data for POST/PUT requests
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{path}"
        
        try:
            if method == "GET":
                response = self.client.get(url)
            elif method == "POST":
                response = self.client.post(url, json=data)
            elif method == "PUT":
                response = self.client.put(url, json=data)
            elif method == "DELETE":
                response = self.client.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            if response.status_code == 204:  # No content
                return {"status": "success"}
            
            return response.json()
        
        except httpx.HTTPStatusError as e:
            print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
            return {"error": str(e)}
        except httpx.RequestError as e:
            print(f"Error: {str(e)}")
            return {"error": str(e)}
    
    def get_devices(self, scan: bool = False) -> List[Dict]:
        """Get all discovered devices
        
        Args:
            scan: Whether to trigger a new scan before returning devices
            
        Returns:
            List of devices
        """
        return self._make_request("GET", f"/devices?scan={str(scan).lower()}")
    
    def get_device(self, device_id: str) -> Dict:
        """Get a specific device
        
        Args:
            device_id: Device ID
            
        Returns:
            Device information
        """
        return self._make_request("GET", f"/devices/{device_id}")
    
    def get_device_settings(self, device_id: str) -> Dict:
        """Get settings for a specific device
        
        Args:
            device_id: Device ID
            
        Returns:
            Device settings
        """
        return self._make_request("GET", f"/devices/{device_id}/settings")
    
    def update_device_settings(self, device_id: str, settings: Dict) -> Dict:
        """Update settings for a specific device
        
        Args:
            device_id: Device ID
            settings: Settings to update
            
        Returns:
            Result of the operation
        """
        return self._make_request("POST", f"/devices/{device_id}/settings", settings)
    
    def perform_device_operation(self, device_id: str, operation: str, parameters: Optional[Dict] = None) -> Dict:
        """Perform an operation on a specific device
        
        Args:
            device_id: Device ID
            operation: Operation to perform
            parameters: Operation parameters
            
        Returns:
            Result of the operation
        """
        data = {"operation": operation, "parameters": parameters or {}}
        return self._make_request("POST", f"/devices/{device_id}/operation", data)
    
    def get_groups(self) -> List[Dict]:
        """Get all device groups
        
        Returns:
            List of groups
        """
        return self._make_request("GET", "/groups")
    
    def create_group(self, name: str, device_ids: List[str], description: Optional[str] = None) -> Dict:
        """Create a new device group
        
        Args:
            name: Group name
            device_ids: List of device IDs
            description: Group description
            
        Returns:
            Created group
        """
        data = {"name": name, "device_ids": device_ids, "description": description}
        return self._make_request("POST", "/groups", data)
    
    def get_group(self, group_name: str) -> Dict:
        """Get a specific group
        
        Args:
            group_name: Group name
            
        Returns:
            Group information
        """
        return self._make_request("GET", f"/groups/{group_name}")
    
    def update_group(self, group_name: str, device_ids: List[str], description: Optional[str] = None) -> Dict:
        """Update an existing group
        
        Args:
            group_name: Group name
            device_ids: List of device IDs
            description: Group description
            
        Returns:
            Updated group
        """
        data = {"name": group_name, "device_ids": device_ids, "description": description}
        return self._make_request("PUT", f"/groups/{group_name}", data)
    
    def delete_group(self, group_name: str) -> Dict:
        """Delete a group
        
        Args:
            group_name: Group name
            
        Returns:
            Result of the operation
        """
        return self._make_request("DELETE", f"/groups/{group_name}")
    
    def perform_group_operation(self, group_name: str, operation: str, parameters: Optional[Dict] = None) -> Dict:
        """Perform an operation on all devices in a group
        
        Args:
            group_name: Group name
            operation: Operation to perform
            parameters: Operation parameters
            
        Returns:
            Result of the operation
        """
        data = {"operation": operation, "parameters": parameters or {}}
        return self._make_request("POST", f"/groups/{group_name}/operation", data)
    
    def set_group_parameters(self, group_name: str, parameters: Dict, reboot_if_needed: bool = False) -> Dict:
        """Set parameters for all devices in a group
        
        Args:
            group_name: Group name
            parameters: Parameters to set
            reboot_if_needed: Whether to reboot devices if needed
            
        Returns:
            Result of the operation
        """
        data = {"parameters": parameters, "reboot_if_needed": reboot_if_needed}
        return self._make_request("POST", f"/groups/{group_name}/parameters", data)
    
    def trigger_scan(self) -> Dict:
        """Trigger a new network scan for devices
        
        Returns:
            Result of the operation
        """
        return self._make_request("POST", "/discovery/scan")
    
    def get_system_status(self) -> Dict:
        """Get system status information
        
        Returns:
            System status
        """
        return self._make_request("GET", "/system/status")

def print_json(data: Any):
    """Print JSON data in a human-readable format"""
    print(json.dumps(data, indent=2))

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Shelly Device Manager API Client")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Devices
    get_devices_parser = subparsers.add_parser("devices", help="Get all devices")
    get_devices_parser.add_argument("--scan", action="store_true", help="Trigger a new scan")
    
    get_device_parser = subparsers.add_parser("device", help="Get a specific device")
    get_device_parser.add_argument("id", help="Device ID")
    
    # Groups
    get_groups_parser = subparsers.add_parser("groups", help="Get all groups")
    
    create_group_parser = subparsers.add_parser("create-group", help="Create a new group")
    create_group_parser.add_argument("name", help="Group name")
    create_group_parser.add_argument("--device-ids", required=True, help="Comma-separated list of device IDs")
    create_group_parser.add_argument("--description", help="Group description")
    
    # Operations
    operation_parser = subparsers.add_parser("operate", help="Perform an operation")
    operation_parser.add_argument("--device", help="Device ID")
    operation_parser.add_argument("--group", help="Group name")
    operation_parser.add_argument("--operation", required=True, help="Operation to perform")
    operation_parser.add_argument("--params", help="Operation parameters as JSON string")
    
    # Parameters
    params_parser = subparsers.add_parser("set-params", help="Set parameters")
    params_parser.add_argument("--device", help="Device ID")
    params_parser.add_argument("--group", help="Group name")
    params_parser.add_argument("--params", required=True, help="Parameters as JSON string")
    params_parser.add_argument("--reboot", action="store_true", help="Reboot if needed")
    
    # System
    subparsers.add_parser("status", help="Get system status")
    subparsers.add_parser("scan", help="Trigger a new network scan")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    client = ShellyManagerClient(args.url)
    
    if args.command == "devices":
        print_json(client.get_devices(args.scan))
    
    elif args.command == "device":
        print_json(client.get_device(args.id))
    
    elif args.command == "groups":
        print_json(client.get_groups())
    
    elif args.command == "create-group":
        device_ids = args.device_ids.split(",")
        print_json(client.create_group(args.name, device_ids, args.description))
    
    elif args.command == "operate":
        if not (args.device or args.group):
            print("Error: Either --device or --group must be specified")
            sys.exit(1)
        
        params = {}
        if args.params:
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError:
                print("Error: Invalid JSON in --params")
                sys.exit(1)
        
        if args.device:
            print_json(client.perform_device_operation(args.device, args.operation, params))
        else:
            print_json(client.perform_group_operation(args.group, args.operation, params))
    
    elif args.command == "set-params":
        if not (args.device or args.group):
            print("Error: Either --device or --group must be specified")
            sys.exit(1)
        
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            print("Error: Invalid JSON in --params")
            sys.exit(1)
        
        if args.device:
            print_json(client.update_device_settings(args.device, params))
        else:
            print_json(client.set_group_parameters(args.group, params, args.reboot))
    
    elif args.command == "status":
        print_json(client.get_system_status())
    
    elif args.command == "scan":
        print_json(client.trigger_scan())

if __name__ == "__main__":
    main() 