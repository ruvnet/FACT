#!/usr/bin/env node
/**
 * FACT MCP Server CLI
 * Command-line interface for starting the FACT MCP server
 */

import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Start the MCP server
const serverPath = path.join(__dirname, 'index.js');

console.error('Starting FACT MCP Server...');
console.error('Use this server with: claude mcp add fact-mcp npx @fact/mcp-server');

const server = spawn('node', [serverPath], {
  stdio: 'inherit',
  env: {
    ...process.env,
    NODE_ENV: process.env.NODE_ENV || 'production',
  },
});

server.on('error', (err) => {
  console.error('Failed to start FACT MCP Server:', err);
  process.exit(1);
});

server.on('exit', (code) => {
  process.exit(code || 0);
});