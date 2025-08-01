#!/usr/bin/env node

/**
 * FACT MCP Server Tests
 * 
 * Comprehensive test suite for the MCP server implementation
 */

const { spawn } = require('child_process');
const { createInterface } = require('readline');
const path = require('path');

/**
 * Test runner class
 */
class McpServerTester {
    constructor() {
        this.serverProcess = null;
        this.testResults = [];
        this.currentTest = 0;
        this.totalTests = 0;
    }

    /**
     * Start the MCP server process
     */
    async startServer() {
        return new Promise((resolve, reject) => {
            const serverPath = path.join(__dirname, '../src/mcp-server.js');
            this.serverProcess = spawn('node', [serverPath], {
                stdio: ['pipe', 'pipe', 'pipe'],
                cwd: path.dirname(serverPath)
            });

            this.serverProcess.stderr.on('data', (data) => {
                const message = data.toString();
                if (message.includes('FACT MCP Server ready')) {
                    resolve();
                } else if (message.includes('Fatal error')) {
                    reject(new Error(`Server startup failed: ${message}`));
                }
            });

            this.serverProcess.on('error', reject);
            
            // Timeout after 10 seconds
            setTimeout(() => {
                reject(new Error('Server startup timeout'));
            }, 10000);
        });
    }

    /**
     * Stop the MCP server process
     */
    stopServer() {
        if (this.serverProcess) {
            this.serverProcess.kill('SIGTERM');
            this.serverProcess = null;
        }
    }

    /**
     * Send a JSON-RPC request to the server
     */
    async sendRequest(request) {
        return new Promise((resolve, reject) => {
            if (!this.serverProcess) {
                reject(new Error('Server not running'));
                return;
            }

            let responseData = '';
            let responseReceived = false;

            const onData = (data) => {
                responseData += data.toString();
                const lines = responseData.split('\n');
                
                for (const line of lines) {
                    if (line.trim() && line.startsWith('{')) {
                        try {
                            const response = JSON.parse(line);
                            if (response.jsonrpc === '2.0' && response.id === request.id) {
                                this.serverProcess.stdout.removeListener('data', onData);
                                responseReceived = true;
                                resolve(response);
                                return;
                            }
                        } catch (e) {
                            // Continue parsing
                        }
                    }
                }
            };

            this.serverProcess.stdout.on('data', onData);
            
            // Send request
            this.serverProcess.stdin.write(JSON.stringify(request) + '\n');

            // Timeout after 5 seconds
            setTimeout(() => {
                if (!responseReceived) {
                    this.serverProcess.stdout.removeListener('data', onData);
                    reject(new Error('Request timeout'));
                }
            }, 5000);
        });
    }

    /**
     * Run a single test
     */
    async runTest(testName, testFn) {
        this.currentTest++;
        console.log(`\n[${this.currentTest}/${this.totalTests}] Running: ${testName}`);
        
        const startTime = Date.now();
        
        try {
            await testFn();
            const duration = Date.now() - startTime;
            console.log(`✅ PASS: ${testName} (${duration}ms)`);
            this.testResults.push({ name: testName, status: 'PASS', duration });
        } catch (error) {
            const duration = Date.now() - startTime;
            console.log(`❌ FAIL: ${testName} (${duration}ms)`);
            console.log(`   Error: ${error.message}`);
            this.testResults.push({ name: testName, status: 'FAIL', duration, error: error.message });
        }
    }

    /**
     * Test server initialization
     */
    async testInitialization() {
        const request = {
            jsonrpc: '2.0',
            id: 1,
            method: 'initialize',
            params: {
                protocolVersion: '2024-11-05',
                capabilities: {},
                clientInfo: {
                    name: 'test-client',
                    version: '1.0.0'
                }
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result) {
            throw new Error('No result in initialize response');
        }
        
        if (!response.result.serverInfo) {
            throw new Error('No serverInfo in initialize response');
        }
        
        if (response.result.serverInfo.name !== 'fact-mcp') {
            throw new Error(`Unexpected server name: ${response.result.serverInfo.name}`);
        }
    }

    /**
     * Test tools listing
     */
    async testToolsList() {
        const request = {
            jsonrpc: '2.0',
            id: 2,
            method: 'tools/list',
            params: {}
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.tools) {
            throw new Error('No tools in response');
        }
        
        const tools = response.result.tools;
        const expectedTools = [
            'process_template',
            'list_templates', 
            'analyze_context',
            'optimize_performance',
            'create_template',
            'get_metrics'
        ];
        
        for (const expectedTool of expectedTools) {
            const found = tools.find(t => t.name === expectedTool);
            if (!found) {
                throw new Error(`Tool not found: ${expectedTool}`);
            }
        }
    }

    /**
     * Test template listing
     */
    async testListTemplates() {
        const request = {
            jsonrpc: '2.0',
            id: 3,
            method: 'tools/call',
            params: {
                name: 'list_templates',
                arguments: {}
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.content) {
            throw new Error('No content in response');
        }
        
        const content = JSON.parse(response.result.content[0].text);
        
        if (!content.success) {
            throw new Error(`Tool call failed: ${content.error}`);
        }
        
        if (!content.templates || !Array.isArray(content.templates)) {
            throw new Error('No templates array in response');
        }
        
        if (content.templates.length === 0) {
            throw new Error('No templates returned');
        }
    }

    /**
     * Test template processing
     */
    async testProcessTemplate() {
        const request = {
            jsonrpc: '2.0',
            id: 4,
            method: 'tools/call',
            params: {
                name: 'process_template',
                arguments: {
                    template_id: 'data-analysis',
                    context: {
                        data: [1, 2, 3, 4, 5],
                        query: 'analyze this dataset'
                    },
                    options: {
                        cache: true
                    }
                }
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.content) {
            throw new Error('No content in response');
        }
        
        const content = JSON.parse(response.result.content[0].text);
        
        if (!content.success) {
            throw new Error(`Template processing failed: ${content.error}`);
        }
        
        if (!content.result) {
            throw new Error('No result in template processing response');
        }
        
        if (!content.metadata) {
            throw new Error('No metadata in template processing response');
        }
    }

    /**
     * Test context analysis
     */
    async testAnalyzeContext() {
        const request = {
            jsonrpc: '2.0',
            id: 5,
            method: 'tools/call',
            params: {
                name: 'analyze_context',
                arguments: {
                    context: {
                        query: 'How do I optimize my database queries?',
                        type: 'performance',
                        urgency: 'high'
                    },
                    suggest_templates: true
                }
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.content) {
            throw new Error('No content in response');
        }
        
        const content = JSON.parse(response.result.content[0].text);
        
        if (!content.success) {
            throw new Error(`Context analysis failed: ${content.error}`);
        }
        
        if (!content.analysis) {
            throw new Error('No analysis in response');
        }
        
        if (!content.suggested_templates) {
            throw new Error('No template suggestions in response');
        }
    }

    /**
     * Test performance optimization
     */
    async testOptimizePerformance() {
        const request = {
            jsonrpc: '2.0',
            id: 6,
            method: 'tools/call',
            params: {
                name: 'optimize_performance',
                arguments: {
                    operation: 'cache',
                    aggressive: false
                }
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.content) {
            throw new Error('No content in response');
        }
        
        const content = JSON.parse(response.result.content[0].text);
        
        if (!content.success) {
            throw new Error(`Performance optimization failed: ${content.error}`);
        }
        
        if (content.optimization !== 'cache') {
            throw new Error(`Unexpected optimization type: ${content.optimization}`);
        }
    }

    /**
     * Test metrics retrieval
     */
    async testGetMetrics() {
        const request = {
            jsonrpc: '2.0',
            id: 7,
            method: 'tools/call',
            params: {
                name: 'get_metrics',
                arguments: {}
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.content) {
            throw new Error('No content in response');
        }
        
        const content = JSON.parse(response.result.content[0].text);
        
        if (!content.success) {
            throw new Error(`Metrics retrieval failed: ${content.error}`);
        }
        
        if (!content.metrics) {
            throw new Error('No metrics in response');
        }
        
        if (!content.system_info) {
            throw new Error('No system info in response');
        }
    }

    /**
     * Test resources listing
     */
    async testResourcesList() {
        const request = {
            jsonrpc: '2.0',
            id: 8,
            method: 'resources/list',
            params: {}
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.resources) {
            throw new Error('No resources in response');
        }
        
        const resources = response.result.resources;
        
        if (!Array.isArray(resources)) {
            throw new Error('Resources is not an array');
        }
        
        if (resources.length === 0) {
            throw new Error('No resources returned');
        }
    }

    /**
     * Test resource reading
     */
    async testResourceRead() {
        const request = {
            jsonrpc: '2.0',
            id: 9,
            method: 'resources/read',
            params: {
                uri: 'template://data-analysis'
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.contents) {
            throw new Error('No contents in response');
        }
        
        const contents = response.result.contents[0];
        
        if (!contents.text) {
            throw new Error('No text content in resource');
        }
        
        const templateData = JSON.parse(contents.text);
        
        if (templateData.id !== 'data-analysis') {
            throw new Error(`Unexpected template ID: ${templateData.id}`);
        }
    }

    /**
     * Test error handling
     */
    async testErrorHandling() {
        const request = {
            jsonrpc: '2.0',
            id: 10,
            method: 'tools/call',
            params: {
                name: 'process_template',
                arguments: {
                    template_id: 'nonexistent-template',
                    context: {}
                }
            }
        };

        const response = await this.sendRequest(request);
        
        if (!response.result || !response.result.content) {
            throw new Error('No content in response');
        }
        
        const content = JSON.parse(response.result.content[0].text);
        
        if (content.success) {
            throw new Error('Expected error but got success');
        }
        
        if (!content.error) {
            throw new Error('No error message in failed response');
        }
    }

    /**
     * Run all tests
     */
    async runAllTests() {
        console.log('🧪 Starting FACT MCP Server Tests\n');
        
        // Define all tests
        const tests = [
            ['Server Initialization', () => this.testInitialization()],
            ['Tools List', () => this.testToolsList()],
            ['List Templates', () => this.testListTemplates()],
            ['Process Template', () => this.testProcessTemplate()],
            ['Analyze Context', () => this.testAnalyzeContext()],
            ['Optimize Performance', () => this.testOptimizePerformance()],
            ['Get Metrics', () => this.testGetMetrics()],
            ['Resources List', () => this.testResourcesList()],
            ['Resource Read', () => this.testResourceRead()],
            ['Error Handling', () => this.testErrorHandling()]
        ];
        
        this.totalTests = tests.length;
        
        try {
            // Start server
            console.log('🚀 Starting MCP server...');
            await this.startServer();
            console.log('✅ Server started successfully');
            
            // Run tests
            for (const [testName, testFn] of tests) {
                await this.runTest(testName, testFn);
            }
            
        } catch (error) {
            console.log(`❌ Server startup failed: ${error.message}`);
            this.testResults.push({ 
                name: 'Server Startup', 
                status: 'FAIL', 
                error: error.message 
            });
        } finally {
            // Stop server
            this.stopServer();
        }
        
        // Print summary
        this.printSummary();
    }

    /**
     * Print test summary
     */
    printSummary() {
        console.log('\n' + '='.repeat(60));
        console.log('🧪 TEST SUMMARY');
        console.log('='.repeat(60));
        
        const passed = this.testResults.filter(r => r.status === 'PASS').length;
        const failed = this.testResults.filter(r => r.status === 'FAIL').length;
        const total = this.testResults.length;
        
        console.log(`Total Tests: ${total}`);
        console.log(`✅ Passed: ${passed}`);
        console.log(`❌ Failed: ${failed}`);
        
        if (failed > 0) {
            console.log('\n❌ Failed Tests:');
            this.testResults
                .filter(r => r.status === 'FAIL')
                .forEach(r => {
                    console.log(`   • ${r.name}: ${r.error || 'Unknown error'}`);
                });
        }
        
        const totalDuration = this.testResults.reduce((sum, r) => sum + (r.duration || 0), 0);
        console.log(`\n⏱️  Total Duration: ${totalDuration}ms`);
        
        const successRate = total > 0 ? (passed / total * 100).toFixed(1) : 0;
        console.log(`📊 Success Rate: ${successRate}%`);
        
        if (passed === total) {
            console.log('\n🎉 All tests passed!');
            process.exit(0);
        } else {
            console.log('\n💥 Some tests failed!');
            process.exit(1);
        }
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    const tester = new McpServerTester();
    tester.runAllTests().catch(error => {
        console.error('Test runner failed:', error);
        process.exit(1);
    });
}

module.exports = McpServerTester;