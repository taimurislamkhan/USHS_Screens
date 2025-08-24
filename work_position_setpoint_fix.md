# Work Position Setpoint Persistence Fix

## Problem
The work position setpoint was not persisting after screen changes. When navigating away from and back to the work position screen, the saved setpoint value was being lost.

## Root Causes

1. **Controller Data Override**: When the controller sent work position data (WP packet), if it didn't include a setpoint field, the app would forward this incomplete data to the renderer, causing the setpoint to disappear.

2. **Stale Cached Data**: During navigation to the work position page, the app was using cached data instead of reading fresh data from the JSON file.

## Solutions Implemented

### 1. Fixed Controller Data Handling (main.js line 1002)
Changed from:
```javascript
const mergedWPData = {
  ...wpData,  // Controller data might not have setpoint
  tip_states: {}
};
```

To:
```javascript
const mergedWPData = {
  ...updatedWorkPosition,  // Always includes saved setpoint
  tip_states: {}
};
```

### 2. Fixed Navigation Data Loading (main.js line 324)
Changed from using cached data to reading fresh data from JSON:
```javascript
// Use fresh work position data from file
const workPositionData = tipStates.work_position || {
  current_position: 0,
  setpoint: 0,
  speed_mode: 'rapid',
  tip_distances: {}
};
```

### 3. Added Debug Logging
- Added logging to track setpoint values during initial load
- Added logging when sending work position updates
- Added delay to ensure UI is ready before applying updates

## Testing
1. Navigate to Settings → Work Position
2. Set a work position using the "Set Work Position" button
3. Navigate away to another screen
4. Navigate back to Work Position
5. The setpoint should now persist and show the previously saved value

## Technical Details
- The setpoint is saved in `tip_states.json` under `work_position.setpoint` and `work_position.setpoint_mm` (for backwards compatibility)
- The work position screen reads this value on load via `requestInitialState()`
- The main process ensures this value is always included when sending work position updates to the renderer
