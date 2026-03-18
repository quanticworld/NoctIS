#!/bin/bash
# Stop development services

set -e

echo "🛑 Stopping NoctIS development services..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Read PIDs
if [ -f .backend.pid ]; then
    BACKEND_PID=$(cat .backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${GREEN}Stopping backend (PID: $BACKEND_PID)${NC}"
        kill $BACKEND_PID 2>/dev/null || true
    fi
    rm .backend.pid
fi

if [ -f .frontend.pid ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "${GREEN}Stopping frontend (PID: $FRONTEND_PID)${NC}"
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    rm .frontend.pid
fi

# Kill any remaining processes
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite.*frontend" 2>/dev/null || true

echo -e "${GREEN}✅ Services stopped${NC}"
