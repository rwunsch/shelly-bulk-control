import click
from shelly_manager.services.discovery_service import DiscoveryService
from shelly_manager.utils.logging import setup_logging

@click.option('--network', default='192.168.1.0/24', help='Network to scan in CIDR notation (e.g. 192.168.1.0/24)')
@click.option('--force-http', is_flag=True, help='Force HTTP discovery even if mDNS devices are found')
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--ips', help='Comma-separated list of specific IP addresses to probe')
@click.pass_context
async def discover(ctx, network, force_http, debug, ips):
    """Discover Shelly devices on the network"""
    # Configure logging
    setup_logging(debug=debug)
    
    # Create discovery service
    discovery_service = DiscoveryService()
    logger.debug(f"Discovery service initialized")
    
    ip_addresses = None
    if ips:
        # Parse comma-separated list of IPs
        ip_addresses = [ip.strip() for ip in ips.split(',')]
        logger.info(f"Will probe specific IP addresses: {ip_addresses}")
    
    # Start device discovery
    devices = await discovery_service.discover_devices(
        network=network,
        force_http=force_http,
        ip_addresses=ip_addresses
    ) 