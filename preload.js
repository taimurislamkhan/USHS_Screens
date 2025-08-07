const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Navigation methods
  navigateToPage: (path) => {
    // For Electron, we'll handle navigation differently
    // This will be used by the renderer to communicate navigation intent
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
  
  // Send messages to Python script
  sendToPython: (data) => ipcRenderer.send('send-to-python', data),
  
  // Get cached UI state
  getCachedState: () => ipcRenderer.invoke('get-cached-state')
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