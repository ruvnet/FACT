/**
 * Error Handler for FACT CLI
 */

import { createLogger } from './logger';
import chalk from 'chalk';

const logger = createLogger('error-handler');

export interface ErrorContext {
  component?: string;
  operation?: string;
  user?: string;
  timestamp: Date;
  additionalData?: any;
}

export class ErrorHandler {
  private errorHistory: Array<{
    error: Error;
    context: ErrorContext;
    handled: boolean;
  }> = [];

  handleError(error: Error, component?: string, additionalData?: any): void {
    const context: ErrorContext = {
      component,
      timestamp: new Date(),
      additionalData,
    };

    // Log the error
    logger.error('Error occurred:', {
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack,
      },
      context,
    });

    // Store in history
    this.errorHistory.push({
      error,
      context,
      handled: true,
    });

    // Keep only recent errors (last 100)
    if (this.errorHistory.length > 100) {
      this.errorHistory = this.errorHistory.slice(-100);
    }

    // Display user-friendly error message
    this.displayError(error, context);
  }

  private displayError(error: Error, context: ErrorContext): void {
    console.error(chalk.red.bold('❌ Error:'), chalk.red(error.message));
    
    if (context.component) {
      console.error(chalk.gray(`   Component: ${context.component}`));
    }
    
    // Show suggestions based on error type
    this.showErrorSuggestions(error);
    
    // Show stack trace in debug mode
    if (process.env.DEBUG || process.env.NODE_ENV === 'development') {
      console.error(chalk.gray('\nStack trace:'));
      console.error(chalk.gray(error.stack));
    }
  }

  private showErrorSuggestions(error: Error): void {
    const suggestions: string[] = [];

    // Common error patterns and suggestions
    if (error.message.includes('WASM')) {
      suggestions.push('Check if WASM module is properly installed and accessible');
      suggestions.push('Try running: npm run copy-wasm');
    }

    if (error.message.includes('permission') || error.message.includes('EACCES')) {
      suggestions.push('Check file permissions');
      suggestions.push('Try running with appropriate permissions');
    }

    if (error.message.includes('ENOENT') || error.message.includes('not found')) {
      suggestions.push('Check if all required files exist');
      suggestions.push('Try running: npm install');
    }

    if (error.message.includes('port') || error.message.includes('EADDRINUSE')) {
      suggestions.push('Check if the port is already in use');
      suggestions.push('Try specifying a different port');
    }

    if (error.message.includes('timeout')) {
      suggestions.push('Operation timed out - try increasing timeout in configuration');
      suggestions.push('Check network connectivity if applicable');
    }

    if (error.message.includes('memory') || error.message.includes('allocation')) {
      suggestions.push('System may be running low on memory');
      suggestions.push('Try reducing memory usage or increasing limits');
    }

    // Display suggestions
    if (suggestions.length > 0) {
      console.error(chalk.yellow('\n💡 Suggestions:'));
      suggestions.forEach((suggestion, index) => {
        console.error(chalk.yellow(`   ${index + 1}. ${suggestion}`));
      });
    }

    // General help
    console.error(chalk.blue('\n📚 For more help:'));
    console.error(chalk.blue('   • Run: fact --help'));
    console.error(chalk.blue('   • Check documentation: https://github.com/your-org/fact'));
    console.error(chalk.blue('   • Report issues: https://github.com/your-org/fact/issues'));
  }

  getErrorHistory(): Array<{
    error: Error;
    context: ErrorContext;
    handled: boolean;
  }> {
    return [...this.errorHistory];
  }

  getErrorSummary(): {
    total: number;
    byComponent: Record<string, number>;
    recent: Array<{
      message: string;
      component?: string;
      timestamp: Date;
    }>;
  } {
    const byComponent: Record<string, number> = {};
    
    this.errorHistory.forEach(({ context }) => {
      const component = context.component || 'unknown';
      byComponent[component] = (byComponent[component] || 0) + 1;
    });

    const recent = this.errorHistory
      .slice(-10)
      .map(({ error, context }) => ({
        message: error.message,
        component: context.component,
        timestamp: context.timestamp,
      }));

    return {
      total: this.errorHistory.length,
      byComponent,
      recent,
    };
  }

  clearHistory(): void {
    this.errorHistory = [];
    logger.info('Error history cleared');
  }

  // Utility methods for common error types
  static createWasmError(message: string, originalError?: Error): Error {
    const error = new Error(`WASM Error: ${message}`);
    if (originalError) {
      error.stack = originalError.stack;
    }
    return error;
  }

  static createConfigError(message: string, configPath?: string): Error {
    return new Error(`Configuration Error: ${message}${configPath ? ` (${configPath})` : ''}`);
  }

  static createTemplateError(message: string, templateId?: string): Error {
    return new Error(`Template Error: ${message}${templateId ? ` (Template: ${templateId})` : ''}`);
  }

  static createMcpError(message: string, operation?: string): Error {
    return new Error(`MCP Error: ${message}${operation ? ` (Operation: ${operation})` : ''}`);
  }
}