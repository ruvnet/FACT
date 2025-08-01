/**
 * Tests for Configuration Manager
 */

import { ConfigManager, FactConfig } from '../src/core/config-manager';
import { readFile, writeFile, pathExists } from 'fs-extra';

// Mock fs-extra
jest.mock('fs-extra');
const mockReadFile = readFile as jest.MockedFunction<typeof readFile>;
const mockWriteFile = writeFile as jest.MockedFunction<typeof writeFile>;
const mockPathExists = pathExists as jest.MockedFunction<typeof pathExists>;

// Mock YAML
jest.mock('yaml', () => ({
  parse: jest.fn(),
  stringify: jest.fn(),
}));

describe('ConfigManager', () => {
  let configManager: ConfigManager;

  beforeEach(() => {
    jest.clearAllMocks();
    configManager = new ConfigManager();
    
    // Setup default mocks
    mockPathExists.mockResolvedValue(false);
  });

  describe('Default Configuration', () => {
    it('should load default configuration', () => {
      const config = configManager.getConfig();

      expect(config).toBeDefined();
      expect(config.wasm).toBeDefined();
      expect(config.performance).toBeDefined();
      expect(config.mcp).toBeDefined();
      expect(config.logging).toBeDefined();
      expect(config.security).toBeDefined();
      expect(config.templates).toBeDefined();
      expect(config.plugins).toBeDefined();
    });

    it('should have sensible defaults', () => {
      const config = configManager.getConfig();

      expect(config.wasm?.optimizationLevel).toBe('balanced');
      expect(config.wasm?.memoryLimit).toBe(256);
      expect(config.performance?.enableCaching).toBe(true);
      expect(config.performance?.cacheSize).toBe(100);
      expect(config.mcp?.port).toBe(3000);
      expect(config.mcp?.host).toBe('localhost');
      expect(config.logging?.level).toBe('info');
      expect(config.security?.enableSandbox).toBe(true);
    });
  });

  describe('Configuration Loading', () => {
    it('should load JSON configuration', async () => {
      const testConfig = {
        wasm: { memoryLimit: 512 },
        performance: { cacheSize: 200 }
      };

      mockPathExists.mockResolvedValue(true);
      mockReadFile.mockResolvedValue(JSON.stringify(testConfig));

      await configManager.loadConfig('test.json');

      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(512);
      expect(config.performance?.cacheSize).toBe(200);
    });

    it('should load YAML configuration', async () => {
      const testConfig = {
        wasm: { memoryLimit: 1024 },
        mcp: { port: 4000 }
      };

      const YAML = require('yaml');
      YAML.parse.mockReturnValue(testConfig);

      mockPathExists.mockResolvedValue(true);
      mockReadFile.mockResolvedValue('wasm:\n  memoryLimit: 1024');

      await configManager.loadConfig('test.yaml');

      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(1024);
      expect(config.mcp?.port).toBe(4000);
    });

    it('should handle missing configuration file', async () => {
      mockPathExists.mockResolvedValue(false);

      await configManager.loadConfig('nonexistent.json');

      // Should still have default config
      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(256);
    });

    it('should handle invalid JSON', async () => {
      mockPathExists.mockResolvedValue(true);
      mockReadFile.mockResolvedValue('invalid json');

      await expect(configManager.loadConfig('invalid.json')).rejects.toThrow();
    });

    it('should search for default config files', async () => {
      const testConfig = { wasm: { memoryLimit: 128 } };

      mockPathExists
        .mockResolvedValueOnce(false) // fact.config.yaml
        .mockResolvedValueOnce(false) // fact.config.yml  
        .mockResolvedValueOnce(true);  // fact.config.json

      mockReadFile.mockResolvedValue(JSON.stringify(testConfig));

      await configManager.loadConfig();

      expect(mockPathExists).toHaveBeenCalledTimes(3);
      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(128);
    });
  });

  describe('Configuration Saving', () => {
    it('should save JSON configuration', async () => {
      configManager.updateConfig({ wasm: { memoryLimit: 512 } });

      await configManager.saveConfig('test.json');

      expect(mockWriteFile).toHaveBeenCalled();
      const [path, content] = mockWriteFile.mock.calls[0];
      expect(path).toBe('test.json');
      expect(content).toContain('512');
    });

    it('should save YAML configuration', async () => {
      const YAML = require('yaml');
      YAML.stringify.mockReturnValue('wasm:\n  memoryLimit: 512\n');

      configManager.updateConfig({ wasm: { memoryLimit: 512 } });

      await configManager.saveConfig('test.yaml');

      expect(mockWriteFile).toHaveBeenCalled();
      expect(YAML.stringify).toHaveBeenCalled();
    });

    it('should handle save errors', async () => {
      mockWriteFile.mockRejectedValue(new Error('Write failed'));

      await expect(configManager.saveConfig('test.json')).rejects.toThrow('Write failed');
    });
  });

  describe('Configuration Updates', () => {
    it('should update configuration', () => {
      const updates = {
        wasm: { memoryLimit: 1024 },
        performance: { cacheSize: 500 }
      };

      configManager.updateConfig(updates);

      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(1024);
      expect(config.performance?.cacheSize).toBe(500);
      // Other defaults should remain
      expect(config.wasm?.optimizationLevel).toBe('balanced');
    });

    it('should merge nested objects', () => {
      configManager.updateConfig({
        wasm: { memoryLimit: 512 }
      });

      configManager.updateConfig({
        wasm: { optimizationLevel: 'speed' as const }
      });

      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(512);
      expect(config.wasm?.optimizationLevel).toBe('speed');
    });

    it('should get specific configuration values', () => {
      const wasmConfig = configManager.get('wasm');
      expect(wasmConfig).toBeDefined();
      expect(wasmConfig?.memoryLimit).toBe(256);

      const mcpConfig = configManager.get('mcp');
      expect(mcpConfig?.port).toBe(3000);
    });

    it('should set specific configuration values', () => {
      configManager.set('wasm', { memoryLimit: 2048, optimizationLevel: 'speed' });

      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(2048);
      expect(config.wasm?.optimizationLevel).toBe('speed');
    });
  });

  describe('Configuration Reset', () => {
    it('should reset to defaults', () => {
      // Modify config
      configManager.updateConfig({
        wasm: { memoryLimit: 2048 },
        mcp: { port: 8080 }
      });

      // Reset
      configManager.reset();

      // Should be back to defaults
      const config = configManager.getConfig();
      expect(config.wasm?.memoryLimit).toBe(256);
      expect(config.mcp?.port).toBe(3000);
    });
  });

  describe('Configuration Path Management', () => {
    it('should track configuration file path', async () => {
      mockPathExists.mockResolvedValue(true);
      mockReadFile.mockResolvedValue('{}');

      await configManager.loadConfig('custom.json');

      expect(configManager.getConfigPath()).toBe('custom.json');
    });

    it('should return undefined for default path initially', () => {
      expect(configManager.getConfigPath()).toBeUndefined();
    });
  });
});