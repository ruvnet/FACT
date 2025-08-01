/**
 * Config commands - Configuration management functionality
 */

import { Command } from 'commander';
import chalk from 'chalk';
import inquirer from 'inquirer';
import { ConfigManager, FactConfig } from '../core/config-manager';
import { FactEngine } from '../core/engine';
import { WasmLoader } from '../wasm/loader';
import { createLogger } from '../core/logger';

const logger = createLogger('cmd-config');

export function initConfigCommands(
  program: Command,
  engine: FactEngine | null,
  wasmLoader: WasmLoader
): void {
  const configCmd = program
    .command('config')
    .alias('cfg')
    .description('Configuration management commands');

  // Show configuration
  configCmd
    .command('show')
    .alias('s')
    .description('Show current configuration')
    .option('--format <type>', 'Output format (json, yaml, table)', 'table')
    .option('--key <key>', 'Show specific configuration key')
    .action(async (options) => {
      try {
        const config = new ConfigManager();
        await config.loadConfig();
        
        const currentConfig = config.getConfig();

        if (options.key) {
          const value = config.get(options.key as keyof FactConfig);
          if (value === undefined) {
            console.error(chalk.red(`❌ Configuration key not found: ${options.key}`));
            process.exit(1);
          }
          
          console.log(chalk.blue.bold(`Configuration: ${options.key}`));
          if (options.format === 'json') {
            console.log(JSON.stringify(value, null, 2));
          } else if (options.format === 'yaml') {
            const YAML = require('yaml');
            console.log(YAML.stringify(value));
          } else {
            console.log(value);
          }
          return;
        }

        console.log(chalk.blue.bold('📋 Current Configuration:'));
        console.log();

        if (options.format === 'json') {
          console.log(JSON.stringify(currentConfig, null, 2));
        } else if (options.format === 'yaml') {
          const YAML = require('yaml');
          console.log(YAML.stringify(currentConfig));
        } else {
          displayConfigTable(currentConfig);
        }

        // Show config file path
        const configPath = config.getConfigPath();
        if (configPath) {
          console.log(chalk.gray(`\nConfiguration file: ${configPath}`));
        } else {
          console.log(chalk.gray('\nUsing default configuration (no config file found)'));
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to show configuration:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Set configuration value
  configCmd
    .command('set')
    .description('Set configuration value')
    .argument('<key>', 'Configuration key (dot notation supported)')
    .argument('<value>', 'Configuration value (JSON string)')
    .option('--save', 'Save to configuration file')
    .action(async (key, value, options) => {
      try {
        const config = new ConfigManager();
        await config.loadConfig();

        // Parse the value
        let parsedValue: any;
        try {
          parsedValue = JSON.parse(value);
        } catch {
          // If not valid JSON, treat as string
          parsedValue = value;
        }

        // Set the value using dot notation
        setNestedValue(config, key, parsedValue);

        console.log(chalk.green.bold('✅ Configuration updated!'));
        console.log(chalk.blue(`${key}: ${JSON.stringify(parsedValue)}`));

        // Save if requested
        if (options.save) {
          await config.saveConfig();
          console.log(chalk.green('💾 Configuration saved to file'));
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to set configuration:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Initialize configuration
  configCmd
    .command('init')
    .alias('i')
    .description('Initialize configuration interactively')
    .option('-f, --file <path>', 'Configuration file path')
    .option('--force', 'Overwrite existing configuration')
    .action(async (options) => {
      try {
        const config = new ConfigManager();
        
        // Check if config exists
        const configPath = config.getConfigPath();
        if (configPath && !options.force) {
          const { overwrite } = await inquirer.prompt([
            {
              type: 'confirm',
              name: 'overwrite',
              message: `Configuration file already exists at ${configPath}. Overwrite?`,
              default: false
            }
          ]);
          
          if (!overwrite) {
            console.log(chalk.yellow('❌ Configuration initialization cancelled'));
            return;
          }
        }

        console.log(chalk.blue.bold('🔧 Initializing FACT configuration...'));
        console.log();

        // Interactive configuration
        const answers = await inquirer.prompt([
          {
            type: 'list',
            name: 'wasmOptimization',
            message: 'WASM optimization level:',
            choices: ['size', 'speed', 'balanced'],
            default: 'balanced'
          },
          {
            type: 'number',
            name: 'wasmMemoryLimit',
            message: 'WASM memory limit (MB):',
            default: 256,
            validate: (input) => input > 0 || 'Memory limit must be positive'
          },
          {
            type: 'confirm',
            name: 'enableCaching',
            message: 'Enable caching:',
            default: true
          },
          {
            type: 'number',
            name: 'cacheSize',
            message: 'Cache size (MB):',
            default: 100,
            when: (answers) => answers.enableCaching,
            validate: (input) => input > 0 || 'Cache size must be positive'
          },
          {
            type: 'number',
            name: 'mcpPort',
            message: 'MCP server port:',
            default: 3000,
            validate: (input) => (input >= 1024 && input <= 65535) || 'Port must be between 1024 and 65535'
          },
          {
            type: 'list',
            name: 'logLevel',
            message: 'Logging level:',
            choices: ['error', 'warn', 'info', 'debug'],
            default: 'info'
          },
          {
            type: 'confirm',
            name: 'enableSandbox',
            message: 'Enable security sandbox:',
            default: true
          }
        ]);

        // Update configuration
        config.updateConfig({
          wasm: {
            optimizationLevel: answers.wasmOptimization,
            memoryLimit: answers.wasmMemoryLimit,
          },
          performance: {
            enableCaching: answers.enableCaching,
            cacheSize: answers.cacheSize,
          },
          mcp: {
            port: answers.mcpPort,
          },
          logging: {
            level: answers.logLevel,
          },
          security: {
            enableSandbox: answers.enableSandbox,
          }
        });

        // Save configuration
        const savePath = options.file || configPath;
        await config.saveConfig(savePath);

        console.log();
        console.log(chalk.green.bold('✅ Configuration initialized successfully!'));
        console.log(chalk.blue(`Configuration saved to: ${savePath || config.getConfigPath()}`));

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to initialize configuration:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Validate configuration
  configCmd
    .command('validate')
    .alias('v')
    .description('Validate configuration')
    .option('-f, --file <path>', 'Configuration file to validate')
    .action(async (options) => {
      try {
        const config = new ConfigManager();
        
        if (options.file) {
          await config.loadConfig(options.file);
        } else {
          await config.loadConfig();
        }

        // Perform validation
        const validationResult = validateConfig(config.getConfig());
        
        if (validationResult.valid) {
          console.log(chalk.green.bold('✅ Configuration is valid!'));
          
          if (validationResult.warnings.length > 0) {
            console.log(chalk.yellow('\n⚠️  Warnings:'));
            validationResult.warnings.forEach(warning => {
              console.log(chalk.yellow(`   • ${warning}`));
            });
          }
        } else {
          console.log(chalk.red.bold('❌ Configuration validation failed!'));
          console.log();
          
          validationResult.errors.forEach(error => {
            console.log(chalk.red(`   • ${error}`));
          });
          
          process.exit(1);
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Configuration validation failed:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Reset configuration
  configCmd
    .command('reset')
    .description('Reset configuration to defaults')
    .option('--save', 'Save reset configuration to file')
    .action(async (options) => {
      try {
        const { confirm } = await inquirer.prompt([
          {
            type: 'confirm',
            name: 'confirm',
            message: 'Are you sure you want to reset configuration to defaults?',
            default: false
          }
        ]);

        if (!confirm) {
          console.log(chalk.yellow('❌ Configuration reset cancelled'));
          return;
        }

        const config = new ConfigManager();
        config.reset();

        console.log(chalk.green.bold('✅ Configuration reset to defaults!'));

        if (options.save) {
          await config.saveConfig();
          console.log(chalk.green('💾 Default configuration saved to file'));
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to reset configuration:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });
}

function displayConfigTable(config: FactConfig): void {
  console.log(chalk.cyan('WASM Settings:'));
  console.log(chalk.gray(`  Optimization Level: ${config.wasm?.optimizationLevel || 'default'}`));
  console.log(chalk.gray(`  Memory Limit: ${config.wasm?.memoryLimit || 'default'}MB`));
  console.log();

  console.log(chalk.cyan('Performance Settings:'));
  console.log(chalk.gray(`  Caching Enabled: ${config.performance?.enableCaching ?? 'default'}`));
  console.log(chalk.gray(`  Cache Size: ${config.performance?.cacheSize || 'default'}MB`));
  console.log(chalk.gray(`  Max Concurrent: ${config.performance?.maxConcurrentTasks || 'default'}`));
  console.log(chalk.gray(`  Timeout: ${config.performance?.timeout || 'default'}s`));
  console.log();

  console.log(chalk.cyan('MCP Server Settings:'));
  console.log(chalk.gray(`  Port: ${config.mcp?.port || 'default'}`));
  console.log(chalk.gray(`  Host: ${config.mcp?.host || 'default'}`));
  console.log(chalk.gray(`  Auth Enabled: ${config.mcp?.enableAuth ?? 'default'}`));
  console.log();

  console.log(chalk.cyan('Logging Settings:'));
  console.log(chalk.gray(`  Level: ${config.logging?.level || 'default'}`));
  console.log(chalk.gray(`  File Logging: ${config.logging?.enableFileLogging ?? 'default'}`));
  console.log();

  console.log(chalk.cyan('Security Settings:'));
  console.log(chalk.gray(`  Sandbox: ${config.security?.enableSandbox ?? 'default'}`));
  console.log(chalk.gray(`  Unsafe Operations: ${config.security?.allowUnsafeOperations ?? 'default'}`));
}

function setNestedValue(config: ConfigManager, key: string, value: any): void {
  const keys = key.split('.');
  const topLevelKey = keys[0] as keyof FactConfig;
  
  if (keys.length === 1) {
    config.set(topLevelKey, value);
  } else {
    // Handle nested keys
    const current = config.get(topLevelKey) || {};
    let target = current;
    
    for (let i = 1; i < keys.length - 1; i++) {
      if (!target[keys[i]]) target[keys[i]] = {};
      target = target[keys[i]];
    }
    
    target[keys[keys.length - 1]] = value;
    config.set(topLevelKey, current);
  }
}

function validateConfig(config: FactConfig): {
  valid: boolean;
  errors: string[];
  warnings: string[];
} {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Validate WASM settings
  if (config.wasm?.memoryLimit && config.wasm.memoryLimit < 64) {
    errors.push('WASM memory limit must be at least 64MB');
  }
  if (config.wasm?.memoryLimit && config.wasm.memoryLimit > 2048) {
    warnings.push('WASM memory limit is very high (>2GB), consider reducing it');
  }

  // Validate performance settings
  if (config.performance?.cacheSize && config.performance.cacheSize < 10) {
    warnings.push('Cache size is very small, performance may be impacted');
  }
  if (config.performance?.maxConcurrentTasks && config.performance.maxConcurrentTasks > 20) {
    warnings.push('High concurrent task limit may cause resource exhaustion');
  }

  // Validate MCP settings
  if (config.mcp?.port && (config.mcp.port < 1024 || config.mcp.port > 65535)) {
    errors.push('MCP port must be between 1024 and 65535');
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings
  };
}