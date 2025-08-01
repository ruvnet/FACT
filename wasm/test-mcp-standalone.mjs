#!/usr/bin/env node

/**
 * Standalone test for FACT MCP Server
 * Tests the server functionality without requiring Claude integration
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Test cases for MCP server
const testCases = [
    {
        name: 'Initialize Server',
        request: {
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
        }
    },
    {
        name: 'List Tools',
        request: {
            jsonrpc: '2.0',
            id: 2,
            method: 'tools/list'
        }
    },
    {
        name: 'List Resources',
        request: {
            jsonrpc: '2.0',
            id: 3,
            method: 'resources/list'
        }
    },
    {
        name: 'Health Check',
        request: {
            jsonrpc: '2.0',
            id: 4,
            method: 'tools/call',
            params: {
                name: 'health_check',
                arguments: {
                    include_wasm: true,
                    include_cache: true,
                    verbose: true
                }
            }
        }
    },
    {
        name: 'Get Metrics',
        request: {
            jsonrpc: '2.0',
            id: 5,
            method: 'tools/call',
            params: {
                name: 'get_metrics',
                arguments: {
                    category: 'all',
                    format: 'summary'
                }
            }
        }
    },
    {
        name: 'List Templates',
        request: {
            jsonrpc: '2.0',
            id: 6,
            method: 'tools/call',
            params: {
                name: 'list_templates',
                arguments: {}
            }
        }
    },
    {
        name: 'Process Template',
        request: {
            jsonrpc: '2.0',
            id: 7,
            method: 'tools/call',
            params: {
                name: 'process_template',
                arguments: {
                    template_id: 'data-analysis',
                    context: {
                        data: [1, 2, 3, 4, 5],
                        query: 'analyze this data for trends'
                    },
                    options: {
                        cache: true,
                        priority: 'medium'
                    }
                }
            }
        }
    },
    {
        name: 'Benchmark Performance',
        request: {
            jsonrpc: '2.0',
            id: 8,
            method: 'tools/call',
            params: {
                name: 'benchmark_performance',
                arguments: {
                    test_type: 'template_processing',
                    iterations: 10,
                    payload_size: 'small'
                }
            }
        }
    },
    {
        name: 'Ping Test',
        request: {
            jsonrpc: '2.0',
            id: 9,
            method: 'ping'
        }
    }
];

async function runTests() {
    console.log('🧪 Starting FACT MCP Server Tests');
    console.log('==================================');
    
    const serverPath = join(__dirname, 'src', 'mcp-server.js');
    console.log(`📍 Server path: ${serverPath}`);
    
    // Start the MCP server
    const server = spawn('node', [serverPath], {
        stdio: ['pipe', 'pipe', 'pipe']
    });
    
    let testResults = [];
    let currentTest = 0;
    
    return new Promise((resolve, reject) => {
        // Handle server stderr (server logs)
        server.stderr.on('data', (data) => {
            const message = data.toString().trim();
            if (message) {
                console.log(`🖥️  Server: ${message}`);
            }
        });
        
        // Handle server stdout (JSON-RPC responses)
        let responseBuffer = '';
        server.stdout.on('data', (data) => {
            responseBuffer += data.toString();
            
            // Process complete JSON responses
            const lines = responseBuffer.split('\n');
            responseBuffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line.trim());
                        console.log(`📥 Response ${response.id}:`, JSON.stringify(response, null, 2));
                        
                        testResults.push({
                            test: testCases[currentTest - 1]?.name || `Test ${response.id}`,
                            request: testCases[currentTest - 1]?.request,
                            response,
                            success: !response.error,
                            timestamp: new Date().toISOString()
                        });
                        
                        // Continue with next test
                        if (currentTest < testCases.length) {
                            setTimeout(() => sendNextTest(), 500);
                        } else {
                            // All tests completed
                            setTimeout(() => {
                                server.kill('SIGTERM');
                                resolve(testResults);
                            }, 1000);
                        }
                    } catch (error) {
                        console.error('❌ Failed to parse response:', line);
                        console.error('   Error:', error.message);
                    }
                }
            }
        });
        
        // Handle server errors
        server.on('error', (error) => {
            console.error('💥 Server error:', error);
            reject(error);
        });
        
        server.on('close', (code) => {
            console.log(`🔚 Server process exited with code ${code}`);
        });
        
        // Send test requests
        function sendNextTest() {
            if (currentTest >= testCases.length) {
                return;
            }
            
            const testCase = testCases[currentTest];
            currentTest++;
            
            console.log(`\n📤 Test ${currentTest}/${testCases.length}: ${testCase.name}`);
            console.log('   Request:', JSON.stringify(testCase.request, null, 2));
            
            // Send request to server
            server.stdin.write(JSON.stringify(testCase.request) + '\n');
        }
        
        // Wait for server to initialize, then start tests
        setTimeout(() => {
            console.log('\n🚀 Starting test sequence...\n');
            sendNextTest();
        }, 2000);
        
        // Timeout after 30 seconds
        setTimeout(() => {
            console.error('⏰ Test timeout reached');
            server.kill('SIGTERM');
            reject(new Error('Test timeout'));
        }, 30000);
    });
}

// Run the tests
runTests()
    .then((results) => {
        console.log('\n📊 Test Results Summary');
        console.log('========================');
        
        const successful = results.filter(r => r.success).length;
        const failed = results.filter(r => !r.success).length;
        
        console.log(`✅ Successful: ${successful}`);
        console.log(`❌ Failed: ${failed}`);
        console.log(`📈 Success Rate: ${(successful / results.length * 100).toFixed(1)}%`);
        
        console.log('\n📋 Detailed Results:');
        results.forEach((result, index) => {
            const status = result.success ? '✅' : '❌';
            console.log(`${status} ${index + 1}. ${result.test}`);
            if (!result.success && result.response.error) {
                console.log(`   Error: ${result.response.error.message}`);
            }
        });
        
        console.log('\n🎯 Test completed successfully!');
        process.exit(successful === results.length ? 0 : 1);
    })
    .catch((error) => {
        console.error('💥 Test failed:', error);
        process.exit(1);
    });