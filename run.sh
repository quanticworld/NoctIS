#!/bin/bash

# NoctIS - Quick Start Script

echo "╔═══════════════════════════════════════╗"
echo "║  NoctIS - OSINT Red Team Toolbox    ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# Check if ripgrep is installed
if ! command -v rg &> /dev/null; then
    echo "❌ ERROR: ripgrep (rg) is not installed"
    echo "Install with: sudo apt install ripgrep"
    exit 1
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 is not installed"
    exit 1
fi

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo "❌ ERROR: Node.js is not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Setup backend
echo "📦 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo "✅ Backend setup complete"
echo ""

# Setup frontend
echo "📦 Setting up frontend..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo "✅ Frontend setup complete"
echo ""

# Run tests
echo "🧪 Running tests..."
cd ../backend
python -m pytest --tb=short

cd ../frontend
npm run test --run

echo ""
echo "✅ All tests passed"
echo ""

# Start servers
echo "🚀 Starting servers..."
echo ""
echo "Backend will run on:  http://localhost:8000"
echo "Frontend will run on: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Start backend in background
cd ../backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend in background
cd ../frontend
npm run dev &
FRONTEND_PID=$!

# Wait for Ctrl+C
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

wait
