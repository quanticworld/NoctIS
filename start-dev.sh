#!/bin/bash
# Development startup script without Docker
# This allows testing the app when Docker is not available

set -e

echo "🚀 Starting NoctIS in development mode (without Docker)..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Typesense is running (optional)
echo -e "${YELLOW}⚠️  Note: Typesense features will not work without Docker${NC}"
echo -e "${YELLOW}   You can still test ripgrep search functionality${NC}"
echo ""

# Set environment variables for backend
export PYTHONUNBUFFERED=1
export TYPESENSE_API_KEY=noctis_dev_key_change_in_prod
export TYPESENSE_HOST=localhost
export TYPESENSE_PORT=8108
export TYPESENSE_PROTOCOL=http
export SEARCH_PATH=/mnt/osint

# Check Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python found: $(python --version)${NC}"

# Check Node
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Node.js found: $(node --version)${NC}"
echo ""

# Install backend dependencies if needed
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}📦 Creating Python virtual environment...${NC}"
    cd backend
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
else
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
fi

echo ""
echo -e "${GREEN}🚀 Starting services...${NC}"
echo ""

# Start backend in background
echo -e "${YELLOW}Starting backend on http://localhost:8000${NC}"
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Start frontend in background
echo -e "${YELLOW}Starting frontend on http://localhost:5173${NC}"
cd frontend
VITE_API_URL=http://localhost:8000 npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for services to start
sleep 3

echo ""
echo -e "${GREEN}✅ Services started!${NC}"
echo ""
echo "📍 Backend:  http://localhost:8000"
echo "📍 Frontend: http://localhost:5173"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "📋 Process IDs:"
echo "   Backend:  $BACKEND_PID"
echo "   Frontend: $FRONTEND_PID"
echo ""
echo "📄 Logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo -e "${YELLOW}⚠️  Typesense features disabled (Docker not running)${NC}"
echo -e "${GREEN}✓  Ripgrep search will work normally${NC}"
echo ""
echo "To stop services, run: ./stop-dev.sh"
echo ""

# Save PIDs for stop script
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid
