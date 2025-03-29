"""CLI commands for managing device groups."""

import typer
from typing import Optional, List
import os

from rich.console import Console
from rich.table import Table
from rich import box

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.grouping.models import DeviceGroup
from shelly_manager.utils.logging import LogConfig, get_logger

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(help="Manage device groups")

# Import the operate app
from shelly_manager.interfaces.cli.commands.operate import app as operate_app

# Add the operate app to the groups app
app.add_typer(operate_app, name="operate", help="Execute operations on device groups")

# Create console for rich output
console = Console()


def display_groups(groups: List[DeviceGroup]) -> None:
    """Display a table of groups.
    
    Args:
        groups: List of groups to display.
    """
    # Create a table
    table = Table(show_header=True, header_style="bold magenta", box=box.DOUBLE_EDGE)
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Devices")
    table.add_column("Tags")
    table.add_column("Config")
    
    # Add groups to the table
    for group in groups:
        table.add_row(
            group.name,
            group.description or "",
            str(len(group.device_ids)),
            ", ".join(group.tags) if group.tags else "",
            str(len(group.config)) if group.config else ""
        )
    
    # Print the table
    console.print(table)


@app.command("list")
def list_groups(debug: bool = typer.Option(False, "--debug", help="Enable debug logging")):
    """List all device groups."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Get all groups
        group_manager = GroupManager()
        all_groups = group_manager.list_groups()
        
        if not all_groups:
            console.print("[yellow]No groups found[/yellow]")
            console.print(f"Groups directory: {os.path.abspath(group_manager.groups_dir)}")
            return
        
        # Display groups
        display_groups(all_groups)
        
    except Exception as e:
        logger.error(f"Failed to list groups: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("show")
def show_group(
    name: str = typer.Argument(..., help="Name of the group to show"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Show details for a specific group."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Get the group
        group_manager = GroupManager()
        group = group_manager.get_group(name)
        
        if not group:
            console.print(f"[red]Group '{name}' not found[/red]")
            return
        
        # Create tables for details
        main_table = Table()
        main_table.add_column("Property")
        main_table.add_column("Value")
        
        # Add basic details
        main_table.add_row("Name", group.name)
        main_table.add_row("Description", group.description or "")
        main_table.add_row("Tags", ", ".join(group.tags) if group.tags else "")
        main_table.add_row("Device Count", str(len(group.device_ids)))
        
        # Print the main table
        console.print(main_table)
        
        # Show devices if available
        if group.device_ids:
            console.print("\n[bold]Devices:[/bold]")
            devices_table = Table()
            devices_table.add_column("Device ID")
            
            for device_id in group.device_ids:
                devices_table.add_row(device_id)
            
            console.print(devices_table)
        
        # Show configuration if available
        if group.config:
            console.print("\n[bold]Configuration:[/bold]")
            config_table = Table()
            config_table.add_column("Key")
            config_table.add_column("Value")
            
            for key, value in group.config.items():
                config_table.add_row(key, str(value))
            
            console.print(config_table)
        
    except Exception as e:
        logger.error(f"Failed to show group details: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("create")
def create_group(
    name: str = typer.Argument(..., help="Name of the group to create"),
    description: Optional[str] = typer.Option(None, "--description", help="Description of the group"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated list of tags"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Create a new device group."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Parse tags
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Create the group
        group_manager = GroupManager()
        
        if group_manager.get_group(name):
            console.print(f"[red]Group '{name}' already exists[/red]")
            return
        
        group = group_manager.create_group(
            name=name,
            description=description,
            tags=tag_list
        )
        
        console.print(f"[green]Created group '{name}'[/green]")
        
    except Exception as e:
        logger.error(f"Failed to create group: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("update")
def update_group(
    name: str = typer.Argument(..., help="Name of the group to update"),
    description: Optional[str] = typer.Option(None, "--description", help="New description"),
    tags: Optional[str] = typer.Option(None, "--tags", help="New comma-separated list of tags"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Update a device group."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Get the group
        group_manager = GroupManager()
        group = group_manager.get_group(name)
        
        if not group:
            console.print(f"[red]Group '{name}' not found[/red]")
            return
        
        # Update description if provided
        if description is not None:
            group.description = description
        
        # Update tags if provided
        if tags is not None:
            group.tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Update the group
        group_manager.update_group(group)
        
        console.print(f"[green]Updated group '{name}'[/green]")
        
    except Exception as e:
        logger.error(f"Failed to update group: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("delete")
def delete_group(
    name: str = typer.Argument(..., help="Name of the group to delete"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Delete a device group."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Delete the group
        group_manager = GroupManager()
        result = group_manager.delete_group(name)
        
        if result:
            console.print(f"[green]Deleted group '{name}'[/green]")
        else:
            console.print(f"[red]Group '{name}' not found[/red]")
        
    except Exception as e:
        logger.error(f"Failed to delete group: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("add-device")
def add_device_to_group(
    group_name: str = typer.Argument(..., help="Name of the group"),
    device_id: str = typer.Argument(..., help="ID of the device to add"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Add a device to a group."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Add device to the group
        group_manager = GroupManager()
        result = group_manager.add_device_to_group(group_name, device_id)
        
        if result:
            console.print(f"[green]Added device '{device_id}' to group '{group_name}'[/green]")
        else:
            console.print(f"[red]Group '{group_name}' not found[/red]")
        
    except Exception as e:
        logger.error(f"Failed to add device to group: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("remove-device")
def remove_device_from_group(
    group_name: str = typer.Argument(..., help="Name of the group"),
    device_id: str = typer.Argument(..., help="ID of the device to remove"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Remove a device from a group."""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        # Remove device from the group
        group_manager = GroupManager()
        result = group_manager.remove_device_from_group(group_name, device_id)
        
        if result:
            console.print(f"[green]Removed device '{device_id}' from group '{group_name}'[/green]")
        else:
            console.print(f"[red]Failed to remove device: Group '{group_name}' not found or device not in group[/red]")
        
    except Exception as e:
        logger.error(f"Failed to remove device from group: {str(e)}")
        console.print(f"[red]Error:[/red] {str(e)}") 