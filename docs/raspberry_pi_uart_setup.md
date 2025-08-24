# Raspberry Pi UART Setup Guide

This guide explains how to connect your USHS Screens Electron app to the hardware UART on your Raspberry Pi 5.

## Hardware Setup

### Pin Connections
The Raspberry Pi UART uses the following GPIO pins:
- **GPIO 14 (Pin 8)** - TXD (Transmit)
- **GPIO 15 (Pin 10)** - RXD (Receive)
- **GND** - Use any ground pin (e.g., Pin 6, 9, 14, 20, 25, 30, 34, or 39)

### Wiring Diagram
```
Raspberry Pi                    Your Device
GPIO 14 (TXD) ----------------> RXD
GPIO 15 (RXD) <---------------- TXD
GND --------------------------- GND
```

**Important**: Remember that TX connects to RX and vice versa!

## Software Setup

### 1. Enable UART on Raspberry Pi

Run the provided setup script with sudo privileges:

```bash
sudo ./scripts/setup_rpi_uart.sh
```

This script will:
- Enable UART in `/boot/config.txt`
- Disable console output on the serial port
- Set appropriate permissions
- Optionally disable Bluetooth (recommended for better UART performance)
- Create persistent udev rules

**Note**: A reboot is required after running the setup script.

### 2. Verify UART is Working

After rebooting, test the UART connection:

```bash
# Check if UART devices are present
ls -la /dev/ttyAMA0 /dev/serial*

# Run the test script
python3 ./scripts/test_uart.py
```

The test script offers two modes:
- **Loopback test**: Connect GPIO 14 to GPIO 15 to test sending/receiving
- **Interactive test**: Communicate with your actual device

### 3. Using UART in the Electron App

1. Start your Electron app:
   ```bash
   npm start
   ```

2. In the Serial Port configuration panel (bottom right):
   - Click the refresh button to list available ports
   - Look for one of these Raspberry Pi UART ports:
     - `/dev/ttyAMA0` - RPi UART (GPIO 14/15)
     - `/dev/serial0` - RPi Primary UART
     - `/dev/serial1` - RPi Secondary UART

3. Select the appropriate port and click "Connect"

## Troubleshooting

### Permission Denied Errors
If you get permission errors:
```bash
# Add your user to the dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

### UART Not Showing Up
1. Check if UART is enabled:
   ```bash
   # Check boot config
   grep enable_uart /boot/config.txt
   # or
   grep enable_uart /boot/firmware/config.txt
   ```

2. Verify no console is using the port:
   ```bash
   # Check if serial console is disabled
   systemctl status serial-getty@ttyAMA0.service
   systemctl status serial-getty@serial0.service
   ```

### Bluetooth Interference
On Raspberry Pi 3/4/5, Bluetooth uses the PL011 UART by default. If you need reliable UART communication:

1. Disable Bluetooth (recommended):
   ```bash
   # Add to /boot/config.txt
   dtoverlay=disable-bt
   
   # Disable Bluetooth services
   sudo systemctl disable hciuart
   sudo systemctl disable bluetooth
   ```

2. Or use mini-UART (less reliable):
   ```bash
   # Add to /boot/config.txt
   dtoverlay=miniuart-bt
   ```

### Testing Communication
Use the interactive test mode to debug communication:
```bash
python3 ./scripts/test_uart.py
# Select option 2 for interactive mode
```

Common test commands for your controller:
- `CP:0` - Set cycle progress to Home
- `CP:3` - Set cycle progress to Heat
- `TD:{"tips":[{"tip_number":1,"joules":100}]}` - Send tip data

## Default Settings
- **Baud Rate**: 9600
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Flow Control**: None

These settings match your controller simulator and should work with most UART devices.

## Additional Resources
- [Raspberry Pi UART Documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts)
- [GPIO Pinout](https://pinout.xyz/)
