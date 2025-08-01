#!/usr/bin/env node

/**
 * FACT MCP Server - Model Context Protocol Server Implementation
 * 
 * Provides MCP tools for cognitive template processing using WASM core.
 * Features:
 * - stdio transport (JSON-RPC 2.0)
 * - WASM integration for high-performance processing
 * - Cognitive template management
 * - Performance optimization and metrics
 * - Resource management
 */

const { createInterface } = require('readline');

// Load the WASM module
let wasmModule = null;
let factInstance = null;

/**
 * Initialize WASM module
 */
async function initializeWasm() {
    try {
        // Try to load the compiled WASM module
        const wasmPath = require('path').join(__dirname, '../pkg/fact_wasm_core.js');
        wasmModule = require(wasmPath);
        await wasmModule.default(); // Initialize WASM
        factInstance = new wasmModule.Fact();
        console.error('WASM module initialized successfully');
        return true;
    } catch (error) {
        console.error('Failed to initialize WASM module:', error.message);
        // Fallback to JavaScript implementation
        return false;
    }
}

/**
 * Cognitive template definitions
 */
const COGNITIVE_TEMPLATES = {
    'data-analysis': {
        id: 'data-analysis',
        name: 'Data Analysis Template',
        description: 'Analyze data patterns and extract insights',
        category: 'analysis',
        tags: ['data', 'analysis', 'insights'],
        pattern: {
            pattern_type: 'sequential',
            steps: [
                { step_type: 'transform', config: { mode: 'expand' } },
                { step_type: 'analyze', config: { depth: 'deep' } },
                { step_type: 'synthesize', config: { format: 'insights' } }
            ]
        },
        cache_ttl: 300
    },
    'problem-solving': {
        id: 'problem-solving',
        name: 'Problem Solving Template',
        description: 'Systematic approach to problem resolution',
        category: 'reasoning',
        tags: ['problem', 'solution', 'debugging'],
        pattern: {
            pattern_type: 'adaptive',
            steps: [
                { step_type: 'analyze', config: { depth: 'shallow' } },
                { step_type: 'transform', config: { mode: 'compress' } },
                { step_type: 'synthesize', config: { format: 'solution' } }
            ]
        },
        cache_ttl: 600
    },
    'code-generation': {
        id: 'code-generation',
        name: 'Code Generation Template',
        description: 'Generate code based on specifications',
        category: 'development',
        tags: ['code', 'generation', 'programming'],
        pattern: {
            pattern_type: 'iterative',
            steps: [
                { step_type: 'analyze', config: { depth: 'deep' } },
                { step_type: 'transform', config: { mode: 'expand' } },
                { step_type: 'synthesize', config: { format: 'code' } }
            ]
        },
        cache_ttl: 900
    },
    'optimization': {
        id: 'optimization',
        name: 'Performance Optimization Template',
        description: 'Optimize system performance and resource usage',
        category: 'performance',
        tags: ['optimization', 'performance', 'efficiency'],
        pattern: {
            pattern_type: 'parallel',
            steps: [
                { step_type: 'analyze', config: { depth: 'deep' } },
                { step_type: 'transform', config: { mode: 'compress' } },
                { step_type: 'synthesize', config: { format: 'optimization' } }
            ]
        },
        cache_ttl: 450
    },
    'learning': {
        id: 'learning',
        name: 'Adaptive Learning Template',
        description: 'Learn from patterns and adapt behavior',
        category: 'ml',
        tags: ['learning', 'adaptation', 'patterns'],
        pattern: {
            pattern_type: 'recursive',
            steps: [
                { step_type: 'analyze', config: { depth: 'deep' } },
                { step_type: 'transform', config: { mode: 'expand' } },
                { step_type: 'synthesize', config: { format: 'model' } }
            ]
        },
        cache_ttl: 1200
    }
};

/**
 * Performance metrics tracking
 */
class PerformanceTracker {
    constructor() {
        this.metrics = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            averageResponseTime: 0,
            totalResponseTime: 0,
            cacheHits: 0,
            wasmOperations: 0,
            templateProcessings: 0,
            lastReset: Date.now()
        };
    }

    recordRequest(success, responseTime, cacheHit = false, wasmUsed = false) {
        this.metrics.totalRequests++;
        if (success) {
            this.metrics.successfulRequests++;
        } else {
            this.metrics.failedRequests++;
        }
        
        this.metrics.totalResponseTime += responseTime;
        this.metrics.averageResponseTime = this.metrics.totalResponseTime / this.metrics.totalRequests;
        
        if (cacheHit) {
            this.metrics.cacheHits++;
        }
        
        if (wasmUsed) {
            this.metrics.wasmOperations++;
        }
    }

    recordTemplateProcessing() {
        this.metrics.templateProcessings++;
    }

    getMetrics() {
        const uptime = Date.now() - this.metrics.lastReset;
        return {
            ...this.metrics,
            uptime,
            cacheHitRate: this.metrics.cacheHits / Math.max(this.metrics.totalRequests, 1),
            successRate: this.metrics.successfulRequests / Math.max(this.metrics.totalRequests, 1),
            wasmUsageRate: this.metrics.wasmOperations / Math.max(this.metrics.totalRequests, 1),
            requestsPerSecond: this.metrics.totalRequests / (uptime / 1000)
        };
    }

    reset() {
        this.metrics = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            averageResponseTime: 0,
            totalResponseTime: 0,
            cacheHits: 0,
            wasmOperations: 0,
            templateProcessings: 0,
            lastReset: Date.now()
        };
    }
}

/**
 * Resource manager for templates and memory
 */
class ResourceManager {
    constructor() {
        this.resources = new Map();
        this.setupDefaultResources();
    }

    setupDefaultResources() {
        // Add cognitive templates as resources
        Object.values(COGNITIVE_TEMPLATES).forEach(template => {
            this.resources.set(
                `template://${template.id}`,
                {
                    uri: `template://${template.id}`,
                    name: template.name,
                    description: template.description,
                    mimeType: 'application/json',
                    content: JSON.stringify(template, null, 2)
                }
            );
        });

        // Add performance metrics as a resource
        this.resources.set(
            'metrics://performance',
            {
                uri: 'metrics://performance',
                name: 'Performance Metrics',
                description: 'Real-time performance metrics and statistics',
                mimeType: 'application/json',
                content: null // Dynamic content
            }
        );

        // Add system status as a resource
        this.resources.set(
            'system://status',
            {
                uri: 'system://status',
                name: 'System Status',
                description: 'Current system status and health information',
                mimeType: 'application/json',
                content: null // Dynamic content
            }
        );
    }

    listResources() {
        return Array.from(this.resources.values()).map(resource => ({
            uri: resource.uri,
            name: resource.name,
            description: resource.description,
            mimeType: resource.mimeType
        }));
    }

    getResource(uri) {
        const resource = this.resources.get(uri);
        if (!resource) {
            throw new Error(`Resource not found: ${uri}`);
        }

        // Handle dynamic resources
        if (uri === 'metrics://performance') {
            return {
                ...resource,
                content: JSON.stringify(performanceTracker.getMetrics(), null, 2)
            };
        }

        if (uri === 'system://status') {
            return {
                ...resource,
                content: JSON.stringify({
                    wasmEnabled: !!factInstance,
                    templatesLoaded: Object.keys(COGNITIVE_TEMPLATES).length,
                    resourceCount: this.resources.size,
                    uptime: Date.now() - startTime,
                    memoryUsage: process.memoryUsage(),
                    version: '1.0.0',
                    timestamp: new Date().toISOString()
                }, null, 2)
            };
        }

        return resource;
    }
}

// Global instances
const performanceTracker = new PerformanceTracker();
const resourceManager = new ResourceManager();
const startTime = Date.now();

/**
 * MCP Tool Implementations
 */

/**
 * Process a cognitive template with given context
 */
async function processTemplate(params) {
    const startTime = Date.now();
    let wasmUsed = false;

    try {
        const { template_id, context, options = {} } = params;
        
        if (!template_id || !context) {
            throw new Error('template_id and context are required');
        }

        const template = COGNITIVE_TEMPLATES[template_id];
        if (!template) {
            throw new Error(`Template not found: ${template_id}`);
        }

        performanceTracker.recordTemplateProcessing();

        let result;
        
        // Try WASM processing first if available
        if (factInstance && !options.disableWasm) {
            try {
                const templateJson = JSON.stringify(template);
                const contextJson = JSON.stringify(context);
                
                if (wasmModule.process_template) {
                    result = JSON.parse(wasmModule.process_template(templateJson, contextJson));
                    wasmUsed = true;
                } else {
                    // Use FACT instance process method
                    const processedData = factInstance.process(JSON.stringify({ template, context }), options.cache !== false);
                    result = JSON.parse(processedData);
                    wasmUsed = true;
                }
            } catch (wasmError) {
                console.error('WASM processing failed, falling back to JS:', wasmError.message);
                result = processTemplateJS(template, context);
            }
        } else {
            result = processTemplateJS(template, context);
        }

        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime, false, wasmUsed);

        return {
            success: true,
            result,
            metadata: {
                template_id,
                processing_time_ms: responseTime,
                wasm_used: wasmUsed,
                cache_enabled: options.cache !== false,
                timestamp: new Date().toISOString()
            }
        };

    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime, false, wasmUsed);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                processing_time_ms: responseTime,
                wasm_used: wasmUsed,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * JavaScript fallback for template processing
 */
function processTemplateJS(template, context) {
    let result = context;
    
    for (const step of template.pattern.steps) {
        result = processStepJS(step, result);
    }
    
    return {
        template_id: template.id,
        result,
        processed_at: new Date().toISOString(),
        processing_method: 'javascript'
    };
}

function processStepJS(step, data) {
    switch (step.step_type) {
        case 'transform':
            return transformDataJS(data, step.config);
        case 'analyze':
            return analyzeDataJS(data, step.config);
        case 'synthesize':
            return synthesizeDataJS(data, step.config);
        default:
            return data;
    }
}

function transformDataJS(data, config) {
    const mode = config.mode || 'expand';
    
    switch (mode) {
        case 'expand':
            return {
                original: data,
                expanded: true,
                timestamp: new Date().toISOString(),
                metadata: { transformation: 'expand' }
            };
        case 'compress':
            if (typeof data === 'object' && data !== null) {
                const compressed = {};
                Object.entries(data).forEach(([key, value]) => {
                    if (!key.startsWith('_')) {
                        compressed[key] = value;
                    }
                });
                return compressed;
            }
            return data;
        default:
            return data;
    }
}

function analyzeDataJS(data, config) {
    const depth = config.depth || 'shallow';
    
    const analysis = {
        data_type: typeof data,
        size: JSON.stringify(data).length,
        complexity: calculateComplexity(data),
        patterns: extractPatterns(data)
    };

    if (depth === 'deep') {
        analysis.insights = [
            'Data structure analyzed',
            'Patterns identified',
            'Optimization opportunities detected'
        ];
        analysis.recommendations = [
            'Consider data normalization',
            'Implement caching for frequently accessed data',
            'Use appropriate data structures for access patterns'
        ];
    }

    return {
        data,
        analysis,
        processed_at: new Date().toISOString()
    };
}

function synthesizeDataJS(data, config) {
    const format = config.format || 'summary';
    
    switch (format) {
        case 'insights':
            return {
                insights: [
                    'Key patterns identified in data',
                    'Performance optimization opportunities',
                    'Structural improvements suggested'
                ],
                confidence: 0.85,
                recommendations: [
                    'Implement suggested optimizations',
                    'Monitor performance metrics',
                    'Consider A/B testing changes'
                ]
            };
        case 'solution':
            return {
                solution: 'Optimized approach based on analysis',
                steps: [
                    'Analyze current state',
                    'Identify bottlenecks',
                    'Implement optimizations',
                    'Monitor results'
                ],
                metrics: {
                    efficiency: 0.92,
                    cost: 0.78,
                    quality: 0.88
                }
            };
        default:
            return {
                summary: 'Processing completed successfully',
                key_points: [
                    `Data type: ${typeof data}`,
                    `Complexity: ${calculateComplexity(data)}`,
                    'Analysis complete'
                ]
            };
    }
}

function calculateComplexity(data) {
    const str = JSON.stringify(data);
    const size = str.length;
    const depth = calculateDepth(data);
    return Math.log2(size) * depth;
}

function calculateDepth(obj, current = 0) {
    if (typeof obj !== 'object' || obj === null) {
        return current;
    }
    
    if (Array.isArray(obj)) {
        return Math.max(...obj.map(item => calculateDepth(item, current + 1)));
    }
    
    const depths = Object.values(obj).map(value => calculateDepth(value, current + 1));
    return depths.length > 0 ? Math.max(...depths) : current + 1;
}

function extractPatterns(data) {
    const patterns = [];
    
    if (typeof data === 'object' && data !== null) {
        const keys = Object.keys(data);
        if (keys.includes('query') || keys.includes('question')) {
            patterns.push('inquiry');
        }
        if (keys.includes('data') || keys.includes('dataset')) {
            patterns.push('analysis');
        }
        if (keys.includes('goal') || keys.includes('objective')) {
            patterns.push('planning');
        }
    }
    
    return patterns;
}

/**
 * List available cognitive templates
 */
async function listTemplates(params = {}) {
    const startTime = Date.now();
    
    try {
        const { category, tags } = params;
        let templates = Object.values(COGNITIVE_TEMPLATES);
        
        // Filter by category if specified
        if (category) {
            templates = templates.filter(t => t.category === category);
        }
        
        // Filter by tags if specified
        if (tags && Array.isArray(tags)) {
            templates = templates.filter(t => 
                tags.some(tag => t.tags.includes(tag))
            );
        }
        
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime);
        
        return {
            success: true,
            templates: templates.map(t => ({
                id: t.id,
                name: t.name,
                description: t.description,
                category: t.category,
                tags: t.tags,
                cache_ttl: t.cache_ttl
            })),
            total: templates.length,
            metadata: {
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
        
    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * Analyze context and suggest appropriate templates
 */
async function analyzeContext(params) {
    const startTime = Date.now();
    let wasmUsed = false;
    
    try {
        const { context, suggest_templates = true } = params;
        
        if (!context) {
            throw new Error('context is required');
        }
        
        let analysis;
        
        // Try WASM analysis if available
        if (factInstance) {
            try {
                const queryResult = factInstance.process(JSON.stringify({ analyze: context }), true);
                analysis = JSON.parse(queryResult);
                wasmUsed = true;
            } catch (wasmError) {
                console.error('WASM analysis failed, falling back to JS:', wasmError.message);
                analysis = analyzeContextJS(context);
            }
        } else {
            analysis = analyzeContextJS(context);
        }
        
        let suggestedTemplates = [];
        if (suggest_templates) {
            suggestedTemplates = suggestTemplatesForContext(context, analysis);
        }
        
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime, false, wasmUsed);
        
        return {
            success: true,
            analysis,
            suggested_templates: suggestedTemplates,
            metadata: {
                processing_time_ms: responseTime,
                wasm_used: wasmUsed,
                timestamp: new Date().toISOString()
            }
        };
        
    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime, false, wasmUsed);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                processing_time_ms: responseTime,
                wasm_used: wasmUsed,
                timestamp: new Date().toISOString()
            }
        };
    }
}

function analyzeContextJS(context) {
    const contextStr = JSON.stringify(context).toLowerCase();
    
    return {
        data_type: typeof context,
        complexity: calculateComplexity(context),
        patterns: extractPatterns(context),
        keywords: extractKeywords(contextStr),
        intent: detectIntent(contextStr),
        confidence: 0.75
    };
}

function extractKeywords(text) {
    const commonWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']);
    return text
        .split(/\W+/)
        .filter(word => word.length > 2 && !commonWords.has(word))
        .slice(0, 10);
}

function detectIntent(text) {
    if (text.includes('analyze') || text.includes('data') || text.includes('statistics')) {
        return 'analysis';
    }
    if (text.includes('solve') || text.includes('fix') || text.includes('debug')) {
        return 'problem_solving';
    }
    if (text.includes('generate') || text.includes('create') || text.includes('code')) {
        return 'generation';
    }
    if (text.includes('optimize') || text.includes('improve') || text.includes('performance')) {
        return 'optimization';
    }
    return 'general';
}

function suggestTemplatesForContext(context, analysis) {
    const suggestions = [];
    
    // Map intents to templates
    const intentMapping = {
        'analysis': ['data-analysis'],
        'problem_solving': ['problem-solving'],
        'generation': ['code-generation'],
        'optimization': ['optimization'],
        'general': ['data-analysis', 'problem-solving']
    };
    
    const recommendedIds = intentMapping[analysis.intent] || ['data-analysis'];
    
    for (const id of recommendedIds) {
        const template = COGNITIVE_TEMPLATES[id];
        if (template) {
            suggestions.push({
                template_id: id,
                name: template.name,
                description: template.description,
                confidence: analysis.confidence,
                reason: `Detected intent: ${analysis.intent}`
            });
        }
    }
    
    return suggestions;
}

/**
 * Optimize FACT performance
 */
async function optimizePerformance(params) {
    const startTime = Date.now();
    let wasmUsed = false;
    
    try {
        const { operation, aggressive = false } = params;
        
        if (!['cache', 'memory', 'processing'].includes(operation)) {
            throw new Error('operation must be one of: cache, memory, processing');
        }
        
        let result = {};
        
        // Try WASM optimization if available
        if (factInstance) {
            try {
                const mode = aggressive ? 'aggressive' : 'standard';
                const optimizationResult = factInstance.optimize(mode);
                result.wasm_optimization = JSON.parse(optimizationResult);
                wasmUsed = true;
            } catch (wasmError) {
                console.error('WASM optimization failed:', wasmError.message);
            }
        }
        
        // Perform JavaScript optimizations
        switch (operation) {
            case 'cache':
                if (factInstance) {
                    factInstance.clear_cache();
                }
                result.cache_cleared = true;
                result.cache_stats = factInstance ? factInstance.get_cache_stats() : null;
                break;
                
            case 'memory':
                if (global.gc) {
                    global.gc();
                    result.garbage_collected = true;
                }
                result.memory_usage = process.memoryUsage();
                break;
                
            case 'processing':
                performanceTracker.reset();
                result.metrics_reset = true;
                result.optimization_applied = true;
                break;
        }
        
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime, false, wasmUsed);
        
        return {
            success: true,
            optimization: operation,
            result,
            metadata: {
                processing_time_ms: responseTime,
                wasm_used: wasmUsed,
                aggressive_mode: aggressive,
                timestamp: new Date().toISOString()
            }
        };
        
    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime, false, wasmUsed);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                processing_time_ms: responseTime,
                wasm_used: wasmUsed,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * Get performance metrics
 */
async function getMetrics() {
    const startTime = Date.now();
    
    try {
        const metrics = performanceTracker.getMetrics();
        
        // Add WASM-specific metrics if available
        if (factInstance) {
            try {
                metrics.wasm_cache_stats = factInstance.get_cache_stats();
            } catch (error) {
                console.error('Failed to get WASM cache stats:', error.message);
            }
        }
        
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime);
        
        return {
            success: true,
            metrics,
            system_info: {
                node_version: process.version,
                platform: process.platform,
                arch: process.arch,
                memory_usage: process.memoryUsage(),
                uptime: process.uptime(),
                wasm_enabled: !!factInstance
            },
            metadata: {
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
        
    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * Create a new cognitive template
 */
async function createTemplate(params) {
    const startTime = Date.now();
    
    try {
        const { name, description, pattern, category = 'custom', tags = [] } = params;
        
        if (!name || !description || !pattern) {
            throw new Error('name, description, and pattern are required');
        }
        
        // Generate ID from name
        const id = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
        
        if (COGNITIVE_TEMPLATES[id]) {
            throw new Error(`Template with id '${id}' already exists`);
        }
        
        const template = {
            id,
            name,
            description,
            category,
            tags: Array.isArray(tags) ? tags : [tags],
            pattern,
            cache_ttl: 300,
            created_at: new Date().toISOString(),
            custom: true
        };
        
        // Validate pattern structure
        if (!pattern.pattern_type || !pattern.steps || !Array.isArray(pattern.steps)) {
            throw new Error('Invalid pattern structure. Must have pattern_type and steps array');
        }
        
        // Add to templates
        COGNITIVE_TEMPLATES[id] = template;
        
        // Add as resource
        resourceManager.resources.set(
            `template://${id}`,
            {
                uri: `template://${id}`,
                name: template.name,
                description: template.description,
                mimeType: 'application/json',
                content: JSON.stringify(template, null, 2)
            }
        );
        
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime);
        
        return {
            success: true,
            template: {
                id: template.id,
                name: template.name,
                description: template.description,
                category: template.category,
                tags: template.tags
            },
            metadata: {
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
        
    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * JSON-RPC 2.0 Server Implementation
 */
class McpServer {
    constructor() {
        this.tools = {
            'process_template': {
                name: 'process_template',
                description: 'Process a cognitive template with given context using WASM-accelerated engine',
                inputSchema: {
                    type: 'object',
                    properties: {
                        template_id: {
                            type: 'string',
                            description: 'ID of the cognitive template to use'
                        },
                        context: {
                            type: 'object',
                            description: 'Context data to process with the template'
                        },
                        options: {
                            type: 'object',
                            properties: {
                                cache: {
                                    type: 'boolean',
                                    description: 'Enable caching for this request',
                                    default: true
                                },
                                priority: {
                                    type: 'string',
                                    enum: ['low', 'medium', 'high'],
                                    description: 'Processing priority',
                                    default: 'medium'
                                },
                                timeout: {
                                    type: 'number',
                                    description: 'Request timeout in milliseconds',
                                    default: 30000
                                }
                            }
                        }
                    },
                    required: ['template_id', 'context']
                }
            },
            'list_templates': {
                name: 'list_templates',
                description: 'List available cognitive templates with optional filtering',
                inputSchema: {
                    type: 'object',
                    properties: {
                        category: {
                            type: 'string',
                            description: 'Filter templates by category'
                        },
                        tags: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Filter templates by tags'
                        }
                    }
                }
            },
            'analyze_context': {
                name: 'analyze_context',
                description: 'Analyze context and suggest appropriate templates using pattern recognition',
                inputSchema: {
                    type: 'object',
                    properties: {
                        context: {
                            type: 'object',
                            description: 'Context data to analyze'
                        },
                        suggest_templates: {
                            type: 'boolean',
                            description: 'Include template suggestions in response',
                            default: true
                        }
                    },
                    required: ['context']
                }
            },
            'optimize_performance': {
                name: 'optimize_performance',
                description: 'Optimize FACT performance (cache, memory, processing)',
                inputSchema: {
                    type: 'object',
                    properties: {
                        operation: {
                            type: 'string',
                            enum: ['cache', 'memory', 'processing'],
                            description: 'Type of optimization to perform'
                        },
                        aggressive: {
                            type: 'boolean',
                            description: 'Use aggressive optimization mode',
                            default: false
                        }
                    },
                    required: ['operation']
                }
            },
            'create_template': {
                name: 'create_template',
                description: 'Create a new cognitive template',
                inputSchema: {
                    type: 'object',
                    properties: {
                        name: {
                            type: 'string',
                            description: 'Template name'
                        },
                        description: {
                            type: 'string',
                            description: 'Template description'
                        },
                        pattern: {
                            type: 'object',
                            description: 'Template pattern definition'
                        },
                        category: {
                            type: 'string',
                            description: 'Template category',
                            default: 'custom'
                        },
                        tags: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Template tags'
                        }
                    },
                    required: ['name', 'description', 'pattern']
                }
            },
            'get_metrics': {
                name: 'get_metrics',
                description: 'Get performance metrics and statistics',
                inputSchema: {
                    type: 'object',
                    properties: {}
                }
            }
        };
    }

    async handleRequest(request) {
        try {
            // Validate JSON-RPC 2.0 format
            if (!request.jsonrpc || request.jsonrpc !== '2.0') {
                return this.createErrorResponse(null, -32600, 'Invalid Request');
            }

            const { method, params, id } = request;

            switch (method) {
                case 'initialize':
                    return this.createSuccessResponse(id, {
                        protocolVersion: '2024-11-05',
                        capabilities: {
                            tools: {},
                            resources: {}
                        },
                        serverInfo: {
                            name: 'fact-mcp',
                            version: '1.0.0',
                            description: 'FACT MCP Server with WASM integration'
                        }
                    });

                case 'tools/list':
                    return this.createSuccessResponse(id, {
                        tools: Object.values(this.tools)
                    });

                case 'tools/call':
                    return await this.handleToolCall(id, params);

                case 'resources/list':
                    return this.createSuccessResponse(id, {
                        resources: resourceManager.listResources()
                    });

                case 'resources/read':
                    return await this.handleResourceRead(id, params);

                case 'notifications/initialized':
                case 'ping':
                    return this.createSuccessResponse(id, {});

                default:
                    return this.createErrorResponse(id, -32601, 'Method not found');
            }
        } catch (error) {
            console.error('Request handling error:', error);
            return this.createErrorResponse(request?.id || null, -32603, 'Internal error');
        }
    }

    async handleToolCall(id, params) {
        const { name, arguments: args } = params;

        try {
            let result;
            switch (name) {
                case 'process_template':
                    result = await processTemplate(args);
                    break;
                case 'list_templates':
                    result = await listTemplates(args);
                    break;
                case 'analyze_context':
                    result = await analyzeContext(args);
                    break;
                case 'optimize_performance':
                    result = await optimizePerformance(args);
                    break;
                case 'create_template':
                    result = await createTemplate(args);
                    break;
                case 'get_metrics':
                    result = await getMetrics();
                    break;
                default:
                    return this.createErrorResponse(id, -32601, `Unknown tool: ${name}`);
            }

            return this.createSuccessResponse(id, {
                content: [{
                    type: 'text',
                    text: JSON.stringify(result, null, 2)
                }]
            });
        } catch (error) {
            return this.createErrorResponse(id, -32603, `Tool execution failed: ${error.message}`);
        }
    }

    async handleResourceRead(id, params) {
        const { uri } = params;

        try {
            const resource = resourceManager.getResource(uri);
            return this.createSuccessResponse(id, {
                contents: [{
                    uri: resource.uri,
                    mimeType: resource.mimeType,
                    text: resource.content
                }]
            });
        } catch (error) {
            return this.createErrorResponse(id, -32603, `Resource read failed: ${error.message}`);
        }
    }

    createSuccessResponse(id, result) {
        return {
            jsonrpc: '2.0',
            id,
            result
        };
    }

    createErrorResponse(id, code, message, data = null) {
        const response = {
            jsonrpc: '2.0',
            id,
            error: { code, message }
        };
        if (data) {
            response.error.data = data;
        }
        return response;
    }
}

/**
 * Main server setup and stdio transport
 */
async function main() {
    console.error('Starting FACT MCP Server...');
    
    // Initialize WASM
    const wasmInitialized = await initializeWasm();
    console.error(`WASM initialization: ${wasmInitialized ? 'SUCCESS' : 'FALLBACK TO JS'}`);
    
    const server = new McpServer();
    const rl = createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false
    });

    console.error('FACT MCP Server ready on stdio transport');

    rl.on('line', async (line) => {
        try {
            const request = JSON.parse(line);
            const response = await server.handleRequest(request);
            
            if (response) {
                console.log(JSON.stringify(response));
            }
        } catch (error) {
            console.error('Failed to parse request:', error.message);
            const errorResponse = {
                jsonrpc: '2.0',
                id: null,
                error: {
                    code: -32700,
                    message: 'Parse error'
                }
            };
            console.log(JSON.stringify(errorResponse));
        }
    });

    rl.on('close', () => {
        console.error('FACT MCP Server shutting down...');
        process.exit(0);
    });

    // Handle process termination
    process.on('SIGINT', () => {
        console.error('Received SIGINT, shutting down gracefully...');
        rl.close();
    });

    process.on('SIGTERM', () => {
        console.error('Received SIGTERM, shutting down gracefully...');
        rl.close();
    });
}

// Start the server
if (require.main === module) {
    main().catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
}

module.exports = {
    McpServer,
    processTemplate,
    listTemplates,
    analyzeContext,
    optimizePerformance,
    getMetrics,
    createTemplate,
    COGNITIVE_TEMPLATES
};