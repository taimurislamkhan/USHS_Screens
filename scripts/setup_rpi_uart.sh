#!/bin/bash

# Setup script for Raspberry Pi UART configuration
# This script enables UART on GPIO 14 (TXD) and GPIO 15 (RXD)

echo "Raspberry Pi UART Setup Script"
echo "=============================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This doesn't appear to be a Raspberry Pi system."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "This script will:"
echo "1. Enable UART on GPIO 14/15"
echo "2. Disable console on serial port"
echo "3. Set appropriate permissions"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Backup config files
echo "Backing up configuration files..."
cp /boot/config.txt /boot/config.txt.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || \
cp /boot/firmware/config.txt /boot/firmware/config.txt.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null

# Determine config file location (RPi OS changed location in newer versions)
if [ -f "/boot/firmware/config.txt" ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
else
    CONFIG_FILE="/boot/config.txt"
fi

echo "Using config file: $CONFIG_FILE"

# Enable UART in config.txt
echo ""
echo "Enabling UART..."
if ! grep -q "^enable_uart=1" "$CONFIG_FILE"; then
    echo "enable_uart=1" >> "$CONFIG_FILE"
    echo "Added enable_uart=1 to $CONFIG_FILE"
else
    echo "UART already enabled in $CONFIG_FILE"
fi

# For Pi 5, we might need additional configuration
if grep -q "Raspberry Pi 5" /proc/cpuinfo 2>/dev/null; then
    echo ""
    echo "Detected Raspberry Pi 5 - applying specific configuration..."
    
    # Ensure we're using the right UART
    if ! grep -q "^dtoverlay=disable-bt" "$CONFIG_FILE"; then
        echo ""
        echo "Note: By default, Bluetooth uses the PL011 UART."
        echo "To use UART on GPIO 14/15, you can either:"
        echo "1. Disable Bluetooth (recommended for serial communication)"
        echo "2. Use the mini UART (less reliable at high speeds)"
        echo ""
        read -p "Disable Bluetooth to use PL011 UART? (Y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "dtoverlay=disable-bt" >> "$CONFIG_FILE"
            echo "Added Bluetooth disable overlay"
            
            # Disable Bluetooth services
            systemctl disable hciuart 2>/dev/null
            systemctl disable bluetooth 2>/dev/null
        fi
    fi
fi

# Disable console on serial port
echo ""
echo "Disabling console on serial port..."
if systemctl is-enabled serial-getty@ttyAMA0.service 2>/dev/null; then
    systemctl disable serial-getty@ttyAMA0.service
    systemctl stop serial-getty@ttyAMA0.service
    echo "Disabled serial console on ttyAMA0"
fi

if systemctl is-enabled serial-getty@serial0.service 2>/dev/null; then
    systemctl disable serial-getty@serial0.service
    systemctl stop serial-getty@serial0.service
    echo "Disabled serial console on serial0"
fi

# Remove console from cmdline.txt
echo ""
echo "Updating boot command line..."
CMDLINE_FILE="/boot/cmdline.txt"
if [ -f "/boot/firmware/cmdline.txt" ]; then
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
fi

if [ -f "$CMDLINE_FILE" ]; then
    cp "$CMDLINE_FILE" "$CMDLINE_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    sed -i 's/console=serial0,[0-9]\+ //g' "$CMDLINE_FILE"
    sed -i 's/console=ttyAMA0,[0-9]\+ //g' "$CMDLINE_FILE"
    echo "Removed serial console from $CMDLINE_FILE"
fi

# Add user to dialout group for serial port access
echo ""
echo "Setting up user permissions..."
CURRENT_USER=${SUDO_USER:-$USER}
if [ "$CURRENT_USER" != "root" ]; then
    usermod -a -G dialout "$CURRENT_USER" 2>/dev/null
    echo "Added $CURRENT_USER to dialout group"
fi

# Set permissions on serial devices
echo ""
echo "Setting device permissions..."
chmod 666 /dev/ttyAMA0 2>/dev/null
chmod 666 /dev/serial0 2>/dev/null
chmod 666 /dev/serial1 2>/dev/null

# Create udev rule for persistent permissions
echo ""
echo "Creating udev rule for persistent permissions..."
cat > /etc/udev/rules.d/99-serial.rules << EOF
KERNEL=="ttyAMA[0-9]*", GROUP="dialout", MODE="0666"
KERNEL=="serial[0-9]*", GROUP="dialout", MODE="0666"
EOF
echo "Created /etc/udev/rules.d/99-serial.rules"

# Test serial ports
echo ""
echo "Testing serial port availability..."
echo "Available serial ports:"
ls -la /dev/ttyAMA* 2>/dev/null || echo "  No /dev/ttyAMA* devices found"
ls -la /dev/serial* 2>/dev/null || echo "  No /dev/serial* devices found"

echo ""
echo "UART Pin Configuration:"
echo "======================"
echo "GPIO 14 (Pin 8)  -> TXD (Transmit)"
echo "GPIO 15 (Pin 10) -> RXD (Receive)"
echo "GND (Pin 6/9/14/20/25/30/34/39) -> Ground"
echo ""
echo "Default UART settings: 9600 baud, 8N1"
echo ""
echo "Setup complete!"
echo ""
echo "IMPORTANT: A reboot is required for all changes to take effect."
read -p "Reboot now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    reboot
else
    echo "Please reboot manually when ready: sudo reboot"
fi
