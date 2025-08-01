/**
 * Template commands - Template management functionality
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import inquirer from 'inquirer';
import { readFile, writeFile } from 'fs-extra';
import { FactEngine, Template } from '../core/engine';
import { WasmLoader } from '../wasm/loader';
import { createLogger } from '../core/logger';

const logger = createLogger('cmd-template');

export function initTemplateCommands(
  program: Command,
  engine: FactEngine | null,
  wasmLoader: WasmLoader
): void {
  const templateCmd = program
    .command('template')
    .alias('t')
    .description('Template management commands');

  // List templates
  templateCmd
    .command('list')
    .alias('ls')
    .description('List available templates')
    .option('-c, --category <category>', 'Filter by category')
    .option('-t, --tag <tags>', 'Filter by tags (comma-separated)')
    .option('--format <type>', 'Output format (table, json, yaml)', 'table')
    .action(async (options) => {
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        const tags = options.tag ? options.tag.split(',').map((t: string) => t.trim()) : undefined;
        const templates = await engine.listTemplates(options.category, tags);

        if (templates.length === 0) {
          console.log(chalk.yellow('No templates found matching the criteria.'));
          return;
        }

        console.log(chalk.blue.bold(`📋 Found ${templates.length} template(s):`));

        if (options.format === 'json') {
          console.log(JSON.stringify(templates, null, 2));
        } else if (options.format === 'yaml') {
          const YAML = require('yaml');
          console.log(YAML.stringify(templates));
        } else {
          // Table format
          console.log();
          templates.forEach((template, index) => {
            console.log(chalk.cyan(`${index + 1}. ${template.name} (${template.id})`));
            console.log(chalk.gray(`   Description: ${template.description}`));
            console.log(chalk.gray(`   Category: ${template.category || 'none'}`));
            console.log(chalk.gray(`   Tags: ${template.tags?.join(', ') || 'none'}`));
            console.log(chalk.gray(`   Created: ${template.created.toISOString()}`));
            console.log();
          });
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to list templates:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Show template details
  templateCmd
    .command('show')
    .alias('s')
    .description('Show template details')
    .argument('<id>', 'Template ID')
    .option('--format <type>', 'Output format (json, yaml)', 'json')
    .action(async (id, options) => {
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        const template = await engine.getTemplate(id);
        
        if (!template) {
          console.error(chalk.red(`❌ Template not found: ${id}`));
          process.exit(1);
        }

        console.log(chalk.blue.bold(`📋 Template: ${template.name}`));
        console.log();

        if (options.format === 'yaml') {
          const YAML = require('yaml');
          console.log(YAML.stringify(template));
        } else {
          console.log(JSON.stringify(template, null, 2));
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to show template:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Create template
  templateCmd
    .command('create')
    .alias('c')
    .description('Create a new template')
    .option('-f, --file <path>', 'Load template from file')
    .option('-i, --interactive', 'Create template interactively')
    .option('-n, --name <name>', 'Template name')
    .option('-d, --description <desc>', 'Template description')
    .option('--category <category>', 'Template category')
    .option('--tags <tags>', 'Template tags (comma-separated)')
    .action(async (options) => {
      const spinner = ora();
      
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        let templateData: Omit<Template, 'id' | 'created' | 'updated'>;

        if (options.file) {
          // Load from file
          spinner.start('Loading template from file...');
          const fileContent = await readFile(options.file, 'utf8');
          templateData = JSON.parse(fileContent);
          spinner.stop();
          
        } else if (options.interactive) {
          // Interactive creation
          console.log(chalk.blue.bold('🔧 Creating template interactively...'));
          
          const answers = await inquirer.prompt([
            {
              type: 'input',
              name: 'name',
              message: 'Template name:',
              validate: (input) => input.trim().length > 0 || 'Name is required'
            },
            {
              type: 'input',
              name: 'description',
              message: 'Template description:',
              validate: (input) => input.trim().length > 0 || 'Description is required'
            },
            {
              type: 'input',
              name: 'category',
              message: 'Category (optional):',
            },
            {
              type: 'input',
              name: 'tags',
              message: 'Tags (comma-separated, optional):',
            },
            {
              type: 'editor',
              name: 'pattern',
              message: 'Template pattern (JSON):',
              default: '{\n  "type": "template",\n  "steps": []\n}'
            }
          ]);

          templateData = {
            name: answers.name,
            description: answers.description,
            category: answers.category || undefined,
            tags: answers.tags ? answers.tags.split(',').map((t: string) => t.trim()) : undefined,
            pattern: JSON.parse(answers.pattern),
          };
          
        } else {
          // Use command line options
          if (!options.name || !options.description) {
            console.error(chalk.red('❌ Name and description are required when not using interactive mode'));
            console.error(chalk.yellow('Use --interactive or provide --name and --description'));
            process.exit(1);
          }

          templateData = {
            name: options.name,
            description: options.description,
            category: options.category,
            tags: options.tags ? options.tags.split(',').map((t: string) => t.trim()) : undefined,
            pattern: { type: 'basic', steps: [] }, // Default pattern
          };
        }

        spinner.start('Creating template...');
        const template = await engine.createTemplate(templateData);
        spinner.stop();

        console.log(chalk.green.bold('✅ Template created successfully!'));
        console.log(chalk.blue(`Template ID: ${template.id}`));
        console.log(chalk.gray(`Name: ${template.name}`));
        console.log(chalk.gray(`Description: ${template.description}`));

      } catch (error) {
        spinner.stop();
        console.error(chalk.red.bold('❌ Failed to create template:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Delete template
  templateCmd
    .command('delete')
    .alias('rm')
    .description('Delete a template')
    .argument('<id>', 'Template ID')
    .option('-f, --force', 'Force deletion without confirmation')
    .action(async (id, options) => {
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        // Check if template exists
        const template = await engine.getTemplate(id);
        if (!template) {
          console.error(chalk.red(`❌ Template not found: ${id}`));
          process.exit(1);
        }

        // Confirm deletion
        if (!options.force) {
          const { confirm } = await inquirer.prompt([
            {
              type: 'confirm',
              name: 'confirm',
              message: `Are you sure you want to delete template "${template.name}" (${id})?`,
              default: false
            }
          ]);

          if (!confirm) {
            console.log(chalk.yellow('❌ Deletion cancelled'));
            return;
          }
        }

        const deleted = await engine.deleteTemplate(id);
        
        if (deleted) {
          console.log(chalk.green.bold('✅ Template deleted successfully!'));
        } else {
          console.error(chalk.red('❌ Failed to delete template'));
          process.exit(1);
        }

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to delete template:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Export template
  templateCmd
    .command('export')
    .alias('e')
    .description('Export template to file')
    .argument('<id>', 'Template ID')
    .option('-o, --output <path>', 'Output file path')
    .option('--format <type>', 'Output format (json, yaml)', 'json')
    .action(async (id, options) => {
      try {
        if (!engine) {
          throw new Error('Engine not initialized');
        }

        const template = await engine.getTemplate(id);
        
        if (!template) {
          console.error(chalk.red(`❌ Template not found: ${id}`));
          process.exit(1);
        }

        let content: string;
        let extension: string;

        if (options.format === 'yaml') {
          const YAML = require('yaml');
          content = YAML.stringify(template);
          extension = '.yaml';
        } else {
          content = JSON.stringify(template, null, 2);
          extension = '.json';
        }

        const outputPath = options.output || `${template.name.replace(/\s+/g, '-').toLowerCase()}-${id}${extension}`;
        
        await writeFile(outputPath, content);
        
        console.log(chalk.green.bold('✅ Template exported successfully!'));
        console.log(chalk.blue(`File: ${outputPath}`));

      } catch (error) {
        console.error(chalk.red.bold('❌ Failed to export template:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });
}