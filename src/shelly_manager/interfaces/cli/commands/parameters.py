"""CLI commands for managing device parameters."""

import typer
import asyncio
from typing import Optional, List, Dict, Any, Union
import os
import json
import yaml

from rich.console import Console
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.discovery.discovery_service import DiscoveryService
from shelly_manager.parameter.parameter_service import ParameterService
from shelly_manager.utils.logging import LogConfig, get_logger
from shelly_manager.models.device_registry import device_registry
from shelly_manager.models.device import DeviceGeneration
from shelly_manager.models.device_capabilities import device_capabilities
from shelly_manager.models.device import Device
from shelly_manager.config_manager.config_manager import ConfigManager
from shelly_manager.models.device_config import DeviceConfigManager
from shelly_manager.grouping.group_service import GroupService

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(help="Device parameter management")
get_app = typer.Typer(help="Get parameter values")
set_app = typer.Typer(help="Set parameter values")
common_app = typer.Typer(help="Common parameter operations")

app.add_typer(get_app, name="get")
app.add_typer(set_app, name="set")
app.add_typer(common_app, name="common")

# Create console for rich output
console = Console()

def configure_logging(debug: bool = False):
    """Configure logging for the application"""
    log_config = LogConfig(
        app_name="shelly_manager",
        debug=debug,
        log_to_file=True,
        log_to_console=True
    )
    log_config.setup()


@app.command("list")
def list_parameters(
    ctx: typer.Context,
    device_id: str = typer.Argument(..., help="Device ID to list parameters for"),
    writable_only: bool = typer.Option(False, "--writable", "-w", help="Show only writable parameters"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode")
):
    """
    List all parameters for a device.
    
    This command displays all parameters for a specified device,
    showing parameter names, current values, and metadata.
    """
    # Run the async function
    asyncio.run(_list_parameters_async(device_id, writable_only, debug))


async def _list_parameters_async(device_id: str, writable_only: bool, debug: bool):
    """List parameters for a device."""
    # Set up logging
    configure_logging(debug=debug)
    
    # Initialize services
    parameter_service = ParameterService()
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # Get device
        device = device_registry.get_device(device_id)
        if not device:
            console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
            return
        
        console.print(f"[cyan]Loading parameters for {device.name} ({device.id})...[/cyan]")
        
        # List device parameters
        parameters = await parameter_service.list_all_device_parameters(device, not writable_only)
        
        # Display results
        _display_device_parameters(device, parameters)
    
    finally:
        # Stop parameter service
        await parameter_service.stop()


def _display_device_parameters(device: Device, parameters: Dict[str, Dict[str, Any]]):
    """
    Display parameters for a device in a table.
    
    Args:
        device: The device
        parameters: Dictionary of parameters
    """
    if not parameters:
        console.print(f"[yellow]No parameters found for device {device.name} ({device.id})[/yellow]")
        return
    
    # Create a header message
    header = f"Parameters for {device.name} ({device.id})"
    
    # Create table for parameters
    table = Table(title=header)
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Type", style="blue")
    table.add_column("API", style="magenta")
    table.add_column("Read-Only", style="yellow")
    
    # Add rows for each parameter, sorted by name
    for param_name, param_details in sorted(parameters.items()):
        # Format the value
        value = param_details.get("value")
        if value is None:
            value_str = "[dim]N/A[/dim]"
        elif isinstance(value, bool):
            value_str = "[green]True[/green]" if value else "[red]False[/red]"
        else:
            value_str = str(value)
        
        # Format read-only status
        read_only = "Yes" if param_details.get("read_only", True) else "No"
        
        # Truncate very long values
        if len(value_str) > 50:
            value_str = value_str[:47] + "..."
        
        # Add row to table
        table.add_row(
            param_name,
            value_str,
            param_details.get("type", "unknown"),
            param_details.get("api", "N/A"),
            read_only
        )
    
    console.print(table)
    console.print(f"\nTotal parameters: {len(parameters)}")


@app.command("get")
def get_parameter(
    ctx: typer.Context,
    device_id: str = typer.Argument(..., help="Device ID to get parameter from"),
    parameter: str = typer.Argument(..., help="Parameter name to get"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode")
):
    """
    Get the current value of a parameter.
    
    This command retrieves and displays the current value of a parameter for a device.
    """
    # Run the async function
    asyncio.run(_get_parameter_async(device_id, parameter, debug))


async def _get_parameter_async(device_id: str, parameter_name: str, debug: bool):
    """Get a parameter value."""
    # Set up logging
    configure_logging(debug=debug)
    
    # Initialize services
    parameter_service = ParameterService()
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # Get device
        device = device_registry.get_device(device_id)
        if not device:
            console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
            return
        
        console.print(f"[cyan]Getting parameter '{parameter_name}' for {device.name} ({device.id})...[/cyan]")
        
        # Get parameter value
        success, value = await parameter_service.get_parameter_value(device, parameter_name)
        
        if success:
            if isinstance(value, (dict, list)):
                # Format complex objects nicely
                value_str = json.dumps(value, indent=2)
                console.print(f"Parameter '{parameter_name}' value:")
                console.print(value_str)
            else:
                console.print(f"Parameter '{parameter_name}' value: {value}")
        else:
            console.print(f"[red]Failed to get parameter '{parameter_name}' for device {device.name}[/red]")
    
    finally:
        # Stop parameter service
        await parameter_service.stop()


@app.command("set")
def set_parameter(
    ctx: typer.Context,
    parameter: str = typer.Argument(..., help="Parameter name to set"),
    value: str = typer.Argument(..., help="Value to set"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode")
):
    """
    Set a parameter value on a device or group of devices.
    
    This command sets the value of a parameter for a specific device or all devices in a group.
    
    Examples:
        - Set eco_mode on a single device:
          shelly-manager parameters set eco_mode true --device abc123
          
        - Set max_power on all devices in a group:
          shelly-manager parameters set max_power 2000 --group living_room
    """
    # Run the async function
    asyncio.run(_set_parameter_async(parameter, value, device_id, group_name, debug))


async def _set_parameter_async(parameter_name: str, value_str: str, device_id: Optional[str] = None, 
                               group_name: Optional[str] = None, debug: bool = False):
    """Set a parameter value on a device or group."""
    # Set up logging
    configure_logging(debug=debug)
    
    # Check that at least one of device_id or group_name is provided
    if not device_id and not group_name:
        console.print("[red]Error: Either --device or --group must be specified[/red]")
        return
    
    # Parse value
    value = _parse_value(value_str)
    
    # Initialize services
    parameter_service = ParameterService()
    group_manager = None
    
    if group_name:
        group_manager = GroupManager()
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # Handle single device case
        if device_id:
            device = device_registry.get_device(device_id)
            if not device:
                console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
                return
            
            console.print(f"[cyan]Setting parameter '{parameter_name}' for {device.name} ({device.id}) to '{value}'...[/cyan]")
            
            # Get capability for validation
            capability = device_capabilities.get_capability_for_device(device)
            if capability:
                param_details = capability.get_parameter_details(parameter_name)
                if not param_details:
                    console.print(f"[yellow]Warning: Parameter '{parameter_name}' is not defined for this device type.[/yellow]")
                    console.print("[yellow]The operation might fail if the parameter doesn't exist.[/yellow]")
                elif param_details.get("read_only", True):
                    console.print(f"[red]Error: Parameter '{parameter_name}' is read-only for this device type.[/red]")
                    return
            
            # Set parameter on the device
            success, result = await parameter_service.set_parameter_value(device, parameter_name, value)
            
            if success:
                console.print(f"[green]Successfully set {parameter_name} = {value} for {device.name}[/green]")
                
                # Check if device needs a restart
                if isinstance(result, dict) and result.get("restart_required", False):
                    console.print(f"[yellow]Device {device.name} requires a restart to apply changes[/yellow]")
            else:
                console.print(f"[red]Failed to set {parameter_name} for {device.name}[/red]")
                if isinstance(result, dict) and "error" in result:
                    console.print(f"[red]Error details: {result['error']}[/red]")
        
        # Handle group case
        elif group_name:
            # Get the group
            group = group_manager.get_group(group_name)
            if not group:
                console.print(f"[red]Error: Group '{group_name}' not found[/red]")
                return
            
            console.print(f"[cyan]Setting parameter '{parameter_name}' to '{value}' for all devices in group '{group_name}'...[/cyan]")
            
            # Get devices in the group
            devices = device_registry.get_devices(group.device_ids)
            if not devices:
                console.print(f"[yellow]Warning: No devices found in group '{group_name}'[/yellow]")
                return
            
            console.print(f"[cyan]Found {len(devices)} devices in group '{group_name}'[/cyan]")
            
            # Set up progress tracking
            success_count = 0
            failure_count = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"[cyan]Setting parameter on devices...[/cyan]", total=len(devices))
                
                for device in devices:
                    progress.update(task, description=f"[cyan]Setting parameter on {device.name} ({device.id})...[/cyan]")
                    
                    # Get capability for validation
                    capability = device_capabilities.get_capability_for_device(device)
                    if capability:
                        param_details = capability.get_parameter_details(parameter_name)
                        if not param_details:
                            progress.console.print(f"[yellow]  Warning: Parameter '{parameter_name}' is not defined for {device.id}, skipping[/yellow]")
                            failure_count += 1
                            progress.advance(task)
                            continue
                        elif param_details.get("read_only", True):
                            progress.console.print(f"[yellow]  Warning: Parameter '{parameter_name}' is read-only for {device.id}, skipping[/yellow]")
                            failure_count += 1
                            progress.advance(task)
                            continue
                    
                    # Set parameter on the device
                    try:
                        success, result = await parameter_service.set_parameter_value(device, parameter_name, value)
                        
                        if success:
                            progress.console.print(f"[green]  Set {parameter_name} = {value} for {device.name}[/green]")
                            success_count += 1
                            
                            # Check if device needs a restart
                            if isinstance(result, dict) and result.get("restart_required", False):
                                progress.console.print(f"[yellow]  Device {device.name} requires a restart to apply changes[/yellow]")
                        else:
                            progress.console.print(f"[red]  Failed to set {parameter_name} for {device.name}[/red]")
                            if isinstance(result, dict) and "error" in result:
                                progress.console.print(f"[red]  Error details: {result['error']}[/red]")
                            failure_count += 1
                    except Exception as e:
                        progress.console.print(f"[red]  Error setting {parameter_name} for {device.name}: {str(e)}[/red]")
                        failure_count += 1
                    
                    progress.advance(task)
            
            # Show summary
            if success_count == len(devices):
                console.print(f"[green]Parameter successfully set on all {len(devices)} devices[/green]")
            else:
                console.print(f"[yellow]Parameter set on {success_count} of {len(devices)} devices with {failure_count} failures[/yellow]")
    
    finally:
        # Stop parameter service
        await parameter_service.stop()


@app.command("bulk-set")
def bulk_set_parameters(
    ctx: typer.Context,
    parameter_file: str = typer.Argument(..., help="Path to YAML file with parameters"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Apply to devices in this group"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Apply to a specific device"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode")
):
    """
    Set multiple parameters from a YAML file.
    
    This command reads a YAML file containing parameter definitions and applies them
    to one or more devices. The file should have the following format:
    
    ```yaml
    parameters:
      eco_mode: true
      name: "Living Room Light"
    
    devices:  # Optional, if not using --device or --group
      - abc123
      - def456
    ```
    """
    # Run the async function
    asyncio.run(_bulk_set_parameters_async(parameter_file, group_name, device_id, debug))


async def _bulk_set_parameters_async(parameter_file: str, group_name: Optional[str], device_id: Optional[str], debug: bool):
    """Set parameters in bulk."""
    # Set up logging
    configure_logging(debug=debug)
    
    # Check if file exists
    if not os.path.exists(parameter_file):
        console.print(f"[red]Error: Parameter file '{parameter_file}' not found[/red]")
        return
    
    # Load parameter file
    try:
        with open(parameter_file, 'r') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error loading parameter file: {str(e)}[/red]")
        return
    
    # Validate file format
    if not isinstance(data, dict) or "parameters" not in data:
        console.print(f"[red]Error: Invalid parameter file format. Missing 'parameters' section.[/red]")
        return
    
    parameters = data.get("parameters", {})
    if not parameters:
        console.print(f"[red]Error: No parameters defined in the file.[/red]")
        return
    
    # Get devices to update
    devices = []
    
    if device_id:
        # Single device
        device = device_registry.get_device(device_id)
        if device:
            devices.append(device)
        else:
            console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
            return
    elif group_name:
        # Devices in a group
        group = device_registry.get_group(group_name)
        if group:
            for device_id in group.device_ids:
                device = device_registry.get_device(device_id)
                if device:
                    devices.append(device)
            
            if not devices:
                console.print(f"[red]Error: No devices found in group '{group_name}'[/red]")
                return
        else:
            console.print(f"[red]Error: Group '{group_name}' not found[/red]")
            return
    elif "devices" in data:
        # Devices listed in the file
        for device_id in data.get("devices", []):
            device = device_registry.get_device(device_id)
            if device:
                devices.append(device)
            else:
                console.print(f"[yellow]Warning: Device with ID {device_id} not found, skipping[/yellow]")
        
        if not devices:
            console.print(f"[red]Error: No valid devices found in parameter file[/red]")
            return
    else:
        console.print(f"[red]Error: No devices specified. Use --device, --group, or include a 'devices' section in the file.[/red]")
        return
    
    # Initialize parameter service
    parameter_service = ParameterService()
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # Process each device
        success_count = 0
        failure_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]Setting parameters on {len(devices)} devices...[/cyan]", total=len(devices))
            
            for device in devices:
                progress.update(task, description=f"[cyan]Setting parameters on {device.name} ({device.id})...[/cyan]")
                
                # Get capability for this device
                capability = device_capabilities.get_capability_for_device(device)
                device_failures = 0
                
                # Apply each parameter
                for param_name, value in parameters.items():
                    # Validate parameter if capability is available
                    if capability:
                        param_details = capability.get_parameter_details(param_name)
                        if not param_details:
                            progress.console.print(f"[yellow]  Warning: Parameter '{param_name}' is not defined for {device.id}, skipping[/yellow]")
                            continue
                        elif param_details.get("read_only", True):
                            progress.console.print(f"[yellow]  Warning: Parameter '{param_name}' is read-only for {device.id}, skipping[/yellow]")
                            continue
                    
                    # Set parameter
                    try:
                        success, result = await parameter_service.set_parameter_value(device, param_name, value)
                        
                        if success:
                            progress.console.print(f"[green]  Set {param_name} = {value} for {device.name}[/green]")
                        else:
                            progress.console.print(f"[red]  Failed to set {param_name} for {device.id}[/red]")
                            if isinstance(result, dict) and "error" in result:
                                progress.console.print(f"[red]  Error details: {result['error']}[/red]")
                            device_failures += 1
                    except Exception as e:
                        progress.console.print(f"[red]  Error setting {param_name} for {device.id}: {str(e)}[/red]")
                        device_failures += 1
                
                # Count successes and failures
                if device_failures == 0:
                    success_count += 1
                else:
                    failure_count += 1
                
                progress.advance(task)
        
        # Show summary
        if success_count == len(devices):
            console.print(f"[green]Parameters successfully set on all {len(devices)} devices[/green]")
        else:
            console.print(f"[yellow]Parameters set on {success_count} of {len(devices)} devices with {failure_count} failures[/yellow]")
    
    finally:
        # Stop parameter service
        await parameter_service.stop()


@common_app.command("eco_mode")
def set_eco_mode(
    ctx: typer.Context,
    enable: bool = typer.Argument(..., help="Enable (true) or disable (false) eco mode"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Enable or disable eco mode on device(s).
    
    This command sets the eco_mode parameter for devices that support it.
    Example: shelly-manager parameters common eco_mode true --group living_room
    """
    # Run the async function to set the parameter
    asyncio.run(_set_parameter_async("eco_mode", str(enable).lower(), device_id, group_name, debug))


@common_app.command("night_mode")
def set_night_mode(
    ctx: typer.Context,
    enable: bool = typer.Argument(..., help="Enable (true) or disable (false) night mode"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Enable or disable night mode on device(s).
    
    This command sets the night_mode parameter for devices that support it.
    Example: shelly-manager parameters common night_mode true --group bedroom
    """
    # Run the async function to set the parameter
    asyncio.run(_set_parameter_async("night_mode", str(enable).lower(), device_id, group_name, debug))


@common_app.command("led_status")
def set_led_status(
    ctx: typer.Context,
    enable: bool = typer.Argument(..., help="Enable (true) or disable (false) status LEDs"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Enable or disable status LEDs on device(s).
    
    This command controls the status LED on devices. This is often called 'led_status_disable'
    but this command inverts the value for more intuitive usage (true = LEDs on, false = LEDs off).
    
    Example: shelly-manager parameters common led_status false --group all_devices
    """
    # Invert the value since the actual parameter is led_status_disable
    # true value for this command = status LEDs ON = led_status_disable set to false
    value = str(not enable).lower()
    
    # Run the async function to set the parameter
    asyncio.run(_set_parameter_async("led_status_disable", value, device_id, group_name, debug))


@common_app.command("max_power")
def set_max_power(
    ctx: typer.Context,
    watts: float = typer.Argument(..., help="Maximum power in watts"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Set maximum power limit on device(s).
    
    This command sets the max_power parameter for devices that support it.
    Example: shelly-manager parameters common max_power 2000 --group high_power_devices
    """
    # Run the async function to set the parameter
    asyncio.run(_set_parameter_async("max_power", str(watts), device_id, group_name, debug))


@common_app.command("power_on_state")
def set_power_on_state(
    ctx: typer.Context,
    state: str = typer.Argument(..., help="State on power on (on/off/last)", case_sensitive=False),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Set power-on state for device(s).
    
    This command sets the behavior when power is restored to the device.
    Valid values: on, off, last (restore last state before power loss).
    
    Example: shelly-manager parameters common power_on_state last --group all_switches
    """
    # Validate state value
    valid_states = ["on", "off", "last"]
    if state.lower() not in valid_states:
        console.print(f"[red]Error: Invalid state '{state}'. Must be one of: {', '.join(valid_states)}[/red]")
        return
    
    # Run the async function to set the parameter
    asyncio.run(_set_parameter_async("power_on_state", state.lower(), device_id, group_name, debug))


@common_app.command("auto_off")
def set_auto_off(
    ctx: typer.Context,
    enable: bool = typer.Argument(..., help="Enable (true) or disable (false) auto-off"),
    timeout_seconds: Optional[int] = typer.Option(None, "--timeout", "-t", help="Auto-off timeout in seconds"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Configure auto-off functionality on device(s).
    
    This command enables or disables the auto-off feature. If enabled, 
    the device will automatically turn off after the specified timeout.
    If timeout is not specified, only the auto_off parameter will be changed.
    
    Examples:
      - Enable auto-off with a 60-second timeout:
        shelly-manager parameters common auto_off true --timeout 60 --group bathroom
        
      - Disable auto-off:
        shelly-manager parameters common auto_off false --group bathroom
    """
    # First, enable/disable auto-off
    asyncio.run(_set_parameter_async("auto_off", str(enable).lower(), device_id, group_name, debug))
    
    # If timeout is specified and auto-off is enabled, set the timeout
    if timeout_seconds is not None and enable:
        asyncio.run(_set_parameter_async("auto_off_delay", str(timeout_seconds), device_id, group_name, debug))


def _parse_value(value_str: str) -> Union[str, int, float, bool]:
    """Parse a string value into the appropriate type."""
    # Check for boolean values
    if value_str.lower() in ["true", "false"]:
        return value_str.lower() == "true"
    
    # Check for integer values
    try:
        int_value = int(value_str)
        return int_value
    except ValueError:
        pass
    
    # Check for float values
    try:
        float_value = float(value_str)
        return float_value
    except ValueError:
        pass
    
    # Default to string if no other type matches
    return value_str


@set_app.command("group")
async def set_parameter_for_group(
    group_id: str = typer.Argument(..., help="ID of the group"),
    parameter_id: str = typer.Argument(..., help="ID of the parameter to set"),
    value: str = typer.Argument(..., help="Value to set"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip parameter validation"),
) -> None:
    """Set a parameter value for all devices in a group."""
    console.print(f"Setting parameter [bold]{parameter_id}[/bold] to [bold]{value}[/bold] for all devices in group [bold]{group_id}[/bold]")
    
    parameter_service = ParameterService()
    group_service = GroupService()
    
    # Verify group exists
    groups = await group_service.list_groups()
    group = next((g for g in groups if g.id == group_id), None)
    if not group:
        console.print(f"[bold red]Error:[/bold red] Group {group_id} not found")
        return
    
    # Get devices in the group
    device_ids = group.device_ids
    if not device_ids:
        console.print(f"[bold yellow]Warning:[/bold yellow] Group {group_id} has no devices")
        return
    
    # Set parameter for each device
    parsed_value = _parse_value(value)
    
    table = Table(title=f"Parameter Update Results for Group: {group.name}")
    table.add_column("Device", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Message", style="yellow")
    
    success_count = 0
    failed_count = 0
    
    for device_id in device_ids:
        try:
            await parameter_service.set_parameter_value(
                device_id=device_id,
                parameter_id=parameter_id, 
                value=parsed_value,
                skip_validation=skip_validation
            )
            table.add_row(device_id, "✅ Success", "")
            success_count += 1
        except Exception as e:
            table.add_row(device_id, "❌ Failed", str(e))
            failed_count += 1
    
    console.print(table)
    console.print(f"Summary: {success_count} successful, {failed_count} failed")


@common_app.command("toggle-switch")
async def toggle_switch(
    device_id: str = typer.Argument(..., help="ID of the device"),
) -> None:
    """Toggle a switch device on/off."""
    parameter_service = ParameterService()
    
    try:
        # Get current state
        current_state = await parameter_service.get_parameter_value(
            device_id=device_id,
            parameter_id="switch:0.output"
        )
        
        # Toggle the state
        new_state = not current_state
        await parameter_service.set_parameter_value(
            device_id=device_id,
            parameter_id="switch:0.output",
            value=new_state
        )
        
        console.print(f"Switch toggled from [bold]{'ON' if current_state else 'OFF'}[/bold] to [bold]{'ON' if new_state else 'OFF'}[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")


@common_app.command("toggle-group")
async def toggle_group(
    group_id: str = typer.Argument(..., help="ID of the group"),
) -> None:
    """Toggle all switch devices in a group on/off."""
    parameter_service = ParameterService()
    group_service = GroupService()
    
    # Verify group exists
    groups = await group_service.list_groups()
    group = next((g for g in groups if g.id == group_id), None)
    if not group:
        console.print(f"[bold red]Error:[/bold red] Group {group_id} not found")
        return
    
    # Get devices in the group
    device_ids = group.device_ids
    if not device_ids:
        console.print(f"[bold yellow]Warning:[/bold yellow] Group {group_id} has no devices")
        return
    
    table = Table(title=f"Toggle Results for Group: {group.name}")
    table.add_column("Device", style="cyan")
    table.add_column("Previous State", style="blue")
    table.add_column("New State", style="green")
    table.add_column("Status", style="yellow")
    
    success_count = 0
    failed_count = 0
    
    for device_id in device_ids:
        try:
            # Try to get current state
            try:
                current_state = await parameter_service.get_parameter_value(
                    device_id=device_id,
                    parameter_id="switch:0.output"
                )
                
                # Toggle the state
                new_state = not current_state
                await parameter_service.set_parameter_value(
                    device_id=device_id,
                    parameter_id="switch:0.output",
                    value=new_state
                )
                
                table.add_row(
                    device_id, 
                    "ON" if current_state else "OFF", 
                    "ON" if new_state else "OFF",
                    "✅ Success"
                )
                success_count += 1
            except Exception as e:
                table.add_row(device_id, "Unknown", "Unknown", f"❌ Failed: {str(e)}")
                failed_count += 1
        except Exception as e:
            table.add_row(device_id, "Unknown", "Unknown", f"❌ Failed: {str(e)}")
            failed_count += 1
    
    console.print(table)
    console.print(f"Summary: {success_count} successful, {failed_count} failed")


@common_app.command("night-mode")
async def set_night_mode(
    device_id: str = typer.Argument(..., help="ID of the device"),
    brightness: int = typer.Option(5, "--brightness", "-b", help="Brightness level (0-100)"),
) -> None:
    """Set a device to night mode with reduced brightness."""
    parameter_service = ParameterService()
    
    try:
        # Check if device has brightness control
        try:
            await parameter_service.set_parameter_value(
                device_id=device_id,
                parameter_id="light:0.brightness",
                value=brightness
            )
            console.print(f"Set brightness to [bold]{brightness}%[/bold]")
        except Exception:
            console.print(f"[bold yellow]Warning:[/bold yellow] Device doesn't support brightness control")
        
        # Turn on night light if supported
        try:
            await parameter_service.set_parameter_value(
                device_id=device_id,
                parameter_id="light:0.mode",
                value="night"
            )
            console.print("Set light mode to [bold]night[/bold]")
        except Exception:
            console.print(f"[bold yellow]Warning:[/bold yellow] Device doesn't support night mode")
            
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}") 