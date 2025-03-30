from shelly_manager.models.parameter_mapping import ParameterMapper

def test_parameter_mapping():
    # Initialize mapper to load mappings
    mapper = ParameterMapper()
    
    # Test Standard to Gen1 mapping
    assert ParameterMapper.to_gen1_parameter("eco_mode") == "eco_mode_enabled"
    assert ParameterMapper.to_gen1_parameter("unknown_param") == "unknown_param"
    
    # Test Gen1 to Standard mapping
    assert ParameterMapper.to_standard_parameter("eco_mode_enabled") == "eco_mode"
    assert ParameterMapper.to_standard_parameter("unknown_param") == "unknown_param"
    
    print("Parameter mapping tests passed!")

if __name__ == "__main__":
    test_parameter_mapping() 