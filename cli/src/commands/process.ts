/**
 * Process command - Core template processing functionality
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import { readFile } from 'fs-extra';
import { FactEngine } from '../core/engine';
import { WasmLoader } from '../wasm/loader';
import { createLogger } from '../core/logger';

const logger = createLogger('cmd-process');

export function initProcessCommand(
  program: Command,
  engine: FactEngine | null,
  wasmLoader: WasmLoader
): void {
  const processCmd = program
    .command('process')
    .alias('p')
    .description('Process templates with context data')
    .argument('<template>', 'Template ID or path to template file')
    .argument('[context]', 'Context data (JSON string or path to JSON file)')
    .option('-f, --file <path>', 'Read context from file')
    .option('-o, --output <path>', 'Write output to file')
    .option('--cache', 'Enable caching for this operation')
    .option('--no-cache', 'Disable caching for this operation')
    .option('--priority <level>', 'Processing priority (low, medium, high)', 'medium')
    .option('--timeout <seconds>', 'Processing timeout in seconds', '30')
    .option('--format <type>', 'Output format (json, yaml, text)', 'json')
    .action(async (template, context, options) => {
      const spinner = ora('Processing template...').start();
      
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        // Parse template ID or load from file
        let templateId = template;
        if (template.endsWith('.json') || template.endsWith('.yaml')) {
          // TODO: Load template from file
          templateId = template;
        }

        // Parse context data
        let contextData: any = {};
        
        if (options.file) {
          spinner.text = 'Loading context from file...';
          const contextContent = await readFile(options.file, 'utf8');
          contextData = JSON.parse(contextContent);
        } else if (context) {
          if (context.endsWith('.json')) {
            const contextContent = await readFile(context, 'utf8');
            contextData = JSON.parse(contextContent);
          } else {
            contextData = JSON.parse(context);
          }
        }

        spinner.text = 'Processing template...';
        
        // Process the template
        const result = await engine.processTemplate({
          template_id: templateId,
          data: contextData,
          options: {
            cache: options.cache,
            priority: options.priority,
            timeout: parseInt(options.timeout) * 1000,
          }
        });

        spinner.stop();

        if (result.success) {
          console.log(chalk.green.bold('✅ Processing completed successfully!'));
          
          // Display metrics
          if (result.metrics) {
            console.log(chalk.gray('\n📊 Metrics:'));
            console.log(chalk.gray(`   Processing time: ${result.metrics.processingTime}ms`));
            console.log(chalk.gray(`   Memory used: ${(result.metrics.memoryUsed / 1024 / 1024).toFixed(2)}MB`));
            if (result.metrics.cacheHit !== undefined) {
              console.log(chalk.gray(`   Cache hit: ${result.metrics.cacheHit ? 'Yes' : 'No'}`));
            }
          }

          // Display result
          console.log(chalk.blue('\n📋 Result:'));
          
          if (options.format === 'json') {
            console.log(JSON.stringify(result.result, null, 2));
          } else if (options.format === 'yaml') {
            const YAML = require('yaml');
            console.log(YAML.stringify(result.result));
          } else {
            console.log(result.result);
          }

          // Save to file if requested
          if (options.output) {
            const { writeFile } = require('fs-extra');
            const outputContent = options.format === 'json' 
              ? JSON.stringify(result.result, null, 2)
              : String(result.result);
            
            await writeFile(options.output, outputContent);
            console.log(chalk.green(`\n💾 Output saved to: ${options.output}`));
          }

        } else {
          console.log(chalk.red.bold('❌ Processing failed!'));
          console.log(chalk.red(`Error: ${result.error}`));
          
          if (result.metrics) {
            console.log(chalk.gray(`Processing time: ${result.metrics.processingTime}ms`));
          }
          
          process.exit(1);
        }

      } catch (error) {
        spinner.stop();
        console.error(chalk.red.bold('❌ Processing failed:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        
        logger.error('Process command failed:', error);
        process.exit(1);
      }
    });

  // Add analyze subcommand
  processCmd
    .command('analyze')
    .alias('a')
    .description('Analyze context without processing')
    .argument('<context>', 'Context data (JSON string or path to JSON file)')
    .option('-f, --file <path>', 'Read context from file')
    .option('--suggest', 'Suggest appropriate templates')
    .action(async (context, options) => {
      const spinner = ora('Analyzing context...').start();
      
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        // Parse context data
        let contextData: any = {};
        
        if (options.file) {
          const contextContent = await readFile(options.file, 'utf8');
          contextData = JSON.parse(contextContent);
        } else if (context.endsWith('.json')) {
          const contextContent = await readFile(context, 'utf8');
          contextData = JSON.parse(contextContent);
        } else {
          contextData = JSON.parse(context);
        }

        const analysis = await engine.analyzeContext(contextData);
        
        spinner.stop();
        
        console.log(chalk.green.bold('✅ Context analysis completed!'));
        console.log(chalk.blue('\n📋 Analysis Result:'));
        console.log(JSON.stringify(analysis, null, 2));

        // Suggest templates if requested
        if (options.suggest) {
          console.log(chalk.blue('\n💡 Template Suggestions:'));
          const templates = await engine.listTemplates();
          const suggestions = templates.slice(0, 3); // Top 3 suggestions
          
          suggestions.forEach((template, index) => {
            console.log(chalk.yellow(`   ${index + 1}. ${template.name} (${template.id})`));
            console.log(chalk.gray(`      ${template.description}`));
          });
        }

      } catch (error) {
        spinner.stop();
        console.error(chalk.red.bold('❌ Analysis failed:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });
}