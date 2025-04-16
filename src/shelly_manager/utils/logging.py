import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional

class LogConfig:
    """Centralized logging configuration"""
    
    # Class variable to track if logging has been set up
    _is_setup = False
    _early_debug_enabled = False
    
    def __init__(
        self,
        app_name: str = "shelly_manager",
        log_dir: str = "logs",
        debug: bool = False,
        log_to_file: bool = True,
        log_to_console: bool = True,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        self.app_name = app_name
        self.log_dir = log_dir
        self.debug = debug
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Create logs directory if it doesn't exist
        if log_to_file:
            os.makedirs(log_dir, exist_ok=True)
    
    @classmethod
    def setup(cls, **kwargs):
        """Static method to create and set up a LogConfig instance"""
        log_config = cls(**kwargs)
        log_config.configure()
        return log_config
    
    @classmethod
    def check_early_debug(cls):
        """
        Check for --debug flag and set up early logging if needed.
        Returns True if early debug was enabled.
        """
        if cls._early_debug_enabled:
            return True
            
        if "--debug" in sys.argv:
            # Skip if proper logging is already configured
            if cls._is_setup:
                return True
                
            # Set up basic console logging for early debugging
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            
            # Check if a handler already exists
            handler_exists = False
            for handler in root_logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler_exists = True
                    break
                    
            # Only add a handler if one doesn't already exist
            if not handler_exists:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(logging.DEBUG)
                
                # Set a simple formatter
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                console_handler.setFormatter(formatter)
                
                # Add the handler to the logger
                root_logger.addHandler(console_handler)
                
            # Log that early debugging is enabled
            logging.debug("Early debugging enabled")
            
            # Enable debug for key modules
            for module in [
                "shelly_manager.config_manager",
                "shelly_manager.discovery",
                "shelly_manager.interfaces.cli",
                "shelly_manager.models",
                "shelly_manager.utils",
                "shelly_manager.parameter",
                "shelly_manager.grouping",
            ]:
                logging.getLogger(module).setLevel(logging.DEBUG)
                
            debug_logger = logging.getLogger("early_debug")
            debug_logger.debug("Early debug logging enabled via command line --debug flag")
            cls._early_debug_enabled = True
            return True
        return False
    
    def configure(self):
        """Configure logging for the application"""
        # Skip setup if already done to prevent duplicates
        if LogConfig._is_setup:
            logging.getLogger().debug("Logging already configured, skipping setup")
            return
            
        # Check for debug flag in command line arguments
        if "--debug" in sys.argv:
            self.debug = True
            
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Set the root logger level
        root_logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        
        # Remove all existing handlers to prevent duplicates
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            handler.close()  # Properly close handlers
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler with daily rotation
        if self.log_to_file:
            # Create filename with current date
            current_date = datetime.now().strftime("%Y%m%d")
            log_file = os.path.join(
                self.log_dir,
                f"{self.app_name}_{current_date}.log"
            )
            
            # Use TimedRotatingFileHandler for daily rotation
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        # Console handler
        if self.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            # Let console show DEBUG messages if debug mode is enabled
            console_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # Mark logging as set up
        LogConfig._is_setup = True
        
        # Log startup information
        logger = logging.getLogger()
        logger.info(f"Logging configured for {self.app_name}")
        if self.debug:
            logger.info("Debug mode: Enabled")
        if self.log_to_file:
            logger.info(f"Log directory: {os.path.abspath(self.log_dir)}")
            logger.info(f"Log files will be rotated daily")
            logger.info(f"Keeping {self.backup_count} backup files")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name) 