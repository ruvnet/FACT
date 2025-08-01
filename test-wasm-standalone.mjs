#!/usr/bin/env node

/**
 * Standalone WASM test script to verify FACT WASM core integration
 * This tests the CLI WASM integration without Python dependencies
 */

import { pathToFileURL } from 'url';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require = createRequire(import.meta.url);

async function testWasmIntegration() {
  console.log('🧪 Testing FACT WASM Core Integration\n');

  try {
    // Import the WASM module using CommonJS require
    const wasmPath = join(__dirname, 'wasm', 'pkg', 'fact_wasm_core.js');
    const wasmModule = require(wasmPath);
    
    console.log('✅ WASM module loaded successfully');
    console.log('📦 Available exports:', Object.keys(wasmModule).filter(k => k !== '__wasm'));
    
    // Initialize if needed
    if (wasmModule.init && typeof wasmModule.init === 'function') {
      console.log('🔧 Initializing WASM module...');
      wasmModule.init();
      console.log('✅ WASM module initialized');
    }

    // Test FastCache
    if (wasmModule.FastCache) {
      console.log('\n💾 Testing FastCache...');
      const cache = new wasmModule.FastCache();
      
      // Test basic operations
      const testKey = 'test-key';
      const testValue = 'test-value';
      
      const putResult = cache.put(testKey, testValue);
      console.log(`✅ Cache put result: ${putResult}`);
      
      const getValue = cache.get(testKey);
      console.log(`✅ Cache get result: ${getValue}`);
      
      const stats = cache.get_stats();
      console.log('✅ Cache stats:', stats);
      
      const size = cache.size();
      console.log(`✅ Cache size: ${size} entries`);
      
      const memUsage = cache.memory_usage();
      console.log(`✅ Memory usage: ${memUsage} bytes`);
    }

    // Test QueryProcessor
    if (wasmModule.QueryProcessor) {
      console.log('\n🔍 Testing QueryProcessor...');
      const processor = new wasmModule.QueryProcessor();
      
      const testQuery = 'SELECT * FROM test';
      const result = processor.process(testQuery);
      console.log(`✅ Query processing result: ${result}`);
      
      const processorStats = processor.get_stats();
      console.log('✅ Processor stats:', processorStats);
    }

    // Test Fact engine
    if (wasmModule.Fact) {
      console.log('\n🧠 Testing Fact engine...');
      const fact = new wasmModule.Fact();
      
      const testQuery = 'What is the current status?';
      const factResult = fact.process(testQuery, true);
      console.log(`✅ FACT processing result: ${factResult}`);
      
      const factStats = fact.get_cache_stats();
      console.log('✅ FACT cache stats:', factStats);
    }

    // Test template processing
    if (wasmModule.process_template) {
      console.log('\n📝 Testing template processing...');
      const templateJson = JSON.stringify({
        name: 'test-template',
        pattern: 'Hello {{name}}!'
      });
      const contextJson = JSON.stringify({
        name: 'WASM'
      });
      
      const templateResult = wasmModule.process_template(templateJson, contextJson);
      console.log(`✅ Template processing result: ${templateResult}`);
    }

    console.log('\n🎉 All WASM tests completed successfully!');
    
    // Test CLI integration
    console.log('\n🖥️  Testing CLI WASM integration...');
    const { WasmLoader } = await import('./dist/lib/wasm-loader.js');
    const loader = new WasmLoader();
    
    await loader.initialize();
    const coreStatus = loader.getFactCore();
    
    console.log('✅ CLI WASM loader initialized:', coreStatus.initialized);
    
    if (coreStatus.initialized) {
      try {
        const cacheStats = loader.getCacheStats();
        console.log('✅ CLI cache stats access:', typeof cacheStats);
      } catch (e) {
        console.log('⚠️  CLI cache stats error:', e.message);
      }
      
      try {
        const queryResult = loader.processQuery('test query', true);
        console.log('✅ CLI query processing:', queryResult);
      } catch (e) {
        console.log('⚠️  CLI query processing error:', e.message);
      }
    }

    console.log('\n🚀 CLI WASM Integration Test Complete!');

  } catch (error) {
    console.error('❌ WASM test failed:', error.message);
    console.error('Stack:', error.stack);
    process.exit(1);
  }
}

// Run the test
testWasmIntegration();