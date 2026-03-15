#!/bin/bash
# Quick start script - starts both backend and frontend

echo "╔═══════════════════════════════════════╗"
echo "║  NoctIS - Starting servers...        ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# Start backend
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID) - http://localhost:8000"

# Start frontend
cd ../frontend
npm run dev &
FRONTEND_PID=$!
echo "✓ Frontend started (PID: $FRONTEND_PID) - http://localhost:5173"

echo ""
echo "Press Ctrl+C to stop both servers"

# Cleanup on exit
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

wait
