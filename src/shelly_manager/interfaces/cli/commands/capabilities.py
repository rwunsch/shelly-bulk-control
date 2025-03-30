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

from ....models.device_capabilities import DeviceCapabilities, CapabilityDiscovery, device_capabilities
from ....models.device_registry import device_registry
from ....discovery.discovery_service import DiscoveryService
from ....utils.logging import get_logger

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
    network: str = typer.Option("192.168.1.0/24", "--network", help="Network CIDR to scan (default: 192.168.1.0/24)")
):
    """
    Discover capabilities from a device and generate a capability definition.
    
    Either --ip, --id, or --scan must be specified.
    """
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
            # Start the discovery service
            asyncio.run(discovery_service.start())
            
            device = asyncio.run(discovery_service._probe_device(ip))
            if not device:
                console.print(f"[red]Error: No Shelly device found at {ip}[/red]")
                asyncio.run(discovery_service.stop())
                return
        except Exception as e:
            console.print(f"[red]Error discovering device: {e}[/red]")
            asyncio.run(discovery_service.stop())
            return
        
        asyncio.run(discovery_service.stop())
    
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