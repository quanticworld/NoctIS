#!/bin/bash
# Stop all NoctIS servers

echo "╔═══════════════════════════════════════╗"
echo "║  NoctIS - Stopping servers...        ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# Find and kill backend (uvicorn)
BACKEND_PIDS=$(pgrep -f "uvicorn app.main:app")
if [ -n "$BACKEND_PIDS" ]; then
    echo "🔴 Stopping backend (PIDs: $BACKEND_PIDS)"
    kill $BACKEND_PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    pkill -9 -f "uvicorn app.main:app" 2>/dev/null
    echo "✓ Backend stopped"
else
    echo "ℹ  Backend not running"
fi

# Find and kill frontend (vite)
FRONTEND_PIDS=$(pgrep -f "vite")
if [ -n "$FRONTEND_PIDS" ]; then
    echo "🔴 Stopping frontend (PIDs: $FRONTEND_PIDS)"
    kill $FRONTEND_PIDS 2>/dev/null
    sleep 1
    # Force kill if still running
    pkill -9 -f "vite" 2>/dev/null
    echo "✓ Frontend stopped"
else
    echo "ℹ  Frontend not running"
fi

echo ""
echo "✅ All servers stopped"
