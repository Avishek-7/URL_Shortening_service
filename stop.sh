#!/bin/bash

# URL Shortening Service - Stop All Services

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PID_FILE=".service_pids"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No running services found (missing $PID_FILE)"
    exit 0
fi

echo "🛑 Stopping URL Shortening Service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

while read -r pid; do
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "   Stopping process $pid..."
        kill "$pid" 2>/dev/null || true
    fi
done < "$PID_FILE"

# Wait a moment for graceful shutdown
sleep 2

# Force kill any remaining processes
while read -r pid; do
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "   Force stopping process $pid..."
        kill -9 "$pid" 2>/dev/null || true
    fi
done < "$PID_FILE"

rm -f "$PID_FILE"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All services stopped"
