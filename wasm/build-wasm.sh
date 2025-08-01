#!/bin/bash
# FACT WASM Build Script
# Builds optimized WASM modules for different targets

set -e

echo "🚀 Building FACT WASM Core..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_build() {
    echo -e "${BLUE}[BUILD]${NC} $1"
}

# Check if wasm-pack is installed
if ! command -v wasm-pack &> /dev/null; then
    print_error "wasm-pack is not installed. Please install it first:"
    echo "  curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh"
    exit 1
fi

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf pkg/
rm -rf target/wasm32-unknown-unknown/

# Build for web target (optimized)
print_build "Building WASM for web target..."
wasm-pack build --target web --out-dir pkg --release --features performance,cache

# Check build success
if [ ! -f "pkg/fact_wasm_core_bg.wasm" ]; then
    print_error "WASM build failed!"
    exit 1
fi

# Get file size
WASM_SIZE=$(du -h pkg/fact_wasm_core_bg.wasm | cut -f1)
print_status "WASM file size: $WASM_SIZE"

# Create additional target builds
print_build "Building additional targets..."

# Node.js target
mkdir -p pkg/nodejs
wasm-pack build --target nodejs --out-dir pkg/nodejs --release --features performance,cache

# Bundler target  
mkdir -p pkg/bundler
wasm-pack build --target bundler --out-dir pkg/bundler --release --features performance,cache

# Update package.json with proper exports
print_status "Creating optimized package.json..."
cat > pkg/package.json << 'EOF'
{
  "name": "fact-wasm-core",
  "version": "0.1.0",
  "description": "High-performance WASM core for FACT (Fast Augmented Context Tools)",
  "main": "fact_wasm_core.js",
  "module": "fact_wasm_core.js",
  "types": "fact_wasm_core.d.ts",
  "sideEffects": [
    "./fact_wasm_core.js",
    "./snippets/*"
  ],
  "exports": {
    ".": {
      "types": "./fact_wasm_core.d.ts",
      "import": "./fact_wasm_core.js",
      "require": "./fact_wasm_core.js"
    },
    "./nodejs": {
      "types": "./nodejs/fact_wasm_core.d.ts", 
      "import": "./nodejs/fact_wasm_core.js",
      "require": "./nodejs/fact_wasm_core.js"
    },
    "./bundler": {
      "types": "./bundler/fact_wasm_core.d.ts",
      "import": "./bundler/fact_wasm_core.js"
    }
  },
  "files": [
    "fact_wasm_core_bg.wasm",
    "fact_wasm_core.js", 
    "fact_wasm_core.d.ts",
    "nodejs/",
    "bundler/",
    "README.md"
  ],
  "keywords": [
    "wasm",
    "webassembly", 
    "rust",
    "fact",
    "cognitive-templates",
    "ai",
    "performance",
    "cache",
    "fast",
    "optimization"
  ],
  "author": "FACT Team",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/ruvnet/FACT.git",
    "directory": "wasm"
  },
  "homepage": "https://github.com/ruvnet/FACT#readme",
  "bugs": {
    "url": "https://github.com/ruvnet/FACT/issues"
  },
  "engines": {
    "node": ">=14.0.0"
  }
}
EOF

# Display build summary
echo ""
print_status "🎯 Build Summary"
echo "=================="

echo "📦 Package: fact-wasm-core v0.1.0"
echo "📊 WASM Size: $WASM_SIZE"
echo "🎯 Targets built:"

for target in . nodejs bundler; do
    if [ "$target" = "." ]; then
        target_name="web"
        wasm_file="pkg/fact_wasm_core_bg.wasm"
    else
        target_name="$target"
        wasm_file="pkg/$target/fact_wasm_core_bg.wasm"
    fi
    
    if [ -f "$wasm_file" ]; then
        size=$(du -h "$wasm_file" | cut -f1)
        print_status "  ✅ $target_name: $size"
    else
        print_error "  ❌ $target_name: Build failed"
    fi
done

echo "=================="
print_status "🚀 FACT WASM build completed successfully!"
print_status "📁 Package directory: ./pkg/"

# Create a simple test to verify the build
print_status "🧪 Running basic verification..."
if node -e "
const fs = require('fs');
const wasmPath = './pkg/fact_wasm_core_bg.wasm';
if (fs.existsSync(wasmPath)) {
    const stats = fs.statSync(wasmPath);
    console.log('✅ WASM file verified: ' + (stats.size / 1024).toFixed(1) + 'KB');
} else {
    console.log('❌ WASM file not found');
    process.exit(1);
}
"; then
    print_status "✅ Verification passed!"
else
    print_warning "⚠️  Verification skipped (Node.js not available)"
fi

echo ""
print_status "🔗 Next steps:"
echo "  1. Test the WASM module: node -e \"require('./pkg/nodejs/').then(console.log)\""  
echo "  2. Publish to NPM: cd pkg && npm publish"
echo "  3. Use in web: import init from './pkg/fact_wasm_core.js'"
echo "  4. Update project documentation"