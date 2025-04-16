import os
import uvicorn
import argparse
import logging
import logging.config
from configparser import ConfigParser
from pathlib import Path

from .main import app
from ...utils.logging_config import setup_logging

def parse_args():
    """Parse command line arguments for the API server"""
    parser = argparse.ArgumentParser(description="Shelly Device Manager API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--log-level", default="info", 
                        choices=["debug", "info", "warning", "error", "critical"],
                        help="Logging level")
    return parser.parse_args()

def load_config(config_file=None):
    """Load configuration from file"""
    config = ConfigParser()
    
    # Default configuration
    default_config = {
        "server": {
            "host": "0.0.0.0",
            "port": "8000",
            "log_level": "info",
        },
        "discovery": {
            "scan_interval": "300",  # seconds
            "auto_scan_on_startup": "true",
        },
        "security": {
            "enable_auth": "false",
            "cors_origins": "*",
        }
    }
    
    # Set defaults
    for section, options in default_config.items():
        if not config.has_section(section):
            config.add_section(section)
        for option, value in options.items():
            config.set(section, option, value)
    
    # Load from file if provided
    if config_file and os.path.exists(config_file):
        config.read(config_file)
    
    return config

def run_server():
    """Run the API server"""
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup logging - use commandline arg or config value
    log_level = args.log_level.upper() 
    if not log_level and config.has_option("server", "log_level"):
        log_level = config.get("server", "log_level").upper()
    
    # Setup our application logging using the centralized LogConfig
    logger = setup_logging(log_level)
    
    # Get server settings
    host = args.host or config.get("server", "host")
    port = args.port or int(config.get("server", "port"))
    
    # Log startup info
    logger.info(f"Starting Shelly Device Manager API on {host}:{port}")
    logger.info(f"Log level: {log_level}")
    
    # Map log level to uvicorn format (all lowercase)
    uvicorn_log_level = log_level.lower()
    
    # Create custom ASGI configuration to force using our log config
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "default": {
                "class": "logging.NullHandler",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": True},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": True},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": True},
        },
    }
    
    # Start server
    logger.info("Starting Uvicorn server with shared logging configuration")
    try:
        uvicorn.run(
            "shelly_manager.interfaces.api.main:app",
            host=host,
            port=port,
            reload=False,
            log_level=uvicorn_log_level,
            # Explicitly disable uvicorn's default logging
            log_config=log_config,
            access_log=True
        )
    except Exception as e:
        logger.error(f"Error starting API server: {str(e)}")
        raise

if __name__ == "__main__":
    run_server() 