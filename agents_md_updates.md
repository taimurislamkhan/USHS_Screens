# Updates to agents.md

## Summary of Changes Made

### 1. UART Configuration
- **Changed**: Baud rate from 9600 to 115200

### 2. New Commands Added

#### From Controller to App:
- **WAKEUP**: Controller initialization request to get all settings

#### From App to Controller:
- **WPU (Work Position Update)**: Sends new work position setpoint
- **SETTINGS**: Complete settings packet (response to WAKEUP)
- **TIPS**: Tip settings update
- **CFG**: Configuration settings update

### 3. Deprecated Commands
- **WPT (Work Position seT)**: Marked as deprecated. Work position is now saved by the app when user confirms.

### 4. Updated Behavior
- **Work Position Button**: Now saves current position as setpoint (instead of receiving from controller)
- **Controller Initialization**: New WAKEUP/SETTINGS flow ensures controller gets all settings on startup
- **Automatic Updates**: Any setting change in app triggers immediate update to controller

### 5. Updated Implementation Guidelines
- Added comprehensive state structures for C implementation
- Added tip settings and configuration structures
- Updated example code to show WAKEUP request handling
- Added SETTINGS packet parsing example

### 6. Updated Example Flows
- **Startup Sequence**: Now includes WAKEUP/SETTINGS exchange
- **Work Position Setting**: New flow showing how current position is saved as setpoint

### 7. Added Section
- **Key Changes from Previous Protocol**: Summary of major changes for easy reference

## Purpose of Updates

These updates reflect the new architecture where:
1. The controller has no memory and relies on the app for all settings
2. Settings are automatically synchronized on any change
3. Work position behavior is more intuitive (save current position)
4. Communication is faster with higher baud rate
5. Controller initialization is more robust with explicit settings transfer
