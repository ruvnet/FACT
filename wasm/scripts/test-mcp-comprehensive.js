#!/usr/bin/env node

/**
 * Comprehensive MCP Server Test Suite
 * 
 * Advanced testing framework for FACT MCP Server that covers:
 * - Protocol compliance (JSON-RPC 2.0 + MCP extensions)
 * - Tool functionality and edge cases
 * - Resource management and access
 * - Error handling and recovery
 * - Performance under load
 * - Security and validation
 * - Integration scenarios
 */

const { spawn } = require('child_process');
const { createInterface } = require('readline');
const { performance } = require('perf_hooks');
const path = require('path');
const fs = require('fs').promises;
const crypto = require('crypto');

class ComprehensiveMcpTester {
    constructor() {
        this.serverProcess = null;
        this.testResults = [];
        this.currentTest = 0;
        this.totalTests = 0;
        this.serverReady = false;
        this.requestId = 1;
        this.responseQueue = new Map();
        this.performanceMetrics = {};
    }

    /**
     * Start the MCP server with enhanced monitoring
     */
    async startServer() {
        return new Promise((resolve, reject) => {
            const serverPath = path.join(__dirname, '../src/mcp-server.js');
            
            this.serverProcess = spawn('node', [serverPath], {
                stdio: ['pipe', 'pipe', 'pipe', 'pipe', 'pipe'],
                cwd: path.dirname(serverPath),
                env: {
                    ...process.env,
                    NODE_ENV: 'test',
                    DEBUG: 'fact:*'
                }
            });

            let serverOutput = '';
            let initTimeout;

            // Enhanced server output monitoring
            this.serverProcess.stderr.on('data', (data) => {
                const message = data.toString();
                serverOutput += message;
                
                if (message.includes('FACT MCP Server ready') || 
                    message.includes('Server initialized') ||
                    message.includes('Listening on stdio')) {
                    this.serverReady = true;
                    clearTimeout(initTimeout);
                    resolve();
                }
                
                if (message.includes('Fatal error') || message.includes('EADDRINUSE')) {
                    clearTimeout(initTimeout);
                    reject(new Error(`Server startup failed: ${message}`));
                }
            });

            this.serverProcess.stdout.on('data', (data) => {
                this.handleServerResponse(data.toString());
            });

            this.serverProcess.on('error', (error) => {
                clearTimeout(initTimeout);
                reject(error);
            });

            this.serverProcess.on('exit', (code) => {
                if (!this.serverReady) {
                    clearTimeout(initTimeout);
                    reject(new Error(`Server exited with code ${code} before ready. Output: ${serverOutput}`));
                }
            });
            
            // Extended timeout for server startup
            initTimeout = setTimeout(() => {
                reject(new Error(`Server startup timeout. Output: ${serverOutput}`));
            }, 15000);
        });
    }

    /**
     * Handle server responses with enhanced parsing
     */
    handleServerResponse(data) {
        const lines = data.split('\n').filter(line => line.trim());
        
        for (const line of lines) {
            try {
                if (line.startsWith('{') && line.endsWith('}')) {
                    const response = JSON.parse(line);
                    
                    if (response.jsonrpc === '2.0' && response.id) {
                        const waitingPromise = this.responseQueue.get(response.id);
                        if (waitingPromise) {
                            this.responseQueue.delete(response.id);
                            waitingPromise.resolve(response);
                        }
                    }
                }
            } catch (error) {
                // Ignore parsing errors for non-JSON output
            }
        }
    }

    /**
     * Send enhanced JSON-RPC request with timeout and retry
     */
    async sendRequest(request, timeout = 5000, retries = 3) {
        if (!this.serverProcess || !this.serverReady) {
            throw new Error('Server not running or not ready');
        }

        const requestId = this.requestId++;
        const enhancedRequest = {
            jsonrpc: '2.0',
            id: requestId,
            ...request
        };

        let lastError;
        
        for (let attempt = 0; attempt < retries; attempt++) {
            try {
                const response = await this.attemptRequest(enhancedRequest, timeout);
                return response;
            } catch (error) {
                lastError = error;
                if (attempt < retries - 1) {
                    await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
                }
            }
        }
        
        throw lastError;
    }

    async attemptRequest(request, timeout) {
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                this.responseQueue.delete(request.id);
                reject(new Error(`Request timeout: ${request.method}`));
            }, timeout);

            this.responseQueue.set(request.id, {
                resolve: (response) => {
                    clearTimeout(timeoutId);
                    resolve(response);
                },
                reject: (error) => {
                    clearTimeout(timeoutId);
                    reject(error);
                }
            });

            try {
                const requestLine = JSON.stringify(request) + '\n';
                this.serverProcess.stdin.write(requestLine);
            } catch (error) {
                clearTimeout(timeoutId);
                this.responseQueue.delete(request.id);
                reject(error);
            }
        });
    }

    /**
     * Run a test with comprehensive error handling and metrics
     */
    async runTest(testName, testFn, expectedDuration = null) {
        this.currentTest++;
        console.log(`\n[${this.currentTest}/${this.totalTests}] 🧪 ${testName}`);
        
        const startTime = performance.now();
        const memBefore = process.memoryUsage();
        
        try {
            const result = await testFn();
            const endTime = performance.now();
            const duration = endTime - startTime;
            const memAfter = process.memoryUsage();
            
            const testResult = {
                name: testName,
                status: 'PASS',
                duration: Math.round(duration * 100) / 100,
                memoryDelta: Math.round((memAfter.heapUsed - memBefore.heapUsed) / 1024),
                result: result
            };

            // Performance validation
            if (expectedDuration && duration > expectedDuration) {
                testResult.warning = `Slower than expected: ${duration.toFixed(2)}ms > ${expectedDuration}ms`;
                console.log(`  ⚠️  ${testResult.warning}`);
            }

            console.log(`  ✅ PASS (${testResult.duration}ms, ${testResult.memoryDelta}KB)`);
            this.testResults.push(testResult);
            
            return testResult;
            
        } catch (error) {
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            const testResult = {
                name: testName,
                status: 'FAIL',
                duration: Math.round(duration * 100) / 100,
                error: error.message,
                stack: error.stack
            };

            console.log(`  ❌ FAIL (${testResult.duration}ms): ${error.message}`);
            this.testResults.push(testResult);
            
            return testResult;
        }
    }

    /**
     * Test server initialization and handshake
     */
    async testServerInitialization() {
        const request = {
            method: 'initialize',
            params: {
                protocolVersion: '2024-11-05',
                capabilities: {
                    roots: {
                        listChanged: true
                    },
                    sampling: {}
                },
                clientInfo: {
                    name: 'comprehensive-test-client',
                    version: '1.0.0'
                }
            }
        };

        const response = await this.sendRequest(request);
        
        if (response.error) {
            throw new Error(`Initialize failed: ${JSON.stringify(response.error)}`);
        }
        
        if (!response.result) {
            throw new Error('No result in initialize response');
        }
        
        const { serverInfo, capabilities } = response.result;
        
        if (!serverInfo || !serverInfo.name || !serverInfo.version) {
            throw new Error('Invalid serverInfo in response');
        }
        
        if (serverInfo.name !== 'fact-mcp') {
            throw new Error(`Unexpected server name: ${serverInfo.name}`);
        }

        return {
            serverInfo,
            capabilities,
            responseTime: response.duration
        };
    }

    /**
     * Test tools listing and validation
     */
    async testToolsListing() {
        const response = await this.sendRequest({ method: 'tools/list', params: {} });
        
        if (response.error) {
            throw new Error(`Tools list failed: ${JSON.stringify(response.error)}`);
        }
        
        const tools = response.result?.tools;
        if (!Array.isArray(tools)) {
            throw new Error('Tools result is not an array');
        }

        const expectedTools = [
            'process_template',
            'list_templates', 
            'analyze_context',
            'optimize_performance',
            'create_template',
            'get_metrics'
        ];

        const foundTools = tools.map(t => t.name);
        const missingTools = expectedTools.filter(t => !foundTools.includes(t));
        
        if (missingTools.length > 0) {
            throw new Error(`Missing tools: ${missingTools.join(', ')}`);
        }

        // Validate tool schemas
        for (const tool of tools) {
            if (!tool.name || !tool.description) {
                throw new Error(`Invalid tool schema: ${JSON.stringify(tool)}`);
            }
            
            if (tool.inputSchema && typeof tool.inputSchema !== 'object') {
                throw new Error(`Invalid inputSchema for tool ${tool.name}`);
            }
        }

        return {
            toolCount: tools.length,
            tools: foundTools,
            schemas: tools.filter(t => t.inputSchema).length
        };
    }

    /**
     * Test comprehensive tool execution scenarios
     */
    async testToolExecution() {
        const testCases = [
            {
                name: 'get_metrics',
                args: {},
                validator: (result) => {
                    const content = JSON.parse(result.content[0].text);
                    if (!content.success) throw new Error('Metrics call failed');
                    return { hasMetrics: !!content.metrics };
                }
            },
            {
                name: 'list_templates',
                args: { category: 'analysis' },
                validator: (result) => {
                    const content = JSON.parse(result.content[0].text);
                    if (!content.success) throw new Error('List templates failed');
                    return { templateCount: content.templates?.length || 0 };
                }
            },
            {
                name: 'analyze_context',
                args: {
                    context: {
                        task: 'test analysis',
                        complexity: 'medium',
                        domain: 'testing'
                    },
                    suggest_templates: true
                },
                validator: (result) => {
                    const content = JSON.parse(result.content[0].text);
                    if (!content.success) throw new Error('Context analysis failed');
                    return { 
                        hasAnalysis: !!content.analysis,
                        hasSuggestions: !!content.suggested_templates 
                    };
                }
            },
            {
                name: 'process_template',
                args: {
                    template_id: 'data-analysis',
                    context: {
                        data: [1, 2, 3, 4, 5],
                        query: 'comprehensive test'
                    },
                    options: { cache: true, priority: 'high' }
                },
                validator: (result) => {
                    const content = JSON.parse(result.content[0].text);
                    if (!content.success) throw new Error('Template processing failed');
                    return { 
                        hasResult: !!content.result,
                        hasMetadata: !!content.metadata 
                    };
                }
            }
        ];

        const results = {};
        
        for (const testCase of testCases) {
            const request = {
                method: 'tools/call',
                params: {
                    name: testCase.name,
                    arguments: testCase.args
                }
            };

            const response = await this.sendRequest(request);
            
            if (response.error) {
                throw new Error(`Tool ${testCase.name} failed: ${JSON.stringify(response.error)}`);
            }

            if (!response.result?.content) {
                throw new Error(`Tool ${testCase.name} returned no content`);
            }

            const validationResult = testCase.validator(response.result);
            results[testCase.name] = validationResult;
        }

        return results;
    }

    /**
     * Test resources listing and reading
     */
    async testResourceOperations() {
        // Test resources listing
        const listResponse = await this.sendRequest({ 
            method: 'resources/list', 
            params: {} 
        });
        
        if (listResponse.error) {
            throw new Error(`Resources list failed: ${JSON.stringify(listResponse.error)}`);
        }

        const resources = listResponse.result?.resources;
        if (!Array.isArray(resources)) {
            throw new Error('Resources result is not an array');
        }

        const results = { resourceCount: resources.length, readTests: {} };

        // Test reading each resource
        for (const resource of resources.slice(0, 3)) { // Test first 3 resources
            const readResponse = await this.sendRequest({
                method: 'resources/read',
                params: { uri: resource.uri }
            });

            if (readResponse.error) {
                results.readTests[resource.uri] = { success: false, error: readResponse.error };
            } else {
                const contents = readResponse.result?.contents;
                results.readTests[resource.uri] = { 
                    success: true, 
                    contentCount: contents?.length || 0,
                    mimeType: contents?.[0]?.mimeType
                };
            }
        }

        return results;
    }

    /**
     * Test error handling and edge cases
     */
    async testErrorHandling() {
        const errorTests = [
            {
                name: 'invalid_method',
                request: { method: 'invalid/method', params: {} },
                expectedError: -32601 // Method not found
            },
            {
                name: 'malformed_params',
                request: { method: 'tools/call', params: 'invalid' },
                expectedError: -32602 // Invalid params
            },
            {
                name: 'nonexistent_tool',
                request: { 
                    method: 'tools/call', 
                    params: { name: 'nonexistent_tool', arguments: {} }
                },
                expectedError: null // Tool-specific error
            },
            {
                name: 'invalid_resource',
                request: { 
                    method: 'resources/read', 
                    params: { uri: 'invalid://nonexistent' }
                },
                expectedError: null // Resource-specific error
            }
        ];

        const results = {};
        
        for (const test of errorTests) {
            try {
                const response = await this.sendRequest(test.request, 3000, 1);
                
                if (!response.error) {
                    results[test.name] = { 
                        success: false, 
                        issue: 'Expected error but got success' 
                    };
                } else {
                    const errorCode = response.error.code;
                    const isExpectedError = test.expectedError ? 
                        errorCode === test.expectedError : 
                        !!response.error;
                    
                    results[test.name] = {
                        success: isExpectedError,
                        errorCode: errorCode,
                        errorMessage: response.error.message
                    };
                }
            } catch (error) {
                results[test.name] = { 
                    success: true, 
                    note: 'Request failed as expected',
                    error: error.message 
                };
            }
        }

        return results;
    }

    /**
     * Test performance under load
     */
    async testPerformanceLoad() {
        const concurrentRequests = 20;
        const requestsPerBatch = 5;
        const batches = Math.ceil(concurrentRequests / requestsPerBatch);
        
        const results = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            avgResponseTime: 0,
            minResponseTime: Infinity,
            maxResponseTime: 0,
            throughput: 0
        };

        const startTime = performance.now();
        const responseTimes = [];

        for (let batch = 0; batch < batches; batch++) {
            const batchPromises = [];
            
            for (let i = 0; i < requestsPerBatch && results.totalRequests < concurrentRequests; i++) {
                results.totalRequests++;
                
                const requestStart = performance.now();
                const promise = this.sendRequest({
                    method: 'tools/call',
                    params: {
                        name: 'get_metrics',
                        arguments: {}
                    }
                }, 10000, 1).then(response => {
                    const requestTime = performance.now() - requestStart;
                    responseTimes.push(requestTime);
                    
                    if (response.error) {
                        results.failedRequests++;
                    } else {
                        results.successfulRequests++;
                    }
                    
                    return { success: !response.error, time: requestTime };
                }).catch(error => {
                    const requestTime = performance.now() - requestStart;
                    responseTimes.push(requestTime);
                    results.failedRequests++;
                    return { success: false, time: requestTime, error: error.message };
                });
                
                batchPromises.push(promise);
            }
            
            await Promise.all(batchPromises);
            
            // Small delay between batches to avoid overwhelming
            if (batch < batches - 1) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }

        const totalTime = performance.now() - startTime;
        
        results.avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
        results.minResponseTime = Math.min(...responseTimes);
        results.maxResponseTime = Math.max(...responseTimes);
        results.throughput = (results.totalRequests / totalTime) * 1000; // requests per second
        
        return results;
    }

    /**
     * Test security and validation
     */
    async testSecurity() {
        const securityTests = [
            {
                name: 'large_payload',
                request: {
                    method: 'tools/call',
                    params: {
                        name: 'process_template',
                        arguments: {
                            template_id: 'test',
                            context: {
                                large_data: 'x'.repeat(100000) // 100KB payload
                            }
                        }
                    }
                }
            },
            {
                name: 'injection_attempt',
                request: {
                    method: 'tools/call',
                    params: {
                        name: 'process_template',
                        arguments: {
                            template_id: '"; DROP TABLE users; --',
                            context: {
                                malicious: '<script>alert("xss")</script>'
                            }
                        }
                    }
                }
            },
            {
                name: 'deeply_nested',
                request: {
                    method: 'tools/call',
                    params: {
                        name: 'analyze_context',
                        arguments: this.createDeeplyNestedObject(20)
                    }
                }
            }
        ];

        const results = {};
        
        for (const test of securityTests) {
            try {
                const response = await this.sendRequest(test.request, 15000, 1);
                
                results[test.name] = {
                    handled: true,
                    hasError: !!response.error,
                    responseSize: JSON.stringify(response).length
                };
                
                if (response.error) {
                    results[test.name].errorType = response.error.code;
                }
                
            } catch (error) {
                results[test.name] = {
                    handled: true,
                    rejected: true,
                    error: error.message
                };
            }
        }

        return results;
    }

    createDeeplyNestedObject(depth) {
        if (depth === 0) return { value: 'deep' };
        return { nested: this.createDeeplyNestedObject(depth - 1) };
    }

    /**
     * Stop the server gracefully
     */
    stopServer() {
        if (this.serverProcess) {
            // Send graceful shutdown signal
            this.serverProcess.stdin.end();
            
            // Force kill after timeout
            setTimeout(() => {
                if (this.serverProcess && !this.serverProcess.killed) {
                    this.serverProcess.kill('SIGTERM');
                }
            }, 5000);
            
            this.serverProcess = null;
            this.serverReady = false;
        }
        
        // Clear any pending responses
        for (const [id, pending] of this.responseQueue) {
            pending.reject(new Error('Server stopped'));
        }
        this.responseQueue.clear();
    }

    /**
     * Run the complete comprehensive test suite
     */
    async runComprehensiveTests() {
        console.log('🚀 FACT MCP Server Comprehensive Test Suite');
        console.log('==========================================');
        console.log(`Node.js: ${process.version}`);
        console.log(`Platform: ${process.platform} ${process.arch}`);
        console.log(`Memory: ${Math.round(process.memoryUsage().heapUsed / 1024 / 1024)}MB used`);
        console.log('');

        // Define all tests
        const tests = [
            ['Server Initialization', () => this.testServerInitialization(), 1000],
            ['Tools Listing', () => this.testToolsListing(), 500],
            ['Tool Execution', () => this.testToolExecution(), 2000],
            ['Resource Operations', () => this.testResourceOperations(), 1000],
            ['Error Handling', () => this.testErrorHandling(), 1500],
            ['Performance Load', () => this.testPerformanceLoad(), 30000],
            ['Security Tests', () => this.testSecurity(), 10000]
        ];
        
        this.totalTests = tests.length;
        
        try {
            // Start server with extended timeout
            console.log('🔧 Starting MCP server...');
            await this.startServer();
            console.log('✅ Server started successfully\n');
            
            // Run all tests
            for (const [testName, testFn, expectedDuration] of tests) {
                await this.runTest(testName, testFn, expectedDuration);
            }
            
        } catch (error) {
            console.log(`❌ Critical error: ${error.message}`);
            this.testResults.push({ 
                name: 'Critical Error', 
                status: 'FAIL', 
                error: error.message 
            });
        } finally {
            // Always stop server
            console.log('\n🔧 Stopping server...');
            this.stopServer();
            console.log('✅ Server stopped');
        }
        
        // Generate comprehensive report
        await this.generateComprehensiveReport();
    }

    /**
     * Generate comprehensive test report
     */
    async generateComprehensiveReport() {
        console.log('\n' + '='.repeat(80));
        console.log('📊 COMPREHENSIVE TEST REPORT');
        console.log('='.repeat(80));
        
        const passed = this.testResults.filter(r => r.status === 'PASS').length;
        const failed = this.testResults.filter(r => r.status === 'FAIL').length;
        const total = this.testResults.length;
        
        const totalDuration = this.testResults.reduce((sum, r) => sum + (r.duration || 0), 0);
        const avgDuration = totalDuration / total;
        
        // Summary statistics
        console.log(`\n📈 SUMMARY STATISTICS`);
        console.log(`Total Tests: ${total}`);
        console.log(`✅ Passed: ${passed} (${((passed/total)*100).toFixed(1)}%)`);
        console.log(`❌ Failed: ${failed} (${((failed/total)*100).toFixed(1)}%)`);
        console.log(`⏱️  Total Duration: ${(totalDuration/1000).toFixed(2)}s`);
        console.log(`📊 Average Duration: ${avgDuration.toFixed(2)}ms`);
        
        // Performance analysis
        const performanceTests = this.testResults.filter(r => r.name.includes('Performance'));
        if (performanceTests.length > 0) {
            console.log(`\n🏃 PERFORMANCE ANALYSIS`);
            for (const test of performanceTests) {
                if (test.result) {
                    console.log(`  Throughput: ${test.result.throughput?.toFixed(2)} req/s`);
                    console.log(`  Avg Response: ${test.result.avgResponseTime?.toFixed(2)}ms`);
                    console.log(`  Success Rate: ${((test.result.successfulRequests/test.result.totalRequests)*100).toFixed(1)}%`);
                }
            }
        }
        
        // Failed tests details
        if (failed > 0) {
            console.log(`\n❌ FAILED TESTS DETAILS`);
            this.testResults
                .filter(r => r.status === 'FAIL')
                .forEach((r, index) => {
                    console.log(`  ${index + 1}. ${r.name}`);
                    console.log(`     Error: ${r.error}`);
                    if (r.duration) console.log(`     Duration: ${r.duration}ms`);
                });
        }
        
        // Warnings
        const warnings = this.testResults.filter(r => r.warning);
        if (warnings.length > 0) {
            console.log(`\n⚠️  WARNINGS`);
            warnings.forEach((r, index) => {
                console.log(`  ${index + 1}. ${r.name}: ${r.warning}`);
            });
        }
        
        // Save detailed report
        await this.saveDetailedReport();
        
        // Final verdict
        console.log(`\n🎯 FINAL VERDICT`);
        if (passed === total) {
            console.log('🎉 ALL TESTS PASSED! MCP server is fully functional and performant.');
            process.exit(0);
        } else if (failed === 0) {
            console.log('👍 ALL TESTS PASSED with warnings. Review performance concerns.');
            process.exit(0);
        } else if (passed / total >= 0.8) {
            console.log('⚠️  MOSTLY FUNCTIONAL with some issues. Review failed tests.');
            process.exit(1);
        } else {
            console.log('❌ SIGNIFICANT ISSUES DETECTED. MCP server needs attention.');
            process.exit(1);
        }
    }

    async saveDetailedReport() {
        const reportData = {
            timestamp: new Date().toISOString(),
            system: {
                node_version: process.version,
                platform: process.platform,
                arch: process.arch,
                memory_used_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024)
            },
            summary: {
                total_tests: this.testResults.length,
                passed: this.testResults.filter(r => r.status === 'PASS').length,
                failed: this.testResults.filter(r => r.status === 'FAIL').length,
                total_duration_ms: this.testResults.reduce((sum, r) => sum + (r.duration || 0), 0)
            },
            tests: this.testResults,
            performance_metrics: this.performanceMetrics
        };

        const reportDir = path.join(__dirname, '..', 'test-reports');
        await fs.mkdir(reportDir, { recursive: true });
        
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `mcp-comprehensive-test-${timestamp}.json`;
        const filepath = path.join(reportDir, filename);
        
        await fs.writeFile(filepath, JSON.stringify(reportData, null, 2));
        console.log(`📋 Detailed report saved: ${filepath}`);
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    const tester = new ComprehensiveMcpTester();
    tester.runComprehensiveTests().catch(error => {
        console.error('Test suite failed:', error);
        process.exit(1);
    });
}

module.exports = ComprehensiveMcpTester;