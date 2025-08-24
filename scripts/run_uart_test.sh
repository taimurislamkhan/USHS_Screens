#!/bin/bash

# UART Test Runner for Raspberry Pi 5
# This script runs the UART test that sends "hello world" via GPIO 14/15

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_DIR="$PROJECT_DIR/python"
UART_TEST_SCRIPT="$PYTHON_DIR/uart_test.py"

echo -e "${BLUE}=== Raspberry Pi 5 UART Test Runner ===${NC}"
echo -e "Project Directory: $PROJECT_DIR"
echo -e "UART Test Script: $UART_TEST_SCRIPT"
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi${NC}"
    echo -e "The script will still run but may not work properly on other systems."
    echo ""
fi

# Check if the Python script exists
if [ ! -f "$UART_TEST_SCRIPT" ]; then
    echo -e "${RED}Error: UART test script not found at $UART_TEST_SCRIPT${NC}"
    exit 1
fi

# Make the Python script executable
chmod +x "$UART_TEST_SCRIPT"

# Check if UART device exists
UART_DEVICE="/dev/serial0"
if [ ! -e "$UART_DEVICE" ]; then
    echo -e "${YELLOW}Warning: $UART_DEVICE not found${NC}"
    echo -e "Alternative devices to try:"
    echo -e "  - /dev/ttyS0 (Mini UART)"
    echo -e "  - /dev/ttyAMA0 (PL011 UART)"
    echo ""
    echo -e "Make sure UART is enabled in raspi-config:"
    echo -e "  sudo raspi-config → Interface Options → Serial Port"
    echo -e "  - Enable serial port hardware: YES"
    echo -e "  - Enable serial console: NO (for GPIO usage)"
    echo ""
fi

# Check user permissions for dialout group
if ! groups | grep -q dialout; then
    echo -e "${YELLOW}Warning: Current user is not in 'dialout' group${NC}"
    echo -e "You may need to run with sudo or add user to dialout group:"
    echo -e "  sudo usermod -a -G dialout \$USER"
    echo -e "  (then log out and log back in)"
    echo ""
fi

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    echo -e "Install it with: sudo apt install python3"
    exit 1
fi

# Check if pyserial is installed
if ! python3 -c "import serial" &> /dev/null; then
    echo -e "${YELLOW}Warning: pyserial not found${NC}"
    echo -e "Installing pyserial..."
    
    # Try to install pyserial
    if command -v pip3 &> /dev/null; then
        pip3 install pyserial
    elif [ -f "$PYTHON_DIR/requirements.txt" ]; then
        echo -e "Installing from requirements.txt..."
        pip3 install -r "$PYTHON_DIR/requirements.txt"
    else
        echo -e "${RED}Error: Cannot install pyserial${NC}"
        echo -e "Install manually: pip3 install pyserial"
        exit 1
    fi
fi

echo -e "${GREEN}=== Starting UART Test ===${NC}"
echo -e "GPIO 14 (TX) and GPIO 15 (RX) will be used"
echo -e "Press Ctrl+C to stop the test"
echo ""

# Run the Python UART test script
cd "$PROJECT_DIR"
python3 "$UART_TEST_SCRIPT"

echo -e "${GREEN}UART test completed.${NC}"
