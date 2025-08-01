#!/usr/bin/env node

/**
 * FACT CLI - Framework for Autonomous Cognitive Templates
 * High-performance CLI with WASM integration
 */

import { program } from 'commander';
import chalk from 'chalk';
import updateNotifier from 'update-notifier';
import { createLogger } from './core/logger';
import { WasmLoader } from './wasm/loader';
import { FactEngine } from './core/engine';
import { McpServer } from './mcp/server';
import { initializeCommands } from './commands';
import { ErrorHandler } from './core/error-handler';
import { ConfigManager } from './core/config-manager';

const pkg = require('../package.json');
const logger = createLogger('cli');

// Check for updates
const notifier = updateNotifier({ pkg });
notifier.notify();

class FactCli {
  private wasmLoader: WasmLoader;
  private engine: FactEngine | null = null;
  private mcpServer: McpServer | null = null;
  private errorHandler: ErrorHandler;
  private configManager: ConfigManager;

  constructor() {
    this.wasmLoader = new WasmLoader();
    this.errorHandler = new ErrorHandler();
    this.configManager = new ConfigManager();
    
    // Set up global error handling
    this.setupErrorHandling();
  }

  private setupErrorHandling(): void {
    process.on('uncaughtException', (error) => {
      this.errorHandler.handleError(error, 'uncaughtException');
      process.exit(1);
    });

    process.on('unhandledRejection', (reason, promise) => {
      this.errorHandler.handleError(
        new Error(`Unhandled Rejection at: ${promise}, reason: ${reason}`),
        'unhandledRejection'
      );
      process.exit(1);
    });
  }

  async initialize(): Promise<void> {
    try {
      console.log(chalk.blue.bold('🚀 Initializing FACT CLI...'));
      
      // Load WASM module
      console.log(chalk.gray('   Loading WASM core...'));
      await this.wasmLoader.initialize();
      
      // Initialize engine with WASM
      console.log(chalk.gray('   Initializing cognitive engine...'));
      this.engine = new FactEngine(this.wasmLoader.getWasm());
      
      // Initialize MCP server if needed
      if (process.argv.includes('--mcp') || process.argv.includes('mcp')) {
        console.log(chalk.gray('   Starting MCP server...'));
        this.mcpServer = new McpServer(this.engine);
        await this.mcpServer.start();
      }
      
      console.log(chalk.green.bold('✅ FACT CLI initialized successfully!'));
      
    } catch (error) {
      console.error(chalk.red.bold('❌ Failed to initialize FACT CLI:'));
      console.error(chalk.red(error instanceof Error ? error.message : String(error)));
      throw error;
    }
  }

  setupCommands(): void {
    program
      .name('fact')
      .description('FACT - Framework for Autonomous Cognitive Templates')
      .version(pkg.version)
      .option('-v, --verbose', 'Enable verbose logging')
      .option('-c, --config <path>', 'Path to configuration file')
      .option('--mcp', 'Start MCP server mode')
      .hook('preAction', async (thisCommand) => {
        const options = thisCommand.opts();
        if (options.verbose) {
          process.env.DEBUG = 'fact:*';
        }
        if (options.config) {
          await this.configManager.loadConfig(options.config);
        }
      });

    // Initialize all commands
    initializeCommands(program, this.engine, this.wasmLoader);

    // Handle unknown commands
    program.on('command:*', (operands) => {
      console.error(chalk.red(`Unknown command: ${operands[0]}`));
      console.log(chalk.yellow('Run "fact --help" to see available commands.'));
      process.exit(1);
    });
  }

  async run(): Promise<void> {
    try {
      await this.initialize();
      this.setupCommands();
      
      // Parse arguments
      await program.parseAsync(process.argv);
      
    } catch (error) {
      this.errorHandler.handleError(error as Error, 'cli-run');
      process.exit(1);
    }
  }

  async shutdown(): Promise<void> {
    console.log(chalk.yellow('🔄 Shutting down FACT CLI...'));
    
    if (this.mcpServer) {
      await this.mcpServer.stop();
    }
    
    if (this.engine) {
      await this.engine.shutdown();
    }
    
    console.log(chalk.green('✅ FACT CLI shutdown complete'));
  }
}

// Main execution
if (require.main === module) {
  const cli = new FactCli();
  
  // Graceful shutdown handlers
  process.on('SIGINT', async () => {
    console.log(chalk.yellow('\n🛑 Received SIGINT, shutting down gracefully...'));
    await cli.shutdown();
    process.exit(0);
  });
  
  process.on('SIGTERM', async () => {
    console.log(chalk.yellow('\n🛑 Received SIGTERM, shutting down gracefully...'));
    await cli.shutdown();
    process.exit(0);
  });
  
  // Run the CLI
  cli.run().catch((error) => {
    console.error(chalk.red.bold('❌ Fatal error:'), error);
    process.exit(1);
  });
}

export { FactCli };
export * from './core';
export * from './wasm';
export * from './mcp';
export * from './commands';