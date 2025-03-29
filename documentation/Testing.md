# Testing Strategy for Shelly Bulk Control

This document outlines the testing strategy used for the Shelly Bulk Control project, focusing on the verification of the file-per-group approach in the device grouping system.

## Testing Goals

The main goals of our testing strategy are:

1. Verify that all functionalities of the `GroupManager` work correctly with the file-per-group approach
2. Ensure that file operations (create, read, update, delete) work correctly for group files
3. Confirm that the CLI interfaces correctly with the grouping system
4. Validate edge cases (special characters in names, missing directories, etc.)

## Test Levels

### Unit Tests (`tests/test_grouping.py`)

Unit tests focus on testing individual components in isolation. For the `GroupManager`, we test:

- Creating groups (normal and with special characters)
- Updating group properties
- Deleting groups
- Adding devices to groups
- Removing devices from groups
- Getting groups for a device
- Listing all groups
- Getting all devices in a group
- Getting all devices across all groups
- Error handling (non-existent groups, duplicate names)

The unit tests use a temporary directory for testing to avoid interfering with actual group files.

### Integration Tests (`tests/test_integration.py`)

Integration tests verify that different components work together correctly. We focus on:

- File persistence (groups are correctly saved to and loaded from files)
- Cross-group operations (devices in multiple groups)
- Group renaming (delete and recreate process)
- Special character handling in group names
- Directory creation (when missing)

These tests simulate real-world scenarios where multiple operations interact.

### CLI Tests (`test_grouping_cli.sh`)

CLI tests ensure that the command-line interface correctly interacts with the underlying system. The tests:

- Create groups via CLI commands
- Verify that group files are created
- Add devices to groups
- Update group properties
- Remove devices from groups
- Delete groups
- Verify file changes after each operation

This provides confidence that the CLI commands properly manipulate the group files.

## Running Tests

See the [tests/README.md](../tests/README.md) file for detailed instructions on running the tests.

## Continuous Integration

For future development, we recommend implementing a CI/CD pipeline that:

1. Runs all tests on each commit
2. Verifies code quality and style
3. Checks test coverage
4. Builds the project
5. Publishes releases for successful builds

## Manual Testing

In addition to automated tests, manual testing should be performed for:

1. User experience evaluation
2. Complex scenarios that are difficult to automate
3. Performance testing with large numbers of devices and groups

## Testing the File-Per-Group Approach

The file-per-group approach is specifically tested through:

1. Verifying that individual YAML files are created/updated/deleted correctly
2. Checking that files contain the correct content after operations
3. Ensuring that orphaned files (e.g., from deleted groups) are properly cleaned up
4. Validating that the system can handle edge cases like special characters in group names
5. Confirming that a restart of the application correctly loads all groups from their individual files

This comprehensive testing approach ensures that the file-per-group functionality is robust and reliable.

## Running All Tests

A convenient script has been provided to run all the test suites:

```bash
./run_tests.sh
```

This script will:
1. Run all the unit and integration tests
2. Run the pytest-based CLI tests
3. Run the shell script-based CLI tests
4. Report a summary of test results

## Conclusion

The testing strategy for Shelly Bulk Control follows best practices for Python testing:

1. **Test Isolation**: All tests use temporary directories to avoid affecting real data
2. **Comprehensive Coverage**: Tests cover unit functionality, integration, CLI, and edge cases
3. **Well-Structured Tests**: Clear organization between unit, integration, and CLI tests
4. **Automated Verification**: Tests automatically verify file changes and group state
5. **Multiple Testing Frameworks**: Using both unittest and pytest for different testing needs

By following this testing strategy, we ensure that the file-per-group approach works correctly and reliably, providing a solid foundation for the Shelly Bulk Control application. 