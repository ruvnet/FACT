#!/usr/bin/env node

/**
 * Simple CLI test script
 * Tests basic functionality of the FACT CLI
 */

import { spawn } from 'child_process';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const CLI_PATH = join(__dirname, 'dist', 'bin', 'fact.js');

async function runTest(command, args = [], expectedInOutput = null, shouldSucceed = true) {
  return new Promise((resolve) => {
    console.log(`\n🧪 Testing: fact ${command} ${args.join(' ')}`);
    
    const process = spawn('node', [CLI_PATH, command, ...args], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    const timeout = setTimeout(() => {
      process.kill('SIGTERM');
      console.log('⏰ Test timed out');
      resolve({ success: false, reason: 'timeout' });
    }, 10000); // 10 second timeout

    process.on('close', (code) => {
      clearTimeout(timeout);
      
      const output = stdout + stderr;
      const success = shouldSucceed ? code === 0 : code !== 0;
      
      if (expectedInOutput && !output.includes(expectedInOutput)) {
        console.log(`❌ Expected "${expectedInOutput}" in output`);
        console.log(`   Got: ${output.substring(0, 100)}...`);
        resolve({ success: false, reason: 'missing_output' });
        return;
      }

      if (success) {
        console.log(`✅ Test passed`);
        resolve({ success: true, output });
      } else {
        console.log(`❌ Test failed (exit code: ${code})`);
        console.log(`   Output: ${output.substring(0, 200)}...`);
        resolve({ success: false, reason: 'exit_code', code, output });
      }
    });

    process.on('error', (error) => {
      clearTimeout(timeout);
      console.log(`❌ Process error: ${error.message}`);
      resolve({ success: false, reason: 'process_error', error });
    });
  });
}

async function runAllTests() {
  console.log('🚀 Starting FACT CLI Tests\n');
  console.log('=' .repeat(50));

  const tests = [
    // Basic functionality tests
    { name: 'Help Command', command: '--help', expected: 'Commands:', shouldSucceed: true },
    { name: 'Version Command', command: '--version', expected: '1.0.0', shouldSucceed: true },
    { name: 'Status Command', command: 'status', expected: 'System Status', shouldSucceed: true },
    
    // Tool commands
    { name: 'Tools List', command: 'tools', args: ['list'], expected: null, shouldSucceed: true },
    { name: 'Config Show', command: 'config', args: ['show'], expected: null, shouldSucceed: true },
    
    // WASM commands
    { name: 'WASM Info', command: 'wasm', args: ['info'], expected: null, shouldSucceed: true },
    
    // Cache commands
    { name: 'Cache Stats', command: 'cache', args: ['stats'], expected: null, shouldSucceed: true }
  ];

  const results = [];

  for (const test of tests) {
    const result = await runTest(
      test.command,
      test.args || [],
      test.expected,
      test.shouldSucceed
    );
    
    results.push({
      name: test.name,
      success: result.success,
      reason: result.reason
    });
  }

  // Summary
  console.log('\n' + '=' .repeat(50));
  console.log('📊 Test Results Summary\n');

  const passed = results.filter(r => r.success).length;
  const total = results.length;

  results.forEach(result => {
    const icon = result.success ? '✅' : '❌';
    const reason = result.reason ? ` (${result.reason})` : '';
    console.log(`${icon} ${result.name}${reason}`);
  });

  console.log(`\n📈 Overall: ${passed}/${total} tests passed`);

  if (passed === total) {
    console.log('🎉 All tests passed! CLI is working correctly.');
    return true;
  } else {
    console.log('⚠️  Some tests failed. CLI may have issues.');
    return false;
  }
}

// Run tests if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests()
    .then(success => {
      process.exit(success ? 0 : 1);
    })
    .catch(error => {
      console.error('Test runner error:', error);
      process.exit(1);
    });
}

export { runAllTests };