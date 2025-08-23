# USHS Controller Simulator

This Python GUI simulates an embedded controller that communicates with the USHS Electron app via serial port to control the cycle progress states.

## Features

- Simple GUI with up/down buttons to navigate through cycle states
- **NEW**: Individual control for 8 welding tips with joules, distance, and heat percentage
- Serial communication using JSON packet structure
- Support for virtual serial ports (for testing) and real serial ports (for Raspberry Pi)
- Real-time cycle progress and tip data updates in the Electron app
- Large window (900x800) to accommodate all controls

## Requirements

- Python 3.6+
- pyserial library
- tkinter (usually comes with Python)
- socat (for virtual serial ports on Linux)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. For testing with virtual serial ports on Linux, install socat:
```bash
sudo apt-get install socat
```

## Usage

### 1. Set up virtual serial ports (for testing)

Run the setup script to create virtual serial port pair:
```bash
cd /home/osboxes/Desktop/USHS_Screens
./scripts/setup_virtual_serial.sh
```

This creates two connected virtual ports:
- `/tmp/ttyV0` - Connect the Electron app here
- `/tmp/ttyV1` - Connect the Python simulator here

### 2. Start the Electron app

In the USHS_Screens directory:
```bash
npm install  # First time only
npm start
```

The app will start with a serial port configuration widget in the bottom-right corner.

### 3. Start the Python simulator

```bash
python3 python/controller_simulator.py
```

### 4. Connect the serial ports

1. In the Python simulator:
   - Select `/tmp/ttyV1` from the dropdown
   - Click "Connect"

2. In the Electron app (bottom-right widget):
   - Select `/tmp/ttyV0` from the dropdown
   - Click "Connect"

### 5. Control the cycle progress and tip data

In the Python simulator:

**Cycle Control:**
- **Previous**: Move to the previous state
- **Next**: Move to the next state
- **Reset to Inactive**: Reset all stages to inactive

**Tip Control (NEW):**
- Enter values for each of the 8 tips:
  - **Joules**: Energy value (shown as "J" in the app)
  - **Distance**: Distance in millimeters (shown as "mm" in the app)
  - **Heat %**: Heat percentage (0-100, controls the progress bar)
- Click **"Send Tip Data Packet"** to update all tips at once

The Electron app will update in real-time to show both cycle progress and tip data.

## Packet Structure

The simulator now uses a comprehensive JSON packet structure:

### TD (Tip Data) Packet - NEW
```
TD:{"cycle_progress": <state_index>, "tips": [...]}
```

Example:
```json
{
  "cycle_progress": 3,
  "tips": [
    {
      "tip_number": 1,
      "joules": 3.5,
      "distance": 2.0,
      "heat_percentage": 75.0
    },
    // ... 8 tips total
  ]
}
```

### Legacy CP (Cycle Progress) Packet
```
CP:<state_index>
```

Where `state_index` is:
- `-1`: All stages inactive
- `0`: Home stage active
- `1`: Work Position stage active (Home done)
- `2`: Encoder Zero stage active (Home, Work Position done)
- `3`: Heat stage active (previous stages done)
- `4`: Cool stage active (previous stages done)
- `5`: Cycle Complete stage active (previous stages done)
- `6`: All stages done

## Cycle Stages

1. Home
2. Work Position
3. Encoder Zero
4. Heat
5. Cool
6. Cycle Complete

Each stage can be in one of three states:
- **Inactive**: Gray text, no green ellipse, no "Successful" label
- **Active**: White text, green ellipse visible, "Processing..." shown
- **Done**: White text, green ellipse visible, "Successful" label shown

## Using with Real Serial Ports

For deployment on Raspberry Pi with real serial ports:

1. Connect your embedded controller to the Raspberry Pi serial port (e.g., `/dev/ttyUSB0`, `/dev/ttyAMA0`)
2. Select the appropriate port in both the simulator and Electron app
3. Ensure proper permissions for the serial port:
   ```bash
   sudo chmod 666 /dev/ttyUSB0  # or your specific port
   ```

## Troubleshooting

1. **Port not found**: Make sure the virtual serial ports are created or the physical port is connected
2. **Permission denied**: Run with sudo or add your user to the dialout group:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Then log out and back in.
3. **Connection failed**: Check that no other application is using the serial port

## Data Persistence

The Electron app saves all received tip data to `tip_states.json`, ensuring data persists across screen changes and app restarts. The file includes:
- Current joules, distance, and heat percentage for each tip
- Energy setpoints and other configuration values
- Monitor statistics and work position data

## Extending the System

The TD packet structure is designed to be scalable. You can add more data by:

1. Add new fields to the JSON packet structure
2. Update handling in `serial-handler.js` `handleData()` method
3. Add corresponding controls in the Python simulator
4. Update the Electron app UI handling as needed

The system maintains backwards compatibility with the legacy CP packet format.
