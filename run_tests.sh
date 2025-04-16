#!/bin/bash
# Script to run all tests for the Shelly Bulk Control system

set -e  # Exit on error

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}  Running Shelly Bulk Control Tests    ${NC}"
echo -e "${BLUE}=======================================${NC}"

# Function to run tests and report status
run_test() {
    TEST_CMD=$1
    TEST_NAME=$2
    
    echo -e "\n${YELLOW}Running $TEST_NAME...${NC}"
    
    if $TEST_CMD; then
        echo -e "${GREEN}✓ $TEST_NAME passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $TEST_NAME failed${NC}"
        return 1
    fi
}

# Track overall success
SUCCESS=true

# Run unittest tests
if ! run_test "python -m unittest discover -s tests" "Unit and Integration Tests (unittest)"; then
    SUCCESS=false
fi

# Run all pytest tests
if ! run_test "pytest tests -v" "All Tests (pytest)"; then
    SUCCESS=false
fi

# Print summary
echo -e "\n${BLUE}=======================================${NC}"
if $SUCCESS; then
    echo -e "${GREEN}All test suites passed!${NC}"
    exit 0
else
    echo -e "${RED}One or more test suites failed!${NC}"
    exit 1
fi 