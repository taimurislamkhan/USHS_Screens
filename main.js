const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const SerialHandler = require('./serial-handler');


// Disable sandbox for Linux environments
if (process.platform === 'linux') {
  process.env.ELECTRON_NO_SANDBOX = '1';
  process.env.ELECTRON_DISABLE_SANDBOX = '1';
}

// Add command line switches for sandbox and GPU issues
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-setuid-sandbox');
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-gpu-sandbox');

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

// Serial communication handler
let serialHandler = null;

let cachedUIState = {}; // Cache UI state for seamless transitions

// Debounce timer for work position updates
let workPositionUpdateTimer = null;

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
  
  // Note: Initial tip data loading is now handled by individual pages
  // HomeScreen.html handles its own initialization via initializeTipStates()
  // This prevents timing conflicts between state switching and data loading
  mainWindow.webContents.once('did-finish-load', () => {
    console.log('Initial page load complete');
    
    // Load initial cycle progress from JSON file
    try {
      const tipStatesPath = path.join(__dirname, 'tip_states.json');
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      const jsonData = JSON.parse(data);
      
      if (jsonData.cycle_progress) {
        cachedUIState.progressStates = jsonData.cycle_progress;
        console.log('Loaded initial cycle progress states:', cachedUIState.progressStates);
        
        // Send initial progress states to renderer
        mainWindow.webContents.send('update-progress-states', jsonData.cycle_progress);
      }
      
      // Load home screen data
      if (jsonData.home_screen) {
        cachedUIState.homeScreenData = jsonData.home_screen;
        console.log('Loaded initial home screen data:', cachedUIState.homeScreenData);
        
        // Send initial home screen data to renderer
        mainWindow.webContents.send('home-screen-update', jsonData.home_screen);
      }
    } catch (error) {
      console.log('Could not load initial cycle progress states:', error.message);
    }
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });



  // Create application menu
  createMenu();
  
  // Initialize serial handler
  initializeSerialHandler();
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
  console.log('Navigation requested to:', path);
  if (mainWindow) {
    mainWindow.loadFile(path);
    
    // Send cached state immediately after page loads
    mainWindow.webContents.once('did-finish-load', () => {
      // Batch all cached updates into a single message for home page
      if (path === 'index.html' || path === '') {
        // Read fresh tip data from JSON file
        try {
          const tipStatesPath = require('path').join(__dirname, 'tip_states.json');
          const tipStatesData = fs.readFileSync(tipStatesPath, 'utf8');
          const tipStates = JSON.parse(tipStatesData);
          
          // Convert to tip data format
          const freshTipData = [];
          for (let i = 1; i <= 8; i++) {
            const tipState = tipStates[i.toString()];
            if (tipState) {
              freshTipData.push({
                tip_number: i,
                joules: tipState.current_joules || 0,
                distance: tipState.current_distance || 0,
                heat_percentage: tipState.current_heat_percentage || 0
              });
            }
          }
          
          // Load cycle progress from JSON
          const cycleProgress = tipStates.cycle_progress || {
            home: 'inactive',
            work_position: 'inactive',
            encoder_zero: 'inactive',
            heat: 'inactive',
            cool: 'inactive',
            cycle_complete: 'inactive'
          };
          
          console.log('Navigation: Loading cycle progress from JSON:', cycleProgress);
          
          // Update cached state with loaded cycle progress
          cachedUIState.progressStates = cycleProgress;
          
          // Update cached home screen data if available
          if (tipStates.home_screen) {
            cachedUIState.homeScreenData = tipStates.home_screen;
            console.log('Navigation: Loading home screen data from JSON:', tipStates.home_screen);
          }
          
          const batchedUpdates = {
            elements: cachedUIState.elements || {},
            progressBars: cachedUIState.progressBars || {},
            progressStates: cycleProgress,
            tipStates: cachedUIState.tipStates || {},
            currentTipData: freshTipData, // Use fresh data from file
            homeScreen: cachedUIState.homeScreenData || tipStates.home_screen
          };
          
          console.log('Navigation: Sending batch update with progressStates:', batchedUpdates.progressStates);
          
          // Delay sending updates to ensure HomeScreen.html is loaded
          setTimeout(() => {
            // Send all updates in one message
            mainWindow.webContents.send('batch-update', batchedUpdates);
            
            // Also send cycle progress states directly
            mainWindow.webContents.send('update-progress-states', cycleProgress);
            
            // Also send tip data update directly with cycle progress and home screen data
            if (freshTipData.length > 0) {
              mainWindow.webContents.send('tip-data-update', {
                tips: freshTipData,
                cycleProgress: cycleProgress,
                homeScreen: cachedUIState.homeScreenData || tipStates.home_screen
              });
            }
            
            // Request fresh values immediately
            mainWindow.webContents.send('page-navigated-home');
          }, 500); // Give time for HomeScreen.html to load
        } catch (error) {
          console.error('Error reading tip states on navigation:', error);
          
          // Fallback to cached data
          const batchedUpdates = {
            elements: cachedUIState.elements || {},
            progressBars: cachedUIState.progressBars || {},
            progressStates: cachedUIState.progressStates || {},
            tipStates: cachedUIState.tipStates || {},
            currentTipData: cachedUIState.currentTipData || [],
            homeScreen: cachedUIState.homeScreenData || {}
          };
          
          // Delay sending updates to ensure HomeScreen.html is loaded
          setTimeout(() => {
            // Send all updates in one message
            mainWindow.webContents.send('batch-update', batchedUpdates);
            
            // Also send cycle progress states directly
            if (cachedUIState.progressStates) {
              mainWindow.webContents.send('update-progress-states', cachedUIState.progressStates);
            }
            
            // Request fresh values immediately
            mainWindow.webContents.send('page-navigated-home');
          }, 500); // Give time for HomeScreen.html to load
        }
      } else {
        // For other pages, use the normal update method
        if (path.includes('work_position')) {
          // For work position page, read fresh data from JSON file
          try {
            const tipStatesPath = require('path').join(__dirname, 'tip_states.json');
            const data = fs.readFileSync(tipStatesPath, 'utf8');
            const tipStates = JSON.parse(data);
            
            // Use fresh work position data from file
            const workPositionData = tipStates.work_position || {
              current_position: 0,
              setpoint: 0,
              speed_mode: 'rapid',
              tip_distances: {}
            };
            
            // Create merged work position data
            const mergedWPData = {
              ...workPositionData,
              tip_states: {}
            };
            
            // First add individual tip active states
            Object.entries(tipStates).forEach(([tipNumber, tipData]) => {
              if (!isNaN(parseInt(tipNumber))) {
                mergedWPData.tip_states[parseInt(tipNumber)] = tipData.active || false;
              }
            });
            
            // Don't override with saved work position tip states - they should come from individual tip data only
            
            console.log('Sending fresh work position data on navigation:', mergedWPData);
            console.log('Setpoint from file:', mergedWPData.setpoint);
            mainWindow.webContents.send('work-position-update', mergedWPData);
            
            // Update cache with fresh data
            cachedUIState.workPositionData = workPositionData;
          } catch (error) {
            console.error('Error loading work position data:', error);
            // Fallback to sending empty data
            mainWindow.webContents.send('work-position-update', {
              current_position: 0,
              setpoint: 0,
              speed_mode: 'rapid',
              tip_distances: {},
              tip_states: {}
            });
          }
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
    
    // Also send tip data update to renderer immediately
    if (mainWindow) {
      const tipData = [];
      for (let i = 1; i <= 8; i++) {
        const tipState = tipStates[i.toString()];
        if (tipState) {
          tipData.push({
            tip_number: i,
            joules: tipState.current_joules || 0,
            distance: tipState.current_distance || 0,
            heat_percentage: tipState.current_heat_percentage || 0
          });
        }
      }
      
      // Get cycle progress from the JSON
      const cycleProgress = tipStates.cycle_progress || {
        home: 'inactive',
        work_position: 'inactive',
        encoder_zero: 'inactive',
        heat: 'inactive',
        cool: 'inactive',
        cycle_complete: 'inactive'
      };
      
      // Get home screen data from the JSON
      const homeScreen = tipStates.home_screen || {
        banner_text: 'System Is Ready',
        processing_text: 'Processing...',
        spinner_active: true,
        percentage: 0,
        time_text: '∼1m 46sec',
        slider_position: 0
      };
      
      if (tipData.length > 0) {
        console.log('Sending tip data update from read_tip_states with cycle progress');
        // Send tip data, cycle progress, and home screen data in the same event
        mainWindow.webContents.send('tip-data-update', {
          tips: tipData,
          cycleProgress: cycleProgress,
          homeScreen: homeScreen
        });
      }
    }
    
    return { tipStates, cycleProgress: tipStates.cycle_progress, homeScreen: tipStates.home_screen };
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
    

    
    // Notify all renderer processes about the change
    if (mainWindow) {
      mainWindow.webContents.send('tip-state-changed', { tipNumber, active });
    }
    
    // Send updated tip settings to controller
    sendSettingsToController('tips');
    
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
    
    // Send updated tip settings to controller
    sendSettingsToController('tips');
    
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
    
    // Send updated configuration to controller
    sendSettingsToController('configuration');

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

    // Ensure work_position exists with all required fields
    if (!dataObj.work_position) {
      dataObj.work_position = {
        tip_distances: {}
      };
    }
    
    // Update work position with both old and new format for compatibility
    dataObj.work_position = {
      ...dataObj.work_position,
      current_position: numericPosition,
      setpoint: numericSetpoint,
      position_mm: numericPosition,  // Keep for backward compatibility
      setpoint_mm: numericSetpoint,  // Keep for backward compatibility
      updated_at: new Date().toISOString()
    };

    fs.writeFileSync(tipStatesPath, JSON.stringify(dataObj, null, 2));
    
    // Send updated work position to controller
    sendSettingsToController('work_position');
    
    return { success: true };
  } catch (error) {
    console.error('Error saving work position to JSON:', error);
    return { error: error.message };
  }
});

// Save work position speed mode
ipcMain.handle('save_work_position_speed', async (event, { speed_mode }) => {
  try {
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let tipStates = {};
    
    // Read existing file
    try {
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      tipStates = JSON.parse(data);
    } catch (err) {
      console.log('Creating new tip states file');
    }
    
    // Update work position speed mode
    if (!tipStates.work_position) {
      tipStates.work_position = {};
    }
    
    tipStates.work_position.speed_mode = speed_mode;
    tipStates.work_position.updated_at = new Date().toISOString();
    
    // Save updated states
    fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));
    
    console.log('Work position speed mode saved:', speed_mode);
    
    // Also update cached state
    if (!cachedUIState.workPositionData) {
      cachedUIState.workPositionData = {};
    }
    cachedUIState.workPositionData.speed_mode = speed_mode;
    
    // Send updated work position to controller
    sendSettingsToController('work_position');
    
    return { success: true };
  } catch (error) {
    console.error('Error saving work position speed mode:', error);
    return { error: error.message };
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

// Initialize serial handler
function initializeSerialHandler() {
  serialHandler = new SerialHandler();
  
  // Handle serial events
  serialHandler.on('connected', (port) => {
    console.log(`Serial connected to ${port}`);
    if (mainWindow) {
      mainWindow.webContents.send('serial-connected', port);
    }
  });
  
  serialHandler.on('disconnected', () => {
    console.log('Serial disconnected');
    if (mainWindow) {
      mainWindow.webContents.send('serial-disconnected');
    }
  });
  
  serialHandler.on('error', (error) => {
    console.error('Serial error:', error);
    if (mainWindow) {
      mainWindow.webContents.send('serial-error', error.message);
    }
  });
  
  serialHandler.on('cycleProgress', async (stateIndex) => {
    console.log(`Cycle progress update: ${stateIndex}`);
    
    // Convert state index to progress states object
    const progressStates = {
      home: 'inactive',
      work_position: 'inactive',
      encoder_zero: 'inactive',
      heat: 'inactive',
      cool: 'inactive',
      cycle_complete: 'inactive'
    };
    
    const stages = ['home', 'work_position', 'encoder_zero', 'heat', 'cool', 'cycle_complete'];
    
    if (stateIndex >= 0 && stateIndex <= 6) {
      // Update states based on index
      for (let i = 0; i < stages.length; i++) {
        if (i < stateIndex) {
          progressStates[stages[i]] = 'done';
        } else if (i === stateIndex && stateIndex < 6) {
          progressStates[stages[i]] = 'active';
        } else {
          progressStates[stages[i]] = 'inactive';
        }
      }
      
      // Special case: all done
      if (stateIndex === 6) {
        stages.forEach(stage => {
          progressStates[stage] = 'done';
        });
      }
    }
    
    // Update cached state
    if (!cachedUIState.progressStates) {
      cachedUIState.progressStates = {};
    }
    Object.assign(cachedUIState.progressStates, progressStates);
    
    // Save to JSON file
    try {
      const tipStatesPath = path.join(__dirname, 'tip_states.json');
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      const jsonData = JSON.parse(data);
      
      // Update cycle progress
      jsonData.cycle_progress = progressStates;
      
      // Write back to file
      fs.writeFileSync(tipStatesPath, JSON.stringify(jsonData, null, 2));
      console.log('Cycle progress states saved to file');
    } catch (error) {
      console.error('Error saving cycle progress states:', error);
    }
    
    // Send to renderer
    if (mainWindow) {
      mainWindow.webContents.send('update-progress-states', progressStates);
    }
  });
  
  serialHandler.on('homeScreenData', async (homeScreenData) => {
    console.log('Home screen data update received:', homeScreenData);
    
    try {
      // Read current tip states
      const tipStatesPath = path.join(__dirname, 'tip_states.json');
      let tipStates = {};
      
      try {
        const data = fs.readFileSync(tipStatesPath, 'utf8');
        tipStates = JSON.parse(data);
      } catch (err) {
        console.log('Creating new tip states file');
      }
      
      // Update home screen data
      tipStates.home_screen = homeScreenData;
      
      // Save updated states
      fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));
      
      // Cache the home screen data
      cachedUIState.homeScreenData = homeScreenData;
      
      // Send to renderer
      if (mainWindow) {
        console.log('Sending home-screen-update IPC event to renderer');
        mainWindow.webContents.send('home-screen-update', homeScreenData);
      }
      
    } catch (error) {
      console.error('Error handling home screen data:', error);
    }
  });
  
  serialHandler.on('tipData', async (tips) => {
    console.log('Tip data update received:', tips);
    
    try {
      // Read current tip states
      const tipStatesPath = path.join(__dirname, 'tip_states.json');
      let tipStates = {};
      
      try {
        const data = fs.readFileSync(tipStatesPath, 'utf8');
        tipStates = JSON.parse(data);
      } catch (err) {
        console.log('Creating new tip states file');
      }
      
      // Update tip data from serial packet
      tips.forEach(tip => {
        const tipNum = tip.tip_number.toString();
        
        // Keep existing data but update with new values from serial
        if (!tipStates[tipNum]) {
          tipStates[tipNum] = {
            active: true,
            energy_setpoint: 0,
            distance_setpoint: 0,
            heat_start_delay: 0
          };
        }
        
        // Update real-time values
        tipStates[tipNum].current_joules = tip.joules;
        tipStates[tipNum].current_distance = tip.distance;
        tipStates[tipNum].current_heat_percentage = tip.heat_percentage;
      });
      
      // Save updated states
      fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));
      
      // Cache the tip data for page navigation
      cachedUIState.currentTipData = tips;
      
      // Send to all renderer windows with cycle progress
      if (mainWindow) {
        console.log('Sending tip-data-update IPC event to renderer with cycle progress');
        // Include the current cycle progress state with the tip data
        mainWindow.webContents.send('tip-data-update', {
          tips: tips,
          cycleProgress: cachedUIState.progressStates || tipStates.cycle_progress,
          homeScreen: cachedUIState.homeScreenData || tipStates.home_screen
        });
      } else {
        console.error('mainWindow is null, cannot send tip data!');
      }
      
    } catch (error) {
      console.error('Error handling tip data:', error);
    }
  });
  
  // Handle work position data from controller
  serialHandler.on('workPositionData', async (wpData) => {
    console.log('Work position data update received:', wpData);
    
    // Clear any existing timer
    if (workPositionUpdateTimer) {
      clearTimeout(workPositionUpdateTimer);
    }
    
    // Debounce updates to prevent overwhelming the system
    workPositionUpdateTimer = setTimeout(async () => {
      try {
        // Read current tip states
        const tipStatesPath = path.join(__dirname, 'tip_states.json');
        let tipStates = {};
        
        try {
          const data = fs.readFileSync(tipStatesPath, 'utf8');
          tipStates = JSON.parse(data);
        } catch (err) {
          console.log('Creating new tip states file');
        }
      
      // Update work position data
      if (!tipStates.work_position) {
        tipStates.work_position = {
          tip_distances: {},
          current_position: 0,
          setpoint: 0,
          speed_mode: 'rapid'
        };
      }
      
      // Ensure all tip distances are initialized
      if (!tipStates.work_position.tip_distances) {
        tipStates.work_position.tip_distances = {};
      }
      
      for (let i = 1; i <= 8; i++) {
        if (tipStates.work_position.tip_distances[i] === undefined) {
          tipStates.work_position.tip_distances[i] = 0;
        }
      }
      
      // Update work position preserving existing structure
      const updatedWorkPosition = {
        current_position: wpData.current_position !== undefined ? wpData.current_position : tipStates.work_position.current_position,
        setpoint: wpData.setpoint !== undefined ? wpData.setpoint : tipStates.work_position.setpoint,
        speed_mode: wpData.speed_mode || tipStates.work_position.speed_mode || 'rapid',
        tip_distances: { ...tipStates.work_position.tip_distances },
        // Keep old format for backward compatibility
        position_mm: wpData.current_position !== undefined ? wpData.current_position : tipStates.work_position.current_position,
        setpoint_mm: wpData.setpoint !== undefined ? wpData.setpoint : tipStates.work_position.setpoint,
        updated_at: new Date().toISOString()
      };
      
      // Update tip distances if provided
      if (wpData.tip_distances) {
        Object.entries(wpData.tip_distances).forEach(([tip, distance]) => {
          updatedWorkPosition.tip_distances[tip] = distance;
        });
      }
      
      tipStates.work_position = updatedWorkPosition;
      
      // Don't store tip_states in work_position - they should come from individual tip data
      
      // Save updated states
      fs.writeFileSync(tipStatesPath, JSON.stringify(tipStates, null, 2));
      
      // Cache the work position data
      cachedUIState.workPositionData = tipStates.work_position;
      
      // Merge in tip states from individual tip data (not from work position packet)
      // Use the updated work position data that includes the preserved setpoint
      const mergedWPData = {
        ...updatedWorkPosition,
        tip_states: {}
      };
      
      // Get tip states from individual tip data
      Object.entries(tipStates).forEach(([tipNumber, tipData]) => {
        if (!isNaN(parseInt(tipNumber)) && tipData.active !== undefined) {
          mergedWPData.tip_states[parseInt(tipNumber)] = tipData.active;
        }
      });
      
      // Send to renderer
      if (mainWindow) {
        console.log('Sending work-position-update event to renderer');
        console.log('Setpoint being sent:', mergedWPData.setpoint);
        mainWindow.webContents.send('work-position-update', mergedWPData);
      } else {
        console.error('mainWindow is null, cannot send work position data!');
      }
      
      } catch (error) {
        console.error('Error handling work position data:', error);
      }
    }, 100); // 100ms debounce
  });
  
  // Handle controller wakeup request
  serialHandler.on('controllerWakeup', async () => {
    console.log('Controller wakeup request received - sending all settings');
    
    try {
      // Read all settings from tip_states.json
      const tipStatesPath = path.join(__dirname, 'tip_states.json');
      let allSettings = {};
      
      try {
        const data = fs.readFileSync(tipStatesPath, 'utf8');
        allSettings = JSON.parse(data);
      } catch (err) {
        console.error('Error reading tip states for wakeup response:', err);
        return;
      }
      
      // Build comprehensive settings packet
      const settingsPacket = {
        // Work position settings
        work_position: {
          setpoint: allSettings.work_position?.setpoint || allSettings.work_position?.setpoint_mm || 0,
          speed_mode: allSettings.work_position?.speed_mode || 'rapid'
        },
        
        // Tip settings (energy, distance, heat start delay, active state)
        tips: [],
        
        // Configuration settings
        configuration: allSettings.configuration || {
          weld_time: 0,
          pulse_energy: 0,
          cool_time: 0,
          presence_height: 0,
          boss_tolerance_minus: 0,
          boss_tolerance_plus: 0
        }
      };
      
      // Add tip settings for all 8 tips
      for (let i = 1; i <= 8; i++) {
        const tipData = allSettings[i.toString()];
        if (tipData) {
          settingsPacket.tips.push({
            tip_number: i,
            active: tipData.active || false,
            energy_setpoint: tipData.energy_setpoint || 0,
            distance_setpoint: tipData.distance_setpoint || 0,
            heat_start_delay: tipData.heat_start_delay || 0
          });
        } else {
          // Default tip settings
          settingsPacket.tips.push({
            tip_number: i,
            active: false,
            energy_setpoint: 0,
            distance_setpoint: 0,
            heat_start_delay: 0
          });
        }
      }
      
      // Send settings packet to controller
      const packet = `SETTINGS:${JSON.stringify(settingsPacket)}`;
      serialHandler.send(packet);
      console.log('Sent settings packet to controller:', packet);
      
    } catch (error) {
      console.error('Error handling controller wakeup:', error);
    }
  });
}

// Function to send updated settings to controller
async function sendSettingsToController(settingType = 'all') {
  if (!serialHandler || !serialHandler.isConnected) {
    console.log('Serial not connected, cannot send settings');
    return;
  }
  
  try {
    // Read current settings
    const tipStatesPath = path.join(__dirname, 'tip_states.json');
    let allSettings = {};
    
    try {
      const data = fs.readFileSync(tipStatesPath, 'utf8');
      allSettings = JSON.parse(data);
    } catch (err) {
      console.error('Error reading tip states for settings update:', err);
      return;
    }
    
    let packet = '';
    
    switch (settingType) {
      case 'work_position':
        // Send only work position update
        const wpUpdate = {
          setpoint: allSettings.work_position?.setpoint || allSettings.work_position?.setpoint_mm || 0,
          speed_mode: allSettings.work_position?.speed_mode || 'rapid'
        };
        packet = `WPU:${JSON.stringify(wpUpdate)}`;
        break;
        
      case 'tips':
        // Send only tip settings update
        const tipsUpdate = {
          tips: []
        };
        for (let i = 1; i <= 8; i++) {
          const tipData = allSettings[i.toString()];
          if (tipData) {
            tipsUpdate.tips.push({
              tip_number: i,
              active: tipData.active || false,
              energy_setpoint: tipData.energy_setpoint || 0,
              distance_setpoint: tipData.distance_setpoint || 0,
              heat_start_delay: tipData.heat_start_delay || 0
            });
          }
        }
        packet = `TIPS:${JSON.stringify(tipsUpdate)}`;
        break;
        
      case 'configuration':
        // Send only configuration update
        const configUpdate = {
          configuration: allSettings.configuration || {}
        };
        packet = `CFG:${JSON.stringify(configUpdate)}`;
        break;
        
      case 'all':
      default:
        // Send all settings (same as wakeup response)
        const settingsPacket = {
          work_position: {
            setpoint: allSettings.work_position?.setpoint || allSettings.work_position?.setpoint_mm || 0,
            speed_mode: allSettings.work_position?.speed_mode || 'rapid'
          },
          tips: [],
          configuration: allSettings.configuration || {}
        };
        
        for (let i = 1; i <= 8; i++) {
          const tipData = allSettings[i.toString()];
          if (tipData) {
            settingsPacket.tips.push({
              tip_number: i,
              active: tipData.active || false,
              energy_setpoint: tipData.energy_setpoint || 0,
              distance_setpoint: tipData.distance_setpoint || 0,
              heat_start_delay: tipData.heat_start_delay || 0
            });
          }
        }
        
        packet = `SETTINGS:${JSON.stringify(settingsPacket)}`;
        break;
    }
    
    if (packet) {
      serialHandler.send(packet);
      console.log(`Sent ${settingType} settings to controller:`, packet);
    }
    
  } catch (error) {
    console.error('Error sending settings to controller:', error);
  }
}

// Serial port IPC handlers
ipcMain.handle('serial-list-ports', async () => {
  if (serialHandler) {
    return await serialHandler.listPorts();
  }
  return [];
});

ipcMain.handle('serial-connect', async (event, { port, baudRate }) => {
  if (serialHandler) {
    try {
      await serialHandler.connect(port, baudRate || 115200);
      return { success: true };
    } catch (error) {
      return { error: error.message };
    }
  }
  return { error: 'Serial handler not initialized' };
});

ipcMain.handle('serial-disconnect', async () => {
  if (serialHandler) {
    serialHandler.disconnect();
    return { success: true };
  }
  return { error: 'Serial handler not initialized' };
});

ipcMain.handle('serial-send', async (event, data) => {
  if (serialHandler) {
    serialHandler.send(data);
    return { success: true };
  }
  return { error: 'Serial handler not initialized' };
});

// Handle send_to_serial from work position screen
ipcMain.handle('send_to_serial', async (event, data) => {
  if (serialHandler && serialHandler.isConnected) {
    serialHandler.send(data);
    return { success: true };
  }
  return { error: 'Serial port not connected' };
});

ipcMain.handle('serial-get-status', async () => {
  if (serialHandler) {
    return {
      connected: serialHandler.isConnected,
      port: serialHandler.portPath
    };
  }
  return { connected: false, port: null };
});