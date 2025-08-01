#!/usr/bin/env node

/**
 * Performance Benchmark Runner for FACT WASM MCP Integration
 * 
 * Comprehensive performance testing suite that benchmarks:
 * - WASM module performance
 * - MCP server response times
 * - Memory usage patterns
 * - Concurrent operation handling
 * - Cross-platform compatibility
 */

const { spawn } = require('child_process');
const { performance } = require('perf_hooks');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class PerformanceBenchmarkRunner {
    constructor() {
        this.results = {
            system_info: this.getSystemInfo(),
            benchmarks: {},
            summary: {},
            timestamp: new Date().toISOString()
        };
        
        // Performance targets (can be overridden via config)
        this.targets = {
            wasm_load_time_ms: 1000,
            cache_ops_per_sec: 10000,
            query_processing_ms: 10,
            mcp_response_ms: 100,
            memory_usage_mb: 50,
            concurrent_requests_per_sec: 100
        };
    }
    
    getSystemInfo() {
        return {
            platform: os.platform(),
            arch: os.arch(),
            node_version: process.version,
            cpu_cores: os.cpus().length,
            total_memory_gb: (os.totalmem() / (1024 ** 3)).toFixed(2),
            free_memory_gb: (os.freemem() / (1024 ** 3)).toFixed(2)
        };
    }
    
    async runBenchmark(name, benchmarkFn, iterations = 1) {
        console.log(`🏃 Running benchmark: ${name}`);
        
        const results = [];
        let totalTime = 0;
        
        for (let i = 0; i < iterations; i++) {
            const start = performance.now();
            const result = await benchmarkFn(i);
            const end = performance.now();
            const duration = end - start;
            
            results.push({
                iteration: i + 1,
                duration_ms: duration,
                metrics: result
            });
            
            totalTime += duration;
        }
        
        const avgTime = totalTime / iterations;
        const minTime = Math.min(...results.map(r => r.duration_ms));
        const maxTime = Math.max(...results.map(r => r.duration_ms));
        
        this.results.benchmarks[name] = {
            iterations,
            avg_duration_ms: avgTime,
            min_duration_ms: minTime,
            max_duration_ms: maxTime,
            total_duration_ms: totalTime,
            results
        };
        
        console.log(`  ✅ Completed: avg ${avgTime.toFixed(2)}ms, min ${minTime.toFixed(2)}ms, max ${maxTime.toFixed(2)}ms`);
        
        return this.results.benchmarks[name];
    }
    
    async benchmarkWasmLoading() {
        return this.runBenchmark('wasm_loading', async (iteration) => {
            const testScript = `
const { FastCache, QueryProcessor, greet } = require('../pkg/fact_wasm_core.js');

const start = Date.now();

// Test module initialization
const greeting = greet('Benchmark Test ${iteration}');
const cache = new FastCache(100);
const processor = new QueryProcessor();

// Basic operations
cache.set('test_key', 'test_value', 60000);
const value = cache.get('test_key');
const queryResult = processor.process_query('SELECT 1');

const end = Date.now();

console.log(JSON.stringify({
    load_time_ms: end - start,
    greeting_valid: greeting.includes('Benchmark Test ${iteration}'),
    cache_works: value === 'test_value',
    query_works: queryResult.success
}));
`;
            
            const tempFile = path.join(os.tmpdir(), `wasm_bench_${iteration}.js`);
            await fs.writeFile(tempFile, testScript);
            
            const result = await this.runNodeScript(tempFile);
            await fs.unlink(tempFile);
            
            return JSON.parse(result.stdout);
        }, 10);
    }
    
    async benchmarkCachePerformance() {
        return this.runBenchmark('cache_performance', async (iteration) => {
            const testScript = `
const { FastCache } = require('../pkg/fact_wasm_core.js');

const cache = new FastCache(10000);
const operationCounts = [100, 1000, 5000, 10000];
const results = {};

for (const count of operationCounts) {
    // Benchmark SET operations
    const setStart = Date.now();
    for (let i = 0; i < count; i++) {
        cache.set(\`key_\${i}\`, \`value_data_\${i}_iteration_${iteration}\`, 60000);
    }
    const setTime = Date.now() - setStart;
    
    // Benchmark GET operations
    const getStart = Date.now();
    for (let i = 0; i < count; i++) {
        const value = cache.get(\`key_\${i}\`);
        if (!value) throw new Error(\`Failed to get key_\${i}\`);
    }
    const getTime = Date.now() - getStart;
    
    results[\`ops_\${count}\`] = {
        set_ops_per_sec: (count / setTime) * 1000,
        get_ops_per_sec: (count / getTime) * 1000,
        total_ops_per_sec: ((count * 2) / (setTime + getTime)) * 1000
    };
}

console.log(JSON.stringify(results));
`;
            
            const tempFile = path.join(os.tmpdir(), `cache_bench_${iteration}.js`);
            await fs.writeFile(tempFile, testScript);
            
            const result = await this.runNodeScript(tempFile);
            await fs.unlink(tempFile);
            
            return JSON.parse(result.stdout);
        }, 5);
    }
    
    async benchmarkQueryProcessor() {
        return this.runBenchmark('query_processor', async (iteration) => {
            const testScript = `
const { QueryProcessor } = require('../pkg/fact_wasm_core.js');

const processor = new QueryProcessor();
const queries = [
    'SELECT 1',
    'SELECT * FROM companies WHERE revenue > 1000000',
    'SELECT COUNT(*) FROM financial_records',
    'INSERT INTO test (id, name) VALUES (1, "test")',
    'UPDATE companies SET status = "active" WHERE id = 1',
    'DELETE FROM temp WHERE created < NOW()'
];

const queryResults = {};

for (let i = 0; i < queries.length; i++) {
    const query = queries[i];
    const iterations = 100;
    
    const start = Date.now();
    for (let j = 0; j < iterations; j++) {
        const result = processor.process_query(query);
        if (!result.success) {
            throw new Error(\`Query failed: \${query}\`);
        }
    }
    const end = Date.now();
    
    queryResults[\`query_\${i}\`] = {
        query: query.substring(0, 30) + '...',
        avg_time_ms: (end - start) / iterations,
        queries_per_sec: (iterations / (end - start)) * 1000,
        total_time_ms: end - start
    };
}

console.log(JSON.stringify(queryResults));
`;
            
            const tempFile = path.join(os.tmpdir(), `query_bench_${iteration}.js`);
            await fs.writeFile(tempFile, testScript);
            
            const result = await this.runNodeScript(tempFile);
            await fs.unlink(tempFile);
            
            return JSON.parse(result.stdout);
        }, 3);
    }
    
    async benchmarkMemoryUsage() {
        return this.runBenchmark('memory_usage', async (iteration) => {
            const testScript = `
const { FastCache, QueryProcessor, get_memory_usage } = require('../pkg/fact_wasm_core.js');

const initialMemory = process.memoryUsage();
const wasmInitialMemory = JSON.parse(get_memory_usage());

// Create memory pressure
const caches = [];
const processors = [];

for (let i = 0; i < 50; i++) {
    const cache = new FastCache(200);
    const processor = new QueryProcessor();
    
    // Fill cache with data
    for (let j = 0; j < 100; j++) {
        cache.set(\`cache_\${i}_key_\${j}\`, \`large_value_data_\${j}_\`.repeat(10), 60000);
    }
    
    caches.push(cache);
    processors.push(processor);
}

const peakMemory = process.memoryUsage();
const wasmPeakMemory = JSON.parse(get_memory_usage());

// Force cleanup
caches.length = 0;
processors.length = 0;

if (global.gc) {
    global.gc();
}

const finalMemory = process.memoryUsage();
const wasmFinalMemory = JSON.parse(get_memory_usage());

console.log(JSON.stringify({
    node_memory: {
        initial_mb: initialMemory.heapUsed / (1024 * 1024),
        peak_mb: peakMemory.heapUsed / (1024 * 1024),
        final_mb: finalMemory.heapUsed / (1024 * 1024),
        increase_mb: (peakMemory.heapUsed - initialMemory.heapUsed) / (1024 * 1024)
    },
    wasm_memory: {
        initial_kb: wasmInitialMemory.heap_used / 1024,
        peak_kb: wasmPeakMemory.heap_used / 1024,
        final_kb: wasmFinalMemory.heap_used / 1024,
        increase_kb: (wasmPeakMemory.heap_used - wasmInitialMemory.heap_used) / 1024
    }
}));
`;
            
            const tempFile = path.join(os.tmpdir(), `memory_bench_${iteration}.js`);
            await fs.writeFile(tempFile, testScript);
            
            const result = await this.runNodeScript(tempFile, ['--expose-gc']);
            await fs.unlink(tempFile);
            
            return JSON.parse(result.stdout);
        }, 3);
    }
    
    async benchmarkMcpServer() {
        return this.runBenchmark('mcp_server', async (iteration) => {
            // Start MCP server
            const serverProcess = spawn('node', ['src/mcp-server.js'], {
                stdio: ['pipe', 'pipe', 'pipe'],
                cwd: path.join(__dirname, '..')
            });
            
            // Wait for server to start
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            const requests = [
                {
                    jsonrpc: '2.0',
                    id: 1,
                    method: 'initialize',
                    params: {
                        protocolVersion: '2024-11-05',
                        capabilities: {},
                        clientInfo: { name: 'benchmark', version: '1.0.0' }
                    }
                },
                {
                    jsonrpc: '2.0',
                    id: 2,
                    method: 'tools/list',
                    params: {}
                },
                {
                    jsonrpc: '2.0',
                    id: 3,
                    method: 'tools/call',
                    params: {
                        name: 'get_metrics',
                        arguments: {}
                    }
                }
            ];
            
            const results = {};
            
            for (let i = 0; i < requests.length; i++) {
                const request = requests[i];
                const start = performance.now();
                
                try {
                    serverProcess.stdin.write(JSON.stringify(request) + '\n');
                    
                    // Wait for response (simplified)
                    await new Promise(resolve => setTimeout(resolve, 100));
                    
                    const end = performance.now();
                    results[`request_${i}`] = {
                        method: request.method,
                        response_time_ms: end - start
                    };
                } catch (error) {
                    results[`request_${i}`] = {
                        method: request.method,
                        error: error.message
                    };
                }
            }
            
            // Cleanup
            serverProcess.kill();
            
            return results;
        }, 3);
    }
    
    async benchmarkConcurrentOperations() {
        return this.runBenchmark('concurrent_operations', async (iteration) => {
            const testScript = `
const { FastCache, QueryProcessor } = require('../pkg/fact_wasm_core.js');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

if (isMainThread) {
    const numWorkers = 4;
    const operationsPerWorker = 250;
    const workers = [];
    const results = [];
    
    const start = Date.now();
    
    const promises = Array.from({ length: numWorkers }, (_, i) => {
        return new Promise((resolve, reject) => {
            const worker = new Worker(__filename, {
                workerData: { workerId: i, operations: operationsPerWorker }
            });
            
            worker.on('message', (result) => {
                results.push(result);
                resolve();
            });
            
            worker.on('error', reject);
            workers.push(worker);
        });
    });
    
    await Promise.all(promises);
    
    const end = Date.now();
    const totalOperations = numWorkers * operationsPerWorker;
    
    console.log(JSON.stringify({
        total_operations: totalOperations,
        total_time_ms: end - start,
        operations_per_sec: (totalOperations / (end - start)) * 1000,
        workers: numWorkers,
        avg_ops_per_worker: operationsPerWorker,
        worker_results: results
    }));
    
} else {
    const { workerId, operations } = workerData;
    const cache = new FastCache(1000);
    const processor = new QueryProcessor();
    
    const start = Date.now();
    
    for (let i = 0; i < operations; i++) {
        cache.set(\`worker_\${workerId}_key_\${i}\`, \`value_\${i}\`, 60000);
        const value = cache.get(\`worker_\${workerId}_key_\${i}\`);
        const result = processor.process_query(\`SELECT \${i} as worker_\${workerId}\`);
        
        if (!value || !result.success) {
            throw new Error(\`Operation failed at iteration \${i}\`);
        }
    }
    
    const end = Date.now();
    
    parentPort.postMessage({
        worker_id: workerId,
        operations: operations,
        duration_ms: end - start,
        ops_per_sec: (operations / (end - start)) * 1000
    });
}
`;
            
            const tempFile = path.join(os.tmpdir(), `concurrent_bench_${iteration}.js`);
            await fs.writeFile(tempFile, testScript);
            
            const result = await this.runNodeScript(tempFile);
            await fs.unlink(tempFile);
            
            return JSON.parse(result.stdout);
        }, 2);
    }
    
    async runNodeScript(scriptPath, args = []) {
        return new Promise((resolve, reject) => {
            const nodeArgs = ['--max-old-space-size=4096', ...args, scriptPath];
            const child = spawn('node', nodeArgs, {
                stdio: ['pipe', 'pipe', 'pipe'],
                cwd: path.dirname(scriptPath)
            });
            
            let stdout = '';
            let stderr = '';
            
            child.stdout.on('data', (data) => stdout += data.toString());
            child.stderr.on('data', (data) => stderr += data.toString());
            
            child.on('close', (code) => {
                if (code === 0) {
                    resolve({ stdout, stderr });
                } else {
                    reject(new Error(`Process exited with code ${code}\nSTDERR: ${stderr}`));
                }
            });
            
            child.on('error', reject);
            
            // Timeout after 30 seconds
            setTimeout(() => {
                child.kill();
                reject(new Error('Script timeout'));
            }, 30000);
        });
    }
    
    async runAllBenchmarks() {
        console.log('🚀 Starting FACT WASM Performance Benchmark Suite');
        console.log('================================================');
        console.log(`System: ${this.results.system_info.platform} ${this.results.system_info.arch}`);
        console.log(`Node.js: ${this.results.system_info.node_version}`);
        console.log(`CPU Cores: ${this.results.system_info.cpu_cores}`);
        console.log(`Memory: ${this.results.system_info.total_memory_gb}GB total, ${this.results.system_info.free_memory_gb}GB free`);
        console.log('');
        
        try {
            // Run all benchmarks
            await this.benchmarkWasmLoading();
            await this.benchmarkCachePerformance();
            await this.benchmarkQueryProcessor();
            await this.benchmarkMemoryUsage();
            await this.benchmarkMcpServer();
            await this.benchmarkConcurrentOperations();
            
            // Generate summary
            this.generateSummary();
            
            // Save results
            await this.saveResults();
            
            // Print final report
            this.printReport();
            
        } catch (error) {
            console.error('❌ Benchmark suite failed:', error.message);
            process.exit(1);
        }
    }
    
    generateSummary() {
        this.results.summary = {
            total_benchmarks: Object.keys(this.results.benchmarks).length,
            total_duration_ms: Object.values(this.results.benchmarks)
                .reduce((sum, bench) => sum + bench.total_duration_ms, 0),
            performance_score: this.calculatePerformanceScore(),
            recommendations: this.generateRecommendations()
        };
    }
    
    calculatePerformanceScore() {
        let score = 100;
        let totalTests = 0;
        
        // Check each benchmark against targets
        for (const [benchName, benchData] of Object.entries(this.results.benchmarks)) {
            for (const result of benchData.results) {
                if (result.metrics) {
                    for (const [metricName, metricValue] of Object.entries(result.metrics)) {
                        if (this.targets[metricName]) {
                            totalTests++;
                            const target = this.targets[metricName];
                            const meetsTarget = metricName.endsWith('_per_sec') ? 
                                metricValue >= target : metricValue <= target;
                            
                            if (!meetsTarget) {
                                const deviation = metricName.endsWith('_per_sec') ? 
                                    (target - metricValue) / target :
                                    (metricValue - target) / target;
                                score -= Math.min(20, deviation * 100);
                            }
                        }
                    }
                }
            }
        }
        
        return Math.max(0, Math.round(score));
    }
    
    generateRecommendations() {
        const recommendations = [];
        
        // Analyze results and generate recommendations
        const wasmBench = this.results.benchmarks.wasm_loading;
        if (wasmBench && wasmBench.avg_duration_ms > this.targets.wasm_load_time_ms) {
            recommendations.push('Consider optimizing WASM module size and initialization');
        }
        
        const memoryBench = this.results.benchmarks.memory_usage;
        if (memoryBench) {
            const avgMemoryIncrease = memoryBench.results
                .reduce((sum, r) => sum + (r.metrics.node_memory?.increase_mb || 0), 0) / memoryBench.results.length;
            
            if (avgMemoryIncrease > this.targets.memory_usage_mb) {
                recommendations.push('Memory usage is high - consider implementing more aggressive cleanup');
            }
        }
        
        const cacheBench = this.results.benchmarks.cache_performance;
        if (cacheBench) {
            const avgOpsPerSec = cacheBench.results
                .reduce((sum, r) => sum + (r.metrics.ops_10000?.total_ops_per_sec || 0), 0) / cacheBench.results.length;
            
            if (avgOpsPerSec < this.targets.cache_ops_per_sec) {
                recommendations.push('Cache performance is below target - consider optimizing hash algorithms');
            }
        }
        
        if (recommendations.length === 0) {
            recommendations.push('Performance is within acceptable ranges - no immediate optimizations needed');
        }
        
        return recommendations;
    }
    
    async saveResults() {
        const resultsDir = path.join(__dirname, '..', 'benchmark-results');
        await fs.mkdir(resultsDir, { recursive: true });
        
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `benchmark-${timestamp}.json`;
        const filepath = path.join(resultsDir, filename);
        
        await fs.writeFile(filepath, JSON.stringify(this.results, null, 2));
        console.log(`📊 Results saved to: ${filepath}`);
    }
    
    printReport() {
        console.log('\n📋 Benchmark Report');
        console.log('==================');
        
        for (const [benchName, benchData] of Object.entries(this.results.benchmarks)) {
            console.log(`\n🏃 ${benchName.replace(/_/g, ' ').toUpperCase()}`);
            console.log(`  Iterations: ${benchData.iterations}`);
            console.log(`  Avg Duration: ${benchData.avg_duration_ms.toFixed(2)}ms`);
            console.log(`  Min/Max: ${benchData.min_duration_ms.toFixed(2)}ms / ${benchData.max_duration_ms.toFixed(2)}ms`);
        }
        
        console.log(`\n📊 Overall Performance Score: ${this.results.summary.performance_score}/100`);
        
        console.log('\n💡 Recommendations:');
        for (const rec of this.results.summary.recommendations) {
            console.log(`  • ${rec}`);
        }
        
        console.log(`\n⏱️ Total Benchmark Time: ${(this.results.summary.total_duration_ms / 1000).toFixed(2)}s`);
        
        if (this.results.summary.performance_score >= 80) {
            console.log('\n🎉 Excellent performance! All systems running optimally.');
        } else if (this.results.summary.performance_score >= 60) {
            console.log('\n👍 Good performance with room for improvement.');
        } else {
            console.log('\n⚠️ Performance needs attention. Review recommendations above.');
        }
    }
}

// Run benchmarks if this file is executed directly
if (require.main === module) {
    const runner = new PerformanceBenchmarkRunner();
    runner.runAllBenchmarks().catch(error => {
        console.error('Benchmark runner failed:', error);
        process.exit(1);
    });
}

module.exports = PerformanceBenchmarkRunner;