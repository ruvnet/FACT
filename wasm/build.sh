#\!/bin/bash
# FACT WASM Build Script
set -e
echo "🚀 Building FACT WASM Core..."
wasm-pack build --target web --out-dir pkg
echo "✅ Build completed\!"
EOF < /dev/null
