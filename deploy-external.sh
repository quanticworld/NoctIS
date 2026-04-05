#!/bin/bash
# Deploy NoctIS on external disk OS
# This script should be run when booted into the OS on the external USB disk

set -e

echo "========================================="
echo "NoctIS Deployment for External Disk OS"
echo "========================================="
echo ""

# Check if we're running on the external OS
if [ ! -d "/home/quantic/NoctIS" ]; then
    echo "ERROR: This script should be run from the external disk OS"
    echo "Current working directory: $(pwd)"
    echo "Expected to be in: /home/quantic/NoctIS"
    exit 1
fi

# Create data directory for ClickHouse if it doesn't exist
echo "[1/4] Creating ClickHouse data directory..."
mkdir -p /home/quantic/NoctIS/data/clickhouse
chmod 755 /home/quantic/NoctIS/data/clickhouse

# Stop any running containers
echo "[2/4] Stopping existing containers..."
docker-compose -f docker-compose.external.yml down 2>/dev/null || true

# Build and start services
echo "[3/4] Building and starting services..."
docker-compose -f docker-compose.external.yml up -d --build

# Wait for services to be healthy
echo "[4/4] Waiting for services to be ready..."
echo "  - Waiting for ClickHouse..."
for i in {1..30}; do
    if docker-compose -f docker-compose.external.yml exec -T clickhouse wget --spider -q http://localhost:8123/ping 2>/dev/null; then
        echo "  ✓ ClickHouse is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ✗ ClickHouse failed to start"
        docker-compose -f docker-compose.external.yml logs clickhouse
        exit 1
    fi
    sleep 2
done

echo "  - Waiting for Backend..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health >/dev/null 2>&1; then
        echo "  ✓ Backend is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ✗ Backend failed to start"
        docker-compose -f docker-compose.external.yml logs backend
        exit 1
    fi
    sleep 2
done

echo ""
echo "========================================="
echo "✓ Deployment complete!"
echo "========================================="
echo ""
echo "Services are running:"
echo "  - Frontend: http://localhost:5174"
echo "  - Backend:  http://localhost:8001"
echo "  - ClickHouse: http://localhost:8123"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.external.yml logs -f"
echo ""
echo "To stop services:"
echo "  docker-compose -f docker-compose.external.yml down"
echo ""
