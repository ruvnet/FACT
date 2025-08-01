#!/usr/bin/env node

/**
 * FACT MCP Server Entry Point
 */

// Add source map support for better error traces
require('source-map-support/register');

// Force MCP mode
process.argv.push('--mcp');

// Import and run the CLI
require('../lib/index.js');