#!/bin/bash

# FACT WASM Test Runner
# Comprehensive test automation script for FACT WASM MCP integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WASM_DIR="$(dirname "$SCRIPT_DIR")"
TEST_RESULTS_DIR="$WASM_DIR/test-results"
LOG_FILE="$TEST_RESULTS_DIR/test-runner.log"

# Test categories
CATEGORIES=("unit" "integration" "performance" "mcp" "e2e" "security")

# Create results directory
mkdir -p "$TEST_RESULTS_DIR"

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "HEADER")
            echo -e "${BLUE}🚀 $message${NC}"
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    print_status "HEADER" "Checking prerequisites..."
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_status "ERROR" "Node.js is not installed"
        exit 1
    fi
    
    local node_version=$(node --version | cut -d'v' -f2)
    print_status "SUCCESS" "Node.js version: $node_version"
    
    # Check Rust/Cargo
    if ! command -v cargo &> /dev/null; then
        print_status "ERROR" "Cargo is not installed"
        exit 1
    fi
    
    local cargo_version=$(cargo --version | cut -d' ' -f2)
    print_status "SUCCESS" "Cargo version: $cargo_version"
    
    # Check wasm-pack
    if ! command -v wasm-pack &> /dev/null; then
        print_status "WARNING" "wasm-pack not found, installing..."
        curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh
    fi
    
    print_status "SUCCESS" "Prerequisites check completed"
}

# Build WASM module
build_wasm() {
    print_status "HEADER" "Building WASM module..."
    
    cd "$WASM_DIR"
    
    if [ ! -f "Cargo.toml" ]; then
        print_status "ERROR" "Cargo.toml not found in $WASM_DIR"
        exit 1
    fi
    
    # Clean previous build
    rm -rf pkg/ target/
    
    # Build WASM module
    if ./build-wasm.sh > "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "WASM module built successfully"
    else
        print_status "ERROR" "WASM build failed. Check $LOG_FILE for details"
        tail -20 "$LOG_FILE"
        exit 1
    fi
    
    # Install Node.js dependencies
    if [ -f "package.json" ]; then
        print_status "INFO" "Installing Node.js dependencies..."
        npm install >> "$LOG_FILE" 2>&1
        print_status "SUCCESS" "Dependencies installed"
    fi
}

# Run unit tests
run_unit_tests() {
    print_status "HEADER" "Running unit tests..."
    
    cd "$WASM_DIR"
    
    # Rust unit tests
    print_status "INFO" "Running Rust unit tests..."
    if cargo test --lib >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "Rust unit tests passed"
    else
        print_status "ERROR" "Rust unit tests failed"
        return 1
    fi
    
    # WASM unit tests
    print_status "INFO" "Running WASM unit tests..."
    if wasm-pack test --node >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "WASM unit tests passed"
    else
        print_status "ERROR" "WASM unit tests failed"
        return 1
    fi
    
    return 0
}

# Run integration tests
run_integration_tests() {
    print_status "HEADER" "Running integration tests..."
    
    cd "$WASM_DIR"
    
    # Rust integration tests
    print_status "INFO" "Running Rust integration tests..."
    if cargo test --test '*' >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "Rust integration tests passed"
    else
        print_status "WARNING" "Some Rust integration tests failed"
        return 1
    fi
    
    return 0
}

# Run performance benchmarks
run_performance_tests() {
    print_status "HEADER" "Running performance benchmarks..."
    
    cd "$WASM_DIR"
    
    # Rust benchmarks
    print_status "INFO" "Running Rust benchmarks..."
    if cargo bench >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "Rust benchmarks completed"
    else
        print_status "WARNING" "Rust benchmarks had issues"
    fi
    
    # Node.js performance tests
    print_status "INFO" "Running Node.js performance benchmarks..."
    if node scripts/benchmark-runner.js >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "Performance benchmarks completed"
    else
        print_status "WARNING" "Performance benchmarks had issues"
        return 1
    fi
    
    return 0
}

# Run MCP server tests
run_mcp_tests() {
    print_status "HEADER" "Running MCP server tests..."
    
    cd "$WASM_DIR"
    
    # Basic MCP tests
    print_status "INFO" "Running basic MCP tests..."
    if node tests/mcp_server_tests.js >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "Basic MCP tests passed"
    else
        print_status "ERROR" "Basic MCP tests failed"
        return 1
    fi
    
    # Comprehensive MCP tests
    print_status "INFO" "Running comprehensive MCP tests..."
    if node scripts/test-mcp-comprehensive.js >> "$LOG_FILE" 2>&1; then
        print_status "SUCCESS" "Comprehensive MCP tests passed"
    else
        print_status "WARNING" "Some comprehensive MCP tests failed"
        return 1
    fi
    
    return 0
}

# Run end-to-end tests
run_e2e_tests() {
    print_status "HEADER" "Running end-to-end tests..."
    
    cd "$WASM_DIR"
    
    # Start MCP server in background
    print_status "INFO" "Starting MCP server for E2E tests..."
    node src/mcp-server.js > "$TEST_RESULTS_DIR/mcp-server-e2e.log" 2>&1 &
    local server_pid=$!
    
    # Wait for server to start
    sleep 3
    
    # Run E2E tests
    print_status "INFO" "Running E2E test scenarios..."
    local e2e_passed=true
    
    # Test Claude Code integration (if available)
    if command -v claude &> /dev/null; then
        print_status "INFO" "Testing Claude Code MCP integration..."
        if claude mcp list | grep -q "fact-mcp"; then
            print_status "SUCCESS" "FACT MCP server is registered with Claude Code"
        else
            print_status "WARNING" "FACT MCP server not registered with Claude Code"
            e2e_passed=false
        fi
    else
        print_status "WARNING" "Claude Code not available for E2E testing"
    fi
    
    # Kill MCP server
    kill $server_pid 2>/dev/null || true
    wait $server_pid 2>/dev/null || true
    
    if $e2e_passed; then
        print_status "SUCCESS" "E2E tests completed"
        return 0
    else
        print_status "WARNING" "Some E2E tests failed"
        return 1
    fi
}

# Run security tests
run_security_tests() {
    print_status "HEADER" "Running security tests..."
    
    cd "$WASM_DIR"
    
    # Basic security checks
    print_status "INFO" "Running security checks..."
    
    # Check for hardcoded secrets
    if grep -r "password\|secret\|key" src/ --include="*.rs" --include="*.js" | grep -v "test" | grep -v "example"; then
        print_status "WARNING" "Potential hardcoded secrets found"
    else
        print_status "SUCCESS" "No hardcoded secrets detected"
    fi
    
    # Check for unsafe Rust code
    if grep -r "unsafe" src/ --include="*.rs"; then
        print_status "WARNING" "Unsafe Rust code detected"
    else
        print_status "SUCCESS" "No unsafe Rust code detected"
    fi
    
    print_status "SUCCESS" "Security tests completed"
    return 0
}

# Generate test report
generate_report() {
    print_status "HEADER" "Generating test report..."
    
    local report_file="$TEST_RESULTS_DIR/test-report-$(date +%Y%m%d-%H%M%S).html"
    
    cat > "$report_file" << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FACT WASM Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .pass { color: green; }
        .fail { color: red; }
        .warn { color: orange; }
        pre { background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 FACT WASM Test Report</h1>
        <p><strong>Generated:</strong> $(date)</p>
        <p><strong>System:</strong> $(uname -a)</p>
        <p><strong>Node.js:</strong> $(node --version)</p>
        <p><strong>Cargo:</strong> $(cargo --version)</p>
    </div>
    
    <div class="section">
        <h2>📊 Test Summary</h2>
        <ul>
            <li>Unit Tests: <span class="$([ ${test_results[unit]} -eq 0 ] && echo 'pass' || echo 'fail')">$([ ${test_results[unit]} -eq 0 ] && echo 'PASS' || echo 'FAIL')</span></li>
            <li>Integration Tests: <span class="$([ ${test_results[integration]} -eq 0 ] && echo 'pass' || echo 'warn')">$([ ${test_results[integration]} -eq 0 ] && echo 'PASS' || echo 'PARTIAL')</span></li>
            <li>Performance Tests: <span class="$([ ${test_results[performance]} -eq 0 ] && echo 'pass' || echo 'warn')">$([ ${test_results[performance]} -eq 0 ] && echo 'PASS' || echo 'PARTIAL')</span></li>
            <li>MCP Tests: <span class="$([ ${test_results[mcp]} -eq 0 ] && echo 'pass' || echo 'warn')">$([ ${test_results[mcp]} -eq 0 ] && echo 'PASS' || echo 'PARTIAL')</span></li>
            <li>E2E Tests: <span class="$([ ${test_results[e2e]} -eq 0 ] && echo 'pass' || echo 'warn')">$([ ${test_results[e2e]} -eq 0 ] && echo 'PASS' || echo 'PARTIAL')</span></li>
            <li>Security Tests: <span class="$([ ${test_results[security]} -eq 0 ] && echo 'pass' || echo 'warn')">$([ ${test_results[security]} -eq 0 ] && echo 'PASS' || echo 'PARTIAL')</span></li>
        </ul>
    </div>
    
    <div class="section">
        <h2>📝 Test Log</h2>
        <pre>$(tail -100 "$LOG_FILE")</pre>
    </div>
    
    <div class="section">
        <h2>📁 Generated Files</h2>
        <ul>
            $(find "$TEST_RESULTS_DIR" -name "*.json" -o -name "*.log" | sed 's/.*/            <li>&<\/li>/')
        </ul>
    </div>
</body>
</html>
EOF

    print_status "SUCCESS" "Test report generated: $report_file"
}

# Main execution
main() {
    print_status "HEADER" "FACT WASM Test Runner Starting..."
    
    # Initialize test results
    declare -A test_results
    
    # Parse command line arguments
    local categories_to_run=()
    local build_required=true
    local generate_report_flag=true
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --categories)
                IFS=',' read -ra categories_to_run <<< "$2"
                shift 2
                ;;
            --no-build)
                build_required=false
                shift
                ;;
            --no-report)
                generate_report_flag=false
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --categories CATS    Run specific test categories (comma-separated)"
                echo "                       Available: ${CATEGORIES[*]}"
                echo "  --no-build          Skip WASM build step"
                echo "  --no-report         Skip report generation"
                echo "  --help              Show this help message"
                exit 0
                ;;
            *)
                print_status "ERROR" "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Default to all categories if none specified
    if [ ${#categories_to_run[@]} -eq 0 ]; then
        categories_to_run=("${CATEGORIES[@]}")
    fi
    
    print_status "INFO" "Test categories: ${categories_to_run[*]}"
    
    # Check prerequisites
    check_prerequisites
    
    # Build WASM module if required
    if $build_required; then
        build_wasm
    fi
    
    # Run tests based on categories
    local overall_success=true
    
    for category in "${categories_to_run[@]}"; do
        case $category in
            "unit")
                run_unit_tests
                test_results[unit]=$?
                ;;
            "integration")
                run_integration_tests
                test_results[integration]=$?
                ;;
            "performance")
                run_performance_tests
                test_results[performance]=$?
                ;;
            "mcp")
                run_mcp_tests
                test_results[mcp]=$?
                ;;
            "e2e")
                run_e2e_tests
                test_results[e2e]=$?
                ;;
            "security")
                run_security_tests
                test_results[security]=$?
                ;;
            *)
                print_status "WARNING" "Unknown test category: $category"
                ;;
        esac
        
        if [ ${test_results[$category]:-1} -ne 0 ]; then
            overall_success=false
        fi
    done
    
    # Generate report if requested
    if $generate_report_flag; then
        generate_report
    fi
    
    # Final summary
    print_status "HEADER" "Test Run Summary"
    local passed=0
    local total=0
    
    for category in "${categories_to_run[@]}"; do
        if [ -v test_results[$category] ]; then
            total=$((total + 1))
            if [ ${test_results[$category]} -eq 0 ]; then
                passed=$((passed + 1))
                print_status "SUCCESS" "$category tests: PASSED"
            else
                print_status "WARNING" "$category tests: ISSUES DETECTED"
            fi
        fi
    done
    
    print_status "INFO" "Overall: $passed/$total test categories passed"
    
    if $overall_success; then
        print_status "SUCCESS" "All requested tests completed successfully!"
        exit 0
    else
        print_status "WARNING" "Some tests had issues. Check logs for details."
        exit 1
    fi
}

# Run main function with all arguments
main "$@"