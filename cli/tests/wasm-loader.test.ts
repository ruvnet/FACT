/**
 * Tests for WASM Loader
 */

import { WasmLoader } from '../src/wasm/loader';
import { pathExists, readFile } from 'fs-extra';
import { join } from 'path';

// Mock fs-extra
jest.mock('fs-extra');
const mockPathExists = pathExists as jest.MockedFunction<typeof pathExists>;
const mockReadFile = readFile as jest.MockedFunction<typeof readFile>;

// Mock WASM bindings
const mockWasmBindings = {
  default: jest.fn().mockResolvedValue(undefined),
  process_template: jest.fn().mockReturnValue('{"result": "processed"}'),
  analyze_context: jest.fn().mockReturnValue('{"result": "analyzed"}'),
  optimize_performance: jest.fn().mockReturnValue('{"result": "optimized"}'),
  create_template: jest.fn().mockReturnValue('{"result": "created"}'),
  get_metrics: jest.fn().mockReturnValue('{"result": "metrics"}'),
  memory: {} as WebAssembly.Memory,
};

// Mock require for WASM bindings
jest.mock('path', () => ({
  ...jest.requireActual('path'),
  join: jest.fn().mockImplementation((...args) => args.join('/')),
}));

describe('WasmLoader', () => {
  let wasmLoader: WasmLoader;

  beforeEach(() => {
    jest.clearAllMocks();
    wasmLoader = new WasmLoader();
    
    // Setup default mocks
    mockPathExists.mockResolvedValue(true);
    mockReadFile.mockResolvedValue(Buffer.from('mock-wasm-bytes'));
    
    // Mock require for WASM bindings
    jest.doMock('../../wasm/fact_wasm_core.js', () => mockWasmBindings, { virtual: true });
  });

  afterEach(() => {
    jest.dontMock('../../wasm/fact_wasm_core.js');
  });

  describe('Initialization', () => {
    it('should initialize successfully', async () => {
      await wasmLoader.initialize();

      expect(wasmLoader.isReady()).toBe(true);
      expect(mockReadFile).toHaveBeenCalled();
      expect(mockWasmBindings.default).toHaveBeenCalled();
    });

    it('should not initialize twice', async () => {
      await wasmLoader.initialize();
      await wasmLoader.initialize(); // Second call

      expect(mockWasmBindings.default).toHaveBeenCalledTimes(1);
    });

    it('should handle WASM file not found', async () => {
      mockPathExists.mockResolvedValue(false);
      mockReadFile.mockRejectedValue(new Error('File not found'));

      await expect(wasmLoader.initialize()).rejects.toThrow('WASM initialization failed');
    });

    it('should handle WASM binding load failure', async () => {
      // Mock require to throw
      jest.doMock('../../wasm/fact_wasm_core.js', () => {
        throw new Error('Binding load failed');
      }, { virtual: true });

      const newLoader = new WasmLoader();
      await expect(newLoader.initialize()).rejects.toThrow('WASM initialization failed');
    });
  });

  describe('WASM Module Access', () => {
    beforeEach(async () => {
      await wasmLoader.initialize();
    });

    it('should return WASM module when ready', () => {
      const wasm = wasmLoader.getWasm();

      expect(wasm).toBeDefined();
      expect(wasm.process_template).toBeDefined();
      expect(wasm.analyze_context).toBeDefined();
      expect(wasm.optimize_performance).toBeDefined();
      expect(wasm.create_template).toBeDefined();
      expect(wasm.get_metrics).toBeDefined();
      expect(wasm.memory).toBeDefined();
    });

    it('should throw error when not initialized', () => {
      const uninitializedLoader = new WasmLoader();

      expect(() => uninitializedLoader.getWasm()).toThrow('WASM module not initialized');
    });

    it('should test WASM module functions', async () => {
      await wasmLoader.initialize();
      const wasm = wasmLoader.getWasm();

      // Test each function
      expect(wasm.process_template('{}', '{}')).toBe('{"result": "processed"}');
      expect(wasm.analyze_context('{}')).toBe('{"result": "analyzed"}');
      expect(wasm.optimize_performance('cache')).toBe('{"result": "optimized"}');
      expect(wasm.create_template('{}')).toBe('{"result": "created"}');
      expect(wasm.get_metrics()).toBe('{"result": "metrics"}');
    });
  });

  describe('Memory Management', () => {
    beforeEach(async () => {
      // Mock memory
      mockWasmBindings.memory = {
        buffer: new ArrayBuffer(1024 * 1024), // 1MB
      } as WebAssembly.Memory;
      
      await wasmLoader.initialize();
    });

    it('should return memory usage', () => {
      const usage = wasmLoader.getMemoryUsage();

      expect(usage).toBeDefined();
      expect(usage.used).toBeGreaterThanOrEqual(0);
      expect(usage.total).toBeGreaterThanOrEqual(usage.used);
    });

    it('should handle missing memory', () => {
      const loaderWithoutMemory = new WasmLoader();
      const usage = loaderWithoutMemory.getMemoryUsage();

      expect(usage.used).toBe(0);
      expect(usage.total).toBe(0);
    });
  });

  describe('Reload Functionality', () => {
    it('should reload WASM module', async () => {
      await wasmLoader.initialize();
      expect(wasmLoader.isReady()).toBe(true);

      await wasmLoader.reload();
      expect(wasmLoader.isReady()).toBe(true);
      expect(mockWasmBindings.default).toHaveBeenCalledTimes(2);
    });
  });

  describe('Custom WASM Path', () => {
    it('should use custom WASM path', async () => {
      const customPath = '/custom/path/to/wasm';
      const customLoader = new WasmLoader(customPath);

      await customLoader.initialize();

      expect(mockReadFile).toHaveBeenCalledWith(customPath);
    });
  });
});