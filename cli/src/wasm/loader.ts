/**
 * WASM Loader - Handles loading and initialization of the FACT WASM core
 */

import { readFile } from 'fs-extra';
import { join } from 'path';
import { createLogger } from '../core/logger';

const logger = createLogger('wasm-loader');

export interface WasmModule {
  process_template: (templateData: string, context: string) => string;
  analyze_context: (context: string) => string;
  optimize_performance: (operation: string) => string;
  create_template: (template: string) => string;
  get_metrics: () => string;
  memory: WebAssembly.Memory;
}

export class WasmLoader {
  private wasm: WasmModule | null = null;
  private isInitialized = false;
  private wasmPath: string;

  constructor(wasmPath?: string) {
    // Default to the copied WASM files in the CLI package
    this.wasmPath = wasmPath || join(__dirname, '../../wasm/fact_wasm_core_bg.wasm');
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    try {
      logger.info('Loading WASM module from:', this.wasmPath);
      
      // Read the WASM file
      const wasmBytes = await readFile(this.wasmPath);
      logger.info(`WASM file loaded: ${wasmBytes.length} bytes`);
      
      // Import the JavaScript bindings
      const wasmBindings = await this.loadWasmBindings();
      
      // Initialize the WASM module
      await wasmBindings.default(wasmBytes);
      
      // Create our WASM interface
      this.wasm = {
        process_template: wasmBindings.process_template,
        analyze_context: wasmBindings.analyze_context,
        optimize_performance: wasmBindings.optimize_performance,
        create_template: wasmBindings.create_template,
        get_metrics: wasmBindings.get_metrics,
        memory: wasmBindings.memory,
      };
      
      this.isInitialized = true;
      logger.info('WASM module initialized successfully');
      
      // Test the WASM module
      await this.testWasmModule();
      
    } catch (error) {
      logger.error('Failed to initialize WASM module:', error);
      throw new Error(`WASM initialization failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async loadWasmBindings(): Promise<any> {
    try {
      // Try to load the JavaScript bindings
      const bindingsPath = join(__dirname, '../../wasm/fact_wasm_core.js');
      const wasmBindings = require(bindingsPath);
      return wasmBindings;
      
    } catch (error) {
      logger.error('Failed to load WASM bindings:', error);
      throw new Error(`Failed to load WASM bindings: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async testWasmModule(): Promise<void> {
    if (!this.wasm) {
      throw new Error('WASM module not initialized');
    }

    try {
      // Test basic functionality
      const testContext = JSON.stringify({ test: 'initialization' });
      const result = this.wasm.analyze_context(testContext);
      
      logger.info('WASM module test passed:', result ? 'success' : 'no result');
      
    } catch (error) {
      logger.warn('WASM module test failed (may be expected):', error);
      // Don't throw here as some functions might not be fully implemented
    }
  }

  getWasm(): WasmModule {
    if (!this.isInitialized || !this.wasm) {
      throw new Error('WASM module not initialized. Call initialize() first.');
    }
    return this.wasm;
  }

  isReady(): boolean {
    return this.isInitialized && this.wasm !== null;
  }

  getMemoryUsage(): { used: number; total: number } {
    if (!this.wasm?.memory) {
      return { used: 0, total: 0 };
    }

    const memory = this.wasm.memory;
    const used = memory.buffer.byteLength;
    const total = memory.buffer.byteLength; // This is the current size, not max
    
    return { used, total };
  }

  async reload(): Promise<void> {
    logger.info('Reloading WASM module...');
    this.isInitialized = false;
    this.wasm = null;
    await this.initialize();
  }
}