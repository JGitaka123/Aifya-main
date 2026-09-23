#!/bin/bash
# run_system.sh - Start Aifya Health Platform (Mock Environment)

# 1. Start Database and MinIO in Docker
echo "Starting Database and Storage..."
docker compose up -d aifya-db minio

# 2. Start Backend on Host
echo "Starting Backend API (Port 8000)..."
cd backend
source venv/bin/activate
# Ensure dependencies are installed
pip install -r requirements.txt
# Start uvicorn in background
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 3. Start Frontend on Host
echo "Starting Frontend UI (Port 3000)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "------------------------------------------------"
echo "System is starting up!"
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "Health:   http://localhost:8000/health"
echo "------------------------------------------------"
echo "Login with: doctor@aifya.com / Password123!"
echo "------------------------------------------------"

# Keep script running to monitor, or just exit and let them run in background
wait $BACKEND_PID $FRONTEND_PID
