const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const WebSocket = require('ws');

// Disable sandbox for Linux environments
if (process.platform === 'linux') {
  process.env.ELECTRON_NO_SANDBOX = '1';
  process.env.ELECTRON_DISABLE_SANDBOX = '1';
}

// Add command line switches for sandbox issues
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-setuid-sandbox');

// Load configuration
let config = {};
try {
  config = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
} catch (error) {
  console.warn('Could not load config.json, using defaults');
  config = {
    window: {
      width: 1200,
      height: 800,
      minWidth: 800,
      minHeight: 600,
      title: 'USHS Screens',
      icon: 'logo0.png',
      autoHideMenuBar: true,
      show: false
    }
  };
}

// Keep a global reference of the window object
let mainWindow;
let wss; // WebSocket server
let cachedUIState = {}; // Cache UI state for seamless transitions

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: config.window.width,
    height: config.window.height,
    minWidth: config.window.minWidth,
    minHeight: config.window.minHeight,
    webPreferences: {
      nodeIntegration: config.security.nodeIntegration,
      contextIsolation: config.security.contextIsolation,
      enableRemoteModule: config.security.enableRemoteModule,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets', 'logo0.png'),
    title: config.window.title,
    show: config.window.show,
    autoHideMenuBar: config.window.autoHideMenuBar
  });

  // Load the index.html file
  mainWindow.loadFile('index.html');

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Start WebSocket server
  startWebSocketServer();

  // Create application menu
  createMenu();
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Reload',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            if (mainWindow) {
              mainWindow.reload();
            }
          }
        },
        {
          label: 'Toggle Developer Tools',
          accelerator: 'F12',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.toggleDevTools();
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Quit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// This method will be called when Electron has finished initialization
app.whenReady().then(createWindow);

// Quit when all windows are closed
app.on('window-all-closed', () => {
  // On macOS it is common for applications and their menu bar
  // to stay active until the user quits explicitly with Cmd + Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On macOS it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Handle IPC messages from renderer process
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-app-name', () => {
  return app.getName();
});

// Handle navigation requests
ipcMain.on('navigate-to-page', (event, path) => {
  if (mainWindow) {
    mainWindow.loadFile(path);
    
    // Send cached state immediately after page loads
    mainWindow.webContents.once('did-finish-load', () => {
      // Batch all cached updates into a single message for home page
      if (path === 'index.html' || path === '') {
        const batchedUpdates = {
          elements: cachedUIState.elements || {},
          progressBars: cachedUIState.progressBars || {},
          progressStates: cachedUIState.progressStates || {},
          tipStates: cachedUIState.tipStates || {}
        };
        
        // Send all updates in one message
        mainWindow.webContents.send('batch-update', batchedUpdates);
        
        // Request fresh values immediately
        mainWindow.webContents.send('page-navigated-home');
      } else {
        // For other pages, use the normal update method
        if (cachedUIState.workPositionData) {
          mainWindow.webContents.send('work-position-update', cachedUIState.workPositionData);
        }
      }
    });
  }
});

// Handle window control requests
ipcMain.on('minimize-window', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.on('maximize-window', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.on('close-window', () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

ipcMain.on('reload-window', () => {
  if (mainWindow) {
    mainWindow.reload();
  }
});

// Handle messages to Python script
ipcMain.on('send-to-python', (event, data) => {
  if (wss && wss.clients.size > 0) {
    // Send to the first connected client (Python script)
    const client = Array.from(wss.clients)[0];
    client.send(JSON.stringify(data));
  }
});

// Handle request for cached UI state
ipcMain.handle('get-cached-state', () => {
  return cachedUIState;
});

// Handle reading tip states
ipcMain.handle('read_tip_states', async () => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    const data = fs.readFileSync(tipStatesPath, 'utf8');
    const tipStates = JSON.parse(data);
    return { tipStates };
  } catch (error) {
    console.error('Error reading tip states:', error);
    return { error: error.message };
  }
});

// Handle updating tip state
ipcMain.handle('update_tip_state', async (event, { tipNumber, active }) => {
  try {
    // Read current states
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let tipStates = {};
    try {
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      tipStates = JSON.parse(data);
    } catch (err) {
      // Initialize if file doesn't exist
      for (let i = 1; i <= 8; i++) {
        tipStates[i] = {
          active: i <= 4,
          energy_setpoint: 0.0,
          distance_setpoint: 0.0,
          heat_start_delay: 0.0
        };
      }
    }
    
    // Update the specific tip state
    if (tipStates[tipNumber]) {
      tipStates[tipNumber].active = active;
    }
    
    // Write back to file
    fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));
    
    // Send to Python script via WebSocket to write to Modbus
    if (wss && wss.clients.size > 0) {
      const client = Array.from(wss.clients)[0];
      client.send(JSON.stringify({
        type: 'update_tip_active',
        tipNumber: tipNumber,
        active: active
      }));
    }
    
    // Notify all renderer processes about the change
    if (mainWindow) {
      mainWindow.webContents.send('tip-state-changed', { tipNumber, active });
    }
    
    return { success: true };
  } catch (error) {
    console.error('Error updating tip state:', error);
    return { error: error.message };
  }
});

// Handle updating heating setpoints in JSON
ipcMain.handle('update_heating_setpoint', async (event, { tipNumber, type, value }) => {
  try {
    // Read current states
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let tipStates = {};
    try {
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      tipStates = JSON.parse(data);
    } catch (err) {
      // Initialize if file doesn't exist
      for (let i = 1; i <= 8; i++) {
        tipStates[i] = {
          active: i <= 4,
          energy_setpoint: 0.0,
          distance_setpoint: 0.0,
          heat_start_delay: 0.0
        };
      }
    }
    
    // Update the specific setpoint
    if (tipStates[tipNumber]) {
      if (type === 'energy') {
        tipStates[tipNumber].energy_setpoint = value;
      } else if (type === 'distance') {
        tipStates[tipNumber].distance_setpoint = value;
      } else if (type === 'heat_start_delay') {
        tipStates[tipNumber].heat_start_delay = value;
      }
    }
    
    // Write back to file
    fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));
    
    return { success: true };
  } catch (error) {
    console.error('Error updating heating setpoint:', error);
    return { error: error.message };
  }
});

// Handle reading configuration counters from JSON
ipcMain.handle('read_configuration', async () => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    const data = fs.readFileSync(tipStatesPath, 'utf8');
    const tipStates = JSON.parse(data);
    const config = tipStates.configuration || {
      weld_time: 0,
      pulse_energy: 10,
      cool_time: 0,
      presence_height: 0,
      boss_tolerance_minus: 0,
      boss_tolerance_plus: 0
    };
    return { configuration: config };
  } catch (error) {
    console.error('Error reading configuration:', error);
    return { error: error.message };
  }
});

// Handle updating configuration counters in JSON
ipcMain.handle('update_configuration', async (event, { key, value }) => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let tipStates = {};
    try {
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      tipStates = JSON.parse(data);
    } catch (err) {
      // initialize base structure if file missing
      for (let i = 1; i <= 8; i++) {
        tipStates[i] = {
          active: i <= 4,
          energy_setpoint: 0.0,
          distance_setpoint: 0.0,
          heat_start_delay: 0.0
        };
      }
      tipStates.configuration = {
        weld_time: 0,
        pulse_energy: 10,
        cool_time: 0,
        presence_height: 0,
        boss_tolerance_minus: 0,
        boss_tolerance_plus: 0
      };
    }

    if (!tipStates.configuration) {
      tipStates.configuration = {
        weld_time: 0,
        pulse_energy: 10,
        cool_time: 0,
        presence_height: 0,
        boss_tolerance_minus: 0,
        boss_tolerance_plus: 0
      };
    }

    if (key in tipStates.configuration) {
      tipStates.configuration[key] = value;
    }

    fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));

    return { success: true };
  } catch (error) {
    console.error('Error updating configuration:', error);
    return { error: error.message };
  }
});

// Save work position details into JSON
ipcMain.handle('save_work_position_json', async (event, { positionMm, setpointMm }) => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let dataObj = {};
    try {
      dataObj = JSON.parse(fs.readFileSync(tipStatesPath, 'utf8'));
    } catch (_) {
      // initialize base structure if file missing
      for (let i = 1; i <= 8; i++) {
        dataObj[i] = {
          active: i <= 4,
          energy_setpoint: 0.0,
          distance_setpoint: 0.0,
          heat_start_delay: 0.0
        };
      }
    }

    const numericPosition = Number(positionMm) || 0;
    const numericSetpoint = Number(setpointMm) || 0;

    dataObj.work_position = {
      position_mm: numericPosition,
      setpoint_mm: numericSetpoint,
      updated_at: new Date().toISOString()
    };

    fs.writeFileSync(tipStatesPath, JSON.stringify(dataObj, null, 2));
    return { success: true };
  } catch (error) {
    console.error('Error saving work position to JSON:', error);
    return { error: error.message };
  }
});

// WebSocket server functions
function startWebSocketServer() {
  wss = new WebSocket.Server({ port: 8080 });
  
  wss.on('connection', (ws) => {
    console.log('Python script connected to WebSocket server');
    
    ws.on('message', (message) => {
      try {
        const data = JSON.parse(message);
        
        if (data.type === 'update_element' && mainWindow) {
          // Cache the element state
          if (!cachedUIState.elements) cachedUIState.elements = {};
          cachedUIState.elements[data.element_id] = {
            property: data.property || 'textContent',
            value: data.value || data.text || ''
          };
          
          // Send message to renderer process to update DOM
          mainWindow.webContents.send('update-element', {
            elementId: data.element_id,
            property: data.property || 'textContent',
            value: data.value || data.text || ''
          });
        } else if (data.type === 'update_progress_bar' && mainWindow) {
          // Cache progress bar state
          if (!cachedUIState.progressBars) cachedUIState.progressBars = {};
          cachedUIState.progressBars[data.element_id] = data.progress;
          
          // Send message to renderer process to update progress bar
          mainWindow.webContents.send('update-progress-bar', {
            elementId: data.element_id,
            progress: data.progress
          });
        } else if (data.type === 'update_slider' && mainWindow) {
          // Cache slider position
          cachedUIState.sliderPosition = data.position;
          
          // Send message to renderer process to update slider position
          mainWindow.webContents.send('update-slider', {
            position: data.position
          });
        } else if (data.type === 'update_progress_states' && mainWindow) {
          // Cache progress states
          cachedUIState.progressStates = data.states;
          
          // Send message to renderer process to update progress states
          mainWindow.webContents.send('update-progress-states', {
            states: data.states
          });
        } else if (data.type === 'update_progress_text' && mainWindow) {
          // Cache progress text
          cachedUIState.progressText = data.text;
          
          // Send message to renderer process to update progress text
          mainWindow.webContents.send('update-progress-text', {
            text: data.text
          });
        } else if (data.type === 'update_tip_state' && mainWindow) {
          // Cache tip states
          if (!cachedUIState.tipStates) cachedUIState.tipStates = {};
          cachedUIState.tipStates[data.tip_number] = data.is_active;
          
          // Send message to renderer process to update tip active/inactive state
          mainWindow.webContents.send('update-tip-state', {
            tipNumber: data.tip_number,
            isActive: data.is_active
          });
        } else if (data.type === 'work_position_update' && mainWindow) {
          // Cache work position data
          cachedUIState.workPositionData = data.data;
          
          // Send work position update to all renderer windows
          mainWindow.webContents.send('work-position-update', data.data);
          // Also send to all other windows
          BrowserWindow.getAllWindows().forEach(window => {
            if (window !== mainWindow) {
              window.webContents.send('work-position-update', data.data);
            }
          });
        } else if (data.type === 'update_speed_buttons' && mainWindow) {
          // Send speed button update to renderer
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('update-speed-buttons', {
              rapid_active: data.rapid_active,
              fine_active: data.fine_active
            });
          });
        } else if (data.type === 'update_button_state' && mainWindow) {
          // Send button state update to renderer
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('update-button-state', {
              button_id: data.button_id,
              pressed: data.pressed
            });
          });
        } else if (data.type === 'modbus_update' && mainWindow) {
          // Send Modbus data update to all renderer windows
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('modbus-update', data);
          });
        } else if (data.type === 'heating_update' && mainWindow) {
          // Send heating setpoint update to all renderer windows
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('heating-update', data);
          });
        } else if (data.type === 'monitor_update' && mainWindow) {
          // Forward monitor screen updates to all windows
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('monitor-update', data);
          });
        } else if (data.type === 'manual_controls_update' && mainWindow) {
          // Forward manual controls updates to all windows
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('manual-controls-update', data);
          });
        } else if (data.type === 'update_slider_position' && mainWindow) {
          // Send slider position update to renderer
          BrowserWindow.getAllWindows().forEach(window => {
            window.webContents.send('update-slider-position', {
              slider_id: data.slider_id,
              percentage: data.percentage
            });
          });
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    });
    
    ws.on('close', () => {
      console.log('Python script disconnected from WebSocket server');
    });
  });
  
  console.log('WebSocket server started on port 8080');
}

// Clean up WebSocket server when app quits
app.on('before-quit', () => {
  if (wss) {
    wss.close();
  }
});

// Simple JSON storage for monitor stats (cycles)
ipcMain.handle('read_monitor_stats', async () => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    const data = fs.readFileSync(tipStatesPath, 'utf8');
    const j = JSON.parse(data);
    const monitor = j.monitor || { total: 0, successful: 0, unsuccessful: 0, history: [] };
    return { monitor };
  } catch (e) {
    return { monitor: { total: 0, successful: 0, unsuccessful: 0, history: [] } };
  }
});

ipcMain.handle('update_monitor_stats', async (event, payload) => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let j = {};
    try {
      j = JSON.parse(fs.readFileSync(tipStatesPath, 'utf8'));
    } catch (_) {
      // initialize base structure
      for (let i = 1; i <= 8; i++) {
        j[i] = { active: i <= 4, energy_setpoint: 0.0, distance_setpoint: 0.0, heat_start_delay: 0.0 };
      }
    }
    j.monitor = payload && payload.monitor ? payload.monitor : (j.monitor || { total: 0, successful: 0, unsuccessful: 0, history: [] });
    fs.writeFileSync(tipStatesPath, JSON.stringify(j, null, 2));
    return { success: true };
  } catch (e) {
    return { error: e.message };
  }
});