import { FactWasmLoader } from './wasm-loader.js';
import { TemplateRegistry } from './template-registry.js';
import { CacheManager } from './cache-manager.js';
import { PerformanceMonitor } from './performance-monitor.js';
import { logger } from './logger.js';

export interface ProcessingOptions {
  cache?: boolean;
  timeout?: number;
  priority?: 'low' | 'medium' | 'high';
}

export interface ProcessingResult {
  output: any;
  metadata: {
    template_id: string;
    processing_time_ms: number;
    cached?: boolean;
    tokens_processed?: number;
  };
}

export interface ContextAnalysis {
  patterns: string[];
  complexity: 'low' | 'medium' | 'high';
  suggested_approach: string;
  key_entities: string[];
  confidence: number;
}

export class CognitiveTemplateEngine {
  private wasm: FactWasmLoader;
  private templates: TemplateRegistry;
  private cache: CacheManager;
  private monitor: PerformanceMonitor;

  constructor(
    wasmLoader: FactWasmLoader,
    templateRegistry: TemplateRegistry,
    cacheManager: CacheManager,
    performanceMonitor: PerformanceMonitor
  ) {
    this.wasm = wasmLoader;
    this.templates = templateRegistry;
    this.cache = cacheManager;
    this.monitor = performanceMonitor;
  }

  async processTemplate(
    templateId: string,
    context: any,
    options: ProcessingOptions = {}
  ): Promise<ProcessingResult> {
    const startTime = Date.now();
    const cacheKey = this.generateCacheKey(templateId, context);

    // Check cache if enabled
    if (options.cache !== false) {
      const cached = await this.cache.get(cacheKey);
      if (cached) {
        logger.debug(`Cache hit for template ${templateId}`);
        return {
          output: cached,
          metadata: {
            template_id: templateId,
            processing_time_ms: Date.now() - startTime,
            cached: true,
          },
        };
      }
    }

    // Get template
    const template = await this.templates.getTemplate(templateId);
    if (!template) {
      throw new Error(`Template not found: ${templateId}`);
    }

    // Process with WASM
    try {
      const wasmInstance = await this.wasm.getInstance();
      
      // Apply cognitive pattern
      const processed = await this.applyCognitivePattern(
        template,
        context,
        wasmInstance,
        options
      );

      // Cache result
      if (options.cache !== false) {
        await this.cache.set(cacheKey, processed, template.cache_ttl);
      }

      const processingTime = Date.now() - startTime;
      this.monitor.recordMetric('template_processing', processingTime);

      return {
        output: processed,
        metadata: {
          template_id: templateId,
          processing_time_ms: processingTime,
          tokens_processed: this.estimateTokens(context),
        },
      };
    } catch (error) {
      logger.error(`Error processing template ${templateId}:`, error);
      throw error;
    }
  }

  async analyzeContext(context: any): Promise<ContextAnalysis> {
    const wasmInstance = await this.wasm.getInstance();
    
    // Extract patterns using WASM
    const patterns = this.extractPatterns(context);
    const complexity = this.assessComplexity(context);
    const entities = this.extractKeyEntities(context);
    
    return {
      patterns,
      complexity,
      suggested_approach: this.suggestApproach(patterns, complexity),
      key_entities: entities,
      confidence: this.calculateConfidence(patterns, entities),
    };
  }

  private async applyCognitivePattern(
    template: any,
    context: any,
    wasmInstance: any,
    options: ProcessingOptions
  ): Promise<any> {
    // This would use the WASM module to apply the cognitive pattern
    // For now, we'll simulate the processing
    
    const pattern = template.pattern;
    const steps = pattern.steps || [];
    
    let result = context;
    for (const step of steps) {
      result = await this.executeStep(step, result, wasmInstance);
      
      // Check timeout
      if (options.timeout && Date.now() > options.timeout) {
        throw new Error('Processing timeout exceeded');
      }
    }
    
    return result;
  }

  private async executeStep(step: any, data: any, wasmInstance: any): Promise<any> {
    // Execute cognitive processing step
    switch (step.type) {
      case 'transform':
        return this.transform(data, step.config);
      case 'analyze':
        return this.analyze(data, step.config);
      case 'synthesize':
        return this.synthesize(data, step.config);
      default:
        return data;
    }
  }

  private transform(data: any, config: any): any {
    // Implement transformation logic
    return {
      ...data,
      transformed: true,
      timestamp: Date.now(),
    };
  }

  private analyze(data: any, config: any): any {
    // Implement analysis logic
    return {
      ...data,
      analysis: {
        sentiment: 'neutral',
        topics: ['general'],
        confidence: 0.85,
      },
    };
  }

  private synthesize(data: any, config: any): any {
    // Implement synthesis logic
    return {
      summary: 'Processed content',
      insights: ['Key insight 1', 'Key insight 2'],
      recommendations: ['Action 1', 'Action 2'],
      original_data: data,
    };
  }

  private generateCacheKey(templateId: string, context: any): string {
    const contextHash = this.hashObject(context);
    return `template:${templateId}:${contextHash}`;
  }

  private hashObject(obj: any): string {
    // Simple hash function for cache keys
    const str = JSON.stringify(obj);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(16);
  }

  private extractPatterns(context: any): string[] {
    // Extract cognitive patterns from context
    const patterns: string[] = [];
    
    if (typeof context === 'object') {
      if (context.questions) patterns.push('inquiry');
      if (context.data) patterns.push('analysis');
      if (context.goals) patterns.push('planning');
      if (context.constraints) patterns.push('optimization');
    }
    
    return patterns;
  }

  private assessComplexity(context: any): 'low' | 'medium' | 'high' {
    const size = JSON.stringify(context).length;
    const depth = this.getObjectDepth(context);
    
    if (size < 1000 && depth < 3) return 'low';
    if (size < 10000 && depth < 5) return 'medium';
    return 'high';
  }

  private getObjectDepth(obj: any, currentDepth = 0): number {
    if (typeof obj !== 'object' || obj === null) return currentDepth;
    
    let maxDepth = currentDepth;
    for (const key in obj) {
      const depth = this.getObjectDepth(obj[key], currentDepth + 1);
      maxDepth = Math.max(maxDepth, depth);
    }
    
    return maxDepth;
  }

  private extractKeyEntities(context: any): string[] {
    const entities: string[] = [];
    
    // Extract named entities (simplified)
    const text = JSON.stringify(context);
    const capitalizedWords = text.match(/[A-Z][a-z]+/g) || [];
    
    return [...new Set(capitalizedWords)].slice(0, 10);
  }

  private suggestApproach(patterns: string[], complexity: string): string {
    if (patterns.includes('optimization') && complexity === 'high') {
      return 'Use iterative refinement with constraint satisfaction';
    }
    if (patterns.includes('analysis') && patterns.includes('inquiry')) {
      return 'Apply exploratory data analysis with guided discovery';
    }
    if (patterns.includes('planning')) {
      return 'Use goal-oriented backward chaining';
    }
    return 'Apply standard cognitive template processing';
  }

  private calculateConfidence(patterns: string[], entities: string[]): number {
    const patternScore = patterns.length * 0.2;
    const entityScore = Math.min(entities.length * 0.1, 0.5);
    return Math.min(patternScore + entityScore + 0.3, 1.0);
  }

  private estimateTokens(context: any): number {
    const text = JSON.stringify(context);
    // Rough estimate: 1 token per 4 characters
    return Math.ceil(text.length / 4);
  }
}