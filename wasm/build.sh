#!/bin/bash

# FACT WASM Build Script
# Builds optimized WASM module for production and development

set -e

echo "🚀 Building FACT WASM Core..."

# Check if wasm-pack is installed
if ! command -v wasm-pack &> /dev/null; then
    echo "❌ wasm-pack not found. Installing..."
    curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh
fi

# Build directory
BUILD_DIR="../pkg"
CURRENT_DIR="."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf $BUILD_DIR
rm -rf ./pkg

# Development build (faster compilation)
echo "🔧 Building development version..."
wasm-pack build --target web --out-dir ./pkg-dev --dev

# Production build (optimized)
echo "🏗️ Building production version..."
wasm-pack build \
    --target web \
    --out-dir ../pkg \
    --release \
    --scope fact \
    -- --features "performance cache crypto"

# Verify builds
echo "📦 Verifying builds..."
if [ -f "../pkg/fact_wasm_core.js" ] && [ -f "../pkg/fact_wasm_core_bg.wasm" ]; then
    echo "✅ Production build successful"
    PROD_SIZE=$(wc -c < "../pkg/fact_wasm_core_bg.wasm")
    echo "   📊 WASM size: $(numfmt --to=iec-i --suffix=B $PROD_SIZE)"
else
    echo "❌ Production build failed"
    exit 1
fi

if [ -f "pkg-dev/fact_wasm_core.js" ] && [ -f "pkg-dev/fact_wasm_core_bg.wasm" ]; then
    echo "✅ Development build successful"
    DEV_SIZE=$(wc -c < "pkg-dev/fact_wasm_core_bg.wasm")
    echo "   📊 WASM size: $(numfmt --to=iec-i --suffix=B $DEV_SIZE)"
else
    echo "❌ Development build failed"
    exit 1
fi

# Generate TypeScript definitions
echo "📝 Generating TypeScript definitions..."
if command -v tsc &> /dev/null; then
    # Copy JS files to TS for type checking
    cp ../pkg/fact_wasm_core.js ../pkg/fact_wasm_core.d.ts.temp
    # Generate basic type definitions (in production, use proper TS generation)
    cat > ../pkg/fact_wasm_core.d.ts << 'EOF'
/* tslint:disable */
/* eslint-disable */

/**
 * High-performance query result structure
 */
export class QueryResult {
  free(): void;
  constructor(success: boolean, execution_time_ms: number, cache_hit: boolean, data: string);
  readonly success: boolean;
  readonly execution_time_ms: number;
  readonly cache_hit: boolean;
  data: string;
}

/**
 * High-performance cache with optimized hash maps
 */
export class FastCache {
  free(): void;
  constructor(max_size: number);
  set(key: string, data: string, ttl_ms: bigint): boolean;
  get(key: string): string | undefined;
  stats(): any;
  clear(): void;
}

/**
 * High-performance SQL query parser and optimizer
 */
export class QueryProcessor {
  free(): void;
  constructor();
  process_query(query: string): QueryResult;
  get_stats(): any;
  clear_cache(): void;
}

/**
 * Timer utility for performance measurements
 */
export class Timer {
  free(): void;
  constructor(label: string);
  elapsed(): number;
  finish(): number;
}

/**
 * Performance testing utilities
 */
export class PerformanceProfiler {
  free(): void;
  constructor();
  mark(label: string): void;
  get_report(): any;
  reset(): void;
}

export function greet(name: string): string;
export function get_wasm_info(): any;
export function benchmark_cache_operations(iterations: number): any;
export function get_memory_usage(): any;
export function safe_json_parse(json_str: string): any;
export function simple_hash(input: string): number;
export function validate_sql_query(query: string): any;
export function escape_sql_string(input: string): string;
export function format_bytes(bytes: number): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
  readonly memory: WebAssembly.Memory;
}

export default function init (module_or_path?: InitInput | Promise<InitInput>): Promise<InitOutput>;
EOF
    rm -f ../pkg/fact_wasm_core.d.ts.temp
    echo "✅ TypeScript definitions generated"
else
    echo "⚠️ TypeScript not found, skipping type definitions"
fi

# Create integration example
echo "📋 Creating integration examples..."
mkdir -p examples

cat > examples/browser-integration.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>FACT WASM Browser Integration</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .result { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 4px; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; }
        .benchmark { background: #e8f5e8; }
        .error { background: #ffe8e8; }
    </style>
</head>
<body>
    <h1>FACT WASM Integration Demo</h1>
    
    <div>
        <button onclick="testCache()">Test Cache</button>
        <button onclick="testQueryProcessor()">Test Query Processor</button>
        <button onclick="runBenchmark()">Run Benchmark</button>
        <button onclick="getMemoryUsage()">Memory Usage</button>
    </div>
    
    <div id="results"></div>

    <script type="module">
        import init, { 
            FastCache, 
            QueryProcessor, 
            benchmark_cache_operations,
            get_memory_usage,
            get_wasm_info,
            greet
        } from '../pkg/fact_wasm_core.js';

        let cache, processor;

        async function initWasm() {
            await init();
            
            cache = new FastCache(1000);
            processor = new QueryProcessor();
            
            log('✅ WASM initialized successfully');
            log('🎉 ' + greet('FACT System'));
            log('📋 Module info:', get_wasm_info());
        }

        function log(message, data = null) {
            const results = document.getElementById('results');
            const div = document.createElement('div');
            div.className = 'result';
            div.innerHTML = message;
            if (data) {
                div.innerHTML += '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            }
            results.appendChild(div);
        }

        window.testCache = () => {
            try {
                cache.set('test-key', JSON.stringify({message: 'Hello WASM!'}), 60000);
                const result = cache.get('test-key');
                log('Cache test result:', JSON.parse(result));
                log('Cache stats:', cache.stats());
            } catch (e) {
                log('❌ Cache test failed: ' + e.message);
            }
        };

        window.testQueryProcessor = () => {
            try {
                const result = processor.process_query('SELECT * FROM companies');
                log('Query result:', {
                    success: result.success,
                    execution_time: result.execution_time_ms + 'ms',
                    cache_hit: result.cache_hit,
                    data: JSON.parse(result.data)
                });
                log('Processor stats:', processor.get_stats());
            } catch (e) {
                log('❌ Query test failed: ' + e.message);
            }
        };

        window.runBenchmark = () => {
            try {
                log('🚀 Running benchmark...');
                const result = benchmark_cache_operations(10000);
                const div = document.querySelector('#results div:last-child');
                div.className = 'result benchmark';
                log('📊 Benchmark results:', result);
            } catch (e) {
                log('❌ Benchmark failed: ' + e.message);
            }
        };

        window.getMemoryUsage = () => {
            try {
                const usage = get_memory_usage();
                log('💾 Memory usage:', usage);
            } catch (e) {
                log('❌ Memory check failed: ' + e.message);
            }
        };

        // Initialize on page load
        initWasm().catch(e => {
            document.getElementById('results').innerHTML = 
                '<div class="result error">❌ Failed to initialize WASM: ' + e.message + '</div>';
        });
    </script>
</body>
</html>
EOF

cat > examples/node-integration.js << 'EOF'
// FACT WASM Node.js Integration Example

const fs = require('fs');
const path = require('path');

async function testNodeIntegration() {
    try {
        console.log('🚀 Testing FACT WASM in Node.js...');
        
        // Load WASM module
        const wasmPath = path.join(__dirname, '../pkg/fact_wasm_core_bg.wasm');
        const wasmBytes = fs.readFileSync(wasmPath);
        
        // Import the JS bindings
        const { 
            FastCache, 
            QueryProcessor, 
            benchmark_cache_operations,
            get_memory_usage,
            get_wasm_info,
            greet,
            default: init
        } = require('../pkg/fact_wasm_core.js');
        
        // Initialize WASM
        await init(wasmBytes);
        
        console.log('✅ WASM initialized');
        console.log('🎉', greet('Node.js'));
        console.log('📋 Module info:', get_wasm_info());
        
        // Test cache
        console.log('\n🧪 Testing cache...');
        const cache = new FastCache(1000);
        cache.set('test', JSON.stringify({hello: 'world'}), 60000n);
        const result = cache.get('test');
        console.log('Cache result:', JSON.parse(result));
        console.log('Cache stats:', cache.stats());
        
        // Test query processor
        console.log('\n🧪 Testing query processor...');
        const processor = new QueryProcessor();
        const queryResult = processor.process_query('SELECT * FROM test_table');
        console.log('Query result:', {
            success: queryResult.success,
            execution_time: queryResult.execution_time_ms + 'ms',
            cache_hit: queryResult.cache_hit,
            data: JSON.parse(queryResult.data)
        });
        
        // Run benchmark
        console.log('\n📊 Running benchmark...');
        const benchmarkResult = benchmark_cache_operations(10000);
        console.log('Benchmark results:', benchmarkResult);
        
        // Memory usage
        console.log('\n💾 Memory usage:', get_memory_usage());
        
        console.log('\n✅ All tests passed!');
        
    } catch (error) {
        console.error('❌ Test failed:', error);
        process.exit(1);
    }
}

testNodeIntegration();
EOF

echo "📁 Build complete! Files generated:"
echo "  📦 Production build: ../pkg/"
echo "  🔧 Development build: ./pkg-dev/"
echo "  🌐 Browser example: ./examples/browser-integration.html"
echo "  🟢 Node.js example: ./examples/node-integration.js"
echo ""
echo "🚀 To use in your project:"
echo "  import init, { FastCache, QueryProcessor } from './pkg/fact_wasm_core.js';"
echo "  await init();"
echo ""
echo "✅ FACT WASM build completed successfully!"