#!/bin/bash
# Setup ClickHouse external volume with proper permissions

set -e

VOLUME_BASE="/media/quantic/80c1859f-536b-459f-a547-d6ecf1dfceea/home/quantic/NoctIS/data"
CLICKHOUSE_DIR="${VOLUME_BASE}/clickhouse"

echo "=================================================="
echo "ClickHouse Volume Setup"
echo "=================================================="
echo ""
echo "Volume path: ${CLICKHOUSE_DIR}"
echo ""

# Check if base volume is mounted
if [ ! -d "$VOLUME_BASE" ]; then
    echo "❌ ERROR: Base volume not mounted at ${VOLUME_BASE}"
    echo "   Please mount your external USB drive first"
    exit 1
fi

echo "✅ Base volume found"

# Create ClickHouse directory if it doesn't exist
if [ ! -d "$CLICKHOUSE_DIR" ]; then
    echo "📁 Creating ClickHouse directory..."
    sudo mkdir -p "$CLICKHOUSE_DIR"
    echo "✅ Directory created"
else
    echo "✅ ClickHouse directory already exists"
fi

# Set permissions
echo "🔐 Setting permissions..."
echo "   (ClickHouse runs as UID:GID 101:101 in container)"

# Option 1: Strict permissions (recommended for production)
# sudo chown -R 101:101 "$CLICKHOUSE_DIR"
# sudo chmod -R 755 "$CLICKHOUSE_DIR"

# Option 2: Permissive (easier for development)
sudo chmod -R 777 "$CLICKHOUSE_DIR"

echo "✅ Permissions set"

# Check disk space
echo ""
echo "💾 Disk space check:"
df -h "$VOLUME_BASE" | tail -n 1

AVAILABLE_GB=$(df -BG "$VOLUME_BASE" | tail -n 1 | awk '{print $4}' | sed 's/G//')

echo ""
if [ "$AVAILABLE_GB" -lt 100 ]; then
    echo "⚠️  WARNING: Less than 100GB available"
    echo "   For 3 billion records, you'll need ~300-500GB"
else
    echo "✅ Sufficient disk space available (${AVAILABLE_GB}GB)"
fi

echo ""
echo "=================================================="
echo "✅ ClickHouse volume setup complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. docker-compose up -d clickhouse"
echo "  2. python3 test_clickhouse.py"
