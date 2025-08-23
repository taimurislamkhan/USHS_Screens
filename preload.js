const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Navigation methods
  navigateToPage: (path) => {
    // For Electron, we'll handle navigation differently
    // This will be used by the renderer to communicate navigation intent
    console.log('Preload: navigateToPage called with path:', path);
    ipcRenderer.send('navigate-to-page', path);
  },
  
  // App info
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getAppName: () => ipcRenderer.invoke('get-app-name'),
  
  // Window controls
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close: () => ipcRenderer.send('close-window'),
  reload: () => ipcRenderer.send('reload-window'),
  
  // File operations (if needed)
  openFile: () => ipcRenderer.invoke('open-file'),
  saveFile: (data) => ipcRenderer.invoke('save-file', data),
  
  // System info
  getPlatform: () => process.platform,
  isDev: () => process.env.NODE_ENV === 'development',
  

  
  // Get cached UI state
  getCachedState: () => ipcRenderer.invoke('get-cached-state'),
  
  // Send generic messages (for heating screen)
  sendMessage: (messageName, data) => ipcRenderer.invoke(messageName, data),
  
  // Listen for messages
  onMessage: (callback) => {
    // This can be extended for other message types as needed
  },
  
  // Serial port methods
  serial: {
    listPorts: () => ipcRenderer.invoke('serial-list-ports'),
    connect: (port, baudRate) => ipcRenderer.invoke('serial-connect', { port, baudRate }),
    disconnect: () => ipcRenderer.invoke('serial-disconnect'),
    send: (data) => ipcRenderer.invoke('serial-send', data),
    getStatus: () => ipcRenderer.invoke('serial-get-status')
  }
});

// Handle navigation events from renderer
ipcRenderer.on('navigate-response', (event, data) => {
  // This will be handled by the renderer process
  window.dispatchEvent(new CustomEvent('navigation-response', { detail: data }));
});

// Handle element update events from main process
ipcRenderer.on('update-element', (event, data) => {
  // Dispatch custom event for element updates
  window.dispatchEvent(new CustomEvent('update-element', { detail: data }));
});

// Handle progress bar update events from main process
ipcRenderer.on('update-progress-bar', (event, data) => {
  // Dispatch custom event for progress bar updates
  window.dispatchEvent(new CustomEvent('update-progress-bar', { detail: data }));
});

// Handle slider update events from main process
ipcRenderer.on('update-slider', (event, data) => {
  // Dispatch custom event for slider updates
  window.dispatchEvent(new CustomEvent('update-slider', { detail: data }));
});

// Handle progress states update events from main process
ipcRenderer.on('update-progress-states', (event, data) => {
  // Dispatch custom event for progress states updates
  window.dispatchEvent(new CustomEvent('update-progress-states', { detail: data }));
});

// Handle progress text update events from main process
ipcRenderer.on('update-progress-text', (event, data) => {
  // Dispatch custom event for progress text updates
  window.dispatchEvent(new CustomEvent('update-progress-text', { detail: data }));
});

// Handle tip data update events from main process
ipcRenderer.on('tip-data-update', (event, data) => {
  console.log('Preload received tip-data-update IPC event:', data);
  // Dispatch custom event for tip data updates
  const customEvent = new CustomEvent('tip-data-update', { detail: data });
  console.log('Dispatching custom event to window');
  window.dispatchEvent(customEvent);
});

// Handle tip state update events from main process
ipcRenderer.on('update-tip-state', (event, data) => {
  // Dispatch custom event for tip state updates
  window.dispatchEvent(new CustomEvent('update-tip-state', { detail: data }));
});

// Handle work position update events from main process
ipcRenderer.on('work-position-update', (event, data) => {
  // Dispatch custom event for work position updates
  window.dispatchEvent(new CustomEvent('work-position-update', { detail: data }));
});

// Handle speed buttons update events from main process
ipcRenderer.on('update-speed-buttons', (event, data) => {
  // Dispatch custom event for speed buttons updates
  window.dispatchEvent(new CustomEvent('update-speed-buttons', { detail: data }));
});

// Handle button state update events from main process
ipcRenderer.on('update-button-state', (event, data) => {
  // Dispatch custom event for button state updates
  window.dispatchEvent(new CustomEvent('update-button-state', { detail: data }));
});

// Handle slider position update events from main process
ipcRenderer.on('update-slider-position', (event, data) => {
  // Dispatch custom event for slider position updates
  window.dispatchEvent(new CustomEvent('update-slider-position', { detail: data }));
});

// Handle page navigation events from main process
ipcRenderer.on('page-navigated-home', () => {
  window.dispatchEvent(new CustomEvent('page-navigated-home'));
});

// Handle batch updates for faster page loading
ipcRenderer.on('batch-update', (event, data) => {
  window.dispatchEvent(new CustomEvent('batch-update', { detail: data }));
});

// Handle home screen updates
ipcRenderer.on('home-screen-update', (event, data) => {
  console.log('Preload received home-screen-update IPC event:', data);
  window.dispatchEvent(new CustomEvent('home-screen-update', { detail: data }));
});

// Handle tip state changed notifications
ipcRenderer.on('tip-state-changed', (event, data) => {
  window.dispatchEvent(new CustomEvent('tip-state-changed', { detail: data }));
});

// Handle work position updates from controller
ipcRenderer.on('work-position-update', (event, data) => {
  console.log('Preload received work-position-update IPC event:', data);
  window.dispatchEvent(new CustomEvent('work-position-update', { detail: data }));
});

// Handle heating update events
ipcRenderer.on('heating-update', (event, data) => {
  window.dispatchEvent(new CustomEvent('heating-update', { detail: data }));
}); 

// Handle monitor screen updates
ipcRenderer.on('monitor-update', (event, data) => {
  window.dispatchEvent(new CustomEvent('monitor-update', { detail: data }));
});

// Handle manual controls updates
ipcRenderer.on('manual-controls-update', (event, data) => {
  window.dispatchEvent(new CustomEvent('manual-controls-update', { detail: data }));
});

// Handle serial port events
ipcRenderer.on('serial-connected', (event, port) => {
  window.dispatchEvent(new CustomEvent('serial-connected', { detail: port }));
});

ipcRenderer.on('serial-disconnected', () => {
  window.dispatchEvent(new CustomEvent('serial-disconnected'));
});

ipcRenderer.on('serial-error', (event, error) => {
  window.dispatchEvent(new CustomEvent('serial-error', { detail: error }));
});