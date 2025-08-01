#!/bin/bash

# FACT MCP Server Installation Script
# Installs and configures the FACT MCP server for Claude Code

set -e

echo "🚀 FACT MCP Server Installation"
echo "================================="

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js >= 16.0.0"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2)
REQUIRED_VERSION="16.0.0"

if ! npx semver -r ">=$REQUIRED_VERSION" "$NODE_VERSION" &> /dev/null; then
    echo "❌ Node.js version $NODE_VERSION is too old. Please upgrade to >= $REQUIRED_VERSION"
    exit 1
fi

echo "✅ Node.js version: $NODE_VERSION"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WASM_DIR="$(dirname "$SCRIPT_DIR")"

# Navigate to the WASM directory
cd "$WASM_DIR"

echo "📁 Working directory: $WASM_DIR"

# Build WASM module if needed
if [ ! -d "pkg" ] || [ ! -f "pkg/fact_wasm_core.js" ]; then
    echo "🔧 Building WASM module..."
    npm run build:wasm
else
    echo "✅ WASM module already built"
fi

# Make MCP server executable
echo "🔧 Making MCP server executable..."
chmod +x src/mcp-server.js

# Test the MCP server
echo "🧪 Testing MCP server..."
if timeout 5s node src/mcp-server.js < /dev/null 2>/dev/null; then
    echo "✅ MCP server test passed"
else
    echo "⚠️  MCP server test had issues (this may be normal for stdio transport)"
fi

# Check if Claude Code is available
if command -v claude &> /dev/null; then
    echo "✅ Claude Code found"
    
    # Remove existing server if it exists
    if claude mcp list | grep -q "fact-mcp"; then
        echo "🔄 Removing existing fact-mcp server..."
        claude mcp remove fact-mcp || true
    fi
    
    # Add the MCP server to Claude Code
    echo "📋 Adding FACT MCP server to Claude Code..."
    
    # Get absolute path to the MCP server
    MCP_SERVER_PATH="$(realpath src/mcp-server.js)"
    
    if claude mcp add fact-mcp node "$MCP_SERVER_PATH"; then
        echo "✅ FACT MCP server added successfully!"
        
        # List MCP servers to confirm
        echo ""
        echo "📋 Current MCP servers:"
        claude mcp list
        
        echo ""
        echo "🎉 Installation complete!"
        echo ""
        echo "Available MCP tools in Claude Code:"
        echo "  • process_template    - Process cognitive templates with context"
        echo "  • list_templates      - List available templates"
        echo "  • analyze_context     - Analyze context and suggest templates"
        echo "  • optimize_performance - Optimize cache, memory, or processing"
        echo "  • get_metrics         - Get performance metrics"
        echo "  • create_template     - Create custom templates"
        echo ""
        echo "Available resources:"
        echo "  • template://*        - Template definitions"
        echo "  • metrics://performance - Performance metrics"
        echo "  • system://status     - System status"
        echo ""
        echo "Try using these tools in Claude Code to process cognitive templates!"
        
    else
        echo "❌ Failed to add MCP server to Claude Code"
        exit 1
    fi
    
else
    echo "⚠️  Claude Code not found. Please install Claude Code first:"
    echo "   npm install -g @anthropic/claude-code"
    echo ""
    echo "Then run this script again, or manually add the server:"
    echo "   claude mcp add fact-mcp node $(realpath src/mcp-server.js)"
fi

echo ""
echo "📖 Documentation:"
echo "   • README-MCP.md - Complete documentation"
echo "   • tests/mcp_server_tests.js - Test suite"
echo ""
echo "🔧 Useful commands:"
echo "   • npm run start:mcp     - Start MCP server manually"
echo "   • npm run dev:mcp       - Start with debugging"
echo "   • npm run test:mcp      - Test server functionality"
echo "   • node tests/mcp_server_tests.js - Run comprehensive tests"