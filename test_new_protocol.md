# Testing the New UART Protocol

## Summary of Changes

### 1. Work Position Button Behavior
- **Before**: Work position was received from UART
- **Now**: "Set Work Position" button saves the current position as the work position setpoint
- Saves to `tip_states.json` and sends `WPU` packet to controller

### 2. Controller Initialization
- Controller sends `WAKEUP:` request on connection
- App responds with comprehensive `SETTINGS:` packet containing:
  - Work position (setpoint, speed_mode)
  - All 8 tips settings (active, energy_setpoint, distance_setpoint, heat_start_delay)
  - Configuration settings (weld_time, pulse_energy, cool_time, etc.)

### 3. Settings Updates
- Any setting change automatically updates the controller:
  - Work position changes → `WPU:` packet
  - Tip settings changes → `TIPS:` packet
  - Configuration changes → `CFG:` packet

### 4. Baud Rate
- Changed from 9600 to 115200 for faster communication

## Testing Steps

1. **Start the Controller Simulator**:
   ```bash
   cd /home/osboxes/Desktop/USHS_Screens/python
   python3 controller_simulator.py
   ```
   - Select port and click Connect
   - Should see "WAKEUP request" sent
   - Should receive SETTINGS packet with all current settings

2. **Start the USHS App**:
   ```bash
   cd /home/osboxes/Desktop/USHS_Screens
   npm start
   ```
   - Go to Serial Config and connect to the matching port

3. **Test Work Position**:
   - Navigate to Settings → Work Position
   - Move position with up/down buttons
   - Click "Set Work Position"
   - Click "Confirm" in the dialog
   - Controller should receive `WPU` packet with new setpoint

4. **Test Settings Updates**:
   - Change any tip setting in Heating screen
   - Controller should receive `TIPS` packet
   - Change configuration values
   - Controller should receive `CFG` packet

## New Packet Formats

### From Controller:
- `WAKEUP:` - Request all settings on initialization

### From App:
- `SETTINGS:{json}` - Complete settings (response to WAKEUP)
- `WPU:{json}` - Work position update (setpoint, speed_mode)
- `TIPS:{json}` - Tip settings update
- `CFG:{json}` - Configuration update

### JSON Structure Examples:

**SETTINGS packet**:
```json
{
  "work_position": {
    "setpoint": 1.2,
    "speed_mode": "rapid"
  },
  "tips": [
    {
      "tip_number": 1,
      "active": true,
      "energy_setpoint": 3.7,
      "distance_setpoint": 2.0,
      "heat_start_delay": 3.0
    }
    // ... tips 2-8
  ],
  "configuration": {
    "weld_time": 3.21,
    "pulse_energy": 29.5,
    "cool_time": 0.12,
    "presence_height": 0.11,
    "boss_tolerance_minus": 0.009,
    "boss_tolerance_plus": 0.015
  }
}
```

**WPU packet**:
```json
{
  "setpoint": 1.2,
  "speed_mode": "rapid"
}
```
