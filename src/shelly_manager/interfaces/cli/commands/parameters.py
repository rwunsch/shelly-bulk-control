"""CLI commands for managing device parameters."""

import typer
import asyncio
from typing import Optional, List, Dict, Any, Union, Callable
import os
import json
import yaml
import inspect

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
from shelly_manager.models.parameter_mapping import parameter_manager, ParameterType

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(name="parameters", help="""
Manage device parameters.

This command group provides functionality for working with device parameters:

COMMANDS:
  get        Get a parameter value from a specific device
  set        Set a parameter value on a device or group
  common     Manage parameters common to multiple device types
  list       List all parameters for a specific device
  discover   Discover available parameters for a device
  
For detailed help on a specific command, use:
  parameters COMMAND --help
""")
# Remove the get_app and set_app typers since we're using direct commands
common_app = typer.Typer(help="Common parameter operations")

# Don't add the empty typers as subgroups
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


# Register dynamic commands for common parameters
def register_common_parameter_commands():
    """Register CLI commands for common parameters."""
    # Get all common parameters from the parameter manager
    common_params = parameter_manager.get_all_common_parameters()
    
    for param in common_params:
        # Skip parameters that don't make sense as CLI commands
        if param.parameter_type == ParameterType.OBJECT or param.parameter_type == ParameterType.ARRAY:
            continue
            
        # Create a command for this parameter
        command_name = param.name.replace('_', '-')
        command_help = f"Set {param.display_name.lower()} for device(s)"
        
        # For boolean parameters, create a simple enable/disable command
        if param.parameter_type == ParameterType.BOOLEAN:
            create_boolean_parameter_command(param, command_name, command_help)
            
        # For numeric parameters, create a command with a value argument
        elif param.parameter_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            create_numeric_parameter_command(param, command_name, command_help)
            
        # For enum parameters, create a command with choices
        elif param.parameter_type == ParameterType.ENUM and param.enum_values:
            create_enum_parameter_command(param, command_name, command_help)
            
        # For other types (like strings), create a generic command
        else:
            create_string_parameter_command(param, command_name, command_help)


def create_boolean_parameter_command(param, command_name, command_help):
    """Create a CLI command for a boolean parameter."""
    
    @common_app.command(command_name)
    def command(
        ctx: typer.Context,
        enable: bool = typer.Argument(..., help=f"Enable (true) or disable (false) {param.display_name.lower()}"),
        device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
        group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
        auto_restart: bool = typer.Option(param.requires_restart, "--restart/--no-restart", help="Automatically restart device if required"),
        debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    ):
        """
        {command_help}.
        
        This command {param.description.lower()}.
        """
        # Run the async function
        asyncio.run(_set_parameter_async(param.name, str(enable), device_id, group_name, auto_restart, debug))
    
    # Set the command function name and docstring
    command.__name__ = f"set_{param.name}"
    command.__doc__ = f"{command_help}.\n\nThis command {param.description.lower()}."


def create_numeric_parameter_command(param, command_name, command_help):
    """Create a CLI command for a numeric parameter."""
    param_type = int if param.parameter_type == ParameterType.INTEGER else float
    
    @common_app.command(command_name)
    def command(
        ctx: typer.Context,
        value: param_type = typer.Argument(..., help=f"{param.display_name} value{' (in ' + param.unit + ')' if param.unit else ''}"),
        device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
        group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
        auto_restart: bool = typer.Option(param.requires_restart, "--restart/--no-restart", help="Automatically restart device if required"),
        debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    ):
        """
        {command_help}.
        
        This command {param.description.lower()}.
        """
        # Validate value against min/max if defined
        if param.min_value is not None and value < param.min_value:
            console.print(f"[red]Error: Value must be at least {param.min_value}[/red]")
            return
        if param.max_value is not None and value > param.max_value:
            console.print(f"[red]Error: Value must be at most {param.max_value}[/red]")
            return
            
        # Run the async function
        asyncio.run(_set_parameter_async(param.name, str(value), device_id, group_name, auto_restart, debug))
    
    # Set the command function name and docstring
    command.__name__ = f"set_{param.name}"
    command.__doc__ = f"{command_help}.\n\nThis command {param.description.lower()}."


def create_enum_parameter_command(param, command_name, command_help):
    """Create a CLI command for an enum parameter."""
    
    @common_app.command(command_name)
    def command(
        ctx: typer.Context,
        value: str = typer.Argument(..., help=f"{param.display_name} value ({'/'.join(param.enum_values)})", 
                                   case_sensitive=False),
        device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
        group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
        auto_restart: bool = typer.Option(param.requires_restart, "--restart/--no-restart", help="Automatically restart device if required"),
        debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    ):
        """
        {command_help}.
        
        This command {param.description.lower()}.
        """
        # Validate value against enum values
        if value.lower() not in [str(v).lower() for v in param.enum_values]:
            console.print(f"[red]Error: Value must be one of: {', '.join(param.enum_values)}[/red]")
            return
        
        # Find the correct case for the value
        for v in param.enum_values:
            if str(v).lower() == value.lower():
                value = str(v)
                break
                
        # Run the async function
        asyncio.run(_set_parameter_async(param.name, value, device_id, group_name, auto_restart, debug))
    
    # Set the command function name and docstring
    command.__name__ = f"set_{param.name}"
    command.__doc__ = f"{command_help}.\n\nThis command {param.description.lower()}."


def create_string_parameter_command(param, command_name, command_help):
    """Create a CLI command for a string parameter."""
    
    @common_app.command(command_name)
    def command(
        ctx: typer.Context,
        value: str = typer.Argument(..., help=f"{param.display_name} value"),
        device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
        group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
        auto_restart: bool = typer.Option(param.requires_restart, "--restart/--no-restart", help="Automatically restart device if required"),
        debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    ):
        """
        {command_help}.
        
        This command {param.description.lower()}.
        """
        # Run the async function
        asyncio.run(_set_parameter_async(param.name, value, device_id, group_name, auto_restart, debug))
    
    # Set the command function name and docstring
    command.__name__ = f"set_{param.name}"
    command.__doc__ = f"{command_help}.\n\nThis command {param.description.lower()}."


@app.command("list")
def list_parameters(device_id: str = typer.Argument(..., help="Device ID to list parameters for")):
    """
    List all available parameters for a specific device.
    
    This command displays all parameters that can be configured for the specified device,
    based on its model and capabilities. Each parameter is shown with its name,
    current value, and parameter type.
    
    ARGUMENTS:
        DEVICE_ID: The ID of the device to list parameters for (e.g., shellyplus1-441793a3b6c4)
    
    EXAMPLES:
        parameters list shellyplus1-441793a3b6c4
    """
    # Run the async function
    asyncio.run(_list_parameters_async(device_id))


async def _list_parameters_async(device_id: str):
    """List parameters for a device."""
    # Set up logging
    configure_logging()
    
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
        parameters = await parameter_service.list_all_device_parameters(device)
        
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
    Get the current value of a parameter from a specific device.
    
    This command retrieves and displays the current value of a parameter for a specified device.
    The device is identified by its device ID, and you need to provide the exact parameter name.
    Use the 'list' command first to see all available parameters for a device.
    
    ARGUMENTS:
        DEVICE_ID  The ID of the device to get the parameter from
                   (e.g., d8bfc0dbf4fb, shellyplug-s123456)
                   
        PARAMETER  The name of the parameter to retrieve 
                   (e.g., eco_mode_enabled, name, max_power, switch:0.output)
    
    EXAMPLES:
        # Get the name of a device
        parameters get d8bfc0dbf4fb name
        
        # Get the eco mode setting for a plug
        parameters get shellyplug-s123456 eco_mode_enabled
        
        # Get the current switch state
        parameters get shellydimmer-44556677 switch:0.output
        
        # Get the maximum power setting
        parameters get shellyem-aabbccdd max_power
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
    auto_restart: bool = typer.Option(False, "--restart", "-r", help="Automatically restart device if required"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode")
):
    """
    Set a parameter value on a device or group of devices.
    
    This command sets the value of a parameter for a specific device or all devices in a group.
    You must provide the parameter name, value, and either a device ID or group name.
    Use the 'list' command first to see all available parameters for a device.
    
    ARGUMENTS:
        PARAMETER  The name of the parameter to set 
                   (e.g., eco_mode_enabled, name, max_power, switch:0.output)
                   
        VALUE      The value to set for the parameter. The type depends on the parameter:
                   - Boolean: true/false
                   - Integer: numeric value without decimals
                   - Float: numeric value with decimals
                   - String: text value, use quotes if it contains spaces
    
    OPTIONS:
        -d, --device TEXT    Device ID to set parameter on (e.g., shellyplug-s123456)
        -g, --group TEXT     Set parameter on all devices in this group instead of a single device
        -r, --restart        Automatically restart device if required by the parameter change
    
    NOTE: You must specify either --device or --group, but not both.
    
    EXAMPLES:
        # Turn on a switch
        parameters set switch:0.output true --device shellysw-112233
        
        # Set eco mode on a single device
        parameters set eco_mode_enabled true --device shellyplug-s123456
        
        # Set the name of a device
        parameters set name "Living Room Plug" --device shellyplug-s123456
        
        # Set max power for all devices in a group
        parameters set max_power 2000 --group kitchen
        
        # Set static IP configuration with automatic restart
        parameters set static_ip_config true --device shellypro4pm-aabbcc --restart
    """
    # Run the async function
    asyncio.run(_set_parameter_async(parameter, value, device_id, group_name, auto_restart, debug))


async def _set_parameter_async(parameter_name: str, value_str: str, device_id: Optional[str] = None, 
                               group_name: Optional[str] = None, auto_restart: bool = False, debug: bool = False):
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
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # For single device
        if device_id:
            device = device_registry.get_device(device_id)
            if not device:
                console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
                return
            
            console.print(f"[cyan]Setting parameter '{parameter_name}' to '{value}' on {device.name} ({device.id})...[/cyan]")
            
            # Set parameter value
            success, response = await parameter_service.set_parameter_value(device, parameter_name, value, auto_restart=auto_restart)
            
            if success:
                console.print(f"[green]Successfully set parameter '{parameter_name}' on device {device.name}[/green]")
                if auto_restart:
                    console.print("[yellow]Note: Device may have been restarted if required by the parameter[/yellow]")
            else:
                console.print(f"[red]Failed to set parameter '{parameter_name}' on device {device.name}[/red]")
                if response and isinstance(response, dict) and "error" in response:
                    console.print(f"[red]Error: {response['error']}[/red]")
        
        # For group
        elif group_name:
            # Get group manager
            group_manager = GroupManager()
            
            # Load groups
            groups = group_manager.load_groups()
            
            # Check if group exists
            if group_name not in groups:
                console.print(f"[red]Error: Group '{group_name}' not found[/red]")
                return
            
            # Get devices in group
            device_ids = groups[group_name]
            devices = []
            
            for did in device_ids:
                device = device_registry.get_device(did)
                if device:
                    devices.append(device)
            
            if not devices:
                console.print(f"[red]Error: No devices found in group '{group_name}'[/red]")
                return
            
            console.print(f"[cyan]Setting parameter '{parameter_name}' to '{value}' on {len(devices)} devices in group '{group_name}'...[/cyan]")
            
            # Set parameter on each device in the group
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # Create a task for overall progress
                task = progress.add_task(f"Setting parameter on {len(devices)} devices...", total=len(devices))
                
                # Initialize success/failure counters
                success_count = 0
                failure_count = 0
                
                # Process each device
                for device in devices:
                    # Update task description
                    progress.update(task, description=f"Setting parameter on {device.name} ({device.id})...")
                    
                    # Set parameter value
                    success, response = await parameter_service.set_parameter_value(device, parameter_name, value, auto_restart=auto_restart)
                    
                    # Update counters
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                    
                    # Update progress
                    progress.update(task, advance=1)
            
            # Display results
            if success_count == len(devices):
                console.print(f"[green]Successfully set parameter '{parameter_name}' on all {len(devices)} devices in group '{group_name}'[/green]")
                if auto_restart:
                    console.print("[yellow]Note: Devices may have been restarted if required by the parameter[/yellow]")
            elif success_count > 0:
                console.print(f"[yellow]Set parameter '{parameter_name}' on {success_count}/{len(devices)} devices in group '{group_name}'[/yellow]")
                console.print(f"[red]{failure_count} device(s) failed[/red]")
            else:
                console.print(f"[red]Failed to set parameter '{parameter_name}' on any device in group '{group_name}'[/red]")
    
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


@app.command("set-group")
async def set_parameter_for_group(
    group_id: str = typer.Argument(..., help="ID of the group"),
    parameter_id: str = typer.Argument(..., help="ID of the parameter to set"),
    value: str = typer.Argument(..., help="Value to set"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip parameter validation"),
) -> None:
    """
    Set a parameter value for all devices in a group.
    
    This command sets the value of a specified parameter for all devices in a group.
    It's useful when you want to apply the same setting to multiple devices at once.
    
    ARGUMENTS:
        GROUP_ID      The ID of the group containing the devices
        PARAMETER_ID  The name of the parameter to set
        VALUE         The value to set for the parameter
        
    OPTIONS:
        --skip-validation  Skip validation of the parameter value (use with caution)
        
    EXAMPLES:
        # Set eco mode for all devices in the 'kitchen' group
        parameters set-group kitchen eco_mode_enabled true
        
        # Set max power for all devices in the 'high_power' group
        parameters set-group high_power max_power 2000
    """
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


@common_app.command("mqtt-config")
def set_mqtt_configuration(
    ctx: typer.Context,
    enable: bool = typer.Option(True, "--enable/--disable", help="Enable or disable MQTT"),
    server: str = typer.Option(..., "--server", "-s", help="MQTT broker server address"),
    port: int = typer.Option(1883, "--port", "-p", help="MQTT broker port"),
    username: Optional[str] = typer.Option(None, "--username", "-u", help="MQTT username"),
    password: Optional[str] = typer.Option(None, "--password", "-w", help="MQTT password"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    auto_restart: bool = typer.Option(False, "--restart", "-r", help="Automatically restart devices if required"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Configure MQTT settings for a device or group of devices.
    
    This command sets multiple MQTT parameters in one operation.
    
    Examples:
        - Configure MQTT on a single device:
          shelly-manager parameters common mqtt-config --server mqtt.home --device abc123
          
        - Configure MQTT with authentication for a group:
          shelly-manager parameters common mqtt-config --server mqtt.home --username user --password pass --group living_room
    """
    asyncio.run(_set_mqtt_configuration_async(
        enable, server, port, username, password, device_id, group_name, auto_restart, debug
    ))


async def _set_mqtt_configuration_async(
    enable: bool,
    server: str,
    port: int,
    username: Optional[str],
    password: Optional[str],
    device_id: Optional[str],
    group_name: Optional[str],
    auto_restart: bool,
    debug: bool
):
    """Set MQTT configuration on a device or group."""
    # Set up logging
    configure_logging(debug=debug)
    
    # Check that at least one of device_id or group_name is provided
    if not device_id and not group_name:
        console.print("[red]Error: Either --device or --group must be specified[/red]")
        return
    
    # Initialize services
    parameter_service = ParameterService()
    
    # Prepare parameter dictionary
    params = {
        "mqtt_enable": enable,
        "mqtt_server": server,
        "mqtt_port": port
    }
    
    # Add optional parameters if provided
    if username is not None:
        params["mqtt_username"] = username
    if password is not None:
        params["mqtt_password"] = password
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # For single device
        if device_id:
            device = device_registry.get_device(device_id)
            if not device:
                console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
                return
            
            console.print(f"[cyan]Configuring MQTT settings for {device.name} ({device.id})...[/cyan]")
            
            # Apply each parameter
            success_count = 0
            failure_count = 0
            
            for param_name, param_value in params.items():
                console.print(f"  Setting {param_name} to {param_value}...")
                success, response = await parameter_service.set_parameter_value(
                    device, param_name, param_value, auto_restart=(param_name == "mqtt_enable" and auto_restart)
                )
                
                if success:
                    success_count += 1
                    console.print(f"  [green]Successfully set {param_name}[/green]")
                else:
                    failure_count += 1
                    console.print(f"  [red]Failed to set {param_name}[/red]")
            
            # Display results
            if success_count == len(params):
                console.print(f"[green]Successfully configured all MQTT settings on {device.name}[/green]")
                if auto_restart:
                    console.print("[yellow]Note: Device may have been restarted to apply changes[/yellow]")
            else:
                console.print(f"[yellow]Configured {success_count}/{len(params)} MQTT settings on {device.name} with {failure_count} failures[/yellow]")
        
        # For group
        elif group_name:
            # Get group manager
            group_manager = GroupManager()
            
            # Load groups
            groups = group_manager.load_groups()
            
            # Check if group exists
            if group_name not in groups:
                console.print(f"[red]Error: Group '{group_name}' not found[/red]")
                return
            
            # Get devices in group
            device_ids = groups[group_name]
            devices = []
            
            for did in device_ids:
                device = device_registry.get_device(did)
                if device:
                    devices.append(device)
            
            if not devices:
                console.print(f"[red]Error: No devices found in group '{group_name}'[/red]")
                return
            
            console.print(f"[cyan]Configuring MQTT settings for {len(devices)} devices in group '{group_name}'...[/cyan]")
            
            # Overall counters
            total_success_count = 0
            total_failure_count = 0
            
            # Process each device
            for device in devices:
                console.print(f"[cyan]Device: {device.name} ({device.id})[/cyan]")
                
                # Apply each parameter
                device_success_count = 0
                device_failure_count = 0
                
                for param_name, param_value in params.items():
                    success, response = await parameter_service.set_parameter_value(
                        device, param_name, param_value, auto_restart=(param_name == "mqtt_enable" and auto_restart)
                    )
                    
                    if success:
                        device_success_count += 1
                        total_success_count += 1
                    else:
                        device_failure_count += 1
                        total_failure_count += 1
                
                # Display per-device results
                if device_success_count == len(params):
                    console.print(f"  [green]Successfully configured all MQTT settings[/green]")
                else:
                    console.print(f"  [yellow]Configured {device_success_count}/{len(params)} settings with {device_failure_count} failures[/yellow]")
            
            # Display overall results
            total_params = len(params) * len(devices)
            if total_success_count == total_params:
                console.print(f"[green]Successfully configured all MQTT settings on all devices in group '{group_name}'[/green]")
                if auto_restart:
                    console.print("[yellow]Note: Devices may have been restarted to apply changes[/yellow]")
            else:
                console.print(f"[yellow]Configured {total_success_count}/{total_params} MQTT settings with {total_failure_count} failures[/yellow]")
    
    finally:
        # Stop parameter service
        await parameter_service.stop()


@common_app.command("network-config")
def set_network_configuration(
    ctx: typer.Context,
    static: bool = typer.Option(True, "--static/--dhcp", help="Use static IP configuration or DHCP"),
    ip_address: Optional[str] = typer.Option(None, "--ip", help="Static IP address"),
    gateway: Optional[str] = typer.Option(None, "--gateway", "-g", help="Gateway IP address"),
    subnet_mask: Optional[str] = typer.Option(None, "--mask", "-m", help="Subnet mask"),
    dns_server: Optional[str] = typer.Option(None, "--dns", "-d", help="DNS server IP address"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    auto_restart: bool = typer.Option(True, "--restart/--no-restart", help="Automatically restart devices to apply changes"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Configure network settings for a device or group of devices.
    
    This command sets multiple network parameters in one operation.
    Changes to network settings usually require a device restart to take effect.
    
    Examples:
        - Configure static IP on a single device:
          shelly-manager parameters common network-config --static --ip 192.168.1.100 --gateway 192.168.1.1 --device abc123
          
        - Set a group of devices to use DHCP:
          shelly-manager parameters common network-config --dhcp --group office_devices
    """
    # Validate that static IP parameters are provided when static=True
    if static and (not ip_address or not gateway):
        console.print("[red]Error: When using static IP, you must provide --ip and --gateway[/red]")
        return
    
    asyncio.run(_set_network_configuration_async(
        static, ip_address, gateway, subnet_mask, dns_server, device_id, group_name, auto_restart, debug
    ))


async def _set_network_configuration_async(
    static: bool,
    ip_address: Optional[str],
    gateway: Optional[str],
    subnet_mask: Optional[str],
    dns_server: Optional[str],
    device_id: Optional[str],
    group_name: Optional[str],
    auto_restart: bool,
    debug: bool
):
    """Set network configuration on a device or group."""
    # Set up logging
    configure_logging(debug=debug)
    
    # Check that at least one of device_id or group_name is provided
    if not device_id and not group_name:
        console.print("[red]Error: Either --device or --group must be specified[/red]")
        return
    
    # Initialize services
    parameter_service = ParameterService()
    
    # Prepare parameter dictionary
    params = {
        "static_ip_config": static
    }
    
    # Add static IP parameters if static=True
    if static:
        if ip_address:
            params["ip_address"] = ip_address
        if gateway:
            params["gateway"] = gateway
        if subnet_mask:
            params["subnet_mask"] = subnet_mask
        if dns_server:
            params["dns_server"] = dns_server
    
    try:
        # Start parameter service
        await parameter_service.start()
        
        # For single device
        if device_id:
            device = device_registry.get_device(device_id)
            if not device:
                console.print(f"[red]Error: Device with ID {device_id} not found[/red]")
                return
            
            console.print(f"[cyan]Configuring network settings for {device.name} ({device.id})...[/cyan]")
            
            # Apply each parameter
            success_count = 0
            failure_count = 0
            
            for param_name, param_value in params.items():
                console.print(f"  Setting {param_name} to {param_value}...")
                success, response = await parameter_service.set_parameter_value(
                    device, param_name, param_value, auto_restart=False  # We'll restart once at the end
                )
                
                if success:
                    success_count += 1
                    console.print(f"  [green]Successfully set {param_name}[/green]")
                else:
                    failure_count += 1
                    console.print(f"  [red]Failed to set {param_name}[/red]")
            
            # Display results
            if success_count == len(params):
                console.print(f"[green]Successfully configured all network settings on {device.name}[/green]")
                
                # Restart the device if needed
                if auto_restart:
                    console.print(f"[yellow]Restarting device {device.name} to apply network changes...[/yellow]")
                    restart_success = await parameter_service._restart_device(device)
                    if restart_success:
                        console.print(f"[green]Successfully restarted device {device.name}[/green]")
                        console.print(f"[yellow]Note: The device IP address may have changed. You may need to discover it again.[/yellow]")
                    else:
                        console.print(f"[red]Failed to restart device {device.name}[/red]")
            else:
                console.print(f"[yellow]Configured {success_count}/{len(params)} network settings on {device.name} with {failure_count} failures[/yellow]")
        
        # For group
        elif group_name:
            # Get group manager
            group_manager = GroupManager()
            
            # Load groups
            groups = group_manager.load_groups()
            
            # Check if group exists
            if group_name not in groups:
                console.print(f"[red]Error: Group '{group_name}' not found[/red]")
                return
            
            # Get devices in group
            device_ids = groups[group_name]
            devices = []
            
            for did in device_ids:
                device = device_registry.get_device(did)
                if device:
                    devices.append(device)
            
            if not devices:
                console.print(f"[red]Error: No devices found in group '{group_name}'[/red]")
                return
            
            console.print(f"[cyan]Configuring network settings for {len(devices)} devices in group '{group_name}'...[/cyan]")
            console.print("[yellow]Warning: Changing network settings for multiple devices at once may make them unreachable![/yellow]")
            console.print("[yellow]Consider applying these changes to one device at a time instead.[/yellow]")
            
            # Confirm before proceeding
            confirm = typer.confirm("Do you want to continue?")
            if not confirm:
                console.print("Operation cancelled.")
                return
            
            # Overall counters
            total_success_count = 0
            total_failure_count = 0
            restart_success_count = 0
            restart_failure_count = 0
            
            # Process each device
            for device in devices:
                console.print(f"[cyan]Device: {device.name} ({device.id})[/cyan]")
                
                # Apply each parameter
                device_success_count = 0
                device_failure_count = 0
                
                for param_name, param_value in params.items():
                    success, response = await parameter_service.set_parameter_value(
                        device, param_name, param_value, auto_restart=False  # We'll restart once at the end
                    )
                    
                    if success:
                        device_success_count += 1
                        total_success_count += 1
                    else:
                        device_failure_count += 1
                        total_failure_count += 1
                
                # Display per-device results
                if device_success_count == len(params):
                    console.print(f"  [green]Successfully configured all network settings[/green]")
                    
                    # Restart the device if needed
                    if auto_restart:
                        console.print(f"  [yellow]Restarting device {device.name} to apply network changes...[/yellow]")
                        restart_success = await parameter_service._restart_device(device)
                        if restart_success:
                            restart_success_count += 1
                            console.print(f"  [green]Successfully restarted device[/green]")
                        else:
                            restart_failure_count += 1
                            console.print(f"  [red]Failed to restart device[/red]")
                else:
                    console.print(f"  [yellow]Configured {device_success_count}/{len(params)} settings with {device_failure_count} failures[/yellow]")
            
            # Display overall results
            total_params = len(params) * len(devices)
            if total_success_count == total_params:
                console.print(f"[green]Successfully configured all network settings on all devices in group '{group_name}'[/green]")
                
                if auto_restart:
                    if restart_success_count == len(devices):
                        console.print(f"[green]Successfully restarted all devices[/green]")
                    else:
                        console.print(f"[yellow]Restarted {restart_success_count}/{len(devices)} devices with {restart_failure_count} failures[/yellow]")
                    
                    console.print(f"[yellow]Note: The device IP addresses may have changed. You may need to discover them again.[/yellow]")
            else:
                console.print(f"[yellow]Configured {total_success_count}/{total_params} network settings with {total_failure_count} failures[/yellow]")
    
    finally:
        # Stop parameter service
        await parameter_service.stop()


@common_app.command("cloud")
def set_cloud_enabled(
    ctx: typer.Context,
    enable: bool = typer.Argument(..., help="Enable (true) or disable (false) Shelly Cloud connectivity"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="Device ID to set parameter on"),
    group_name: Optional[str] = typer.Option(None, "--group", "-g", help="Set parameter on all devices in this group"),
    auto_restart: bool = typer.Option(False, "--restart", "-r", help="Automatically restart devices if required"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode")
):
    """
    Enable or disable Shelly Cloud connectivity.
    
    This command controls whether devices connect to the Shelly Cloud service.
    Disabling cloud connectivity can improve privacy and reduce network traffic.
    
    Examples:
        - Disable cloud connectivity for a single device:
          shelly-manager parameters common cloud false --device abc123
          
        - Enable cloud connectivity for a group:
          shelly-manager parameters common cloud true --group living_room
    """
    # Run the async function
    asyncio.run(_set_parameter_async("cloud_enable", str(enable), device_id, group_name, auto_restart, debug))


# Register dynamic commands at module import time
register_common_parameter_commands() 