#!/usr/bin/env zsh
set -e

PROJECT_DIR="$HOME/Desktop/code/recruiter-agency"
cd "$PROJECT_DIR"

echo "========================================"
echo " Recruiter Agency — Starting Up"
echo "========================================"
echo ""

echo "[1/3] Installing Python dependencies..."
uv sync --quiet
echo "  Done."

echo "[2/3] Installing frontend dependencies..."
cd frontend && npm install --silent && cd "$PROJECT_DIR"
echo "  Done."

echo "[3/3] Launching servers..."
echo "  Backend  → http://localhost:8000"
uv run uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

sleep 1

echo "  Frontend → http://localhost:3000"
cd frontend && npx next dev -p 3000 &
FRONTEND_PID=$!
cd "$PROJECT_DIR"

echo ""
echo "========================================"
echo " Both servers are running."
echo " Press Ctrl+C to stop both."
echo "========================================"

trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
