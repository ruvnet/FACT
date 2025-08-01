#!/usr/bin/env node

/**
 * Post-install script for FACT CLI
 * Handles WASM file copying and initial setup
 */

const fs = require('fs-extra');
const path = require('path');
const chalk = require('chalk');

async function postInstall() {
  console.log(chalk.blue('🔧 Running FACT CLI post-install setup...'));

  try {
    // Create necessary directories
    const wasmDir = path.join(__dirname, '..', 'wasm');
    const logsDir = path.join(__dirname, '..', 'logs');
    
    await fs.ensureDir(wasmDir);
    await fs.ensureDir(logsDir);
    
    console.log(chalk.gray('   ✓ Created directories'));

    // Copy WASM files from the parent wasm/pkg directory
    const sourceWasmDir = path.join(__dirname, '..', '..', 'wasm', 'pkg');
    
    if (await fs.pathExists(sourceWasmDir)) {
      console.log(chalk.gray('   ✓ Copying WASM files...'));
      
      const wasmFiles = [
        'fact_wasm_core.js',
        'fact_wasm_core_bg.wasm',
        'fact_wasm_core.d.ts',
        'fact_wasm_core_bg.wasm.d.ts'
      ];

      for (const file of wasmFiles) {
        const sourcePath = path.join(sourceWasmDir, file);
        const destPath = path.join(wasmDir, file);
        
        if (await fs.pathExists(sourcePath)) {
          await fs.copy(sourcePath, destPath);
          console.log(chalk.gray(`   ✓ Copied ${file}`));
        } else {
          console.log(chalk.yellow(`   ⚠ WASM file not found: ${file}`));
        }
      }
    } else {
      console.log(chalk.yellow('   ⚠ WASM source directory not found. You may need to build WASM first.'));
      console.log(chalk.yellow('     Run: cd ../wasm && npm run build:wasm'));
    }

    // Check WASM file sizes
    const wasmFile = path.join(wasmDir, 'fact_wasm_core_bg.wasm');
    if (await fs.pathExists(wasmFile)) {
      const stats = await fs.stat(wasmFile);
      const sizeKB = Math.round(stats.size / 1024);
      console.log(chalk.gray(`   ✓ WASM module size: ${sizeKB}KB`));
      
      if (sizeKB > 500) {
        console.log(chalk.yellow(`   ⚠ WASM module is large (${sizeKB}KB). Consider optimization.`));
      }
    }

    // Create initial configuration template
    const configTemplate = path.join(__dirname, '..', 'fact.config.example.yaml');
    if (!(await fs.pathExists(configTemplate))) {
      const exampleConfig = `# FACT CLI Configuration Example
# Copy this to fact.config.yaml and customize as needed

wasm:
  optimizationLevel: "balanced"  # size, speed, balanced
  memoryLimit: 256  # MB

performance:
  enableCaching: true
  cacheSize: 100  # MB
  maxConcurrentTasks: 4
  timeout: 30  # seconds

mcp:
  port: 3000
  host: "localhost"
  enableAuth: false
  maxConnections: 10

logging:
  level: "info"  # error, warn, info, debug
  enableFileLogging: true
  maxLogFiles: 5
  maxLogSize: "10MB"

templates:
  defaultCategory: "general"
  autoSave: true
  searchPaths:
    - "./templates"
    - "~/.fact/templates"

security:
  enableSandbox: true
  allowUnsafeOperations: false
  trustedHosts:
    - "localhost"
    - "127.0.0.1"

plugins:
  enabled: []
  disabled: []
  searchPaths:
    - "./plugins"
    - "~/.fact/plugins"
`;
      
      await fs.writeFile(configTemplate, exampleConfig);
      console.log(chalk.gray('   ✓ Created configuration example'));
    }

    console.log(chalk.green('✅ FACT CLI post-install completed successfully!'));
    console.log();
    console.log(chalk.blue('🚀 Get started:'));
    console.log(chalk.gray('   fact --help                 # Show all commands'));
    console.log(chalk.gray('   fact config init             # Initialize configuration'));
    console.log(chalk.gray('   fact template list           # List available templates'));
    console.log(chalk.gray('   fact mcp start               # Start MCP server'));
    console.log();
    console.log(chalk.blue('📚 Documentation: https://github.com/your-org/fact'));

  } catch (error) {
    console.error(chalk.red('❌ Post-install setup failed:'));
    console.error(chalk.red(error.message));
    
    console.log(chalk.yellow('\n💡 Manual setup:'));
    console.log(chalk.yellow('   1. Build WASM: cd ../wasm && npm run build:wasm'));
    console.log(chalk.yellow('   2. Copy WASM files to ./wasm/ directory'));
    console.log(chalk.yellow('   3. Run: fact config init'));
    
    process.exit(1);
  }
}

// Only run if this script is executed directly
if (require.main === module) {
  postInstall();
}

module.exports = postInstall;