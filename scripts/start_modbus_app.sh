#!/bin/bash

# Start script for USHS with Modbus support
# This starts:
# 1. Virtual serial ports
# 2. Electron app
# 3. Modbus slave GUI
# 4. Modbus UI controller

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to cleanup on exit
cleanup() {
    print_info "Cleaning up..."
    
    # Kill all child processes
    if [ ! -z "$ELECTRON_PID" ]; then
        kill $ELECTRON_PID 2>/dev/null
    fi
    
    if [ ! -z "$SLAVE_PID" ]; then
        kill $SLAVE_PID 2>/dev/null
    fi
    
    if [ ! -z "$CONTROLLER_PID" ]; then
        kill $CONTROLLER_PID 2>/dev/null
    fi
    
    # Kill virtual serial ports
    if [ -f /tmp/vserial_socat.pid ]; then
        kill $(cat /tmp/vserial_socat.pid) 2>/dev/null
        rm /tmp/vserial_socat.pid
    fi
    
    pkill -f "pty,raw,echo=0,link=/tmp/vserial"
    
    print_success "Cleanup complete"
    exit 0
}

# Set up trap for cleanup
trap cleanup EXIT INT TERM

# Parse command line arguments
BAUDRATE=1000000
SLAVE_ID=1
UPDATE_RATE=30

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--baudrate)
            BAUDRATE="$2"
            shift 2
            ;;
        -s|--slave-id)
            SLAVE_ID="$2"
            shift 2
            ;;
        -r|--rate)
            UPDATE_RATE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -b, --baudrate <rate>    Set baudrate (default: 1000000)"
            echo "  -s, --slave-id <id>      Set Modbus slave ID (default: 1)"
            echo "  -r, --rate <hz>          Set update rate in Hz (default: 30)"
            echo "  -h, --help               Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

print_info "Starting USHS with Modbus support..."
print_info "Configuration:"
print_info "  Baudrate: $BAUDRATE bps"
print_info "  Slave ID: $SLAVE_ID"
print_info "  Update Rate: $UPDATE_RATE Hz"
echo ""

# Step 1: Set up virtual serial ports
print_info "Setting up virtual serial ports..."
chmod +x scripts/setup_virtual_serial.sh
./scripts/setup_virtual_serial.sh

if [ $? -ne 0 ]; then
    print_error "Failed to set up virtual serial ports"
    exit 1
fi

# Give ports time to stabilize
sleep 2

# Step 2: Start Electron app
print_info "Starting Electron app..."
npm start &
ELECTRON_PID=$!

# Wait for Electron to start
sleep 3

# Check if Electron started successfully
if ! ps -p $ELECTRON_PID > /dev/null; then
    print_error "Failed to start Electron app"
    exit 1
fi

print_success "Electron app started (PID: $ELECTRON_PID)"

# Step 3: Start Modbus slave GUI
print_info "Starting Modbus slave GUI..."
./venv/bin/python3 python/modbus_slave_gui.py &
SLAVE_PID=$!

# Wait for slave to start
sleep 2

# Check if slave started successfully
if ! ps -p $SLAVE_PID > /dev/null; then
    print_error "Failed to start Modbus slave GUI"
    exit 1
fi

print_success "Modbus slave GUI started (PID: $SLAVE_PID)"

# Step 4: Wait a bit for user to configure and start the slave
print_warning "Please configure and start the Modbus slave in the GUI"
print_warning "Default settings should work. Just click 'Start Server'"
print_info "Waiting 10 seconds for slave configuration..."
sleep 10

# Step 5: Start Modbus UI controller
print_info "Starting Modbus UI controller..."
./venv/bin/python3 python/modbus_simple_ui_controller.py \
    --port /tmp/vserial2 \
    --baudrate $BAUDRATE \
    --slave-id $SLAVE_ID \
    --websocket ws://localhost:8080 &
CONTROLLER_PID=$!

# Check if controller started successfully
sleep 2
if ! ps -p $CONTROLLER_PID > /dev/null; then
    print_error "Failed to start Modbus UI controller"
    exit 1
fi

print_success "Modbus UI controller started (PID: $CONTROLLER_PID)"

# Print status
echo ""
print_success "All components started successfully!"
print_info "System is running with:"
print_info "  - Virtual serial ports: /tmp/vserial1 (slave) <-> /tmp/vserial2 (master)"
print_info "  - Electron app (PID: $ELECTRON_PID)"
print_info "  - Modbus slave GUI (PID: $SLAVE_PID)"
print_info "  - Modbus UI controller (PID: $CONTROLLER_PID)"
echo ""
print_info "You can now:"
print_info "  1. Use the Modbus slave GUI to change values"
print_info "  2. See the updates reflected in the Electron app"
print_info "  3. Adjust communication settings in the slave GUI"
echo ""
print_warning "Press Ctrl+C to stop all components"

# Wait for user to stop
while true; do
    sleep 1
done