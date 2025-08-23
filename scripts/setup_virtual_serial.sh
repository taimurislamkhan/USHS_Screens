#!/bin/bash

# Setup virtual serial ports for testing
# This creates a pair of virtual serial ports connected to each other

echo "Setting up virtual serial ports..."

# Check if socat is installed
if ! command -v socat &> /dev/null; then
    echo "socat is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y socat
fi

# Kill any existing socat processes
pkill socat 2>/dev/null

# Create virtual serial port pair
# /tmp/ttyV0 - For the Electron app
# /tmp/ttyV1 - For the Python simulator
echo "Creating virtual serial port pair..."
socat -d -d pty,raw,echo=0,link=/tmp/ttyV0 pty,raw,echo=0,link=/tmp/ttyV1 &

# Save the PID
echo $! > /tmp/virtual_serial.pid

# Give it a moment to create the ports
sleep 1

# Set permissions
sudo chmod 666 /tmp/ttyV0 2>/dev/null || true
sudo chmod 666 /tmp/ttyV1 2>/dev/null || true

echo "Virtual serial ports created:"
echo "  /tmp/ttyV0 - Connect Electron app here"
echo "  /tmp/ttyV1 - Connect Python simulator here"
echo ""
echo "To stop the virtual ports, run: pkill socat"
