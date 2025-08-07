#!/bin/bash

# Setup virtual serial ports for Modbus testing
# This creates a pair of connected virtual serial ports

echo "Setting up virtual serial ports for Modbus communication..."

# Check if socat is installed
if ! command -v socat &> /dev/null; then
    echo "Error: socat is not installed. Please install it with:"
    echo "  sudo apt-get install socat"
    exit 1
fi

# Kill any existing socat processes using these ports
pkill -f "pty,raw,echo=0,link=/tmp/vserial1"
pkill -f "pty,raw,echo=0,link=/tmp/vserial2"

# Wait a moment for processes to terminate
sleep 1

# Create virtual serial port pair
echo "Creating virtual serial port pair..."
socat -d -d pty,raw,echo=0,link=/tmp/vserial1 pty,raw,echo=0,link=/tmp/vserial2 &

# Save the PID
SOCAT_PID=$!
echo $SOCAT_PID > /tmp/vserial_socat.pid

# Wait for ports to be created
sleep 2

# Set permissions
chmod 666 /tmp/vserial1 2>/dev/null
chmod 666 /tmp/vserial2 2>/dev/null

# Check if ports were created
if [ -e /tmp/vserial1 ] && [ -e /tmp/vserial2 ]; then
    echo "Virtual serial ports created successfully:"
    echo "  Slave port:  /tmp/vserial1"
    echo "  Master port: /tmp/vserial2"
    echo ""
    echo "To stop the virtual ports, run:"
    echo "  kill $SOCAT_PID"
    echo "  or: pkill -f 'pty,raw,echo=0,link=/tmp/vserial'"
else
    echo "Error: Failed to create virtual serial ports"
    exit 1
fi