import fs from 'fs/promises';
import path from 'path';
import { logger } from './logger.js';

export class FactWasmLoader {
  private wasmModule: WebAssembly.Module | null = null;
  private wasmInstance: WebAssembly.Instance | null = null;
  private memory: WebAssembly.Memory | null = null;

  async initialize(): Promise<void> {
    try {
      // Load WASM file
      const wasmPath = path.join(process.cwd(), 'pkg', 'fact_wasm_bg.wasm');
      
      // Check if WASM file exists
      try {
        await fs.access(wasmPath);
      } catch {
        logger.warn('WASM file not found, using mock implementation');
        this.useMockImplementation();
        return;
      }

      const wasmBuffer = await fs.readFile(wasmPath);
      
      // Create memory
      this.memory = new WebAssembly.Memory({
        initial: 256,
        maximum: 1024,
      });

      // Compile WASM module
      this.wasmModule = await WebAssembly.compile(wasmBuffer);
      
      // Instantiate with imports
      this.wasmInstance = await WebAssembly.instantiate(this.wasmModule, {
        env: {
          memory: this.memory,
          abort: (msg: number, file: number, line: number, col: number) => {
            logger.error('WASM abort:', { msg, file, line, col });
          },
        },
        wbindgen: {
          __wbindgen_throw: (ptr: number, len: number) => {
            const msg = this.getString(ptr, len);
            throw new Error(msg);
          },
          __wbindgen_memory: () => this.memory,
        },
      });

      logger.info('WASM module loaded successfully');
    } catch (error) {
      logger.error('Failed to load WASM module:', error);
      this.useMockImplementation();
    }
  }

  async getInstance(): Promise<any> {
    if (!this.wasmInstance) {
      // Return mock implementation if WASM not available
      return this.getMockInstance();
    }
    return this.wasmInstance.exports;
  }

  private getString(ptr: number, len: number): string {
    if (!this.memory) return '';
    
    const buffer = new Uint8Array(this.memory.buffer, ptr, len);
    return new TextDecoder().decode(buffer);
  }

  private useMockImplementation(): void {
    logger.info('Using mock WASM implementation for development');
  }

  private getMockInstance(): any {
    // Mock implementation for when WASM is not available
    return {
      process_query: (query: string) => {
        return JSON.stringify({
          result: 'Mock result for: ' + query,
          cached: false,
          processing_time_ms: 10,
        });
      },
      
      create_cache: () => {
        return { id: 'mock-cache', size: 0 };
      },
      
      cache_get: (key: string) => {
        return null;
      },
      
      cache_put: (key: string, value: string) => {
        return true;
      },
      
      optimize_performance: (mode: string) => {
        return {
          optimized: true,
          improvements: ['mock improvement 1', 'mock improvement 2'],
        };
      },
    };
  }

  getMemoryStats(): { used: number; total: number } {
    if (!this.memory) {
      return { used: 0, total: 0 };
    }
    
    return {
      used: this.memory.buffer.byteLength,
      total: this.memory.buffer.byteLength,
    };
  }
}