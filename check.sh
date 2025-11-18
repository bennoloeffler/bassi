#!/bin/bash
# Quality assurance pipeline for bassi
# Intelligently handles parallel execution issues with E2E tests
# Shows all quality check errors but only fails on pytest failures

# Determine test mode from argument
MODE="${1:-fast}"

# Track quality check failures (but don't exit - they're hints)
QUALITY_ISSUES=0

# Clean up any leftover test servers from previous runs
cleanup_servers() {
    if lsof -ti:8765 >/dev/null 2>&1; then
        echo "⚠️  Cleaning up leftover test server on port 8765..."
        kill -9 $(lsof -ti:8765) 2>/dev/null || true
        sleep 0.5
    fi
}

# Show usage hint
show_usage() {
    echo "============================================="
    echo "Quality Assurance Pipeline"
    echo "============================================="
    echo ""
    echo "Usage:"
    echo "  ./check.sh                    # Fast mode (skip E2E tests) ~30s"
    echo "  ./check.sh fast               # Same as default"
    echo "  ./check.sh e2e                # E2E tests only ~2min"
    echo "  ./check.sh all                # Everything (unit + E2E) ~3min"
    echo "  ./check.sh cov                # Unit tests with coverage report"
    echo "  ./check.sh cov_all            # ALL tests with TOTAL coverage ~3min"
    echo ""
    echo "Marker-based filtering (pytest -m):"
    echo "  ./check.sh \"not integration\"           # Skip integration tests"
    echo "  ./check.sh \"not integration and not e2e\" # Unit tests only"
    echo "  ./check.sh \"integration\"                # Integration tests only"
    echo "  ./check.sh \"e2e or integration\"        # All slow tests"
    echo ""
    echo "Running mode: ${MODE}"
    echo "============================================="
    echo ""
}

# Run code quality checks (show errors but don't exit - they're hints)
run_quality_checks() {
    echo "1. Code Formatting (black)..."
    if ! uv run black .; then
        echo "⚠️  Black formatting found issues (not failing build)"
        QUALITY_ISSUES=$((QUALITY_ISSUES + 1))
    fi

    echo ""
    echo "2. Linting (ruff)..."
    if ! uv run ruff check --fix .; then
        echo "⚠️  Ruff found linting issues (not failing build)"
        QUALITY_ISSUES=$((QUALITY_ISSUES + 1))
    fi

    echo ""
    echo "3. Type Checking (mypy)..."
    if ! uv run mypy bassi/; then
        echo "⚠️  Mypy found type issues (not failing build)"
        QUALITY_ISSUES=$((QUALITY_ISSUES + 1))
    fi
}

# Run unit tests (fast, parallel) - FAIL on test failures
run_unit_tests() {
    echo ""
    echo "4. Running Unit Tests (parallel, ~20s)..."
    echo "   • V1 tests: tests/"
    echo "   • V3 tests: bassi/core_v3/tests/"
    echo "   • Parallel workers: auto"
    echo "   • Skipping: E2E tests (marked with @pytest.mark.e2e)"
    echo ""

    cleanup_servers
    if ! uv run pytest -n auto -m "not e2e" --tb=short; then
        echo ""
        echo "❌ Unit tests FAILED"
        exit 1
    fi
}

# Run E2E tests (slow, sequential) - FAIL on test failures
run_e2e_tests() {
    echo ""
    echo "5. Running E2E Tests (sequential, ~2min)..."
    echo "   • Playwright browser tests"
    echo "   • Chromium, Firefox, WebKit"
    echo "   • Sequential execution (no -n flag)"
    echo "   ⚠️  This is slow - grab coffee!"
    echo ""

    cleanup_servers
    if ! uv run pytest -m e2e --tb=short; then
        echo ""
        echo "❌ E2E tests FAILED"
        exit 1
    fi
}

# Run all tests (parallel unit + sequential E2E) - FAIL on test failures
run_all_tests() {
    echo ""
    echo "4. Running Unit Tests (parallel, ~20s)..."
    echo "   • Skipping: E2E tests"
    echo ""

    cleanup_servers
    if ! uv run pytest -n auto -m "not e2e" --tb=short; then
        echo ""
        echo "❌ Unit tests FAILED"
        exit 1
    fi

    echo ""
    echo "5. Running E2E Tests (sequential, ~2min)..."
    echo ""

    cleanup_servers
    if ! uv run pytest -m e2e --tb=short; then
        echo ""
        echo "❌ E2E tests FAILED"
        exit 1
    fi
}

# Run tests with custom marker filter - FAIL on test failures
run_marker_filter() {
    local marker="$1"

    echo ""
    echo "4. Running Tests with Marker Filter: -m \"${marker}\""
    echo "   • Marker expression: ${marker}"

    # Determine if we can parallelize (no E2E tests)
    if [[ "$marker" == *"not e2e"* ]]; then
        echo "   • Parallel execution: YES (E2E excluded)"
        echo ""
        cleanup_servers
        if ! uv run pytest -n auto -m "${marker}" --tb=short; then
            echo ""
            echo "❌ Tests FAILED (marker: ${marker})"
            exit 1
        fi
    else
        echo "   • Parallel execution: NO (E2E tests may be included)"
        echo "   ⚠️  This may be slow if E2E tests are included"
        echo ""
        cleanup_servers
        if ! uv run pytest -m "${marker}" --tb=short; then
            echo ""
            echo "❌ Tests FAILED (marker: ${marker})"
            exit 1
        fi
    fi
}

# Run coverage-enabled unit tests
run_unit_coverage() {
    echo ""
    echo "4. Running unit tests with coverage..."
    echo "   • Scope: pytest -m \"not e2e and not integration\""
    echo "   • Tooling: pytest-cov (tracks ALL source files)"
    echo "   • Config: .coveragerc (excludes tests, includes untested files)"
    echo ""

    cleanup_servers
    rm -f .coverage .coverage.* 2>/dev/null || true

    if ! uv run pytest -n auto -m "not e2e and not integration" --cov=bassi --cov-branch --cov-report=term-missing --tb=short; then
        echo ""
        echo "❌ Coverage run FAILED"
        exit 1
    fi
}

# Run coverage-enabled ALL tests (unit + E2E)
run_all_coverage() {
    echo ""
    echo "4. Running ALL tests with coverage (unit + integration + E2E, ~3min)..."
    echo "   • Scope: pytest (all tests including E2E and integration)"
    echo "   • Tooling: pytest-cov (tracks ALL source files)"
    echo "   • Config: .coveragerc (excludes tests, includes untested files)"
    echo "   • Parallel unit tests + sequential integration + sequential E2E"
    echo "   ⚠️  This is slow - grab coffee!"
    echo ""

    cleanup_servers
    rm -f .coverage .coverage.* 2>/dev/null || true

    # Run unit tests in parallel with coverage (pytest-cov handles parallel properly)
    echo "→ Running unit tests (parallel)..."
    if ! uv run pytest -n auto -m "not e2e and not integration" --cov=bassi --cov-branch --cov-report= --tb=short; then
        echo ""
        echo "❌ Unit tests with coverage FAILED"
        exit 1
    fi

    # Run integration tests sequentially, appending to coverage data
    echo ""
    echo "→ Running integration tests (sequential)..."
    cleanup_servers
    if ! uv run pytest -m integration --cov=bassi --cov-branch --cov-append --cov-report= --tb=short; then
        echo ""
        echo "❌ Integration tests with coverage FAILED"
        exit 1
    fi

    # Run E2E tests sequentially, appending to coverage data
    echo ""
    echo "→ Running E2E tests (sequential)..."
    cleanup_servers
    if ! uv run pytest -m e2e --cov=bassi --cov-branch --cov-append --cov-report= --tb=short; then
        echo ""
        echo "❌ E2E tests with coverage FAILED"
        exit 1
    fi

    echo ""
    echo "📊 TOTAL Coverage Report (All Tests):"
    echo "   • Including ALL source files (even untested ones)"
    echo ""
    uv run coverage report -m
}

# Show success summary
show_success() {
    echo ""
    echo "============================================="

    # Show quality warnings if any
    if [ $QUALITY_ISSUES -gt 0 ]; then
        echo "⚠️  Quality checks had issues (not failing)"
        echo "✅ Tests passed!"
    else
        echo "✅ All checks passed!"
    fi

    echo "============================================="
    echo ""

    # Show quality issue count
    if [ $QUALITY_ISSUES -gt 0 ]; then
        echo "Quality warnings: ${QUALITY_ISSUES} check(s) found issues"
        echo "  (These are hints - fix when convenient)"
        echo ""
    fi

    case "$MODE" in
        all)
            echo "Test Summary (all tests):"
            uv run pytest --collect-only -q 2>/dev/null | tail -3
            ;;
        e2e)
            echo "Test Summary (E2E only):"
            uv run pytest -m e2e --collect-only -q 2>/dev/null | tail -3
            ;;
        fast)
            echo "Test Summary (unit tests only):"
            uv run pytest -m "not e2e" --collect-only -q 2>/dev/null | tail -3
            echo ""
            echo "💡 Tip: Run './check.sh all' to include E2E tests"
            ;;
        cov)
            echo "Coverage Mode: pytest -m \"not e2e\""
            ;;
        cov_all)
            echo "Coverage Mode: ALL tests (unit + E2E)"
            ;;
        *)
            # Custom marker filter
            echo "Test Summary (marker: ${MODE}):"
            uv run pytest -m "${MODE}" --collect-only -q 2>/dev/null | tail -3
            ;;
    esac
    echo ""
}

# Main execution
case "$MODE" in
    fast)
        show_usage
        run_quality_checks
        run_unit_tests
        show_success
        ;;

    e2e)
        show_usage
        echo "⏭️  Skipping code quality checks (use './check.sh all' for full pipeline)"
        echo ""
        run_e2e_tests
        show_success
        ;;

    all)
        show_usage
        run_quality_checks
        run_all_tests
        show_success
        ;;

    cov)
        show_usage
        echo "⏭️  Skipping code quality checks (coverage-only mode)"
        run_unit_coverage
        show_success
        ;;

    cov_all)
        show_usage
        echo "⏭️  Skipping code quality checks (coverage-only mode)"
        run_all_coverage
        show_success
        ;;

    *)
        # Treat as marker filter (e.g., "not integration", "e2e or integration")
        show_usage
        echo "⏭️  Skipping code quality checks (marker filter mode)"
        echo ""
        run_marker_filter "$MODE"
        show_success
        ;;
esac
