#!/bin/bash

echo "Starting services for local development..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating Python virtual environment..."
    source venv/bin/activate
fi

# Launch the Application service (FastAPI) in the background
echo "Starting Application API service on port 8000..."
python -m src.application.main &
APP_PID=$!

# Launch the Execution service (LiveKit Agent) in the background
echo "Starting Execution worker..."
python -m src.execution.worker start &
WORKER_PID=$!

echo "Application service running with PID: $APP_PID"
echo "Execution worker running with PID: $WORKER_PID"
echo "Press Ctrl+C to stop both services."

# Wait for either process to exit, or for a Ctrl+C
wait -n $APP_PID $WORKER_PID

# Cleanup function on exit
cleanup() {
    echo "Stopping services..."
    kill $APP_PID
    kill $WORKER_PID
    echo "Services stopped."
}

# Trap the exit signal to run the cleanup function
trap cleanup EXIT

# Keep the script alive to hold the background jobs
while true
do
  sleep 1
done
