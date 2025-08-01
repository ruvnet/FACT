/**
 * Configuration Manager for FACT CLI
 */

import { readFile, writeFile, pathExists } from 'fs-extra';
import { join } from 'path';
import { homedir } from 'os';
import YAML from 'yaml';
import { createLogger } from './logger';

const logger = createLogger('config');

export interface FactConfig {
  // Core settings
  wasm?: {
    path?: string;
    optimizationLevel?: 'size' | 'speed' | 'balanced';
    memoryLimit?: number; // in MB
  };
  
  // Performance settings
  performance?: {
    enableCaching?: boolean;
    cacheSize?: number; // in MB
    maxConcurrentTasks?: number;
    timeout?: number; // in seconds
  };
  
  // MCP server settings
  mcp?: {
    port?: number;
    host?: string;
    enableAuth?: boolean;
    maxConnections?: number;
  };
  
  // Logging settings
  logging?: {
    level?: 'error' | 'warn' | 'info' | 'debug';
    enableFileLogging?: boolean;
    maxLogFiles?: number;
    maxLogSize?: string;
  };
  
  // Template settings
  templates?: {
    defaultCategory?: string;
    autoSave?: boolean;
    searchPaths?: string[];
  };
  
  // Security settings
  security?: {
    enableSandbox?: boolean;
    allowUnsafeOperations?: boolean;
    trustedHosts?: string[];
  };
  
  // Plugin settings
  plugins?: {
    enabled?: string[];
    disabled?: string[];
    searchPaths?: string[];
  };
}

export class ConfigManager {
  private config: FactConfig = {};
  private configPath?: string;
  private defaultConfigPaths = [
    join(process.cwd(), 'fact.config.yaml'),
    join(process.cwd(), 'fact.config.yml'),
    join(process.cwd(), 'fact.config.json'),
    join(homedir(), '.fact', 'config.yaml'),
    join(homedir(), '.fact', 'config.yml'),
    join(homedir(), '.fact', 'config.json'),
  ];

  constructor() {
    this.loadDefaultConfig();
  }

  private loadDefaultConfig(): void {
    this.config = {
      wasm: {
        optimizationLevel: 'balanced',
        memoryLimit: 256, // 256MB
      },
      performance: {
        enableCaching: true,
        cacheSize: 100, // 100MB
        maxConcurrentTasks: 4,
        timeout: 30, // 30 seconds
      },
      mcp: {
        port: 3000,
        host: 'localhost',
        enableAuth: false,
        maxConnections: 10,
      },
      logging: {
        level: 'info',
        enableFileLogging: true,
        maxLogFiles: 5,
        maxLogSize: '10MB',
      },
      templates: {
        defaultCategory: 'general',
        autoSave: true,
        searchPaths: ['./templates', '~/.fact/templates'],
      },
      security: {
        enableSandbox: true,
        allowUnsafeOperations: false,
        trustedHosts: ['localhost', '127.0.0.1'],
      },
      plugins: {
        enabled: [],
        disabled: [],
        searchPaths: ['./plugins', '~/.fact/plugins'],
      },
    };
  }

  async loadConfig(configPath?: string): Promise<void> {
    try {
      let pathToLoad = configPath;
      
      // If no path specified, search for default config files
      if (!pathToLoad) {
        for (const defaultPath of this.defaultConfigPaths) {
          if (await pathExists(defaultPath)) {
            pathToLoad = defaultPath;
            break;
          }
        }
      }
      
      if (!pathToLoad) {
        logger.info('No configuration file found, using defaults');
        return;
      }
      
      logger.info('Loading configuration from:', pathToLoad);
      
      const configContent = await readFile(pathToLoad, 'utf8');
      let loadedConfig: FactConfig;
      
      if (pathToLoad.endsWith('.json')) {
        loadedConfig = JSON.parse(configContent);
      } else if (pathToLoad.endsWith('.yaml') || pathToLoad.endsWith('.yml')) {
        loadedConfig = YAML.parse(configContent);
      } else {
        throw new Error(`Unsupported configuration file format: ${pathToLoad}`);
      }
      
      // Merge with default config
      this.config = this.mergeConfig(this.config, loadedConfig);
      this.configPath = pathToLoad;
      
      logger.info('Configuration loaded successfully');
      
    } catch (error) {
      logger.error('Failed to load configuration:', error);
      throw new Error(`Configuration loading failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  async saveConfig(configPath?: string): Promise<void> {
    try {
      const pathToSave = configPath || this.configPath || join(homedir(), '.fact', 'config.yaml');
      
      logger.info('Saving configuration to:', pathToSave);
      
      let configContent: string;
      if (pathToSave.endsWith('.json')) {
        configContent = JSON.stringify(this.config, null, 2);
      } else {
        configContent = YAML.stringify(this.config);
      }
      
      await writeFile(pathToSave, configContent, 'utf8');
      this.configPath = pathToSave;
      
      logger.info('Configuration saved successfully');
      
    } catch (error) {
      logger.error('Failed to save configuration:', error);
      throw error;
    }
  }

  getConfig(): FactConfig {
    return { ...this.config };
  }

  updateConfig(updates: Partial<FactConfig>): void {
    this.config = this.mergeConfig(this.config, updates);
    logger.debug('Configuration updated');
  }

  get<K extends keyof FactConfig>(key: K): FactConfig[K] {
    return this.config[key];
  }

  set<K extends keyof FactConfig>(key: K, value: FactConfig[K]): void {
    this.config[key] = value;
    logger.debug(`Configuration key '${key}' updated`);
  }

  private mergeConfig(base: FactConfig, updates: Partial<FactConfig>): FactConfig {
    const merged = { ...base };
    
    for (const [key, value] of Object.entries(updates)) {
      if (value !== undefined && value !== null) {
        if (typeof value === 'object' && !Array.isArray(value) && merged[key as keyof FactConfig]) {
          // Deep merge for nested objects
          merged[key as keyof FactConfig] = {
            ...(merged[key as keyof FactConfig] as any),
            ...value,
          };
        } else {
          merged[key as keyof FactConfig] = value as any;
        }
      }
    }
    
    return merged;
  }

  getConfigPath(): string | undefined {
    return this.configPath;
  }

  reset(): void {
    logger.info('Resetting configuration to defaults');
    this.loadDefaultConfig();
  }
}