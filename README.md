# USHS Screens - Electron Application

A modular Electron application with Modbus communication support.

## Project Structure

```
USHS_Screens/
├── assets/           # Images and SVG icons
├── python/           # Python backend scripts
│   ├── modbus_map.py
│   ├── modbus_slave_gui.py
│   └── modbus_simple_ui_controller.py
├── scripts/          # Shell scripts
│   ├── start_modbus_app.sh
│   └── setup_virtual_serial.sh
├── admin/            # Admin interface screens
├── settings/         # Settings interface screens
├── main.js           # Electron main process
├── preload.js        # Electron preload script
├── index.html        # Main HTML entry point
├── HomeScreen.html   # Home screen component
└── start_app.sh      # Convenience launcher
```

## Quick Start

To run the application:

```bash
./start_app.sh
```

This will:
1. Set up virtual serial ports for Modbus communication
2. Start the Electron frontend
3. Launch the Modbus slave GUI
4. Start the Modbus UI controller

## Dependencies

- Node.js and npm (for Electron)
- Python 3 with virtual environment
- Required Python packages (see requirements.txt)

## Configuration

- Modbus settings can be adjusted via command line arguments
- UI configuration is stored in `config.json`
- Tip states are tracked in `tip_states.json`