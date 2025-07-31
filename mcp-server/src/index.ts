#!/usr/bin/env node
/**
 * FACT MCP Server - Model Context Protocol Server for Fast Autonomous Cognitive Templates
 * 
 * This server provides cognitive template capabilities through the MCP protocol,
 * enabling AI models to leverage FACT's high-performance template processing.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { logger } from './logger.js';
import { CognitiveTemplateEngine } from './cognitive-engine.js';
import { FactWasmLoader } from './wasm-loader.js';
import { TemplateRegistry } from './template-registry.js';
import { CacheManager } from './cache-manager.js';
import { PerformanceMonitor } from './performance-monitor.js';

// Tool schemas
const ProcessTemplateSchema = z.object({
  template_id: z.string().describe('ID of the cognitive template to process'),
  context: z.object({}).describe('Context data for template processing'),
  options: z.object({
    cache: z.boolean().optional().describe('Whether to use caching'),
    timeout: z.number().optional().describe('Processing timeout in ms'),
    priority: z.enum(['low', 'medium', 'high']).optional(),
  }).optional(),
});

const ListTemplatesSchema = z.object({
  category: z.string().optional().describe('Filter templates by category'),
  tags: z.array(z.string()).optional().describe('Filter by tags'),
});

const AnalyzeContextSchema = z.object({
  context: z.object({}).describe('Context to analyze'),
  suggest_templates: z.boolean().optional().describe('Suggest matching templates'),
});

const OptimizePerformanceSchema = z.object({
  operation: z.enum(['cache', 'memory', 'processing']).describe('What to optimize'),
  aggressive: z.boolean().optional().describe('Use aggressive optimization'),
});

const CreateTemplateSchema = z.object({
  name: z.string().describe('Template name'),
  description: z.string().describe('Template description'),
  pattern: z.object({}).describe('Cognitive pattern definition'),
  category: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

// Initialize components
const wasmLoader = new FactWasmLoader();
const templateRegistry = new TemplateRegistry();
const cacheManager = new CacheManager();
const performanceMonitor = new PerformanceMonitor();
const cognitiveEngine = new CognitiveTemplateEngine(
  wasmLoader,
  templateRegistry,
  cacheManager,
  performanceMonitor
);

// Create MCP server
const server = new Server(
  {
    name: 'fact-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);

// Handle tool listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'process_template',
        description: 'Process a cognitive template with given context',
        inputSchema: {
          type: 'object',
          properties: {
            template_id: { type: 'string' },
            context: { type: 'object' },
            options: {
              type: 'object',
              properties: {
                cache: { type: 'boolean' },
                timeout: { type: 'number' },
                priority: { type: 'string', enum: ['low', 'medium', 'high'] },
              },
            },
          },
          required: ['template_id', 'context'],
        },
      },
      {
        name: 'list_templates',
        description: 'List available cognitive templates',
        inputSchema: {
          type: 'object',
          properties: {
            category: { type: 'string' },
            tags: { type: 'array', items: { type: 'string' } },
          },
        },
      },
      {
        name: 'analyze_context',
        description: 'Analyze context and suggest appropriate templates',
        inputSchema: {
          type: 'object',
          properties: {
            context: { type: 'object' },
            suggest_templates: { type: 'boolean' },
          },
          required: ['context'],
        },
      },
      {
        name: 'optimize_performance',
        description: 'Optimize FACT performance (cache, memory, processing)',
        inputSchema: {
          type: 'object',
          properties: {
            operation: { type: 'string', enum: ['cache', 'memory', 'processing'] },
            aggressive: { type: 'boolean' },
          },
          required: ['operation'],
        },
      },
      {
        name: 'create_template',
        description: 'Create a new cognitive template',
        inputSchema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            description: { type: 'string' },
            pattern: { type: 'object' },
            category: { type: 'string' },
            tags: { type: 'array', items: { type: 'string' } },
          },
          required: ['name', 'description', 'pattern'],
        },
      },
      {
        name: 'get_metrics',
        description: 'Get performance metrics and statistics',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
});

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'process_template': {
        const params = ProcessTemplateSchema.parse(args);
        const startTime = Date.now();
        
        const result = await cognitiveEngine.processTemplate(
          params.template_id,
          params.context,
          params.options
        );
        
        const duration = Date.now() - startTime;
        performanceMonitor.recordMetric('template_processing', duration);
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                success: true,
                result,
                metrics: {
                  processing_time_ms: duration,
                  cache_hit: result.cached || false,
                },
              }, null, 2),
            },
          ],
        };
      }

      case 'list_templates': {
        const params = ListTemplatesSchema.parse(args);
        const templates = await templateRegistry.listTemplates(params);
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                templates,
                total: templates.length,
              }, null, 2),
            },
          ],
        };
      }

      case 'analyze_context': {
        const params = AnalyzeContextSchema.parse(args);
        const analysis = await cognitiveEngine.analyzeContext(params.context);
        
        if (params.suggest_templates) {
          const suggestions = await templateRegistry.findMatchingTemplates(analysis);
          analysis.suggested_templates = suggestions;
        }
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(analysis, null, 2),
            },
          ],
        };
      }

      case 'optimize_performance': {
        const params = OptimizePerformanceSchema.parse(args);
        const results = await performanceMonitor.optimize(
          params.operation,
          params.aggressive
        );
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                optimization: params.operation,
                results,
                success: true,
              }, null, 2),
            },
          ],
        };
      }

      case 'create_template': {
        const params = CreateTemplateSchema.parse(args);
        const template = await templateRegistry.createTemplate(params);
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                success: true,
                template,
              }, null, 2),
            },
          ],
        };
      }

      case 'get_metrics': {
        const metrics = performanceMonitor.getMetrics();
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(metrics, null, 2),
            },
          ],
        };
      }

      default:
        throw new McpError(
          ErrorCode.MethodNotFound,
          `Unknown tool: ${name}`
        );
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new McpError(
        ErrorCode.InvalidParams,
        `Invalid parameters: ${error.errors.map(e => e.message).join(', ')}`
      );
    }
    throw error;
  }
});

// Handle resource listing
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'fact://templates',
        name: 'Cognitive Templates',
        description: 'Available cognitive templates for processing',
        mimeType: 'application/json',
      },
      {
        uri: 'fact://metrics',
        name: 'Performance Metrics',
        description: 'Real-time performance metrics and statistics',
        mimeType: 'application/json',
      },
      {
        uri: 'fact://cache',
        name: 'Cache Status',
        description: 'Current cache status and statistics',
        mimeType: 'application/json',
      },
    ],
  };
});

// Handle resource reading
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  switch (uri) {
    case 'fact://templates': {
      const templates = await templateRegistry.listTemplates({});
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(templates, null, 2),
          },
        ],
      };
    }

    case 'fact://metrics': {
      const metrics = performanceMonitor.getMetrics();
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(metrics, null, 2),
          },
        ],
      };
    }

    case 'fact://cache': {
      const cacheStats = cacheManager.getStats();
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(cacheStats, null, 2),
          },
        ],
      };
    }

    default:
      throw new McpError(
        ErrorCode.InvalidRequest,
        `Unknown resource: ${uri}`
      );
  }
});

// Initialize and start server
async function main() {
  try {
    // Initialize WASM
    logger.info('Initializing FACT WASM module...');
    await wasmLoader.initialize();
    
    // Load default templates
    logger.info('Loading cognitive templates...');
    await templateRegistry.loadDefaultTemplates();
    
    // Start server with stdio transport
    const transport = new StdioServerTransport();
    await server.connect(transport);
    
    logger.info('FACT MCP Server started successfully');
    logger.info('Ready to process cognitive templates');
  } catch (error) {
    logger.error('Failed to start FACT MCP Server:', error);
    process.exit(1);
  }
}

// Handle shutdown
process.on('SIGINT', async () => {
  logger.info('Shutting down FACT MCP Server...');
  await cacheManager.flush();
  await performanceMonitor.saveMetrics();
  process.exit(0);
});

// Start server
main().catch((error) => {
  logger.error('Fatal error:', error);
  process.exit(1);
});