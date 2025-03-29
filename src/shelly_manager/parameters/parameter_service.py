"""Redirector to new parameter service implementation."""

# This module is kept for backward compatibility
# It imports and re-exports the unified ParameterService from the new location

import sys
import logging
from ..utils.logging import get_logger

logger = get_logger(__name__)
logger.info("Using unified ParameterService from parameter.parameter_service")

# Import and re-export the unified implementation
from ..parameter.parameter_service import ParameterService

# Warn about deprecation on import
logger.warning(
    "Importing from 'parameters.parameter_service' is deprecated and will be removed in a future version. "
    "Please update your imports to use 'parameter.parameter_service' instead."
) 