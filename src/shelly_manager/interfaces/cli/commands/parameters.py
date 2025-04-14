"""CLI commands for managing device parameters."""

import typer
import asyncio
from typing import Optional, List, Dict, Any
import os
import json
import yaml

from rich.console import Console
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

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

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(help="Manage device parameters")

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
    device_id: str = typer.Argument(..., help="Device ID to set parameter on"),
    parameter: str = typer.Argument(..., help="Parameter name to set"),
    value: str = typer.Argument(..., help="Value to set"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode")
):
    """
    Set a parameter value.
    
    This command sets the value of a parameter for a device.
    """
    # Run the async function
    asyncio.run(_set_parameter_async(device_id, parameter, value, debug))


async def _set_parameter_async(device_id: str, parameter_name: str, value_str: str, debug: bool):
    """Set a parameter value."""
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
        
        # Parse value
        value = _parse_value(value_str)
        
        console.print(f"[cyan]Setting parameter '{parameter_name}' for {device.name} ({device.id}) to '{value}'...[/cyan]")
        
        # Get capability for validation
        capability = device_capabilities.get_capability_for_device(device)
        if capability:
            param_details = capability.get_parameter_details(parameter_name)
            if not param_details:
                console.print(f"[yellow]Warning: Parameter '{parameter_name}' is not defined for this device type.[/yellow]")
                console.print("[yellow]The operation might fail if the parameter doesn't exist.[/yellow]")
            elif param_details.get("read_only", True):
                console.print(f"[red]Error: Parameter '{parameter_name}' is read-only.[/red]")
                return
        
        # Set parameter value
        success, result = await parameter_service.set_parameter_value(device, parameter_name, value)
        
        if success:
            console.print(f"[green]Successfully set {parameter_name} = {value} for {device.name}[/green]")
            
            # If there's detailed response data, show it
            if isinstance(result, dict) and result:
                console.print("[cyan]Response:[/cyan]")
                console.print(Panel(json.dumps(result, indent=2), expand=False))
        else:
            console.print(f"[red]Error: Failed to set parameter '{parameter_name}' for {device.id}[/red]")
            if isinstance(result, dict) and "error" in result:
                console.print(f"[red]Error details: {result['error']}[/red]")
    
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