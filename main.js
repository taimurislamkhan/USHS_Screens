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