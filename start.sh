#!/bin/bash

# URL Shortening Service - Start All Services
# This script starts FastAPI, Celery worker/beat, and Streamlit frontend

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -d ".venv/bin" ]; then
    source .venv/bin/activate
fi

# PID file to track running processes
PID_FILE=".service_pids"
rm -f "$PID_FILE"

echo "🚀 Starting URL Shortening Service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Start FastAPI backend
echo "📡 Starting FastAPI backend on port 8001..."
uvicorn main:app --port 8001 --reload > logs/fastapi.log 2>&1 &
FASTAPI_PID=$!
echo $FASTAPI_PID >> "$PID_FILE"
echo "   ✓ FastAPI started (PID: $FASTAPI_PID)"

# Start Celery worker with beat
echo "⚙️  Starting Celery worker with beat..."
celery -A services.tasks.celery_app worker --beat --loglevel=info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID >> "$PID_FILE"
echo "   ✓ Celery started (PID: $CELERY_PID)"

# Start Streamlit frontend
echo "🎨 Starting Streamlit frontend on port 8501..."
streamlit run streamlit_app.py --server.port 8501 > logs/streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo $STREAMLIT_PID >> "$PID_FILE"
echo "   ✓ Streamlit started (PID: $STREAMLIT_PID)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All services started successfully!"
echo ""
echo "📊 Service URLs:"
echo "   • FastAPI:   http://localhost:8001"
echo "   • Streamlit: http://localhost:8501"
echo ""
echo "📝 Logs:"
echo "   • FastAPI:   logs/fastapi.log"
echo "   • Celery:    logs/celery.log"
echo "   • Streamlit: logs/streamlit.log"
echo ""
echo "🛑 To stop all services, run: ./stop.sh"
echo "   Or manually: kill \$(cat .service_pids)"
