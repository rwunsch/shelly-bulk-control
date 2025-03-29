# Shelly Bulk Control Tests

This directory contains test cases for the Shelly Bulk Control system. The tests verify the functionality of various components, with a focus on the device grouping functionality.

## Running the Tests

### Unit Tests

To run all the unit tests:

```bash
python -m unittest discover -s tests
```

To run a specific test file:

```bash
python -m unittest tests/test_grouping.py
```

To run a specific test case:

```bash
python -m unittest tests.test_grouping.TestGroupManager
```

To run a specific test method:

```bash
python -m unittest tests.test_grouping.TestGroupManager.test_create_group
```

### Using pytest

For the pytest-based tests:

```bash
pytest tests/test_cli_grouping.py -v
```

### Integration Tests

Integration tests verify that different components work correctly together:

```bash
python -m unittest tests/test_integration.py
```

### CLI Tests

#### Shell Script Method

To test the CLI functionality using a shell script:

```bash
chmod +x test_grouping_cli.sh
./test_grouping_cli.sh
```

This script will:
1. Create a temporary test directory for groups
2. Run a series of CLI commands to test group creation, listing, updating, etc.
3. Verify that each operation produces the expected changes to the group files
4. Clean up the test directory when done

#### Python-Based CLI Testing

A more robust way to test the CLI is using the pytest-based approach:

```bash
pytest tests/test_cli_grouping.py -v
```

This provides better error reporting and more consistent behavior across platforms.

## Test Structure

### Unit Tests

- `test_grouping.py`: Tests the `GroupManager` class functionality with focus on file-per-group operations
- `test_group_file_handling.py`: Tests file-related aspects like filename sanitizing, content structure, and error handling

### Integration Tests

- `test_integration.py`: Tests interactions between components, focusing on cross-group operations and file persistence
- `test_group_concurrency.py`: Tests concurrent access to the group manager from multiple threads

### CLI Tests

- `test_grouping_cli.sh`: Shell script that tests the command-line interface for group management
- `test_cli_grouping.py`: Python-based pytest tests for the CLI functionality

## Testing Approaches

The testing strategy in this project uses multiple approaches for comprehensive coverage:

1. **Unit Testing**: Focused on individual components in isolation (e.g., `GroupManager` class)
2. **Integration Testing**: Testing how components work together
3. **CLI Testing**: Verifying the command-line interface
4. **File Handling Testing**: Ensuring proper file operations for group storage
5. **Concurrency Testing**: Verifying behavior under concurrent use

All tests use temporary directories for isolation to avoid affecting real application data 