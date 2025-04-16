import logging
import os
from .logging import LogConfig, get_logger

def setup_logging(log_level: str = "INFO"):
    """
    Set up logging for the API service using the same LogConfig class used by the CLI.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    debug = log_level.upper() == "DEBUG"
    
    # Configure logging using the centralized LogConfig class
    log_config = LogConfig(
        app_name="shelly_manager",
        debug=debug,
        log_to_file=True,
        log_to_console=True
    )
    log_config.configure()
    
    # Configure more specific logging - make sure these use the right log level
    logging_level = logging.DEBUG if debug else logging.INFO

    # Configure all API-related and web server loggers
    api_loggers = [
        # Core API modules
        "shelly_manager.interfaces.api",
        "shelly_manager.interfaces.api.main",
        "shelly_manager.interfaces.api.server",
        # Web server components
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        # Include HTTP request logging
        "uvicorn.access",
        # Include ASGI protocol handlers
        "uvicorn.protocols",
        # Include server-related components
        "starlette",
        # Include third-party libraries
        "pydantic",
    ]
    
    # Set the appropriate log level for all API-related loggers
    for logger_name in api_loggers:
        module_logger = logging.getLogger(logger_name)
        module_logger.setLevel(logging_level)
        # Make sure these loggers propagate to root
        module_logger.propagate = True
        
    # Also configure the full app modules
    if debug:
        # Enable debug logging for all key modules
        for module in [
            "shelly_manager",
            "shelly_manager.config_manager",
            "shelly_manager.discovery",
            "shelly_manager.interfaces.api",
            "shelly_manager.models",
            "shelly_manager.utils",
            "shelly_manager.parameter",
            "shelly_manager.grouping",
            "shelly_manager.services",
            "shelly_manager.state",
            "aiohttp",
        ]:
            module_logger = logging.getLogger(module)
            module_logger.setLevel(logging.DEBUG)
            module_logger.propagate = True
    
    # Get the root logger and log that we've set up logging
    logger = get_logger("shelly_manager.api")
    logger.info(f"API logging configured with level: {log_level}")
    logger.info(f"Log files will be saved in: {os.path.abspath('logs')}")
    
    return logger 