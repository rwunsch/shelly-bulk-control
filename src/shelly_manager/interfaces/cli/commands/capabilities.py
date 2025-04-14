"""
CLI commands for managing device capabilities.
"""
import asyncio
import typer
from typing import List, Optional
import logging
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import yaml
from pathlib import Path

from ....models.device_capabilities import DeviceCapabilities, CapabilityDiscovery, device_capabilities
from ....models.device_registry import device_registry
from ....discovery.discovery_service import DiscoveryService
from ....utils.logging import get_logger
from ....models.parameter_mapping import ParameterMapper

# Get logger for this module
logger = get_logger(__name__)

# Create typer app
app = typer.Typer(help="Manage device capabilities")
console = Console()

@app.command("list")
def list_capabilities(
    ctx: typer.Context,
    device_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by device type"),
    parameter: Optional[str] = typer.Option(None, "--parameter", "-p", help="Filter by supported parameter")
):
    """
    List available capability definitions.
    """
    capabilities = device_capabilities.capabilities
    
    if not capabilities:
        console.print("[yellow]No capability definitions found[/yellow]")
        return
    
    # Create table
    table = Table(title="Device Capability Definitions")
    table.add_column("Device Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Generation", style="blue")
    table.add_column("Parameters", style="magenta")
    table.add_column("APIs", style="yellow")
    
    # Filter by device type if specified
    if device_type:
        capabilities = {k: v for k, v in capabilities.items() if device_type.lower() in k.lower()}
        
    # Add rows
    for cap_id, capability in capabilities.items():
        table.add_row(
            cap_id,
            capability.name,
            capability.generation,
            str(len(capability.parameters)),
            str(len(capability.apis))
        )
    
    console.print(table)

@app.command("show")
def show_capability(
    device_type: str = typer.Argument(..., help="Device type ID to show"),
    parameters_only: bool = typer.Option(False, "--parameters", "-p", help="Show parameters only"),
    apis_only: bool = typer.Option(False, "--apis", "-a", help="Show APIs only")
):
    """
    Show details of a specific capability definition.
    """
    capability = device_capabilities.get_capability(device_type)
    
    if not capability:
        console.print(f"[red]Capability definition for '{device_type}' not found[/red]")
        return
    
    # Show general info
    if not parameters_only and not apis_only:
        console.print(Panel(f"[cyan bold]{capability.name}[/cyan bold]", 
                           title=f"Device Type: {capability.device_type}"))
        console.print(f"Generation: [blue]{capability.generation}[/blue]")
        console.print("")
    
    # Show parameters
    if not apis_only or parameters_only:
        param_table = Table(title=f"Parameters for {capability.device_type}")
        param_table.add_column("Name", style="cyan")
        param_table.add_column("Type", style="green")
        param_table.add_column("Description", style="white")
        param_table.add_column("API", style="yellow")
        param_table.add_column("Path", style="magenta")
        
        for param_name, param_info in sorted(capability.parameters.items()):
            param_table.add_row(
                param_name,
                param_info.get("type", "unknown"),
                param_info.get("description", ""),
                param_info.get("api", ""),
                param_info.get("parameter_path", "")
            )
        
        console.print(param_table)
        console.print("")
    
    # Show APIs
    if not parameters_only or apis_only:
        api_table = Table(title=f"APIs for {capability.device_type}")
        api_table.add_column("API", style="cyan")
        api_table.add_column("Description", style="white")
        
        for api_name, api_info in sorted(capability.apis.items()):
            api_table.add_row(
                api_name,
                api_info.get("description", "")
            )
        
        console.print(api_table)

@app.command("discover")
def discover_capabilities(
    ip: Optional[str] = typer.Option(None, "--ip", "-i", help="IP address of device to discover"),
    device_id: Optional[str] = typer.Option(None, "--id", help="ID of device to discover"),
    force: bool = typer.Option(False, "--force", "-f", help="Force rediscovery even if capability exists"),
    scan: bool = typer.Option(False, "--scan", help="Scan network for devices and discover capabilities for all"),
    network: str = typer.Option("192.168.1.0/24", "--network", help="Network CIDR to scan (default: 192.168.1.0/24)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging")
):
    """
    Discover capabilities from a device and generate a capability definition.
    
    Either --ip, --id, or --scan must be specified.
    """
    # Configure logging for debug mode
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        console.print("[yellow]Debug mode enabled[/yellow]")
    
    if not ip and not device_id and not scan:
        console.print("[red]Error: Either --ip, --id, or --scan must be specified[/red]")
        return
    
    # Create discovery service
    discovery_service = DiscoveryService()
    
    # Handle network scan case
    if scan:
        console.print(f"Scanning network {network} for devices and discovering capabilities...")
        
        # Start discovery service and scan for devices
        try:
            # Create async function to run the scan and capability discovery
            async def scan_and_discover():
                # Initialize the discovery service
                await discovery_service.start()
                
                # Discover devices
                console.print(f"[cyan]Scanning network {network} for devices...[/cyan]")
                devices = await discovery_service.discover_devices(network=network)
                
                if not devices:
                    console.print("[yellow]No devices found in network scan[/yellow]")
                    await discovery_service.stop()
                    return
                
                console.print(f"[green]Found {len(devices)} devices[/green]")
                
                # Discover capabilities for each device
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task(f"[cyan]Discovering capabilities for {len(devices)} devices...[/cyan]", total=len(devices))
                    
                    results = {}
                    for i, device in enumerate(devices):
                        progress.update(task, description=f"[cyan]Discovering capabilities for device {i+1}/{len(devices)}: {device.id}[/cyan]")
                        
                        # Check if capability already exists and we're not forcing rediscovery
                        capability = device_capabilities.get_capability_for_device(device)
                        if capability and not force:
                            progress.console.print(f"[yellow]  Skipping {device.id} - capability already exists ({capability.device_type})[/yellow]")
                            results[device.id] = "skipped"
                            progress.advance(task)
                            continue
                        
                        # Discover capabilities
                        success = await discovery_service.discover_device_capabilities(device)
                        results[device.id] = "success" if success else "failed"
                        progress.advance(task)
                
                # Close the discovery service
                await discovery_service.stop()
                
                # Print results
                table = Table(title="Capability Discovery Results")
                table.add_column("Device ID", style="cyan")
                table.add_column("Result", style="green")
                
                for device_id, result in results.items():
                    if result == "success":
                        status = "[green]Success[/green]"
                    elif result == "skipped":
                        status = "[yellow]Skipped (existing)[/yellow]"
                    else:
                        status = "[red]Failed[/red]"
                    table.add_row(device_id, status)
                
                console.print(table)
            
            # Run the async function
            asyncio.run(scan_and_discover())
            
        except Exception as e:
            console.print(f"[red]Error scanning network and discovering capabilities: {e}[/red]")
        
        return
    
    # Single device discovery logic (existing code)
    device = None
    
    if device_id:
        device = device_registry.get_device(device_id)
        if not device:
            console.print(f"[red]Error: Device with ID '{device_id}' not found[/red]")
            return
    
    # If we only have IP, we need to discover the device
    if not device and ip:
        console.print(f"Discovering device at {ip}...")
        
        try:
            console.print(f"[cyan]Probing IP {ip} for device...[/cyan]")
            # Start discovery service
            discovery_service = DiscoveryService()
            try:
                device = asyncio.run(discovery_service._probe_device(ip))
                if not device:
                    console.print(f"[red]Error: No Shelly device found at {ip}[/red]")
                    return
                
                # Discover capabilities for the device
                console.print(f"[cyan]Discovering capabilities for device at {ip}...[/cyan]")
                success = asyncio.run(discovery_service.discover_device_capabilities(device))
                if success:
                    console.print(f"[green]Successfully discovered capabilities for {device.name} ({device.id})[/green]")
                else:
                    console.print(f"[red]Failed to discover capabilities for device at {ip}[/red]")
            finally:
                # Make sure we stop the discovery service
                try:
                    asyncio.run(discovery_service.stop())
                except RuntimeError:
                    # Ignore runtime errors about closed event loops
                    pass
        except Exception as e:
            console.print(f"[red]Error discovering device: {e}[/red]")
            return
        
    if not device:
        console.print("[red]Error: No device found to discover capabilities for[/red]")
        return
    
    # Check if capability already exists
    capability = device_capabilities.get_capability_for_device(device)
    if capability and not force:
        console.print(f"[yellow]Capability definition for this device type already exists: {capability.device_type}[/yellow]")
        console.print("Use --force to rediscover and update")
        return
    
    # Discover capabilities
    console.print(f"Discovering capabilities for {device.id} ({device.ip_address})...")
    
    # Use the discovery service directly for capability discovery
    try:
        # Start the discovery service
        asyncio.run(discovery_service.start())
        
        # Discover capabilities
        success = asyncio.run(discovery_service.discover_device_capabilities(device))
        
        # Stop the discovery service
        asyncio.run(discovery_service.stop())
        
        if success:
            # Get the capability that was just discovered
            capability = device_capabilities.get_capability_for_device(device)
            if capability:
                console.print(f"[green]Successfully discovered capabilities for {device.id}[/green]")
                console.print(f"Capability definition saved as: [cyan]{capability.device_type}.yaml[/cyan]")
                console.print(f"Found [yellow]{len(capability.apis)}[/yellow] APIs and [yellow]{len(capability.parameters)}[/yellow] parameters")
            else:
                console.print(f"[green]Successfully discovered capabilities but couldn't retrieve the definition[/green]")
        else:
            console.print(f"[red]Failed to discover capabilities for {device.id}[/red]")
    except Exception as e:
        console.print(f"[red]Error during capability discovery: {e}[/red]")
        try:
            asyncio.run(discovery_service.stop())
        except:
            pass

@app.command("check-parameter")
def check_parameter(
    parameter: str = typer.Argument(..., help="Parameter name to check"),
    device_id: Optional[str] = typer.Option(None, "--id", help="Check for a specific device"),
    device_type: Optional[str] = typer.Option(None, "--type", "-t", help="Check for a specific device type")
):
    """
    Check which devices/types support a specific parameter.
    """
    # Get all capability definitions
    capabilities = device_capabilities.capabilities
    
    if not capabilities:
        console.print("[yellow]No capability definitions found[/yellow]")
        return
    
    # Filter by device type if specified
    if device_type:
        capabilities = {k: v for k, v in capabilities.items() if device_type.lower() in k.lower()}
    
    # If device ID is specified, get that device's capability
    if device_id:
        device = device_registry.get_device(device_id)
        if not device:
            console.print(f"[red]Error: Device with ID '{device_id}' not found[/red]")
            return
            
        capability = device_capabilities.get_capability_for_device(device)
        if not capability:
            console.print(f"[yellow]No capability definition found for device {device_id}[/yellow]")
            return
            
        capabilities = {capability.device_type: capability}
    
    # Create table
    table = Table(title=f"Support for parameter: {parameter}")
    table.add_column("Device Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Supported", style="yellow")
    table.add_column("Type", style="blue")
    table.add_column("API", style="magenta")
    
    # Check each capability definition
    found = False
    for cap_id, capability in capabilities.items():
        supported = capability.has_parameter(parameter)
        found = found or supported
        
        if supported:
            param_details = capability.get_parameter_details(parameter)
            table.add_row(
                cap_id,
                capability.name,
                "[green]Yes[/green]",
                param_details.get("type", ""),
                param_details.get("api", "")
            )
        else:
            table.add_row(
                cap_id,
                capability.name,
                "[red]No[/red]",
                "",
                ""
            )
    
    if not found:
        console.print(f"[yellow]Parameter '{parameter}' not supported by any known device type[/yellow]")
    else:
        console.print(table)

@app.command("standardize-parameters")
def standardize_parameters(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying them")
):
    """
    Standardize parameter names in capability files to use Gen2+ naming conventions.
    
    This ensures all capability files use the same parameter names regardless of
    device generation, making parameter compatibility checks simpler.
    """
    try:
        # Get capabilities directory
        capabilities_dir = Path("config/device_capabilities")
        if not capabilities_dir.exists():
            console.print("[red]Capabilities directory not found[/red]")
            return
            
        # Initialize parameter mapper to load mappings
        mapper = ParameterMapper()
        
        # Track files processed
        files_processed = 0
        files_changed = 0
        
        # Process each YAML file
        for file_path in capabilities_dir.glob("*.yaml"):
            try:
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                if not data or "parameters" not in data:
                    continue
                    
                files_processed += 1
                file_changed = False
                
                # Check if this is a Gen1 device
                is_gen1 = data.get("generation") == "gen1"
                
                if is_gen1 and "parameters" in data:
                    parameters = data["parameters"]
                    params_to_rename = {}
                    
                    # Find parameters that need to be renamed
                    for param_name, param_data in list(parameters.items()):
                        standard_name = ParameterMapper.to_standard_parameter(param_name)
                        if standard_name != param_name:
                            params_to_rename[param_name] = standard_name
                            file_changed = True
                            
                            # Log the changes we'll make
                            console.print(f"  - {file_path.name}: Rename '{param_name}' to '{standard_name}'")
                            
                    # Update the parameters dict
                    for old_name, new_name in params_to_rename.items():
                        param_data = parameters.pop(old_name)
                        parameters[new_name] = param_data
                        # Make sure parameter_path preserves the original Gen1 name
                        if "parameter_path" in param_data and param_data["parameter_path"] == old_name:
                            param_data["parameter_path"] = old_name
                
                # Save changes if needed
                if file_changed:
                    files_changed += 1
                    console.print(f"[yellow]Standardizing parameters in {file_path}[/yellow]")
                    
                    if not dry_run:
                        with open(file_path, 'w') as f:
                            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            except Exception as e:
                console.print(f"[red]Error processing {file_path}: {str(e)}[/red]")
        
        # Summary
        if dry_run:
            console.print(f"[green]Dry run complete. {files_changed} of {files_processed} files would be modified.[/green]")
        else:
            console.print(f"[green]Standardization complete. Modified {files_changed} of {files_processed} files.[/green]")
    
    except Exception as e:
        console.print(f"[red]Error standardizing parameters: {str(e)}[/red]")

@app.command("refresh")
def refresh_capabilities(
    force: bool = typer.Option(False, "--force", "-f", help="Force refresh without confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted without actually deleting"),
    no_discover: bool = typer.Option(False, "--no-discover", help="Skip automatic capability discovery after deletion")
):
    """
    Refresh all device capability files by deleting and rediscovering them.
    
    This is useful when you want to rebuild capability files from scratch,
    ensuring all parameters are correctly discovered and standardized.
    
    By default, capabilities will be automatically rediscovered after deletion.
    Use --no-discover to skip discovery and just delete the files.
    """
    # Invert the no_discover flag to get auto_discover
    auto_discover = not no_discover
    
    try:
        # Get capabilities directory
        capabilities_dir = Path("config/device_capabilities")
        if not capabilities_dir.exists():
            console.print("[red]Capabilities directory not found[/red]")
            return
            
        # Count files
        capability_files = list(capabilities_dir.glob("*.yaml"))
        file_count = len(capability_files)
        
        # Show what we're about to do
        console.print(f"[yellow]Found {file_count} capability files in {capabilities_dir}[/yellow]")
        
        if not force and not dry_run:
            confirm = typer.confirm("Are you sure you want to delete all capability files? They will be rediscovered on next use.")
            if not confirm:
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        
        # Delete files
        if not dry_run:
            for file_path in capability_files:
                try:
                    file_path.unlink()
                    console.print(f"Deleted: {file_path}")
                except Exception as e:
                    console.print(f"[red]Failed to delete {file_path}: {str(e)}[/red]")
        else:
            for file_path in capability_files:
                console.print(f"Would delete: {file_path}")
        
        # Summary
        if dry_run:
            console.print(f"[green]Dry run complete. Would delete {file_count} capability files.[/green]")
        else:
            console.print(f"[green]Refresh initiated. Deleted {file_count} capability files.[/green]")
            if not auto_discover:
                console.print("Capability files will need to be manually regenerated or will be created on next use.")
            
        # Run discovery if requested and not in dry run mode
        if auto_discover and not dry_run:
            console.print("\n[cyan]Starting automatic capability discovery...[/cyan]")
            
            # Run scan for all accessible devices
            try:
                # Create discovery service
                discovery_service = DiscoveryService()
                
                # Create async function to run discovery
                async def run_discovery():
                    # Initialize services
                    await discovery_service.start()
                    
                    # Use cached devices if available to avoid network scan
                    console.print("[cyan]Using cached devices for capability discovery...[/cyan]")
                    device_registry.load_all_devices()
                    # Fix: get_devices() method now requires a parameter
                    # We'll pass None or an empty list to get all devices
                    try:
                        # First try with None parameter (if API accepts it)
                        devices = list(device_registry.get_devices(None).values())
                    except TypeError:
                        try:
                            # Then try with empty list (to get all devices)
                            devices = list(device_registry.get_devices([]).values())
                        except Exception as e:
                            console.print(f"[yellow]Error retrieving devices from registry: {str(e)}[/yellow]")
                            console.print("[yellow]Falling back to discovery service...[/yellow]")
                            devices = []
                    
                    # If no devices found in registry, try network scan
                    if not devices:
                        console.print("[yellow]No cached devices found. Performing network scan...[/yellow]")
                        # Fall back to network scan if no cached devices
                        await discovery_service.discover_devices()
                        
                        # Get devices from discovery service
                        if hasattr(discovery_service, 'devices'):
                            # Handle both cases where devices might be a dict or a list
                            if isinstance(discovery_service.devices, dict):
                                devices = list(discovery_service.devices.values())
                            else:  # If it's a list
                                devices = discovery_service.devices
                        elif hasattr(discovery_service, 'get_devices'):
                            # Handle different API versions
                            try:
                                devices = list(discovery_service.get_devices().values())
                            except TypeError:
                                try:
                                    devices = list(discovery_service.get_devices(None).values())
                                except Exception:
                                    devices = []
                    
                    # Final check if we have any devices
                    if not devices:
                        console.print("[yellow]No devices found. Cannot discover capabilities.[/yellow]")
                        await discovery_service.stop()
                        return
                    
                    console.print(f"[green]Found {len(devices)} devices for capability discovery[/green]")
                    
                    # Create capability discovery
                    capability_discovery = CapabilityDiscovery(device_capabilities)
                    
                    # Discover capabilities for each device
                    success_count = 0
                    for device in devices:
                        console.print(f"Discovering capabilities for {device.id} ({device.name or 'Unknown'})...")
                        capability = await capability_discovery.discover_device_capabilities(device)
                        if capability:
                            success_count += 1
                            console.print(f"[green]  Success: Created capability definition for {capability.device_type}[/green]")
                    
                    # Stop discovery service
                    await discovery_service.stop()
                    
                    # Summary
                    console.print(f"\n[green]Capability discovery complete. Created {success_count} of {len(devices)} capability definitions.[/green]")
                
                # Run discovery
                asyncio.run(run_discovery())
                
            except Exception as e:
                console.print(f"[red]Error during automatic capability discovery: {str(e)}[/red]")
                console.print("You may need to run capability discovery manually:")
                console.print("python -m shelly_manager.interfaces.cli.main capabilities discover --scan")
        
    except Exception as e:
        console.print(f"[red]Error refreshing capabilities: {str(e)}[/red]")

async def _discover_capabilities(device_id: Optional[str], scan_network: bool, 
                             ip_address: Optional[str], network: Optional[str], 
                             debug: bool):
    """Discover capabilities from devices."""
    # Create capability discovery services
    capabilities_manager = DeviceCapabilities()
    discovery_service = DiscoveryService()
    capability_discovery = CapabilityDiscovery(capabilities_manager)
    
    # Start discovery service
    await discovery_service.start()
    
    try:
        logger.info("Initializing device discovery...")
        console.print("[bold]Discovering devices...[/bold]")
        
        # Discover devices based on options
        if ip_address:
            logger.info(f"Scanning specific IP: {ip_address}")
            console.print(f"Scanning IP: {ip_address}")
            devices = await discovery_service.discover_devices_by_ip([ip_address])
        elif network:
            logger.info(f"Scanning network: {network}")
            console.print(f"Scanning network: {network}")
            devices = await discovery_service.discover_devices_by_network(network)
        elif scan_network:
            logger.info("Scanning entire local network")
            console.print("Scanning local network (this may take a while)...")
            devices = await discovery_service.discover_devices()
        else:
            # If no scan options are provided, look for cached devices
            logger.info("Using cached devices")
            console.print("Using cached devices...")
            device_registry.load_all_devices()
            devices = list(device_registry.get_devices().values())
            
            # Filter to specific device if requested
            if device_id:
                devices = [d for d in devices if d.id == device_id]
        
        if not devices:
            logger.warning("No devices found")
            console.print("[yellow]No devices found[/yellow]")
            return
        
        # Filter to specific device if requested
        if device_id:
            logger.info(f"Filtering to device: {device_id}")
            devices = [d for d in devices if d.id == device_id]
            if not devices:
                logger.warning(f"Device {device_id} not found")
                console.print(f"[red]Device {device_id} not found[/red]")
                return
        
        # Report discovered devices
        logger.info(f"Discovered {len(devices)} devices")
        console.print(f"[green]Discovered {len(devices)} devices[/green]")
        
        # Discover capabilities for each device
        for device in devices:
            logger.info(f"Discovering capabilities for {device.id} ({device.name})")
            console.print(f"\nDiscovering capabilities for [bold]{device.name}[/bold] ({device.id})...")
            console.print(f"  Type: {device.raw_type if device.raw_type else 'N/A'}")
            console.print(f"  App: {device.raw_app if device.raw_app else 'N/A'}")
            console.print(f"  Model: {device.raw_model if device.raw_model else 'N/A'}")
            console.print(f"  Generation: {device.generation.name}")
            console.print(f"  IP: {device.ip_address if device.ip_address else 'N/A'}")
            
            # Check if we already have this capability
            existing_capability = capabilities_manager.get_capability_for_device(device)
            if existing_capability:
                logger.info(f"Found existing capability definition: {existing_capability.device_type}")
                console.print(f"[yellow]Found existing capability definition: {existing_capability.device_type}[/yellow]")
                console.print(f"  Type mappings: {existing_capability.data.get('type_mappings', [])}")
                continue
            
            # Discover capabilities
            logger.debug(f"Starting capability discovery for {device.id}")
            capability = await capability_discovery.discover_device_capabilities(device)
            
            if capability:
                logger.info(f"Successfully discovered capabilities for {device.id}")
                console.print(f"[green]Successfully discovered capabilities for {device.id}[/green]")
                console.print(f"  Device type: {capability.device_type}")
                console.print(f"  Name: {capability.name}")
                console.print(f"  Generation: {capability.generation}")
                console.print(f"  APIs: {list(capability.apis.keys())}")
                console.print(f"  Parameters: {list(capability.parameters.keys())}")
                console.print(f"  Type mappings: {capability.data.get('type_mappings', [])}")
            else:
                logger.warning(f"Failed to discover capabilities for {device.id}")
                console.print(f"[red]Failed to discover capabilities for {device.id}[/red]")
    
    finally:
        # Stop discovery service
        await discovery_service.stop() 