"""Models for device parameter management."""

from typing import Dict, Any, Optional
from ..utils.logging import get_logger
from .parameter_mapping import parameter_manager, ParameterDefinition, ParameterType

logger = get_logger(__name__)

def get_parameters_for_model(model: str) -> Dict[str, ParameterDefinition]:
    """
    Get parameter definitions for a specific model based on device capabilities.
    
    This function leverages the device capabilities system to determine which
    parameters are supported by a specific device model. It will return only
    the parameter definitions that apply to the given model.
    
    Args:
        model: Device model name or identifier
    
    Returns:
        Dictionary of parameter definitions by name that apply to this model
    """
    from .device_capabilities import device_capabilities
    
    if not model:
        logger.warning("No model provided, returning common parameters")
        # Return common parameters that are likely to be supported by most devices
        return {param.name: param for param in parameter_manager.get_all_common_parameters()}
    
    # Try to find capability for this model
    capability = device_capabilities.get_capability_for_model(model)
    
    if not capability:
        logger.warning(f"No capability found for model '{model}', returning common parameters")
        return {param.name: param for param in parameter_manager.get_all_common_parameters()}
    
    # Get all parameter definitions
    all_params = parameter_manager.get_all_parameter_definitions()
    
    # Filter to those that are in the capability's parameters
    result = {}
    for param_name, param_def in all_params.items():
        # Check using standard name
        if param_name in capability.parameters:
            result[param_name] = param_def
            continue
            
        # Try using Gen1 name for backward compatibility
        gen1_name = parameter_manager.to_gen1_parameter(param_name)
        if gen1_name != param_name and gen1_name in capability.parameters:
            result[param_name] = param_def
    
    if not result:
        logger.warning(f"No parameters found for model '{model}', returning common parameters")
        return {param.name: param for param in parameter_manager.get_all_common_parameters()}
    
    return result

def get_parameter_by_name(name: str) -> Optional[ParameterDefinition]:
    """
    Get a parameter definition by name.
    
    Args:
        name: Parameter name
        
    Returns:
        Parameter definition if found, None otherwise
    """
    return parameter_manager.get_parameter_definition(name)

def get_parameters_by_group(group_name: str) -> Dict[str, ParameterDefinition]:
    """
    Get all parameters in a specific group.
    
    Args:
        group_name: Group name (e.g., power, network, mqtt, etc.)
        
    Returns:
        Dictionary of parameter definitions by name in the specified group
    """
    params = parameter_manager.get_parameters_by_group(group_name)
    return {param.name: param for param in params}

def get_all_parameter_names() -> Dict[str, str]:
    """
    Get all parameter names with their display names.
    
    Returns:
        Dictionary of parameter names to display names
    """
    return {name: param.display_name 
            for name, param in parameter_manager.get_all_parameter_definitions().items()}

def get_common_parameters() -> Dict[str, ParameterDefinition]:
    """
    Get all common parameters that are used across multiple device types.
    
    Returns:
        Dictionary of common parameter definitions by name
    """
    return {param.name: param for param in parameter_manager.get_all_common_parameters()} 