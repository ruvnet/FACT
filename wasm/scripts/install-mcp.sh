#!/bin/bash
# FACT MCP Server Installation Script for Claude Code
# This script installs the FACT MCP server and configures it for use with Claude Code

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

echo "🚀 FACT MCP Server Installation"
echo "================================"

# Check if Node.js is installed
print_step "Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 16+ first."
    echo "  Visit: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2)
print_status "Node.js version: $NODE_VERSION"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    print_error "npm is not installed. Please install npm first."
    exit 1
fi

NPM_VERSION=$(npm --version)
print_status "npm version: $NPM_VERSION"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
WASM_DIR="$( dirname "$SCRIPT_DIR" )"
MCP_SERVER_PATH="$WASM_DIR/src/mcp-server.js"

print_step "Setting up FACT MCP Server..."
print_status "WASM directory: $WASM_DIR"
print_status "MCP server path: $MCP_SERVER_PATH"

# Verify MCP server exists
if [ ! -f "$MCP_SERVER_PATH" ]; then
    print_error "MCP server not found at: $MCP_SERVER_PATH"
    exit 1
fi

# Make MCP server executable
chmod +x "$MCP_SERVER_PATH"
print_status "Made MCP server executable"

# Install dependencies if package.json exists
if [ -f "$WASM_DIR/package.json" ]; then
    print_step "Installing dependencies..."
    cd "$WASM_DIR"
    npm install
    print_status "Dependencies installed"
fi

# Build WASM if build script exists and pkg directory doesn't exist
if [ -f "$WASM_DIR/build-wasm.sh" ] && [ ! -d "$WASM_DIR/pkg" ]; then
    print_step "Building WASM modules..."
    cd "$WASM_DIR"
    chmod +x build-wasm.sh
    ./build-wasm.sh || {
        print_warning "WASM build failed - server will run in JavaScript fallback mode"
    }
fi

# Test the MCP server
print_step "Testing MCP server..."
cd "$WASM_DIR"

# Create a simple test
TEST_OUTPUT=$(timeout 10s node -e "
const { spawn } = require('child_process');
const server = spawn('node', ['$MCP_SERVER_PATH'], { stdio: ['pipe', 'pipe', 'pipe'] });
let initialized = false;

server.stderr.on('data', (data) => {
    if (data.toString().includes('ready on stdio transport')) {
        initialized = true;
        server.kill('SIGTERM');
    }
});

server.on('close', (code) => {
    console.log(initialized ? 'SUCCESS' : 'FAILED');
    process.exit(initialized ? 0 : 1);
});

setTimeout(() => {
    server.kill('SIGTERM');
    console.log('TIMEOUT');
    process.exit(1);
}, 8000);
" 2>/dev/null) || TEST_OUTPUT="FAILED"

if [ "$TEST_OUTPUT" = "SUCCESS" ]; then
    print_status "✅ MCP server test passed"
else
    print_warning "⚠️ MCP server test failed - but server may still work"
fi

# Provide installation instructions
echo ""
print_step "Installation Complete!"
echo "======================================"

echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Add FACT MCP server to Claude Code:"
echo "   ${GREEN}claude mcp add fact-mcp node \"$MCP_SERVER_PATH\"${NC}"
echo ""
echo "2. Verify the installation:"
echo "   ${GREEN}claude mcp list${NC}"
echo ""
echo "3. Test the server with Claude Code:"
echo "   - Open Claude Code"
echo "   - Try using FACT MCP tools in your conversation"
echo ""
echo "📖 Available Tools:"
echo "   • process_template     - Process cognitive templates"
echo "   • list_templates       - List available templates"
echo "   • analyze_context      - Analyze context and suggest templates"
echo "   • get_metrics          - Get performance metrics"
echo "   • health_check         - Check server health"
echo "   • benchmark_performance - Run performance benchmarks"
echo "   • optimize_performance - Optimize server performance"
echo "   • create_template      - Create custom templates"
echo ""
echo "🔧 Configuration:"
echo "   Server path: $MCP_SERVER_PATH"
echo "   WASM enabled: $([ -d "$WASM_DIR/pkg" ] && echo "Yes" || echo "No (fallback mode)")"
echo "   Transport: stdio"
echo ""
echo "📚 Documentation:"
echo "   README: $WASM_DIR/README-MCP.md"
echo "   Examples: $WASM_DIR/tests/"
echo ""
echo "✅ FACT MCP Server is ready to use!"

# Create a quick test command
cat > "$WASM_DIR/test-mcp.sh" << 'EOF'
#!/bin/bash
# Quick MCP server test
echo "🧪 Testing FACT MCP Server..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
node "$SCRIPT_DIR/test-mcp-standalone.mjs"
EOF

chmod +x "$WASM_DIR/test-mcp.sh"
print_status "Created test script: $WASM_DIR/test-mcp.sh"

echo ""
print_status "🎯 Run '$WASM_DIR/test-mcp.sh' to test the server anytime"