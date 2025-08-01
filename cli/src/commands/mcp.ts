/**
 * MCP commands - MCP server management functionality
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import { FactEngine } from '../core/engine';
import { WasmLoader } from '../wasm/loader';
import { McpServer } from '../mcp/server';
import { createLogger } from '../core/logger';

const logger = createLogger('cmd-mcp');

export function initMcpCommands(
  program: Command,
  engine: FactEngine | null,
  wasmLoader: WasmLoader
): void {
  const mcpCmd = program
    .command('mcp')
    .description('MCP server management commands');

  // Start MCP server
  mcpCmd
    .command('start')
    .alias('s')
    .description('Start MCP server')
    .option('-p, --port <port>', 'Server port', '3000')
    .option('-h, --host <host>', 'Server host', 'localhost')
    .option('-d, --daemon', 'Run as daemon')
    .action(async (options) => {
      const spinner = ora('Starting MCP server...').start();
      
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        const server = new McpServer(engine);
        
        // Update configuration
        const { ConfigManager } = require('../core/config-manager');
        const config = new ConfigManager();
        config.updateConfig({
          mcp: {
            port: parseInt(options.port),
            host: options.host,
          }
        });

        await server.start();
        spinner.stop();

        console.log(chalk.green.bold('✅ MCP server started successfully!'));
        console.log(chalk.blue(`🌐 Server running on: ${options.host}:${options.port}`));
        console.log(chalk.blue(`📡 WebSocket endpoint: ws://${options.host}:${options.port}/mcp`));
        
        const serverInfo = server.getServerInfo();
        console.log(chalk.gray(`🔧 Available tools: ${serverInfo.toolsCount}`));

        if (!options.daemon) {
          console.log(chalk.yellow('\n⚠️  Press Ctrl+C to stop the server'));
          
          // Keep the process running
          process.on('SIGINT', async () => {
            console.log(chalk.yellow('\n🛑 Stopping MCP server...'));
            await server.stop();
            console.log(chalk.green('✅ MCP server stopped'));
            process.exit(0);
          });
          
          // Keep alive
          setInterval(() => {}, 1000);
        }

      } catch (error) {
        spinner.stop();
        console.error(chalk.red.bold('❌ Failed to start MCP server:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Server status
  mcpCmd
    .command('status')
    .description('Check MCP server status')
    .action(async () => {
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        const server = new McpServer(engine);
        const info = server.getServerInfo();

        console.log(chalk.blue.bold('📊 MCP Server Status:'));
        console.log();
        console.log(chalk.cyan(`Status: ${info.running ? chalk.green('Running') : chalk.red('Stopped')}`));
        
        if (info.running) {
          console.log(chalk.cyan(`Host: ${info.host}`));
          console.log(chalk.cyan(`Port: ${info.port}`));
          console.log(chalk.cyan(`Tools: ${info.toolsCount}`));
          console.log(chalk.cyan(`Endpoint: ws://${info.host}:${info.port}/mcp`));
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to get server status:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // List tools
  mcpCmd
    .command('tools')
    .alias('t')
    .description('List available MCP tools')
    .option('--format <type>', 'Output format (table, json)', 'table')
    .action(async (options) => {
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        const server = new McpServer(engine);
        // Note: This would require the server to be running to get actual tools
        // For now, we'll show the static tool definitions

        const tools = [
          {
            name: 'process_template',
            description: 'Process a cognitive template with given context'
          },
          {
            name: 'list_templates',
            description: 'List available cognitive templates'
          },
          {
            name: 'analyze_context',
            description: 'Analyze context and suggest appropriate templates'
          },
          {
            name: 'optimize_performance',
            description: 'Optimize FACT performance (cache, memory, processing)'
          },
          {
            name: 'create_template',
            description: 'Create a new cognitive template'
          },
          {
            name: 'get_metrics',
            description: 'Get performance metrics and statistics'
          }
        ];

        console.log(chalk.blue.bold(`🔧 Available MCP Tools (${tools.length}):`));
        console.log();

        if (options.format === 'json') {
          console.log(JSON.stringify(tools, null, 2));
        } else {
          tools.forEach((tool, index) => {
            console.log(chalk.cyan(`${index + 1}. ${tool.name}`));
            console.log(chalk.gray(`   ${tool.description}`));
            console.log();
          });
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to list tools:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Test connection
  mcpCmd
    .command('test')
    .description('Test MCP server connection')
    .option('-u, --url <url>', 'Server URL', 'ws://localhost:3000/mcp')
    .action(async (options) => {
      const spinner = ora('Testing MCP connection...').start();
      
      try {
        const WebSocket = require('ws');
        
        const ws = new WebSocket(options.url);
        
        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Connection timeout'));
          }, 5000);

          ws.on('open', () => {
            clearTimeout(timeout);
            
            // Send a test message
            ws.send(JSON.stringify({
              jsonrpc: '2.0',
              method: 'ping',
              id: 1
            }));
          });

          ws.on('message', (data: Buffer) => {
            const message = JSON.parse(data.toString());
            console.log('Received:', message);
            ws.close();
            resolve();
          });

          ws.on('error', (error: Error) => {
            clearTimeout(timeout);
            reject(error);
          });
        });

        spinner.stop();
        console.log(chalk.green.bold('✅ MCP server connection test passed!'));
        console.log(chalk.blue(`Connected to: ${options.url}`));

      } catch (error) {
        spinner.stop();
        console.error(chalk.red.bold('❌ MCP connection test failed:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        
        console.log(chalk.yellow('\n💡 Suggestions:'));
        console.log(chalk.yellow('   • Make sure the MCP server is running: fact mcp start'));
        console.log(chalk.yellow('   • Check the server URL and port'));
        console.log(chalk.yellow('   • Verify firewall settings'));
        
        process.exit(1);
      }
    });
}