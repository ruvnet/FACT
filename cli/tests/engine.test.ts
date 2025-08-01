/**
 * Tests for FACT Engine
 */

import { FactEngine } from '../src/core/engine';
import { WasmLoader } from '../src/wasm/loader';

// Mock WASM loader for testing
class MockWasmLoader extends WasmLoader {
  private mockWasm = {
    process_template: (templateData: string, context: string) => {
      return JSON.stringify({ processed: true, input: JSON.parse(context) });
    },
    analyze_context: (context: string) => {
      return JSON.stringify({ analyzed: true, context: JSON.parse(context) });
    },
    optimize_performance: (operation: string) => {
      return JSON.stringify({ optimized: operation });
    },
    create_template: (template: string) => {
      return JSON.stringify({ created: true });
    },
    get_metrics: () => {
      return JSON.stringify({ wasm_calls: 1, memory_usage: 1024 });
    },
    memory: {} as WebAssembly.Memory,
  };

  async initialize(): Promise<void> {
    // Mock initialization
  }

  getWasm() {
    return this.mockWasm;
  }

  isReady(): boolean {
    return true;
  }
}

describe('FactEngine', () => {
  let engine: FactEngine;
  let wasmLoader: MockWasmLoader;

  beforeEach(async () => {
    wasmLoader = new MockWasmLoader();
    await wasmLoader.initialize();
    engine = new FactEngine(wasmLoader.getWasm());
    await engine.initialize();
  });

  describe('Template Processing', () => {
    it('should process template successfully', async () => {
      const result = await engine.processTemplate({
        data: { test: 'data' }
      });

      expect(result.success).toBe(true);
      expect(result.result).toEqual({ processed: true, input: { test: 'data' } });
      expect(result.metrics).toBeDefined();
      expect(result.metrics!.processingTime).toBeGreaterThan(0);
    });

    it('should handle processing errors gracefully', async () => {
      // Mock WASM to throw error
      const errorWasm = {
        ...wasmLoader.getWasm(),
        process_template: () => {
          throw new Error('WASM processing error');
        }
      };

      const errorEngine = new FactEngine(errorWasm);
      await errorEngine.initialize();

      const result = await errorEngine.processTemplate({
        data: { test: 'data' }
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('WASM processing error');
    });

    it('should process with specific template ID', async () => {
      // Create a template first
      const template = await engine.createTemplate({
        name: 'Test Template',
        description: 'A test template',
        pattern: { type: 'test', steps: ['analyze', 'process'] }
      });

      const result = await engine.processTemplate({
        template_id: template.id,
        data: { test: 'data' }
      });

      expect(result.success).toBe(true);
    });
  });

  describe('Context Analysis', () => {
    it('should analyze context successfully', async () => {
      const result = await engine.analyzeContext({ test: 'context' });

      expect(result).toEqual({ analyzed: true, context: { test: 'context' } });
    });
  });

  describe('Template Management', () => {
    it('should create template successfully', async () => {
      const templateData = {
        name: 'Test Template',
        description: 'A test template',
        pattern: { type: 'test' },
        category: 'testing',
        tags: ['test', 'example']
      };

      const template = await engine.createTemplate(templateData);

      expect(template.id).toBeDefined();
      expect(template.name).toBe(templateData.name);
      expect(template.description).toBe(templateData.description);
      expect(template.category).toBe(templateData.category);
      expect(template.tags).toEqual(templateData.tags);
      expect(template.created).toBeInstanceOf(Date);
      expect(template.updated).toBeInstanceOf(Date);
    });

    it('should list templates', async () => {
      // Create some templates
      await engine.createTemplate({
        name: 'Template 1',
        description: 'First template',
        pattern: { type: 'test1' },
        category: 'testing'
      });

      await engine.createTemplate({
        name: 'Template 2',
        description: 'Second template',
        pattern: { type: 'test2' },
        category: 'analysis'
      });

      const allTemplates = await engine.listTemplates();
      expect(allTemplates.length).toBeGreaterThanOrEqual(4); // 2 created + 2 default

      const testingTemplates = await engine.listTemplates('testing');
      expect(testingTemplates.length).toBeGreaterThanOrEqual(1);
    });

    it('should get specific template', async () => {
      const created = await engine.createTemplate({
        name: 'Specific Template',
        description: 'A specific template',
        pattern: { type: 'specific' }
      });

      const retrieved = await engine.getTemplate(created.id);
      expect(retrieved).toBeDefined();
      expect(retrieved!.id).toBe(created.id);
      expect(retrieved!.name).toBe(created.name);
    });

    it('should delete template', async () => {
      const created = await engine.createTemplate({
        name: 'To Delete',
        description: 'Template to be deleted',
        pattern: { type: 'delete' }
      });

      const deleted = await engine.deleteTemplate(created.id);
      expect(deleted).toBe(true);

      const retrieved = await engine.getTemplate(created.id);
      expect(retrieved).toBeUndefined();
    });
  });

  describe('Performance Optimization', () => {
    it('should optimize performance', async () => {
      const result = await engine.optimizePerformance('cache');

      expect(result).toEqual({ optimized: 'cache' });
    });
  });

  describe('Metrics', () => {
    it('should get metrics', async () => {
      const metrics = await engine.getMetrics();

      expect(metrics).toBeDefined();
      expect(metrics.wasm).toBeDefined();
      expect(metrics.performance).toBeDefined();
      expect(metrics.templates).toBeDefined();
      expect(metrics.memory).toBeDefined();
    });
  });
});