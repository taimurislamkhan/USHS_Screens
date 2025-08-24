# UART Communication Protocol for STM32F4 Controller
## USHS Screens Embedded Controller Implementation Guide

This document describes the UART communication protocol used between the USHS Electron application and the embedded controller. This protocol should be implemented on an STM32F4 controller running FreeRTOS.

## Overview

The communication protocol uses a text-based format with JSON payloads for complex data structures. All packets are terminated with a newline character (`\n`).

### Separation of Responsibilities

**STM32F4 Controller:**
- Receives and parses UART commands from the Electron app
- Controls hardware (motors, heating elements, sensors)
- Maintains current system state in RAM only
- Sends status updates via UART packets
- Does NOT store any data persistently

**Electron App:**
- Sends control commands to the controller
- Receives status updates from the controller
- Manages all persistent storage (JSON files)
- Handles all UI updates and user interactions
- Maintains configuration and state history

### UART Configuration
- **Baud Rate**: 115200
- **Data Bits**: 8
- **Stop Bits**: 1
- **Parity**: None
- **Flow Control**: None
- **Line Terminator**: `\n` (0x0A)

## Packet Format

All packets follow this general structure:
```
COMMAND:PAYLOAD\n
```

Where:
- `COMMAND` is a 2-3 character command identifier
- `:` is the delimiter between command and payload
- `PAYLOAD` is either a simple value or JSON data
- `\n` is the line terminator

## Commands from Electron App to Controller (Incoming)

### 1. WPB - Work Position Button Command
Sent when user presses/releases movement buttons on the work position screen.

**Format:**
```
WPB:{"type":"WPB","button":"up"|"down","pressed":true|false,"speed_mode":"rapid"|"fine","timestamp":1234567890}\n
```

**Fields:**
- `type`: Always "WPB"
- `button`: Either "up" or "down"
- `pressed`: true when button pressed, false when released
- `speed_mode`: Current speed mode ("rapid" or "fine")
- `timestamp`: Unix timestamp in milliseconds

**Example:**
```
WPB:{"type":"WPB","button":"up","pressed":true,"speed_mode":"rapid","timestamp":1703123456789}\n
```

**Controller Action:**
- Start/stop motor movement based on button state
- Apply speed mode for movement rate
- Implement safety timeout (auto-stop after 5 seconds if no release received)

### 2. WPS - Work Position Speed Command
Sent when user changes speed mode.

**Format:**
```
WPS:{"type":"WPS","speed_mode":"rapid"|"fine","timestamp":1234567890}\n
```

**Fields:**
- `type`: Always "WPS"
- `speed_mode`: Either "rapid" or "fine"
- `timestamp`: Unix timestamp in milliseconds

**Example:**
```
WPS:{"type":"WPS","speed_mode":"fine","timestamp":1703123456789}\n
```

**Controller Action:**
- Update motor speed settings
- Rapid mode: Fast movement speed
- Fine mode: Slow/precise movement speed

### 3. WPT - Work Position seT Command (DEPRECATED)
This command is no longer used. Work position setpoint is now saved by the Electron app when the user confirms setting the work position. The app saves the current position as the setpoint and sends a WPU command to update the controller.

### 4. WPU - Work Position Update Command
Sent when the work position setpoint is changed by the user.

**Format:**
```
WPU:{"setpoint":15.0,"speed_mode":"rapid"}\n
```

**Fields:**
- `setpoint`: New work position setpoint in mm (float)
- `speed_mode`: Current speed mode ("rapid" or "fine")

**Example:**
```
WPU:{"setpoint":12.5,"speed_mode":"fine"}\n
```

**Controller Action:**
- Update the work position setpoint in controller memory (RAM only)
- Use this setpoint for work position operations

### 5. SETTINGS - Complete Settings Command
Sent in response to WAKEUP request from controller. Contains all settings needed to initialize the controller.

**Format:**
```
SETTINGS:{"work_position":{...},"tips":[...],"configuration":{...}}\n
```

**Fields:**
- `work_position`: Work position settings object
  - `setpoint`: Work position setpoint in mm (float)
  - `speed_mode`: Speed mode ("rapid" or "fine")
- `tips`: Array of 8 tip settings objects
- `configuration`: Configuration settings object

**Tip Settings Object:**
```json
{
  "tip_number": 1,
  "active": true,
  "energy_setpoint": 3.7,
  "distance_setpoint": 2.0,
  "heat_start_delay": 3.0
}
```

**Configuration Object:**
```json
{
  "weld_time": 3.21,
  "pulse_energy": 29.5,
  "cool_time": 0.12,
  "presence_height": 0.11,
  "boss_tolerance_minus": 0.009,
  "boss_tolerance_plus": 0.015
}
```

**Example:**
```
SETTINGS:{"work_position":{"setpoint":15.0,"speed_mode":"rapid"},"tips":[{"tip_number":1,"active":true,"energy_setpoint":3.7,"distance_setpoint":2.0,"heat_start_delay":3.0},...7 more tips...],"configuration":{"weld_time":3.21,"pulse_energy":29.5,"cool_time":0.12,"presence_height":0.11,"boss_tolerance_minus":0.009,"boss_tolerance_plus":0.015}}\n
```

**Controller Action:**
- Store all settings in controller memory (RAM only)
- Use these settings for operation until next power cycle

### 6. TIPS - Tip Settings Update Command
Sent when any tip setting is changed.

**Format:**
```
TIPS:{"tips":[...]}\n
```

**Fields:**
- `tips`: Array of tip settings objects (same structure as in SETTINGS command)

**Controller Action:**
- Update tip settings in controller memory

### 7. CFG - Configuration Update Command
Sent when any configuration setting is changed.

**Format:**
```
CFG:{"configuration":{...}}\n
```

**Fields:**
- `configuration`: Configuration object (same structure as in SETTINGS command)

**Controller Action:**
- Update configuration settings in controller memory

## Commands from Controller to Electron App (Outgoing)

### 1. TD - Tip Data Command (Primary)
This is the main data packet sent by the controller to update the UI. It contains cycle progress, tip data, and home screen information.

**Format:**
```
TD:{"cycle_progress":-1|0|1|2|3|4|5|6,"tips":[...],"home_screen":{...}}\n
```

**Fields:**
- `cycle_progress`: Current cycle state
  - `-1`: All stages inactive
  - `0`: Home stage active
  - `1`: Work Position stage active
  - `2`: Encoder Zero stage active
  - `3`: Heat stage active
  - `4`: Cool stage active
  - `5`: Cycle Complete stage active
  - `6`: All stages complete
- `tips`: Array of 8 tip objects
- `home_screen`: Home screen display data

**Tip Object Structure:**
```json
{
  "tip_number": 1,              // Tip number (1-8)
  "joules": 3.5,                // Energy in joules (float)
  "distance": 2.0,              // Distance in mm (float)
  "heat_percentage": 75.0       // Heat percentage 0-100 (float)
}
```

**Home Screen Object Structure:**
```json
{
  "banner_text": "System Is Ready",      // Banner display text
  "processing_text": "Processing...",    // Processing status text
  "spinner_active": true,                // Show/hide spinner
  "percentage": 45,                      // Progress percentage (0-100)
  "time_text": "∼1m 46sec",             // Time display text
  "slider_position": 45                  // Slider position (0-100)
}
```

**Complete Example:**
```
TD:{"cycle_progress":3,"tips":[{"tip_number":1,"joules":3.5,"distance":2.0,"heat_percentage":75.0},{"tip_number":2,"joules":0.0,"distance":0.0,"heat_percentage":0.0},{"tip_number":3,"joules":2.1,"distance":1.5,"heat_percentage":50.0},{"tip_number":4,"joules":0.0,"distance":0.0,"heat_percentage":0.0},{"tip_number":5,"joules":0.0,"distance":0.0,"heat_percentage":0.0},{"tip_number":6,"joules":0.0,"distance":0.0,"heat_percentage":0.0},{"tip_number":7,"joules":0.0,"distance":0.0,"heat_percentage":0.0},{"tip_number":8,"joules":1.2,"distance":0.8,"heat_percentage":25.0}],"home_screen":{"banner_text":"Heating in Progress","processing_text":"Heating tips...","spinner_active":true,"percentage":45,"time_text":"∼1m 15sec","slider_position":45}}\n
```

**Controller Implementation Notes:**
- Send TD packets periodically (recommended: every 100-250ms during active operations)
- Always include all 8 tips even if inactive (set values to 0)
- Heat percentage controls the progress bar display for each tip
- Active tips (heat_percentage > 0) will be displayed with highlighting

### 2. WP - Work Position Data Command
Sent to update work position screen information.

**Format:**
```
WP:{"current_position":12.5,"setpoint":15.0,"speed_mode":"rapid","tip_distances":{...}}\n
```

**Fields:**
- `current_position`: Current position in mm (float)
- `setpoint`: Target position in mm (float)
- `speed_mode`: Current speed mode ("rapid" or "fine")
- `tip_distances`: Object with tip numbers (1-8) as keys and distances (0-8mm) as values

**Example:**
```
WP:{"current_position":12.5,"setpoint":15.0,"speed_mode":"rapid","tip_distances":{"1":2.5,"2":0.0,"3":1.8,"4":0.0,"5":0.0,"6":0.0,"7":0.0,"8":3.2}}\n
```

**Controller Implementation Notes:**
- Send when work position data changes
- Send after receiving WPU command to confirm new setpoint
- Tip distances should be 0-8mm range
- Include all 8 tip distances even if 0

### 3. WAKEUP - Controller Wakeup Request
Sent by the controller on initialization to request all settings from the Electron app.

**Format:**
```
WAKEUP:\n
```

**Example:**
```
WAKEUP:\n
```

**App Response:**
The Electron app will respond with a SETTINGS packet containing all current settings.

**Controller Implementation Notes:**
- Send this immediately after establishing UART connection
- Wait for SETTINGS response before starting normal operations
- Can be sent after power-on or reset

### 4. CP - Cycle Progress Command (Legacy)
Simple cycle progress update. Still supported but TD command is preferred.

**Format:**
```
CP:STATE_INDEX\n
```

Where STATE_INDEX is -1 to 6 (same as cycle_progress in TD command).

**Example:**
```
CP:3\n
```

## Implementation Guidelines for STM32F4 with FreeRTOS

### Controller State Management
The controller should maintain the following state in RAM only:
- Current position and setpoint
- Cycle progress state
- Tip states (active/inactive, current readings)
- Tip settings (energy setpoint, distance setpoint, heat start delay)
- Speed mode (rapid/fine)
- Motor control states
- Configuration settings (weld time, pulse energy, etc.)

**No persistent storage is required on the controller side.** All settings are received from the Electron app via the SETTINGS packet on startup.

### 1. Task Structure
```c
// System state structure (RAM only)
typedef struct {
    float currentPosition;      // Current position in mm
    float workPositionSetpoint; // Work position setpoint in mm
    int8_t cycleProgress;       // -1 to 6
    TipState_t tips[8];         // Array of tip states
    SpeedMode_t speedMode;      // RAPID or FINE
    ConfigSettings_t config;    // Configuration settings
} SystemState_t;

// Tip state structure
typedef struct {
    bool active;                // Tip active/inactive
    float energySetpoint;       // Energy setpoint in joules
    float distanceSetpoint;     // Distance setpoint in mm  
    float heatStartDelay;       // Heat start delay in seconds
    // Runtime values
    float currentJoules;        // Current joules reading
    float currentDistance;      // Current distance reading
    float heatPercentage;       // Current heat percentage
} TipState_t;

// Configuration settings structure
typedef struct {
    float weldTime;             // Weld time in seconds
    float pulseEnergy;          // Pulse energy in joules
    float coolTime;             // Cool time in seconds
    float presenceHeight;       // Presence height in mm
    float bossToleranceMinus;   // Boss tolerance minus in mm
    float bossTolerancePlus;    // Boss tolerance plus in mm
} ConfigSettings_t;

// Recommended FreeRTOS task structure
typedef struct {
    QueueHandle_t txQueue;      // Queue for outgoing packets
    QueueHandle_t rxQueue;      // Queue for incoming packets
    SemaphoreHandle_t uartMutex; // Mutex for UART access
    SystemState_t state;        // Current system state (RAM only)
} UartComm_t;

// Main communication task
void vUartCommTask(void *pvParameters) {
    // Initialize UART
    // Create packet parser
    
    // Send WAKEUP request on startup
    sendWakeupRequest();
    
    // Main loop: receive, parse, process, respond
    while (1) {
        // Check for incoming packets
        if (receivePacket(&packet)) {
            processPacket(&packet);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

// Periodic data transmission task
void vDataTransmitTask(void *pvParameters) {
    // Wait for settings to be received before starting
    while (!settingsReceived) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    
    // Send TD packets every 100-250ms
    while (1) {
        buildAndSendTDPacket(&systemState);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

// Send WAKEUP request
void sendWakeupRequest(void) {
    sendUartPacket("WAKEUP:\n");
}

// Handle SETTINGS packet
void handleSettingsPacket(const char *json) {
    // Parse work_position object
    parseWorkPosition(json, &systemState.workPositionSetpoint, 
                            &systemState.speedMode);
    
    // Parse tips array
    for (int i = 0; i < 8; i++) {
        parseTipSettings(json, i, &systemState.tips[i]);
    }
    
    // Parse configuration
    parseConfiguration(json, &systemState.config);
    
    settingsReceived = true;
}
```

### 2. Packet Parser Implementation
```c
typedef enum {
    PARSER_STATE_IDLE,
    PARSER_STATE_COMMAND,
    PARSER_STATE_PAYLOAD
} ParserState_t;

typedef struct {
    ParserState_t state;
    char command[4];
    char payload[512];  // Adjust size based on your needs
    uint16_t index;
} PacketParser_t;
```

### 3. JSON Generation
For memory-constrained systems, consider using a lightweight JSON library or manual string formatting. The controller only formats current RAM values - no file I/O needed:

```c
// Example of manual JSON generation for TD packet from RAM state
void buildTipDataPacket(char *buffer, size_t bufSize, SystemState_t *state) {
    snprintf(buffer, bufSize, 
        "TD:{\"cycle_progress\":%d,\"tips\":[", 
        state->cycleProgress);
    
    // Add tip data from current RAM state
    for (int i = 0; i < 8; i++) {
        char tipBuf[64];
        snprintf(tipBuf, sizeof(tipBuf), 
            "%s{\"tip_number\":%d,\"joules\":%.1f,"
            "\"distance\":%.1f,\"heat_percentage\":%.1f}",
            (i > 0) ? "," : "", 
            i + 1,
            state->tips[i].joules,        // From RAM
            state->tips[i].distance,      // From RAM
            state->tips[i].heatPercentage); // From RAM
        strcat(buffer, tipBuf);
    }
    
    // Add home screen data from current system state
    strcat(buffer, "],\"home_screen\":{...}}\\n");
}
```

### 4. Safety Considerations

1. **Button Watchdog**: Implement auto-release for movement buttons
```c
#define BUTTON_TIMEOUT_MS 5000  // 5 seconds safety timeout
```

2. **Command Validation**: Validate all incoming commands
```c
bool validateCommand(const char *cmd, const char *payload) {
    // Check command format
    // Validate JSON structure
    // Verify parameter ranges
}
```

3. **Error Handling**: Implement robust error recovery
```c
// Send error state in TD packet if needed
if (errorCondition) {
    homeScreen.banner_text = "Error: Check System";
    homeScreen.spinner_active = false;
}
```

### 5. Memory Management
- Use static allocation where possible
- Pre-allocate buffers for JSON generation
- Consider using circular buffers for UART RX/TX

### 6. Real-time Considerations
- Set appropriate task priorities
- Use DMA for UART if available
- Keep ISRs minimal (defer processing to tasks)

## Testing

### 1. Simulator Compatibility
The Python simulator (`python/controller_simulator.py`) can be used to test your implementation:
- Connect STM32F4 UART to PC via USB-to-serial adapter
- Run simulator and connect to STM32F4's serial port
- Verify bidirectional communication

### 2. Test Scenarios
1. **Cycle Progress**: Verify all states -1 through 6
2. **Tip Data**: Test with various joules/distance/heat values
3. **Work Position**: Test up/down buttons with rapid/fine modes
4. **Button Safety**: Verify auto-release after timeout
5. **Error Recovery**: Test disconnection/reconnection

### 3. Performance Metrics
- Packet latency: < 50ms
- Update rate: 4-10 Hz for TD packets
- Button response: < 100ms

## Example Packet Flow

### Startup Sequence
1. Controller initializes with default values (all zeros/inactive states)
2. Controller → App: `WAKEUP:\n` (Request all settings)
3. App → Controller: `SETTINGS:{"work_position":{...},"tips":[...],"configuration":{...}}\n`
4. Controller stores received settings in RAM
5. Controller → App: `TD:{"cycle_progress":-1,"tips":[...],"home_screen":{...}}\n` (Start normal operation)
6. User interactions trigger commands from App to Controller
7. Any setting changes in the app trigger update commands (WPU, TIPS, or CFG)

### Work Position Adjustment
1. User presses UP button
2. App → Controller: `WPB:{"type":"WPB","button":"up","pressed":true,...}\n`
3. Controller starts movement
4. Controller → App: `WP:{"current_position":12.5,...}\n` (periodic updates)
5. User releases UP button
6. App → Controller: `WPB:{"type":"WPB","button":"up","pressed":false,...}\n`
7. Controller stops movement

### Setting Work Position
1. User clicks "Set Work Position" button
2. App displays confirmation dialog showing current position
3. User confirms
4. App saves current position as setpoint to JSON file
5. App → Controller: `WPU:{"setpoint":12.5,"speed_mode":"rapid"}\n`
6. Controller updates setpoint in RAM
7. Controller → App: `WP:{"current_position":12.5,"setpoint":12.5,...}\n` (confirmation)

### Heating Cycle
1. Controller → App: `TD:{"cycle_progress":0,...}\n` (Home active)
2. Controller → App: `TD:{"cycle_progress":1,...}\n` (Work Position active)
3. Controller → App: `TD:{"cycle_progress":3,...}\n` (Heat active)
4. During heating, update tip heat_percentage values
5. Controller → App: `TD:{"cycle_progress":6,...}\n` (Complete)

## Notes

1. All numeric values in JSON should use dot (.) as decimal separator
2. Strings in JSON must be properly escaped
3. Empty/zero values should still be included in packets
4. Packet size typically ranges from 200-800 bytes
5. Consider implementing packet acknowledgment for critical commands

## Important: Data Persistence

**The STM32F4 controller does NOT handle any data persistence.** All persistent storage is managed by the Electron application:

- **Controller**: Maintains state in RAM only, resets to defaults on power cycle
- **Electron App**: Saves/loads all configuration and state data to/from JSON files
- **On Startup**: Controller sends WAKEUP request, Electron app responds with all saved settings
- **During Operation**: Controller sends current values, Electron app saves as needed
- **Setting Changes**: Any setting change in the app automatically sends update to controller (WPU, TIPS, or CFG)

### Key Changes from Previous Protocol

1. **Baud Rate**: Increased from 9600 to 115200 for faster communication
2. **Controller Initialization**: Controller now sends WAKEUP request to receive all settings
3. **Work Position Button**: Now saves current position as setpoint (instead of receiving from controller)
4. **Automatic Updates**: All setting changes trigger immediate updates to controller
5. **Comprehensive Settings Transfer**: SETTINGS packet ensures controller has all configuration on startup

This protocol is designed to be simple yet extensible. Additional commands or fields can be added to the JSON structures as needed for future enhancements.
