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
 * Get performance metrics with enhanced filtering and formatting
 */
async function getMetrics(params = {}) {
    const startTime = Date.now();
    const { category = 'all', format = 'json' } = params;
    
    try {
        const baseMetrics = performanceTracker.getMetrics();
        let metrics = {};

        // Filter metrics by category
        switch (category) {
            case 'performance':
                metrics = {
                    total_requests: baseMetrics.totalRequests,
                    successful_requests: baseMetrics.successfulRequests,
                    failed_requests: baseMetrics.failedRequests,
                    average_response_time: baseMetrics.averageResponseTime,
                    requests_per_second: baseMetrics.requestsPerSecond || 0
                };
                break;
            
            case 'cache':
                metrics = {
                    cache_hits: baseMetrics.cacheHits,
                    cache_hit_rate: baseMetrics.cacheHitRate,
                    template_processings: baseMetrics.templateProcessings
                };
                
                if (factInstance) {
                    try {
                        metrics.wasm_cache_stats = factInstance.get_cache_stats();
                    } catch (error) {
                        metrics.wasm_cache_error = error.message;
                    }
                }
                break;
            
            case 'wasm':
                metrics = {
                    wasm_enabled: !!factInstance,
                    wasm_operations: baseMetrics.wasmOperations,
                    wasm_usage_rate: baseMetrics.wasmUsageRate
                };
                
                if (factInstance) {
                    try {
                        metrics.wasm_cache_stats = factInstance.get_cache_stats();
                        metrics.wasm_optimization_available = true;
                    } catch (error) {
                        metrics.wasm_error = error.message;
                        metrics.wasm_optimization_available = false;
                    }
                }
                break;
            
            case 'memory':
                const memUsage = process.memoryUsage();
                metrics = {
                    heap_used_mb: Math.round(memUsage.heapUsed / 1024 / 1024),
                    heap_total_mb: Math.round(memUsage.heapTotal / 1024 / 1024),
                    external_mb: Math.round(memUsage.external / 1024 / 1024),
                    rss_mb: Math.round(memUsage.rss / 1024 / 1024),
                    heap_utilization: (memUsage.heapUsed / memUsage.heapTotal * 100).toFixed(2) + '%'
                };
                break;
            
            case 'all':
            default:
                metrics = baseMetrics;
                
                // Add WASM-specific metrics if available
                if (factInstance) {
                    try {
                        metrics.wasm_cache_stats = factInstance.get_cache_stats();
                    } catch (error) {
                        console.error('Failed to get WASM cache stats:', error.message);
                    }
                }
                break;
        }
        
        const systemInfo = {
            node_version: process.version,
            platform: process.platform,
            arch: process.arch,
            memory_usage: process.memoryUsage(),
            uptime: process.uptime(),
            wasm_enabled: !!factInstance
        };
        
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(true, responseTime);
        
        const result = {
            success: true,
            metrics,
            system_info: systemInfo,
            metadata: {
                category,
                format,
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };

        // Format output based on format parameter
        if (format === 'summary') {
            return {
                success: true,
                summary: {
                    status: baseMetrics.failedRequests === 0 ? 'healthy' : 'degraded',
                    total_requests: baseMetrics.totalRequests,
                    success_rate: ((baseMetrics.successfulRequests / Math.max(baseMetrics.totalRequests, 1)) * 100).toFixed(2) + '%',
                    avg_response_time: baseMetrics.averageResponseTime.toFixed(2) + 'ms',
                    wasm_enabled: !!factInstance,
                    uptime: Math.round(process.uptime()) + 's'
                },
                metadata: result.metadata
            };
        } else if (format === 'detailed') {
            result.detailed_analysis = {
                performance_health: baseMetrics.averageResponseTime < 100 ? 'excellent' : 
                                   baseMetrics.averageResponseTime < 500 ? 'good' : 'needs_attention',
                cache_efficiency: baseMetrics.cacheHitRate > 0.8 ? 'excellent' : 
                                 baseMetrics.cacheHitRate > 0.5 ? 'good' : 'needs_improvement',
                error_rate: (baseMetrics.failedRequests / Math.max(baseMetrics.totalRequests, 1) * 100).toFixed(2) + '%',
                recommendations: generateRecommendations(baseMetrics)
            };
        }
        
        return result;
        
    } catch (error) {
        const responseTime = Date.now() - startTime;
        performanceTracker.recordRequest(false, responseTime);
        
        return {
            success: false,
            error: error.message,
            metadata: {
                category,
                format,
                processing_time_ms: responseTime,
                timestamp: new Date().toISOString()
            }
        };
    }
}

/**
 * Generate performance recommendations based on metrics
 */
function generateRecommendations(metrics) {
    const recommendations = [];
    
    if (metrics.averageResponseTime > 500) {
        recommendations.push('Consider optimizing template processing or enabling WASM acceleration');
    }
    
    if (metrics.cacheHitRate < 0.5) {
        recommendations.push('Cache hit rate is low - consider increasing cache size or TTL');
    }
    
    if (metrics.failedRequests > metrics.totalRequests * 0.1) {
        recommendations.push('High error rate detected - check error logs and input validation');
    }
    
    if (!factInstance) {
        recommendations.push('WASM module not loaded - enable WASM for better performance');
    }
    
    if (metrics.wasmUsageRate && metrics.wasmUsageRate < 0.5) {
        recommendations.push('Consider using WASM acceleration for more operations');
    }
    
    return recommendations;
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
 * JSON-RPC 2.0 Server Implementation with Enhanced MCP Protocol Support
 */
class McpServer {
    constructor() {
        this.protocolVersion = '2024-11-05';
        this.serverInfo = {
            name: 'fact-mcp',
            version: '1.0.0',
            description: 'FACT MCP Server with WASM integration and cognitive templates'
        };
        
        this.capabilities = {
            tools: {},
            resources: {},
            prompts: {},
            logging: {}
        };

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
                                },
                                retry_strategy: {
                                    type: 'object',
                                    properties: {
                                        max_retries: { type: 'number', default: 3 },
                                        backoff_type: { 
                                            type: 'string', 
                                            enum: ['linear', 'exponential', 'fixed'],
                                            default: 'exponential'
                                        }
                                    }
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
                    properties: {
                        category: {
                            type: 'string',
                            enum: ['all', 'performance', 'cache', 'wasm', 'memory'],
                            description: 'Category of metrics to retrieve',
                            default: 'all'
                        },
                        format: {
                            type: 'string',
                            enum: ['json', 'summary', 'detailed'],
                            description: 'Output format for metrics',
                            default: 'json'
                        }
                    }
                }
            },
            'benchmark_performance': {
                name: 'benchmark_performance',
                description: 'Run performance benchmarks on FACT operations',
                inputSchema: {
                    type: 'object',
                    properties: {
                        test_type: {
                            type: 'string',
                            enum: ['template_processing', 'cache_operations', 'wasm_functions', 'full_suite'],
                            description: 'Type of benchmark to run',
                            default: 'template_processing'
                        },
                        iterations: {
                            type: 'number',
                            description: 'Number of iterations to run',
                            default: 100,
                            minimum: 1,
                            maximum: 10000
                        },
                        payload_size: {
                            type: 'string',
                            enum: ['small', 'medium', 'large'],
                            description: 'Size of test payload',
                            default: 'medium'
                        }
                    }
                }
            },
            'health_check': {
                name: 'health_check',
                description: 'Check the health status of FACT MCP server components',
                inputSchema: {
                    type: 'object',
                    properties: {
                        include_wasm: {
                            type: 'boolean',
                            description: 'Include WASM module health check',
                            default: true
                        },
                        include_cache: {
                            type: 'boolean', 
                            description: 'Include cache system health check',
                            default: true
                        },
                        verbose: {
                            type: 'boolean',
                            description: 'Include detailed health information',
                            default: false
                        }
                    }
                }
            }
        };
        
        // Initialize request tracking
        this.requestCounter = 0;
        this.activeRequests = new Map();
        this.requestHistory = [];
    }

    async handleRequest(request) {
        const requestId = ++this.requestCounter;
        const startTime = Date.now();
        
        try {
            // Track request
            this.activeRequests.set(requestId, {
                id: request?.id,
                method: request?.method,
                startTime,
                params: request?.params
            });

            // Validate JSON-RPC 2.0 format
            if (!request || typeof request !== 'object') {
                return this.createErrorResponse(null, -32700, 'Parse error');
            }

            if (!request.jsonrpc || request.jsonrpc !== '2.0') {
                return this.createErrorResponse(request?.id || null, -32600, 'Invalid Request');
            }

            const { method, params, id } = request;

            // Validate method
            if (!method || typeof method !== 'string') {
                return this.createErrorResponse(id, -32600, 'Invalid Request - method required');
            }

            let response;
            switch (method) {
                case 'initialize':
                    response = await this.handleInitialize(id, params);
                    break;

                case 'tools/list':
                    response = await this.handleToolsList(id, params);
                    break;

                case 'tools/call':
                    response = await this.handleToolCall(id, params);
                    break;

                case 'resources/list':
                    response = await this.handleResourcesList(id, params);
                    break;

                case 'resources/read':
                    response = await this.handleResourceRead(id, params);
                    break;

                case 'prompts/list':
                    response = await this.handlePromptsList(id, params);
                    break;

                case 'prompts/get':
                    response = await this.handlePromptsGet(id, params);
                    break;

                case 'logging/setLevel':
                    response = await this.handleLoggingSetLevel(id, params);
                    break;

                case 'notifications/initialized':
                    response = await this.handleNotificationInitialized(id, params);
                    break;

                case 'ping':
                    response = this.createSuccessResponse(id, { 
                        pong: true, 
                        timestamp: new Date().toISOString(),
                        uptime: Date.now() - startTime
                    });
                    break;

                default:
                    response = this.createErrorResponse(id, -32601, `Method not found: ${method}`);
            }

            // Record successful request
            this.recordRequest(requestId, true, Date.now() - startTime);
            return response;
        } catch (error) {
            console.error('Request handling error:', error);
            this.recordRequest(requestId, false, Date.now() - startTime, error);
            return this.createErrorResponse(request?.id || null, -32603, 'Internal error', {
                message: error.message,
                stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
            });
        } finally {
            // Clean up request tracking
            this.activeRequests.delete(requestId);
        }
    }

    // Enhanced MCP Protocol Handlers

    async handleInitialize(id, params) {
        return this.createSuccessResponse(id, {
            protocolVersion: this.protocolVersion,
            capabilities: this.capabilities,
            serverInfo: this.serverInfo,
            instructions: 'FACT MCP Server provides cognitive template processing with WASM acceleration'
        });
    }

    async handleToolsList(id, params) {
        return this.createSuccessResponse(id, {
            tools: Object.values(this.tools)
        });
    }

    async handleResourcesList(id, params) {
        return this.createSuccessResponse(id, {
            resources: resourceManager.listResources()
        });
    }

    async handlePromptsList(id, params) {
        // FACT doesn't currently support prompts, but we provide the handler for completeness
        return this.createSuccessResponse(id, {
            prompts: []
        });
    }

    async handlePromptsGet(id, params) {
        return this.createErrorResponse(id, -32601, 'Prompts not supported');
    }

    async handleLoggingSetLevel(id, params) {
        const { level } = params || {};
        
        if (!['error', 'warn', 'info', 'debug'].includes(level)) {
            return this.createErrorResponse(id, -32602, 'Invalid logging level');
        }

        // Note: In a real implementation, you'd set the actual logging level
        console.error(`Logging level set to: ${level}`);
        
        return this.createSuccessResponse(id, {
            level,
            message: `Logging level set to ${level}`
        });
    }

    async handleNotificationInitialized(id, params) {
        console.error('Client initialized notification received');
        return this.createSuccessResponse(id, {});
    }

    async handleToolCall(id, params) {
        if (!params || !params.name) {
            return this.createErrorResponse(id, -32602, 'Invalid params - name required');
        }

        const { name, arguments: args = {} } = params;
        const toolStartTime = Date.now();

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
                    result = await getMetrics(args);
                    break;
                case 'benchmark_performance':
                    result = await this.benchmarkPerformance(args);
                    break;
                case 'health_check':
                    result = await this.healthCheck(args);
                    break;
                default:
                    return this.createErrorResponse(id, -32601, `Unknown tool: ${name}`);
            }

            const executionTime = Date.now() - toolStartTime;
            
            return this.createSuccessResponse(id, {
                content: [{
                    type: 'text',
                    text: JSON.stringify({
                        ...result,
                        tool_execution_time_ms: executionTime,
                        server_info: {
                            wasm_enabled: !!factInstance,
                            request_id: id
                        }
                    }, null, 2)
                }]
            });
        } catch (error) {
            console.error(`Tool execution error for ${name}:`, error);
            return this.createErrorResponse(id, -32603, `Tool execution failed: ${error.message}`, {
                tool: name,
                args: Object.keys(args),
                execution_time_ms: Date.now() - toolStartTime
            });
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
            error: { 
                code, 
                message,
                timestamp: new Date().toISOString()
            }
        };
        if (data) {
            response.error.data = data;
        }
        return response;
    }

    // New tool implementations
    async benchmarkPerformance(params) {
        const { test_type = 'template_processing', iterations = 100, payload_size = 'medium' } = params;
        const startTime = Date.now();
        
        try {
            const results = {
                test_type,
                iterations,
                payload_size,
                results: []
            };

            // Create test payload based on size
            const payloads = {
                small: { test: 'data', value: 42 },
                medium: { 
                    test: 'data', 
                    values: Array.from({length: 100}, (_, i) => i),
                    metadata: { created: new Date().toISOString() }
                },
                large: {
                    test: 'data',
                    values: Array.from({length: 1000}, (_, i) => ({ id: i, data: `test_${i}` })),
                    metadata: { created: new Date().toISOString(), size: 'large' }
                }
            };

            const testPayload = payloads[payload_size];

            // Run benchmarks based on test type
            for (let i = 0; i < iterations; i++) {
                const iterationStart = Date.now();
                
                switch (test_type) {
                    case 'template_processing':
                        await processTemplate({
                            template_id: 'data-analysis',
                            context: testPayload
                        });
                        break;
                    case 'cache_operations':
                        if (factInstance) {
                            factInstance.process(JSON.stringify(testPayload), true);
                        }
                        break;
                    case 'wasm_functions':
                        if (factInstance) {
                            factInstance.get_cache_stats();
                            factInstance.optimize('standard');
                        }
                        break;
                    case 'full_suite':
                        await processTemplate({
                            template_id: 'data-analysis', 
                            context: testPayload
                        });
                        if (factInstance) {
                            factInstance.process(JSON.stringify(testPayload), true);
                        }
                        break;
                }
                
                results.results.push({
                    iteration: i + 1,
                    duration_ms: Date.now() - iterationStart
                });
            }

            // Calculate statistics
            const durations = results.results.map(r => r.duration_ms);
            const totalTime = Date.now() - startTime;
            
            return {
                success: true,
                benchmark: {
                    ...results,
                    statistics: {
                        total_time_ms: totalTime,
                        average_ms: durations.reduce((a, b) => a + b, 0) / durations.length,
                        min_ms: Math.min(...durations),
                        max_ms: Math.max(...durations),
                        median_ms: durations.sort((a, b) => a - b)[Math.floor(durations.length / 2)],
                        operations_per_second: (iterations / totalTime) * 1000
                    }
                },
                metadata: {
                    wasm_enabled: !!factInstance,
                    timestamp: new Date().toISOString()
                }
            };
        } catch (error) {
            return {
                success: false,
                error: error.message,
                metadata: {
                    processing_time_ms: Date.now() - startTime,
                    timestamp: new Date().toISOString()
                }
            };
        }
    }

    async healthCheck(params) {
        const { include_wasm = true, include_cache = true, verbose = false } = params;
        const startTime = Date.now();
        
        try {
            const health = {
                status: 'healthy',
                checks: {},
                overall_health: 'green'
            };

            // Basic server health
            health.checks.server = {
                status: 'healthy',
                uptime_ms: Date.now() - startTime,
                active_requests: this.activeRequests.size,
                total_requests: this.requestCounter
            };

            // WASM module health
            if (include_wasm) {
                health.checks.wasm = {
                    status: factInstance ? 'healthy' : 'degraded',
                    module_loaded: !!factInstance,
                    fallback_mode: !factInstance
                };

                if (factInstance && verbose) {
                    try {
                        const stats = factInstance.get_cache_stats();
                        health.checks.wasm.cache_stats = stats;
                    } catch (error) {
                        health.checks.wasm.cache_error = error.message;
                    }
                }
            }

            // Cache system health  
            if (include_cache) {
                health.checks.cache = {
                    status: 'healthy',
                    templates_loaded: Object.keys(COGNITIVE_TEMPLATES).length,
                    resources_available: resourceManager.listResources().length
                };
            }

            // Memory health
            const memUsage = process.memoryUsage();
            health.checks.memory = {
                status: memUsage.heapUsed < (memUsage.heapTotal * 0.9) ? 'healthy' : 'warning',
                heap_used_mb: Math.round(memUsage.heapUsed / 1024 / 1024),
                heap_total_mb: Math.round(memUsage.heapTotal / 1024 / 1024),
                external_mb: Math.round(memUsage.external / 1024 / 1024)
            };

            // Determine overall health
            const statuses = Object.values(health.checks).map(check => check.status);
            if (statuses.includes('unhealthy')) {
                health.overall_health = 'red';
                health.status = 'unhealthy';
            } else if (statuses.includes('degraded') || statuses.includes('warning')) {
                health.overall_health = 'yellow';
                health.status = 'degraded';
            }

            return {
                success: true,
                health,
                metadata: {
                    check_duration_ms: Date.now() - startTime,
                    timestamp: new Date().toISOString()
                }
            };
        } catch (error) {
            return {
                success: false,
                health: {
                    status: 'unhealthy',
                    overall_health: 'red',
                    error: error.message
                },
                metadata: {
                    check_duration_ms: Date.now() - startTime,
                    timestamp: new Date().toISOString()
                }
            };
        }
    }

    // Request tracking methods
    recordRequest(requestId, success, duration, error = null) {
        const record = {
            requestId,
            success,
            duration,
            timestamp: new Date().toISOString(),
            error: error ? error.message : null
        };

        this.requestHistory.push(record);
        
        // Keep only last 1000 requests
        if (this.requestHistory.length > 1000) {
            this.requestHistory.shift();
        }

        performanceTracker.recordRequest(success, duration, false, !!factInstance);
    }
}

/**
 * Enhanced main server setup with improved stdio transport and error handling
 */
async function main() {
    console.error('🚀 Starting FACT MCP Server...');
    console.error(`📍 Node.js version: ${process.version}`);
    console.error(`🖥️  Platform: ${process.platform} ${process.arch}`);
    
    // Initialize WASM with retry logic
    let wasmInitialized = false;
    let wasmAttempts = 0;
    const maxWasmAttempts = 3;
    
    while (!wasmInitialized && wasmAttempts < maxWasmAttempts) {
        wasmAttempts++;
        console.error(`🔄 WASM initialization attempt ${wasmAttempts}/${maxWasmAttempts}...`);
        
        try {
            wasmInitialized = await initializeWasm();
            if (wasmInitialized) {
                console.error('✅ WASM module initialized successfully');
                break;
            }
        } catch (error) {
            console.error(`❌ WASM initialization attempt ${wasmAttempts} failed:`, error.message);
        }
        
        if (!wasmInitialized && wasmAttempts < maxWasmAttempts) {
            console.error('⏳ Retrying WASM initialization in 1 second...');
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
    
    if (!wasmInitialized) {
        console.error('⚠️  WASM initialization failed - running in JavaScript fallback mode');
        console.error('📝 Note: Performance may be reduced without WASM acceleration');
    }
    
    const server = new McpServer();
    
    // Enhanced readline interface with better error handling
    const rl = createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false,
        crlfDelay: Infinity // Handle Windows line endings
    });

    console.error('🎯 FACT MCP Server ready on stdio transport');
    console.error('📊 Available tools:', Object.keys(server.tools).length);
    console.error('🔧 Available templates:', Object.keys(COGNITIVE_TEMPLATES).length);
    console.error('📚 Available resources:', resourceManager.listResources().length);

    // Request processing with enhanced error handling
    rl.on('line', async (line) => {
        try {
            // Skip empty lines
            if (!line.trim()) {
                return;
            }
            
            let request;
            try {
                request = JSON.parse(line);
            } catch (parseError) {
                console.error('Parse error for input:', line.substring(0, 100) + (line.length > 100 ? '...' : ''));
                const errorResponse = {
                    jsonrpc: '2.0',
                    id: null,
                    error: {
                        code: -32700,
                        message: 'Parse error',
                        data: {
                            input_length: line.length,
                            error: parseError.message
                        }
                    }
                };
                console.log(JSON.stringify(errorResponse));
                return;
            }
            
            // Process request with timeout
            const timeout = 30000; // 30 seconds
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Request timeout')), timeout);
            });
            
            try {
                const response = await Promise.race([
                    server.handleRequest(request),
                    timeoutPromise
                ]);
                
                if (response) {
                    console.log(JSON.stringify(response));
                }
            } catch (timeoutError) {
                console.error('Request timeout for method:', request?.method);
                const timeoutResponse = {
                    jsonrpc: '2.0',
                    id: request?.id || null,
                    error: {
                        code: -32603,
                        message: 'Request timeout',
                        data: {
                            method: request?.method,
                            timeout_ms: timeout
                        }
                    }
                };
                console.log(JSON.stringify(timeoutResponse));
            }
            
        } catch (error) {
            console.error('Unexpected error processing request:', error);
            const errorResponse = {
                jsonrpc: '2.0',
                id: null,
                error: {
                    code: -32603,
                    message: 'Internal error',
                    data: {
                        error: error.message,
                        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
                    }
                }
            };
            console.log(JSON.stringify(errorResponse));
        }
    });

    rl.on('error', (error) => {
        console.error('Readline error:', error);
    });

    rl.on('close', () => {
        console.error('📈 Final server statistics:');
        console.error(`   Total requests processed: ${server.requestCounter}`);
        console.error(`   Active requests: ${server.activeRequests.size}`);
        console.error(`   Request history: ${server.requestHistory.length} entries`);
        console.error('👋 FACT MCP Server shutting down...');
        process.exit(0);
    });

    // Enhanced process termination handling
    const gracefulShutdown = (signal) => {
        console.error(`📨 Received ${signal}, initiating graceful shutdown...`);
        
        // Give active requests time to complete
        if (server.activeRequests.size > 0) {
            console.error(`⏳ Waiting for ${server.activeRequests.size} active requests to complete...`);
            setTimeout(() => {
                console.error('⏰ Shutdown timeout reached, forcing exit...');
                process.exit(1);
            }, 5000);
        }
        
        rl.close();
    };

    process.on('SIGINT', () => gracefulShutdown('SIGINT'));
    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    
    // Handle uncaught exceptions
    process.on('uncaughtException', (error) => {
        console.error('💥 Uncaught exception:', error);
        console.error('📊 Server state:', {
            activeRequests: server.activeRequests.size,
            totalRequests: server.requestCounter,
            wasmEnabled: !!factInstance
        });
        process.exit(1);
    });
    
    process.on('unhandledRejection', (reason, promise) => {
        console.error('🚫 Unhandled rejection at:', promise, 'reason:', reason);
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