#!/bin/bash

echo "🚀 Starting Flipkart Automation System Setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    print_error "PostgreSQL is not running. Please start PostgreSQL first."
    print_status "To start PostgreSQL: sudo systemctl start postgresql"
    exit 1
fi

print_status "PostgreSQL is running!"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js first."
    exit 1
fi

print_status "Node.js found: $(node --version)"

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python3 is not installed. Please install Python3 first."
    exit 1
fi

print_status "Python3 found: $(python3 --version)"

# Set up backend
print_status "Setting up backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
print_status "Installing backend dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# Check if database is already initialized
if ! python database_schema.py --check 2>/dev/null; then
    print_status "Database schema is already initialized!"
else
    print_status "Database ready!"
fi

# Go back to root directory
cd ..

# Install frontend dependencies
print_status "Installing frontend dependencies..."
npm install

# Function to kill processes using specific ports
kill_port_processes() {
    local port=$1
    local service_name=$2
    
    # Find processes using the port
    local pids=$(lsof -ti :$port 2>/dev/null)
    
    if [ ! -z "$pids" ]; then
        print_warning "$service_name port $port is already in use. Stopping existing processes..."
        for pid in $pids; do
            kill -9 $pid 2>/dev/null
            print_status "Killed process $pid using port $port"
        done
        sleep 2
    fi
}

# Kill any existing processes using our ports
print_status "Checking for existing services..."
kill_port_processes 8000 "Backend"
kill_port_processes 3000 "Frontend"

# Also kill any python main.py processes
print_status "Stopping any existing backend processes..."
pkill -f "python main.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 2

# Start services
print_status "Starting backend server..."
cd backend
source venv/bin/activate

# Try to start backend with error handling
python main.py &
BACKEND_PID=$!

# Check if backend started successfully
sleep 3
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    print_error "Backend failed to start. Trying again..."
    # Kill any processes that might be holding the port
    kill_port_processes 8000 "Backend"
    sleep 2
    python main.py &
    BACKEND_PID=$!
    sleep 3
fi

cd ..

print_status "Starting frontend server..."
# Try to start frontend with error handling
npm run dev &
FRONTEND_PID=$!

# Check if frontend started successfully
sleep 3
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    print_error "Frontend failed to start. Trying again..."
    # Kill any processes that might be holding the port
    kill_port_processes 3000 "Frontend"
    sleep 2
    npm run dev &
    FRONTEND_PID=$!
fi

# Wait a moment for frontend to start
sleep 5

# Verify services are running
echo ""
print_status "Verifying services..."

# Check backend
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    print_success "✅ Backend is running and accessible"
else
    print_warning "⚠️ Backend may not be fully ready yet (this is normal)"
fi

# Check frontend
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    print_success "✅ Frontend is running and accessible"
else
    print_warning "⚠️ Frontend may still be compiling (this is normal)"
fi

echo ""
print_success "🎉 Flipkart Automation System is running!"
echo ""
echo -e "${BLUE}Frontend:${NC} http://localhost:3000"
echo -e "${BLUE}Backend API:${NC} http://localhost:8000"
echo -e "${BLUE}API Docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "${GREEN}Default Login:${NC}"
echo -e "  Username: admin"
echo -e "  Password: admin123"
echo ""
echo -e "${YELLOW}Database Details:${NC}"
echo -e "  Host: localhost:5432"
echo -e "  Database: flipkart_automation"
echo -e "  User: flipkart_admin"
echo ""
print_status "Press Ctrl+C to stop all services"

# Function to cleanup on exit
cleanup() {
    echo ""
    print_status "Stopping services..."
    
    # Kill our specific PIDs
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    # Also kill any remaining processes
    print_status "Cleaning up any remaining processes..."
    pkill -f "python main.py" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    
    # Kill processes using our ports as a final cleanup
    kill_port_processes 8000 "Backend" 2>/dev/null || true
    kill_port_processes 3000 "Frontend" 2>/dev/null || true
    
    print_success "All services stopped."
    exit 0
}

# Set trap to cleanup on exit
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait 