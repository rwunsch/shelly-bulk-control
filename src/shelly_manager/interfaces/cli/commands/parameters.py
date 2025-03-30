"""CLI commands for managing device parameters."""

import typer
import asyncio
from typing import Optional, List, Dict, Any
import os
import json

from rich.console import Console
from rich.table import Table
from rich import box

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.discovery.discovery_service import DiscoveryService
from shelly_manager.parameter.parameter_service import ParameterService
from shelly_manager.utils.logging import LogConfig, get_logger
from shelly_manager.models.device_registry import device_registry
from shelly_manager.models.device import DeviceGeneration

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(help="Manage device parameters")

# Create console for rich output
console = Console()


@app.command("list")
def list_parameters(
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to list parameters for"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Group name to list parameters for"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """
    List available parameters for devices.
    
    Examples:
        - List parameters for all devices:
          shelly-bulk-control parameters list
          
        - List parameters for a specific device:
          shelly-bulk-control parameters list --device shellyplug-s-12345
          
        - List parameters for all devices in a group:
          shelly-bulk-control parameters list --group living_room
    """
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Run the operation asynchronously
        asyncio.run(_list_parameters_async(device_id, group_name, debug))
        
    except Exception as e:
        logger.error(f"Failed to list parameters: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


async def _list_parameters_async(device_id: Optional[str], group_name: Optional[str], debug: bool):
    """
    List parameters asynchronously.
    
    Args:
        device_id: Optional device ID to filter by
        group_name: Optional group name to filter by
        debug: Whether to enable debug logging
    """
    # Initialize services
    discovery_service = DiscoveryService()
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    # Start services
    await discovery_service.start()
    await parameter_service.start()
    
    try:
        console.print("Discovering devices...")
        await discovery_service.discover_devices()
        
        devices = discovery_service.get_devices()
        if not devices:
            console.print("[yellow]No devices found[/yellow]")
            return
            
        # Filter devices if needed
        filtered_devices = list(devices.values())
        
        if device_id:
            filtered_devices = [d for d in filtered_devices if d.id == device_id]
            if not filtered_devices:
                console.print(f"[yellow]Device '{device_id}' not found[/yellow]")
                return
                
        elif group_name:
            # Get devices in the group
            group = group_manager.get_group(group_name)
            if not group:
                console.print(f"[red]Group '{group_name}' not found[/red]")
                return
                
            filtered_devices = [d for d in filtered_devices if d.id in group.device_ids]
            if not filtered_devices:
                console.print(f"[yellow]No devices found in group '{group_name}'[/yellow]")
                return
        
        # Get parameters for each device
        console.print("Discovering parameters...")
        
        all_parameters = {}
        for device in filtered_devices:
            parameters = await parameter_service.discover_device_parameters(device)
            if parameters:
                values = {}
                for param_name, param_def in parameters.items():
                    success, value = await parameter_service.get_parameter_value(device, param_name)
                    if success:
                        values[param_name] = value
                    else:
                        values[param_name] = None
                        
                all_parameters[device.id] = {
                    "device": device,
                    "parameters": parameters,
                    "values": values
                }
        
        # Display results
        _display_parameters(all_parameters)
        
    finally:
        # Stop services
        await parameter_service.stop()
        await discovery_service.stop()


def _display_parameters(all_parameters: Dict[str, Dict[str, Any]]):
    """
    Display parameters in a table.
    
    Args:
        all_parameters: Dictionary of parameters by device
    """
    if not all_parameters:
        console.print("[yellow]No parameters found[/yellow]")
        return
    
    for device_id, device_info in all_parameters.items():
        device = device_info["device"]
        parameters = device_info["parameters"]
        values = device_info["values"]
        
        console.print(f"\n[bold]Parameters for {device.name} ({device.id})[/bold]")
        console.print(f"Model: {device.model}, Generation: {device.generation}, IP: {device.ip}")
        
        if not parameters:
            console.print("[yellow]No parameters available for this device[/yellow]")
            continue
            
        # Create table for parameters
        table = Table(show_header=True, header_style="bold magenta", box=box.SQUARE)
        table.add_column("Parameter", style="dim")
        table.add_column("Display Name")
        table.add_column("Type")
        table.add_column("Value")
        table.add_column("Description")
        
        # Add rows for each parameter
        for param_name, param_def in parameters.items():
            value = values.get(param_name, "N/A")
            value_str = str(value) if value is not None else "N/A"
            
            table.add_row(
                param_name,
                param_def.display_name,
                param_def.parameter_type.value,
                value_str,
                param_def.description
            )
        
        # Display the table
        console.print(table)


@app.command("get")
def get_parameter(
    device_id: str = typer.Argument(..., help="Device ID to get parameter from"),
    parameter_name: str = typer.Argument(..., help="Name of the parameter to get"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """
    Get a parameter value from a device.
    
    Examples:
        - Get the eco_mode parameter from a device:
          shelly-bulk-control parameters get shellyplug-s-12345 eco_mode
    """
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Run the operation asynchronously
        asyncio.run(_get_parameter_async(device_id, parameter_name, debug))
        
    except Exception as e:
        logger.error(f"Failed to get parameter: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


async def _get_parameter_async(device_id: str, parameter_name: str, debug: bool):
    """
    Get a parameter asynchronously.
    
    Args:
        device_id: Device ID to get parameter from
        parameter_name: Name of the parameter
        debug: Whether to enable debug logging
    """
    # Initialize services
    discovery_service = DiscoveryService()
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    # Start services
    await discovery_service.start()
    await parameter_service.start()
    
    try:
        console.print("Discovering devices...")
        await discovery_service.discover_devices()
        
        devices = discovery_service.get_devices()
        if not devices or device_id not in devices:
            console.print(f"[red]Device '{device_id}' not found[/red]")
            return
            
        device = devices[device_id]
        
        # Get parameter value
        console.print(f"Getting parameter '{parameter_name}' from {device.name}...")
        success, value = await parameter_service.get_parameter_value(device, parameter_name)
        
        if success:
            console.print(f"\nParameter: [cyan]{parameter_name}[/cyan]")
            console.print(f"Value: [green]{value}[/green]")
        else:
            console.print(f"[red]Failed to get parameter '{parameter_name}' from device {device.id}[/red]")
        
    finally:
        # Stop services
        await parameter_service.stop()
        await discovery_service.stop()


@app.command("set")
def set_parameter(
    device_id: str = typer.Argument(..., help="Device ID to set parameter on"),
    parameter_name: str = typer.Argument(..., help="Name of the parameter to set"),
    value: str = typer.Argument(..., help="Value to set"),
    reboot: bool = typer.Option(False, "--reboot", help="Reboot device after setting parameter"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """
    Set a parameter value on a device.
    
    Examples:
        - Set the eco_mode parameter on a device to true:
          shelly-bulk-control parameters set shellyplug-s-12345 eco_mode true
          
        - Set the max_power parameter on a device:
          shelly-bulk-control parameters set shellyplug-s-12345 max_power 2000
          
        - Set parameter and reboot the device:
          shelly-bulk-control parameters set shellyplug-s-12345 eco_mode true --reboot
    """
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Parse value
        parsed_value = _parse_value(value)
        
        # Run the operation asynchronously
        asyncio.run(_set_parameter_async(device_id, parameter_name, parsed_value, reboot, debug))
        
    except Exception as e:
        logger.error(f"Failed to set parameter: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


def _parse_value(value_str: str) -> Any:
    """
    Parse a string value into the appropriate type.
    
    Args:
        value_str: Value as string
        
    Returns:
        Parsed value
    """
    # Try to convert to appropriate type
    value_lower = value_str.lower()
    
    # Boolean
    if value_lower == "true":
        return True
    elif value_lower == "false":
        return False
    
    # Number
    try:
        # Integer
        if value_str.isdigit():
            return int(value_str)
        
        # Float
        if "." in value_str and all(p.isdigit() for p in value_str.split(".")):
            return float(value_str)
    except:
        pass
    
    # Default to string
    return value_str


async def _set_parameter_async(device_id: str, parameter_name: str, value: Any, reboot: bool, debug: bool):
    """
    Set a parameter asynchronously.
    
    Args:
        device_id: Device ID to set parameter on
        parameter_name: Name of the parameter
        value: Value to set
        reboot: Whether to reboot after setting
        debug: Whether to enable debug logging
    """
    # Initialize services without starting discovery yet
    discovery_service = DiscoveryService()
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    discovery_started = False
    
    # Start parameter service only - without discovery
    await parameter_service.start(no_discovery=True)
    
    try:
        # Use cached devices first, specifically using device_registry
        device = None
        
        # Prioritize device_registry for lookups without network scanning
        console.print(f"Looking up device {device_id}...")
        
        # Load devices from registry
        device_registry.load_all_devices()
        
        # Try to get the device by MAC address (normalized)
        mac_address = device_id.replace(":", "").upper()
        device = device_registry.get_device(mac_address)
        
        # Check if the device has a valid IP address
        if device and not device.ip_address:
            logger.warning(f"Device found in registry but has no IP address: {device.id}")
            device = None  # Force discovery to find the IP
        
        # If device still not found, start discovery service but try to avoid full network scanning
        if not device:
            console.print("Device not found in registry with valid IP. Starting discovery service...")
            
            # Only start discovery service if we actually need it
            await discovery_service.start()
            discovery_started = True
            
            # Check if get_device method exists
            if hasattr(discovery_service, 'get_device'):
                device = discovery_service.get_device(device_id)
            elif hasattr(discovery_service, 'devices'):
                if isinstance(discovery_service.devices, dict):
                    device = discovery_service.devices.get(device_id)
                else:
                    # If devices is a list, find the device by ID
                    for d in discovery_service.devices:
                        if d.id == device_id:
                            device = d
                            break
            
            # Last resort: do a minimal discovery targeting only our device
            if not device:
                console.print("Device not found in cache. Attempting targeted discovery...")
                # Create a list of the device ID to specifically target
                target_ids = [device_id]
                # Use a short timeout for faster response
                await discovery_service.discover_specific_devices(target_ids, scan_timeout=2)
                
                # Try to get the device again
                if hasattr(discovery_service, 'get_device'):
                    device = discovery_service.get_device(device_id)
                elif hasattr(discovery_service, 'devices'):
                    if isinstance(discovery_service.devices, dict):
                        device = discovery_service.devices.get(device_id)
                    else:
                        # If devices is a list, find the device by ID
                        for d in discovery_service.devices:
                            if d.id == device_id:
                                device = d
                                break
        
        if not device:
            console.print(f"[red]Device '{device_id}' not found[/red]")
            return
            
        # Set parameter value
        console.print(f"Setting parameter '{parameter_name}' on {device.name}...")
        
        # Make sure the device has an IP address
        if not device.ip_address:
            console.print(f"[yellow]Warning: Device {device.id} has no IP address. Trying to find IP address...[/yellow]")
            # If we need to look up the IP, start discovery if not already started
            if not discovery_started:
                await discovery_service.start()
                discovery_started = True
                # Try to find the device with mDNS
                await discovery_service.discover_specific_devices([device.id], scan_timeout=2)
                # Try to get updated device info
                if hasattr(discovery_service, 'get_device'):
                    updated_device = discovery_service.get_device(device.id)
                    if updated_device and updated_device.ip_address:
                        device = updated_device
                        console.print(f"[green]Found IP address for device: {device.ip_address}[/green]")
        
        success = await parameter_service.set_parameter_value(device, parameter_name, value)
        
        if success:
            console.print(f"[green]Successfully set parameter '{parameter_name}' to {value}[/green]")
            
            # Reboot device if requested
            if reboot:
                console.print(f"Rebooting device {device.name}...")
                reboot_success = await _reboot_device(device, parameter_service.session)
                if reboot_success:
                    console.print(f"[green]Device {device.name} is rebooting[/green]")
                else:
                    console.print(f"[yellow]Warning: Could not reboot device {device.name}[/yellow]")
        else:
            console.print(f"[red]Failed to set parameter '{parameter_name}' on device {device.id}[/red]")
        
    finally:
        # Stop services
        await parameter_service.stop()
        if discovery_started:
            await discovery_service.stop()


async def _reboot_device(device, session) -> bool:
    """
    Reboot a device.
    
    Args:
        device: The device to reboot
        session: aiohttp ClientSession to use for requests
        
    Returns:
        Success status
    """
    if not device.ip_address:
        logger.error(f"Cannot reboot device: {device.id} has no IP address")
        return False
    
    try:
        if device.generation == DeviceGeneration.GEN1:
            # Gen1 reboot endpoint
            url = f"http://{device.ip_address}/reboot"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    logger.info(f"Successfully sent reboot command to Gen1 device {device.id}")
                    return True
                else:
                    logger.error(f"Failed to reboot Gen1 device {device.id}, status: {response.status}")
                    return False
        else:
            # Gen2/Gen3 reboot method
            url = f"http://{device.ip_address}/rpc"
            payload = {
                "id": 1,
                "src": "shelly-bulk-control",
                "method": "Shelly.Reboot",
                "params": {}
            }
            
            async with session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if "result" in response_data:
                        logger.info(f"Successfully sent reboot command to Gen2/Gen3 device {device.id}")
                        return True
                    else:
                        logger.error(f"Invalid response from Gen2/Gen3 device {device.id}: {response_data}")
                        return False
                else:
                    logger.error(f"Failed to reboot Gen2/Gen3 device {device.id}, status: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error rebooting device {device.id}: {str(e)}")
        return False


@app.command("apply")
def apply_parameter(
    group_name: str = typer.Argument(..., help="Name of the group to apply parameter to"),
    parameter_name: str = typer.Argument(..., help="Name of the parameter to apply"),
    value: str = typer.Argument(..., help="Value to set"),
    reboot: bool = typer.Option(False, "--reboot", help="Reboot devices after setting parameter if needed"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """
    Apply a parameter value to all devices in a group.
    
    Examples:
        - Disable eco mode for all devices in a group:
          shelly-bulk-control parameters apply eco_enabled eco_mode false
          
        - Set parameter and reboot devices if needed:
          shelly-bulk-control parameters apply eco_enabled eco_mode true --reboot
    """
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Parse value
        parsed_value = _parse_value(value)
        
        # Run the operation asynchronously
        asyncio.run(_apply_parameter_async(group_name, parameter_name, parsed_value, reboot, debug))
        
    except Exception as e:
        logger.error(f"Failed to apply parameter: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


async def _apply_parameter_async(group_name: str, parameter_name: str, value: Any, reboot: bool, debug: bool):
    """
    Apply a parameter asynchronously.
    
    Args:
        group_name: Name of the group
        parameter_name: Name of the parameter
        value: Value to set
        reboot: Whether to reboot devices after setting parameter if needed
        debug: Whether to enable debug logging
    """
    # Initialize services
    discovery_service = DiscoveryService()
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    # Start parameter service without discovery
    await parameter_service.start(no_discovery=True)
    discovery_started = False
    
    try:
        # Get the group
        group = group_manager.get_group(group_name)
        if not group:
            console.print(f"[red]Group '{group_name}' not found[/red]")
            return
        
        console.print(f"Loading devices for group '{group_name}' from registry...")
        
        # Load devices from registry first
        device_registry.load_all_devices()
        
        # Get devices from the group
        devices = []
        missing_devices = []
        
        for device_id in group.device_ids:
            # Normalize device ID
            mac_address = device_id.replace(":", "").upper()
            device = device_registry.get_device(mac_address)
            
            if device and device.ip_address:
                devices.append(device)
            else:
                missing_devices.append(device_id)
        
        # Only start discovery if some devices are missing from registry
        if missing_devices:
            console.print(f"[yellow]Some devices not found in registry or missing IP addresses: {', '.join(missing_devices)}[/yellow]")
            console.print("Starting targeted discovery for missing devices...")
            
            # Start discovery service
            await discovery_service.start()
            discovery_started = True
            
            # Use targeted discovery instead of full network scan
            await discovery_service.discover_specific_devices(missing_devices, scan_timeout=5)
            
            # Try to get devices again
            for device_id in missing_devices[:]:  # Create a copy to iterate
                device = None
                
                # Try to get from discovery service
                if hasattr(discovery_service, 'get_device'):
                    device = discovery_service.get_device(device_id)
                elif hasattr(discovery_service, 'devices'):
                    if isinstance(discovery_service.devices, dict):
                        device = discovery_service.devices.get(device_id)
                    else:
                        # If devices is a list, find the device by ID
                        for d in discovery_service.devices:
                            if d.id == device_id:
                                device = d
                                break
                
                if device:
                    devices.append(device)
                    missing_devices.remove(device_id)
        
        if missing_devices:
            console.print(f"[yellow]Warning: Could not find {len(missing_devices)} devices: {', '.join(missing_devices)}[/yellow]")
        
        # Display found devices
        console.print(f"Found {len(devices)} out of {len(group.device_ids)} devices in group '{group_name}'")
        
        if not devices:
            console.print("[red]No devices found to apply parameter[/red]")
            return
            
        # Apply parameter to each device
        console.print(f"Applying parameter '{parameter_name}' to {len(devices)} devices with value {value}...")
        
        success_count = 0
        reboot_required_devices = []
        failed_devices = []
        
        for device in devices:
            console.print(f"Setting {parameter_name} on {device.name} ({device.id})...")
            success = await parameter_service.set_parameter_value(device, parameter_name, value)
            
            if success:
                success_count += 1
                
                # Check if device needs to be rebooted for changes to take effect
                if hasattr(device, 'restart_required') and device.restart_required:
                    reboot_required_devices.append(device)
                    logger.info(f"Device {device.id} requires restart for changes to take effect.")
            else:
                failed_devices.append(device.id)
        
        # Handle rebooting if requested
        if reboot and reboot_required_devices:
            console.print(f"\nRebooting {len(reboot_required_devices)} devices that require restart...")
            reboot_success_count = 0
            
            for device in reboot_required_devices:
                console.print(f"Rebooting device {device.name} ({device.id})...")
                reboot_success = await _reboot_device(device, parameter_service.session)
                
                if reboot_success:
                    reboot_success_count += 1
                    console.print(f"[green]Successfully rebooted device {device.name}[/green]")
                else:
                    console.print(f"[yellow]Failed to reboot device {device.name}[/yellow]")
            
            console.print(f"\nReboot summary: {reboot_success_count}/{len(reboot_required_devices)} devices rebooted successfully")
        elif reboot_required_devices:
            console.print(f"\n[yellow]Note: {len(reboot_required_devices)} devices require reboot for changes to take effect.[/yellow]")
            console.print("[yellow]Use --reboot flag to automatically reboot these devices.[/yellow]")
        
        # Display summary
        if success_count == len(devices):
            console.print(f"[green]Successfully set parameter '{parameter_name}' on all {success_count} devices[/green]")
        else:
            console.print(f"[yellow]Set parameter '{parameter_name}' on {success_count} out of {len(devices)} devices[/yellow]")
            
            if failed_devices:
                console.print(f"[red]Failed devices: {', '.join(failed_devices)}[/red]")
        
    finally:
        # Stop services
        await parameter_service.stop()
        if discovery_started:
            await discovery_service.stop() 