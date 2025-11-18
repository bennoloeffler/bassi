#!/bin/bash
#
# Test Runner - Run bassi test suites in correct order
#
# Usage:
#   ./run-tests.sh            # Run all test suites
#   ./run-tests.sh unit       # Run only unit tests
#   ./run-tests.sh integration  # Run only integration tests
#   ./run-tests.sh e2e        # Run only E2E tests
#

set -e  # Exit on first error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test type selection
TEST_TYPE="${1:-all}"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Bassi Test Runner                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

run_unit_tests() {
    echo -e "${YELLOW}━━━ Running Unit Tests ━━━${NC}"
    echo "Location: bassi/core_v3/tests/unit/"
    echo "Parallel: Yes (-n auto)"
    echo ""
    uv run pytest bassi/core_v3/tests/unit/ -n auto "$@"
    echo -e "${GREEN}✓ Unit tests passed${NC}\n"
}

run_integration_tests() {
    echo -e "${YELLOW}━━━ Running Integration Tests ━━━${NC}"
    echo "Location: bassi/core_v3/tests/integration/"
    echo "Parallel: Yes (-n auto)"
    echo "Note: E2E tests are in separate e2e/ folder"
    echo ""
    uv run pytest bassi/core_v3/tests/integration/ -n auto "$@"
    echo -e "${GREEN}✓ Integration tests passed${NC}\n"
}

run_e2e_tests() {
    echo -e "${YELLOW}━━━ Running E2E Tests (Playwright) ━━━${NC}"
    echo "Location: bassi/core_v3/tests/e2e/"
    echo "Parallel: No (serial execution)"
    echo "Note: E2E tests use shared live_server fixture on port 18765"
    echo ""
    uv run pytest bassi/core_v3/tests/e2e/ "$@"
    echo -e "${GREEN}✓ E2E tests passed${NC}\n"
}

# Main execution
case "$TEST_TYPE" in
    unit)
        run_unit_tests "${@:2}"
        ;;
    integration)
        run_integration_tests "${@:2}"
        ;;
    e2e)
        run_e2e_tests "${@:2}"
        ;;
    all)
        echo -e "${BLUE}Running all test suites (3 separate processes)${NC}\n"
        run_unit_tests "${@:2}"
        run_integration_tests "${@:2}"
        run_e2e_tests "${@:2}"
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ✓ ALL TESTS PASSED                  ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
        ;;
    *)
        echo -e "${RED}Error: Unknown test type '${TEST_TYPE}'${NC}"
        echo ""
        echo "Usage:"
        echo "  ./run-tests.sh              # Run all test suites"
        echo "  ./run-tests.sh unit         # Run only unit tests"
        echo "  ./run-tests.sh integration  # Run only integration tests"
        echo "  ./run-tests.sh e2e          # Run only E2E tests"
        echo ""
        echo "Additional pytest args can be passed after test type:"
        echo "  ./run-tests.sh unit -v      # Run unit tests with verbose output"
        exit 1
        ;;
esac
