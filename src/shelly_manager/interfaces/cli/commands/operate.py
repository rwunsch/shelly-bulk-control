"""CLI commands for operating on device groups."""

import typer
import asyncio
from typing import Optional, List, Dict, Any
import os
import json

from rich.console import Console
from rich.table import Table
from rich import box

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.grouping.command_service import GroupCommandService
from shelly_manager.utils.logging import LogConfig, get_logger

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(help="Operate on device groups")

# Create console for rich output
console = Console()


@app.command("execute")
def operate_group(
    group_name: str = typer.Argument(..., help="Name of the group to operate on"),
    action: str = typer.Option(..., "--action", "-a", help="Action to perform (turn_on, turn_off, toggle, status, reboot)"),
    parameters: str = typer.Option(None, "--parameters", "-p", help="Additional parameters in format key1=value1,key2=value2"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """
    Execute an operation on a group of devices.
    
    Examples:
        - shelly-bulk-control groups operate execute living_room --action turn_on
        - shelly-bulk-control groups operate execute lights --action set_brightness --parameters brightness=50
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
        
        # Parse parameters
        param_dict = {}
        if parameters:
            for param in parameters.split(","):
                if "=" in param:
                    key, value = param.split("=", 1)
                    # Try to convert value to int or float if possible
                    try:
                        if value.isdigit():
                            value = int(value)
                        elif "." in value and all(p.isdigit() for p in value.split(".")):
                            value = float(value)
                        elif value.lower() == "true":
                            value = True
                        elif value.lower() == "false":
                            value = False
                    except:
                        pass  # Keep as string if conversion fails
                    param_dict[key.strip()] = value
                else:
                    console.print(f"[yellow]Warning: Invalid parameter format: {param}. Expected key=value[/yellow]")
        
        # Run the operation asynchronously
        asyncio.run(_operate_group_async(group_name, action, param_dict, debug))
        
    except Exception as e:
        logger.error(f"Failed to operate on group: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


async def _operate_group_async(group_name: str, action: str, parameters: Dict[str, Any], debug: bool):
    """
    Execute a group operation asynchronously.
    
    Args:
        group_name: Name of the group to operate on
        action: Action to perform
        parameters: Additional parameters
        debug: Whether to enable debug logging
    """
    # Initialize group manager and command service
    logger.debug("Initializing group manager and command service")
    group_manager = GroupManager()
    command_service = GroupCommandService(group_manager)
    
    # Start the command service
    await command_service.start()
    
    try:
        # Validate that the group exists
        group = group_manager.get_group(group_name)
        if not group:
            console.print(f"[red]Error:[/red] Group '{group_name}' not found")
            return
        
        # Execute the appropriate action
        if action == "turn_on":
            console.print(f"Turning on all devices in group '{group_name}'...")
            result = await command_service.turn_on_group(group_name)
        elif action == "turn_off":
            console.print(f"Turning off all devices in group '{group_name}'...")
            result = await command_service.turn_off_group(group_name)
        elif action == "toggle":
            console.print(f"Toggling all devices in group '{group_name}'...")
            result = await command_service.toggle_group(group_name)
        elif action == "status":
            console.print(f"Getting status for all devices in group '{group_name}'...")
            result = await command_service.get_group_status(group_name)
        elif action == "reboot":
            console.print(f"Rebooting all devices in group '{group_name}'...")
            result = await command_service.reboot_group(group_name)
        elif action == "set_brightness" and "brightness" in parameters:
            brightness = parameters["brightness"]
            console.print(f"Setting brightness to {brightness} for all devices in group '{group_name}'...")
            result = await command_service.set_brightness_group(group_name, brightness)
        elif action == "check_updates":
            console.print(f"Checking for firmware updates for all devices in group '{group_name}'...")
            result = await command_service.check_updates_group(group_name)
        elif action == "apply_updates":
            only_with_updates = parameters.get("only_with_updates", True)
            if only_with_updates:
                console.print(f"Applying firmware updates to devices with available updates in group '{group_name}'...")
            else:
                console.print(f"Applying firmware updates to all devices in group '{group_name}'...")
            result = await command_service.apply_updates_group(group_name, only_with_updates)
        else:
            # Generic operation
            console.print(f"Executing '{action}' on all devices in group '{group_name}'...")
            result = await command_service.operate_group(group_name, action, parameters)
        
        # Display results
        _display_operation_results(result)
        
    finally:
        # Stop the command service
        await command_service.stop()


def _display_operation_results(results: Dict):
    """
    Display operation results in a table.
    
    Args:
        results: The operation results to display
    """
    if "error" in results:
        console.print(f"[red]Error:[/red] {results['error']}")
        return
        
    if "warning" in results:
        console.print(f"[yellow]Warning:[/yellow] {results['warning']}")
        return
    
    # Create table header
    console.print(f"\n[bold]Operation results for group '{results['group']}'[/bold]")
    console.print(f"Action: [cyan]{results['action']}[/cyan]")
    if results["parameters"]:
        console.print(f"Parameters: {json.dumps(results['parameters'])}")
    console.print(f"Devices affected: {results['device_count']}")
    
    # Create table for device results
    table = Table(show_header=True, header_style="bold magenta", box=box.SQUARE)
    table.add_column("Device ID", style="dim")
    table.add_column("Success")
    table.add_column("Result/Error")
    
    # Add rows for each device
    for device_id, device_result in results["results"].items():
        success = device_result.get("success", False)
        result_text = ""
        
        if "error" in device_result:
            result_text = device_result["error"]
        elif "result" in device_result:
            # Format result as string, truncate if too long
            result_str = str(device_result["result"])
            if len(result_str) > 50:
                result_text = result_str[:47] + "..."
            else:
                result_text = result_str
        
        table.add_row(
            device_id,
            "[green]Yes[/green]" if success else "[red]No[/red]",
            result_text
        )
    
    # Display the table
    console.print(table)
    
    # Calculate success rate
    success_count = sum(1 for r in results["results"].values() if r.get("success", False))
    success_rate = success_count / results["device_count"] * 100 if results["device_count"] > 0 else 0
    
    console.print(f"\nSuccess rate: [{'green' if success_rate == 100 else 'yellow' if success_rate > 50 else 'red'}]{success_rate:.0f}%[/]")


# Command aliases for common operations
@app.command("on")
def turn_on(
    group_name: str = typer.Argument(..., help="Name of the group to turn on"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Turn on all devices in a group."""
    operate_group(group_name=group_name, action="turn_on", parameters=None, debug=debug)


@app.command("off")
def turn_off(
    group_name: str = typer.Argument(..., help="Name of the group to turn off"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Turn off all devices in a group."""
    operate_group(group_name=group_name, action="turn_off", parameters=None, debug=debug)


@app.command("toggle")
def toggle(
    group_name: str = typer.Argument(..., help="Name of the group to toggle"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Toggle all devices in a group."""
    operate_group(group_name=group_name, action="toggle", parameters=None, debug=debug)


@app.command("status")
def status(
    group_name: str = typer.Argument(..., help="Name of the group to check status"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Check status of all devices in a group."""
    operate_group(group_name=group_name, action="status", parameters=None, debug=debug)


@app.command("reboot")
def reboot(
    group_name: str = typer.Argument(..., help="Name of the group to reboot"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Reboot all devices in a group."""
    operate_group(group_name=group_name, action="reboot", parameters=None, debug=debug)


@app.command("brightness")
def set_brightness(
    group_name: str = typer.Argument(..., help="Name of the group to set brightness"),
    level: int = typer.Argument(..., help="Brightness level (0-100)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Set brightness for all light devices in a group."""
    parameters = f"brightness={level}"
    operate_group(group_name=group_name, action="set_brightness", parameters=parameters, debug=debug)


@app.command("check-updates")
def check_updates(
    group_name: str = typer.Argument(..., help="Name of the group to check for updates"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Check for firmware updates for all devices in a group."""
    operate_group(group_name=group_name, action="check_updates", parameters=None, debug=debug)


@app.command("update-firmware")
def apply_firmware_updates(
    group_name: str = typer.Argument(..., help="Name of the group to update firmware for"),
    all_devices: bool = typer.Option(False, "--all", help="Update all devices, not just those with available updates"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Apply firmware updates to all devices in a group."""
    parameters = f"only_with_updates={not all_devices}"
    operate_group(group_name=group_name, action="apply_updates", parameters=parameters, debug=debug) 