#!/bin/bash

echo "USHS Screens - Serial Communication Demo"
echo "========================================"
echo ""
echo "This demo will:"
echo "1. Set up virtual serial ports"
echo "2. Start the Python controller simulator"
echo "3. Provide instructions for connecting"
echo ""
echo "Press Enter to continue..."
read

# Set up virtual serial ports
echo "Setting up virtual serial ports..."
./scripts/setup_virtual_serial.sh

echo ""
echo "Virtual serial ports created successfully!"
echo ""
echo "Next steps:"
echo "1. In another terminal, start the Electron app: npm start"
echo "2. In the Electron app (bottom-right), connect to /tmp/ttyV0"
echo "3. In the Python simulator below, connect to /tmp/ttyV1"
echo "4. Use the up/down buttons to control cycle progress"
echo "5. Enter values for tip joules, distance, and heat percentage"
echo "6. Click 'Send Tip Data Packet' to update all tips in the Electron app"
echo ""
echo "Starting Python simulator in 3 seconds..."
sleep 3

# Start the Python simulator
python3 python/controller_simulator.py
