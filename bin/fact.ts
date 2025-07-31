#!/usr/bin/env node

/**
 * FACT CLI - Command Line Interface for Fast Augmented Context Tools
 * 
 * This is the main entry point for the FACT CLI, providing a comprehensive
 * command-line interface for interacting with the FACT system.
 */

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import chalk from 'chalk';
import boxen from 'boxen';
import ora from 'ora';
import updateNotifier from 'update-notifier';
import { readFileSync } from 'fs';

// Local imports
import { FactCLI } from '../lib/cli.js';
import { WasmLoader } from '../lib/wasm-loader.js';
import { PythonBridge } from '../lib/python-bridge.js';
import { InteractivePrompts } from '../lib/interactive.js';
import { validateEnvironment } from '../lib/validator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load package.json for version info - adjust path for build output
const packagePath = join(__dirname, '..', '..', 'package.json');
const packageJson = JSON.parse(readFileSync(packagePath, 'utf8'));

// Check for updates
const notifier = updateNotifier({
  pkg: packageJson,
  updateCheckInterval: 1000 * 60 * 60 * 24 // Check daily
});

if (notifier.update) {
  console.log(boxen(
    `Update available: ${chalk.green(notifier.update.latest)}\n` +
    `Current version: ${chalk.red(notifier.update.current)}\n` +
    `Run ${chalk.cyan('npm install -g fact-cli')} to update`,
    {
      padding: 1,
      margin: 1,
      borderStyle: 'round',
      borderColor: 'yellow'
    }
  ));
}

// ASCII Art Banner
const banner = `
██████   █████   ██████ ████████ 
██      ██   ██ ██         ██    
█████   ███████ ██         ██    
██      ██   ██ ██         ██    
██      ██   ██  ██████    ██    
                                 
Fast Augmented Context Tools
`;

async function main() {
  const cli = new FactCLI();
  const wasmLoader = new WasmLoader();
  const pythonBridge = new PythonBridge();
  const interactive = new InteractivePrompts();

  const argv = await yargs(hideBin(process.argv))
    .scriptName('fact')
    .usage('$0 <command> [options]')
    .version(packageJson.version)
    .alias('version', 'v')
    .help('help')
    .alias('help', 'h')
    
    // Main commands
    .command('init', 'Initialize FACT system', {
      force: {
        type: 'boolean',
        description: 'Force reinitialize even if already initialized',
        default: false
      },
      config: {
        type: 'string',
        description: 'Path to configuration file',
        alias: 'c'
      }
    }, async (args) => {
      await cli.handleInit(args);
    })
    
    .command('query <question>', 'Ask a question to FACT', {
      interactive: {
        type: 'boolean',
        description: 'Use interactive mode',
        alias: 'i',
        default: false
      },
      format: {
        type: 'string',
        description: 'Output format (json, table, plain)',
        choices: ['json', 'table', 'plain'],
        default: 'plain'
      },
      cache: {
        type: 'boolean',
        description: 'Enable caching',
        default: true
      }
    }, async (args) => {
      await cli.handleQuery(args);
    })
    
    .command('interactive', 'Start interactive mode', {
      mode: {
        type: 'string',
        description: 'Interactive mode type',
        choices: ['cli', 'guided', 'wizard'],
        default: 'cli'
      }
    }, async (args) => {
      await cli.handleInteractive(args);
    })
    
    .command('status', 'Show system status', {
      detailed: {
        type: 'boolean',
        description: 'Show detailed status information',
        alias: 'd',
        default: false
      }
    }, async (args) => {
      await cli.handleStatus(args);
    })
    
    .command('benchmark', 'Run performance benchmarks', {
      iterations: {
        type: 'number',
        description: 'Number of benchmark iterations',
        default: 10
      },
      compare: {
        type: 'boolean',
        description: 'Compare with traditional systems',
        default: false
      }
    }, async (args) => {
      await cli.handleBenchmark(args);
    })
    
    .command('tools', 'Manage FACT tools', {}, () => {
      yargs.command('list', 'List available tools', {}, async (args) => {
        await cli.handleToolsList(args);
      })
      .command('info <tool>', 'Get tool information', {}, async (args) => {
        await cli.handleToolInfo(args);
      })
      .command('test <tool>', 'Test a specific tool', {}, async (args) => {
        await cli.handleToolTest(args);
      })
      .demandCommand(1, 'You need to specify a tools subcommand')
      .help();
    })
    
    .command('cache', 'Manage cache system', {}, () => {
      yargs.command('clear', 'Clear cache', {
        all: {
          type: 'boolean',
          description: 'Clear all cache data',
          default: false
        }
      }, async (args) => {
        await cli.handleCacheClear(args);
      })
      .command('stats', 'Show cache statistics', {}, async (args) => {
        await cli.handleCacheStats(args);
      })
      .command('optimize', 'Optimize cache performance', {}, async (args) => {
        await cli.handleCacheOptimize(args);
      })
      .demandCommand(1, 'You need to specify a cache subcommand')
      .help();
    })
    
    .command('wasm', 'WASM module management', {}, () => {
      yargs.command('load', 'Load WASM modules', {
        module: {
          type: 'string',
          description: 'Specific module to load'
        }
      }, async (args) => {
        await cli.handleWasmLoad(args);
      })
      .command('info', 'Show WASM module information', {}, async (args) => {
        await cli.handleWasmInfo(args);
      })
      .demandCommand(1, 'You need to specify a wasm subcommand')
      .help();
    })
    
    .command('doctor', 'Diagnose system health', {
      fix: {
        type: 'boolean',
        description: 'Attempt to fix issues automatically',
        default: false
      }
    }, async (args) => {
      await cli.handleDoctor(args);
    })
    
    .command('config', 'Configuration management', {}, () => {
      yargs.command('show', 'Show current configuration', {}, async (args) => {
        await cli.handleConfigShow(args);
      })
      .command('set <key> <value>', 'Set configuration value', {}, async (args) => {
        await cli.handleConfigSet(args);
      })
      .command('reset', 'Reset to default configuration', {}, async (args) => {
        await cli.handleConfigReset(args);
      })
      .demandCommand(1, 'You need to specify a config subcommand')
      .help();
    })
    
    // Global options
    .option('verbose', {
      type: 'boolean',
      description: 'Enable verbose output',
      alias: 'V',
      global: true
    })
    .option('quiet', {
      type: 'boolean',
      description: 'Suppress non-essential output',
      alias: 'q',
      global: true
    })
    .option('no-color', {
      type: 'boolean',
      description: 'Disable colored output',
      global: true
    })
    
    // Examples
    .example('$0 init', 'Initialize the FACT system')
    .example('$0 query "What is TechCorp\'s revenue?"', 'Ask a question')
    .example('$0 interactive', 'Start interactive mode')
    .example('$0 benchmark --iterations 20', 'Run benchmarks')
    .example('$0 status --detailed', 'Show detailed system status')
    
    .demandCommand(1, 'You need to specify a command')
    .strict()
    .recommendCommands()
    .showHelpOnFail(false, 'Specify --help for available options')
    .wrap(120)
    .parseAsync();

  // Handle global options
  if (argv.noColor) {
    chalk.level = 0;
  }
  
  if (argv.verbose) {
    process.env.FACT_VERBOSE = 'true';
  }
  
  if (argv.quiet) {
    process.env.FACT_QUIET = 'true';
  }
}

// Error handling
process.on('uncaughtException', (error) => {
  console.error(chalk.red('Fatal Error:'), error.message);
  if (process.env.FACT_VERBOSE === 'true') {
    console.error(error.stack);
  }
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error(chalk.red('Unhandled Rejection at:'), promise, chalk.red('reason:'), reason);
  process.exit(1);
});

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log(chalk.yellow('\n\nGracefully shutting down...'));
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log(chalk.yellow('\n\nGracefully shutting down...'));
  process.exit(0);
});

// Show banner and run
if (!process.env.FACT_QUIET) {
  console.log(chalk.cyan(banner));
  console.log(chalk.gray(`v${packageJson.version}\n`));
}

main().catch((error) => {
  console.error(chalk.red('CLI Error:'), error.message);
  if (process.env.FACT_VERBOSE === 'true') {
    console.error(error.stack);
  }
  process.exit(1);
});