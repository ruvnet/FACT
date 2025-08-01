/**
 * MCP Server Implementation for FACT CLI
 */

import { WebSocketServer } from 'ws';
import { createServer } from 'http';
import { JSONRPCRequest, JSONRPCResponse, parse, format } from 'jsonrpc-lite';
import { FactEngine, Template, ProcessingContext } from '../core/engine';
import { createLogger } from '../core/logger';
import { ConfigManager } from '../core/config-manager';

const logger = createLogger('mcp-server');

export interface McpTool {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
}

export class McpServer {
  private server?: WebSocketServer;
  private httpServer?: any;
  private engine: FactEngine;
  private config: ConfigManager;
  private isRunning = false;
  private tools: Map<string, McpTool> = new Map();

  constructor(engine: FactEngine) {
    this.engine = engine;
    this.config = new ConfigManager();
    this.initializeTools();
  }

  private initializeTools(): void {
    // Process Template Tool
    this.tools.set('process_template', {
      name: 'process_template',
      description: 'Process a cognitive template with given context',
      parameters: {
        type: 'object',
        properties: {
          template_id: {
            type: 'string',
            description: 'ID of the template to process'
          },
          context: {
            type: 'object',
            description: 'Context data for template processing'
          },
          options: {
            type: 'object',
            properties: {
              cache: { type: 'boolean' },
              priority: { type: 'string', enum: ['low', 'medium', 'high'] },
              timeout: { type: 'number' }
            }
          }
        },
        required: ['template_id', 'context']
      }
    });

    // List Templates Tool
    this.tools.set('list_templates', {
      name: 'list_templates',
      description: 'List available cognitive templates',
      parameters: {
        type: 'object',
        properties: {
          category: {
            type: 'string',
            description: 'Filter by category'
          },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Filter by tags'
          }
        }
      }
    });

    // Analyze Context Tool
    this.tools.set('analyze_context', {
      name: 'analyze_context',
      description: 'Analyze context and suggest appropriate templates',
      parameters: {
        type: 'object',
        properties: {
          context: {
            type: 'object',
            description: 'Context to analyze'
          },
          suggest_templates: {
            type: 'boolean',
            description: 'Whether to suggest templates',
            default: true
          }
        },
        required: ['context']
      }
    });

    // Optimize Performance Tool
    this.tools.set('optimize_performance', {
      name: 'optimize_performance',
      description: 'Optimize FACT performance (cache, memory, processing)',
      parameters: {
        type: 'object',
        properties: {
          operation: {
            type: 'string',
            enum: ['cache', 'memory', 'processing'],
            description: 'Type of optimization to perform'
          },
          aggressive: {
            type: 'boolean',
            description: 'Enable aggressive optimization'
          }
        },
        required: ['operation']
      }
    });

    // Create Template Tool
    this.tools.set('create_template', {
      name: 'create_template',
      description: 'Create a new cognitive template',
      parameters: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          description: { type: 'string' },
          pattern: { type: 'object' },
          category: { type: 'string' },
          tags: {
            type: 'array',
            items: { type: 'string' }
          }
        },
        required: ['name', 'description', 'pattern']
      }
    });

    // Get Metrics Tool
    this.tools.set('get_metrics', {
      name: 'get_metrics',
      description: 'Get performance metrics and statistics',
      parameters: {
        type: 'object',
        properties: {}
      }
    });

    logger.info(`Initialized ${this.tools.size} MCP tools`);
  }

  async start(): Promise<void> {
    if (this.isRunning) {
      return;
    }

    try {
      const port = this.config.get('mcp')?.port || 3000;
      const host = this.config.get('mcp')?.host || 'localhost';

      logger.info(`Starting MCP server on ${host}:${port}`);

      // Create HTTP server
      this.httpServer = createServer();

      // Create WebSocket server
      this.server = new WebSocketServer({
        server: this.httpServer,
        path: '/mcp'
      });

      // Set up connection handling
      this.server.on('connection', (ws, request) => {
        logger.info('New MCP client connected:', request.socket.remoteAddress);

        ws.on('message', async (data) => {
          try {
            const message = data.toString();
            const response = await this.handleMessage(message);
            
            if (response) {
              ws.send(JSON.stringify(response));
            }
            
          } catch (error) {
            logger.error('Error handling message:', error);
            
            const errorResponse = format.error(
              null,
              format.JsonRpcError.internalError(
                error instanceof Error ? error.message : String(error)
              )
            );
            
            ws.send(JSON.stringify(errorResponse));
          }
        });

        ws.on('close', () => {
          logger.info('MCP client disconnected');
        });

        ws.on('error', (error) => {
          logger.error('WebSocket error:', error);
        });

        // Send welcome message
        const welcome = {
          jsonrpc: '2.0',
          method: 'notification',
          params: {
            type: 'welcome',
            message: 'Connected to FACT MCP Server',
            tools: Array.from(this.tools.keys()),
            version: require('../../package.json').version
          }
        };
        
        ws.send(JSON.stringify(welcome));
      });

      // Start the server
      await new Promise<void>((resolve, reject) => {
        this.httpServer.listen(port, host, (error?: Error) => {
          if (error) {
            reject(error);
          } else {
            resolve();
          }
        });
      });

      this.isRunning = true;
      logger.info(`MCP server started successfully on ${host}:${port}`);

    } catch (error) {
      logger.error('Failed to start MCP server:', error);
      throw error;
    }
  }

  private async handleMessage(message: string): Promise<any> {
    try {
      const parsed = parse(message);
      
      if (Array.isArray(parsed)) {
        // Batch request
        const responses = await Promise.all(
          parsed.map(req => this.handleSingleRequest(req))
        );
        return responses.filter(res => res !== null);
      } else {
        // Single request
        return await this.handleSingleRequest(parsed);
      }
      
    } catch (error) {
      logger.error('Error parsing message:', error);
      return format.error(
        null,
        format.JsonRpcError.parseError()
      );
    }
  }

  private async handleSingleRequest(request: any): Promise<any> {
    if (request.type === 'invalid') {
      return format.error(
        request.payload.id || null,
        format.JsonRpcError.invalidRequest()
      );
    }

    if (request.type === 'notification') {
      // Handle notifications (no response needed)
      await this.handleNotification(request.payload.method, request.payload.params);
      return null;
    }

    if (request.type === 'request') {
      try {
        const result = await this.handleToolCall(
          request.payload.method,
          request.payload.params || {}
        );
        
        return format.success(request.payload.id, result);
        
      } catch (error) {
        logger.error(`Error handling tool call '${request.payload.method}':`, error);
        
        return format.error(
          request.payload.id,
          format.JsonRpcError.internalError(
            error instanceof Error ? error.message : String(error)
          )
        );
      }
    }

    return format.error(
      null,
      format.JsonRpcError.methodNotFound()
    );
  }

  private async handleNotification(method: string, params: any): Promise<void> {
    logger.debug('Received notification:', method, params);
    
    // Handle notifications like ping, status updates, etc.
    switch (method) {
      case 'ping':
        // Just log the ping
        break;
      case 'status':
        // Handle status updates
        break;
      default:
        logger.debug('Unknown notification method:', method);
    }
  }

  private async handleToolCall(method: string, params: any): Promise<any> {
    logger.debug('Handling tool call:', method, params);

    switch (method) {
      case 'process_template':
        return await this.processTemplate(params);
        
      case 'list_templates':
        return await this.listTemplates(params);
        
      case 'analyze_context':
        return await this.analyzeContext(params);
        
      case 'optimize_performance':
        return await this.optimizePerformance(params);
        
      case 'create_template':
        return await this.createTemplate(params);
        
      case 'get_metrics':
        return await this.getMetrics(params);
        
      case 'tools/list':
        return this.listTools();
        
      default:
        throw new Error(`Unknown method: ${method}`);
    }
  }

  private async processTemplate(params: any): Promise<any> {
    const context: ProcessingContext = {
      template_id: params.template_id,
      data: params.context,
      options: params.options
    };
    
    return await this.engine.processTemplate(context);
  }

  private async listTemplates(params: any): Promise<Template[]> {
    return await this.engine.listTemplates(params.category, params.tags);
  }

  private async analyzeContext(params: any): Promise<any> {
    const analysis = await this.engine.analyzeContext(params.context);
    
    if (params.suggest_templates !== false) {
      const templates = await this.engine.listTemplates();
      return {
        analysis,
        suggested_templates: templates.slice(0, 5) // Top 5 suggestions
      };
    }
    
    return { analysis };
  }

  private async optimizePerformance(params: any): Promise<any> {
    return await this.engine.optimizePerformance(params.operation);
  }

  private async createTemplate(params: any): Promise<Template> {
    return await this.engine.createTemplate({
      name: params.name,
      description: params.description,
      pattern: params.pattern,
      category: params.category,
      tags: params.tags
    });
  }

  private async getMetrics(params: any): Promise<any> {
    return await this.engine.getMetrics();
  }

  private listTools(): McpTool[] {
    return Array.from(this.tools.values());
  }

  async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    logger.info('Stopping MCP server...');

    if (this.server) {
      this.server.close();
      this.server = undefined;
    }

    if (this.httpServer) {
      await new Promise<void>((resolve) => {
        this.httpServer.close(() => resolve());
      });
      this.httpServer = undefined;
    }

    this.isRunning = false;
    logger.info('MCP server stopped');
  }

  isServerRunning(): boolean {
    return this.isRunning;
  }

  getServerInfo(): {
    running: boolean;
    port?: number;
    host?: string;
    toolsCount: number;
  } {
    return {
      running: this.isRunning,
      port: this.config.get('mcp')?.port,
      host: this.config.get('mcp')?.host,
      toolsCount: this.tools.size,
    };
  }
}