# Integration Test Suite

This directory contains comprehensive integration tests for the FACT WASM CLI and MCP server components.

## Test Structure

### Core Test Categories

- **CLI Tests** (`cli/`) - Command-line interface integration tests
- **MCP Tests** (`mcp/`) - Model Context Protocol server tests  
- **WASM Tests** (`wasm/`) - WebAssembly loading and functionality tests
- **E2E Tests** (`e2e/`) - End-to-end workflow validation
- **Performance Tests** (`performance/`) - Benchmarking and performance validation
- **Utils** (`utils/`) - Test utilities and helpers

### Supporting Components

- **Fixtures** (`fixtures/`) - Test data and configuration files
- **Mocks** (`mocks/`) - Mock implementations for testing
- **Scripts** (`scripts/`) - Automated validation and setup scripts

## Running Tests

### Prerequisites

```bash
# Install test dependencies
cargo install wasm-pack
npm install -g @modelcontextprotocol/inspector
pip install pytest pytest-asyncio

# Build WASM module
cd /workspaces/FACT/wasm
./build-wasm.sh
```

### Test Execution

```bash
# Run all integration tests
npm test

# Run specific test categories
npm run test:cli          # CLI integration tests
npm run test:mcp          # MCP server tests
npm run test:wasm         # WASM functionality tests
npm run test:e2e          # End-to-end tests
npm run test:performance  # Performance benchmarks

# Run with coverage
npm run test:coverage

# Validate complete system
npm run validate:system
```

### Test Categories

#### 1. CLI Integration Tests
- Command execution and exit codes
- Output format validation
- Error handling and recovery
- Configuration loading
- Cache management operations
- Performance benchmarking commands

#### 2. MCP Server Tests
- JSON-RPC protocol compliance
- Tool execution and validation
- Resource access patterns
- Error response handling
- Performance monitoring
- Template processing workflows

#### 3. WASM Loading Tests
- Module initialization and loading
- Memory management validation
- Cross-platform compatibility
- Performance optimization verification
- Error boundary testing
- Security validation

#### 4. End-to-End Tests
- Complete workflow validation
- Multi-component integration
- Real-world usage scenarios
- Data flow verification
- System resilience testing
- Recovery and cleanup

#### 5. Performance Tests
- Throughput benchmarking
- Latency measurement
- Memory usage profiling
- Cache efficiency validation
- Concurrent operation testing
- Resource utilization monitoring

## Test Data Management

### Fixtures
- Sample configuration files
- Test datasets and templates
- Mock API responses
- Expected output patterns

### Mocks
- HTTP server mocks
- Database connection mocks
- File system operation mocks
- Network request mocks

## Validation Scripts

### Health Checks
- System component validation
- Dependency verification
- Configuration validation
- Service availability checks

### Automated Validation
- Pre-commit validation
- CI/CD pipeline integration
- Performance regression detection
- Security vulnerability scanning

## Best Practices

### Test Design
- Isolated test execution
- Deterministic outcomes
- Comprehensive error coverage
- Performance regression detection

### Test Maintenance
- Regular test data updates
- Mock service maintenance
- Documentation synchronization
- Continuous integration updates

## Contributing

When adding new tests:

1. Follow the established directory structure
2. Include comprehensive documentation
3. Add appropriate fixtures and mocks
4. Update validation scripts
5. Ensure CI/CD integration

## Troubleshooting

### Common Issues
- WASM module loading failures
- MCP server connection timeouts
- CLI command execution errors
- Performance test instability

### Debug Mode
```bash
# Enable debug logging
export FACT_DEBUG=1
export RUST_LOG=debug

# Run tests with verbose output
npm run test:debug
```