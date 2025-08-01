/**
 * FACT Engine - Core cognitive processing engine with WASM integration
 */

import { WasmModule } from '../wasm/loader';
import { createLogger } from './logger';
import { ConfigManager } from './config-manager';
import { PerformanceMonitor } from './performance-monitor';

const logger = createLogger('engine');

export interface Template {
  id: string;
  name: string;
  description: string;
  pattern: any;
  category?: string;
  tags?: string[];
  created: Date;
  updated: Date;
}

export interface ProcessingContext {
  template_id?: string;
  data: any;
  options?: {
    cache?: boolean;
    priority?: 'low' | 'medium' | 'high';
    timeout?: number;
  };
}

export interface ProcessingResult {
  success: boolean;
  result?: any;
  error?: string;
  metrics?: {
    processingTime: number;
    memoryUsed: number;
    cacheHit?: boolean;
  };
}

export class FactEngine {
  private wasm: WasmModule;
  private config: ConfigManager;
  private performanceMonitor: PerformanceMonitor;
  private templates: Map<string, Template> = new Map();
  private isInitialized = false;

  constructor(wasmModule: WasmModule) {
    this.wasm = wasmModule;
    this.config = new ConfigManager();
    this.performanceMonitor = new PerformanceMonitor();
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    try {
      logger.info('Initializing FACT Engine...');
      
      // Initialize performance monitoring
      await this.performanceMonitor.initialize();
      
      // Load default templates
      await this.loadDefaultTemplates();
      
      this.isInitialized = true;
      logger.info('FACT Engine initialized successfully');
      
    } catch (error) {
      logger.error('Failed to initialize FACT Engine:', error);
      throw error;
    }
  }

  async processTemplate(context: ProcessingContext): Promise<ProcessingResult> {
    const startTime = Date.now();
    const startMemory = this.getMemoryUsage();

    try {
      logger.debug('Processing template:', context.template_id);
      
      // Validate context
      if (!context.data) {
        throw new Error('Processing context data is required');
      }

      // Get template if specified
      let template: Template | undefined;
      if (context.template_id) {
        template = this.templates.get(context.template_id);
        if (!template) {
          throw new Error(`Template not found: ${context.template_id}`);
        }
      }

      // Prepare data for WASM
      const templateData = template ? JSON.stringify(template.pattern) : '{}';
      const contextData = JSON.stringify(context.data);
      
      // Process using WASM
      const wasmResult = this.wasm.process_template(templateData, contextData);
      
      // Parse result
      let result: any;
      try {
        result = JSON.parse(wasmResult);
      } catch {
        result = wasmResult; // Fallback to raw string
      }

      const endTime = Date.now();
      const endMemory = this.getMemoryUsage();

      const processingResult: ProcessingResult = {
        success: true,
        result,
        metrics: {
          processingTime: endTime - startTime,
          memoryUsed: endMemory.used - startMemory.used,
        }
      };

      // Record performance metrics
      this.performanceMonitor.recordProcessing(processingResult.metrics!);
      
      logger.debug('Template processing completed successfully');
      return processingResult;
      
    } catch (error) {
      const endTime = Date.now();
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      logger.error('Template processing failed:', errorMessage);
      
      return {
        success: false,
        error: errorMessage,
        metrics: {
          processingTime: endTime - startTime,
          memoryUsed: 0,
        }
      };
    }
  }

  async analyzeContext(context: any): Promise<any> {
    try {
      logger.debug('Analyzing context');
      
      const contextData = JSON.stringify(context);
      const result = this.wasm.analyze_context(contextData);
      
      return JSON.parse(result);
      
    } catch (error) {
      logger.error('Context analysis failed:', error);
      throw error;
    }
  }

  async createTemplate(template: Omit<Template, 'id' | 'created' | 'updated'>): Promise<Template> {
    try {
      const newTemplate: Template = {
        ...template,
        id: this.generateTemplateId(),
        created: new Date(),
        updated: new Date(),
      };

      // Validate template using WASM
      const templateData = JSON.stringify(newTemplate.pattern);
      const wasmResult = this.wasm.create_template(templateData);
      
      // Store template
      this.templates.set(newTemplate.id, newTemplate);
      
      logger.info('Template created:', newTemplate.id);
      return newTemplate;
      
    } catch (error) {
      logger.error('Template creation failed:', error);
      throw error;
    }
  }

  async listTemplates(category?: string, tags?: string[]): Promise<Template[]> {
    const templates = Array.from(this.templates.values());
    
    return templates.filter(template => {
      if (category && template.category !== category) {
        return false;
      }
      
      if (tags && tags.length > 0) {
        const templateTags = template.tags || [];
        return tags.some(tag => templateTags.includes(tag));
      }
      
      return true;
    });
  }

  async getTemplate(id: string): Promise<Template | undefined> {
    return this.templates.get(id);
  }

  async deleteTemplate(id: string): Promise<boolean> {
    const deleted = this.templates.delete(id);
    if (deleted) {
      logger.info('Template deleted:', id);
    }
    return deleted;
  }

  async optimizePerformance(operation: string): Promise<any> {
    try {
      logger.debug('Optimizing performance for operation:', operation);
      
      const result = this.wasm.optimize_performance(operation);
      return JSON.parse(result);
      
    } catch (error) {
      logger.error('Performance optimization failed:', error);
      throw error;
    }
  }

  async getMetrics(): Promise<any> {
    try {
      const wasmMetrics = JSON.parse(this.wasm.get_metrics());
      const performanceMetrics = this.performanceMonitor.getMetrics();
      
      return {
        wasm: wasmMetrics,
        performance: performanceMetrics,
        templates: {
          total: this.templates.size,
          categories: this.getTemplateCategories(),
        },
        memory: this.getMemoryUsage(),
      };
      
    } catch (error) {
      logger.error('Failed to get metrics:', error);
      throw error;
    }
  }

  private async loadDefaultTemplates(): Promise<void> {
    // Load some default templates for common use cases
    const defaultTemplates = [
      {
        name: 'Simple Analysis',
        description: 'Basic context analysis template',
        pattern: {
          type: 'analysis',
          steps: ['extract', 'analyze', 'summarize'],
        },
        category: 'analysis',
        tags: ['basic', 'analysis'],
      },
      {
        name: 'Code Generation',
        description: 'Template for code generation tasks',
        pattern: {
          type: 'generation',
          language: 'auto-detect',
          steps: ['analyze', 'design', 'implement'],
        },
        category: 'generation',
        tags: ['code', 'generation'],
      },
    ];

    for (const template of defaultTemplates) {
      await this.createTemplate(template);
    }
    
    logger.info(`Loaded ${defaultTemplates.length} default templates`);
  }

  private generateTemplateId(): string {
    return `tpl_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
  }

  private getTemplateCategories(): string[] {
    const categories = new Set<string>();
    for (const template of this.templates.values()) {
      if (template.category) {
        categories.add(template.category);
      }
    }
    return Array.from(categories);
  }

  private getMemoryUsage(): { used: number; total: number } {
    return {
      used: process.memoryUsage().heapUsed,
      total: process.memoryUsage().heapTotal,
    };
  }

  async shutdown(): Promise<void> {
    logger.info('Shutting down FACT Engine...');
    
    // Save templates if needed
    // Clean up resources
    
    this.isInitialized = false;
    logger.info('FACT Engine shutdown complete');
  }
}