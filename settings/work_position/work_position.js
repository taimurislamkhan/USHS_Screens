/**
 * Work Position Screen JavaScript Controller
 * ==========================================
 * 
 * Handles all UI updates and interactions for the work position screen
 */

// No WebSocket needed - using IPC from main process

// UI element references
const elements = {
    // Position displays
    currentPositionText: null,
    setpointText: null,
    
    // Buttons
    upButton: null,
    downButton: null,
    rapidSpeedButton: null,
    fineSpeedButton: null,
    setWorkPositionButton: null,
    
    // Tip elements (1-8)
    tipElements: {}
};

// Button state tracking
const buttonStates = {
    up: false,
    down: false,
    lastSentUp: false,
    lastSentDown: false,
    watchdogTimers: {
        up: null,
        down: null
    },
    continuousSendIntervals: {
        up: null,
        down: null
    },
    speedMode: 'rapid' // Default to rapid speed
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Work Position screen initializing...');
    
    // Cache element references
    cacheElements();
    
    // Setup IPC event listeners
    setupIPCListeners();
    
    // Setup button event handlers
    setupEventHandlers();
    
    // Request initial state
    requestInitialState();
    
    // Remove periodic state sync as it was causing issues with user interactions
    // The state will be loaded once on page load and updated via serial events
    
    // Global event to catch any missed button releases
    window.addEventListener('mouseup', function(e) {
        if (buttonStates.up) {
            console.log('Global mouseup - releasing up button');
            releaseButton('up');
        }
        if (buttonStates.down) {
            console.log('Global mouseup - releasing down button');
            releaseButton('down');
        }
    });
    
    // Release all buttons if window loses focus
    window.addEventListener('blur', function() {
        if (buttonStates.up || buttonStates.down) {
            console.log('Window blur - releasing all buttons');
            if (buttonStates.up) releaseButton('up');
            if (buttonStates.down) releaseButton('down');
        }
    });
});

function requestInitialState() {
    console.log('Requesting initial work position state');
    
    // Load tip states and work position data from JSON file
    if (window.electronAPI) {
        window.electronAPI.sendMessage('read_tip_states').then(response => {
            if (response && response.tipStates) {
                // Apply initial tip states
                Object.entries(response.tipStates).forEach(([tipNumber, tipData]) => {
                    if (!isNaN(parseInt(tipNumber))) {
                        updateTipState(parseInt(tipNumber), tipData.active);
                    }
                });
                
                // Load work position data if available
                if (response.tipStates.work_position) {
                    const wpData = response.tipStates.work_position;
                    console.log('Loading saved work position data:', wpData);
                    console.log('Setpoint value:', wpData.setpoint, 'Setpoint_mm value:', wpData.setpoint_mm);
                    
                    // Create a properly formatted work position update
                    // Handle both old format (position_mm/setpoint_mm) and new format (current_position/setpoint)
                    const formattedData = {
                        current_position: wpData.current_position || wpData.position_mm || 0,
                        setpoint: wpData.setpoint || wpData.setpoint_mm || 0,
                        speed_mode: wpData.speed_mode || 'rapid',
                        tip_distances: {},
                        tip_states: {}
                    };
                    
                    console.log('Formatted data for UI update:', formattedData);
                    
                    // Ensure all tip distances are present
                    for (let i = 1; i <= 8; i++) {
                        formattedData.tip_distances[i] = (wpData.tip_distances && wpData.tip_distances[i]) || 0;
                    }
                    
                    // Merge tip states from both sources
                    // First, get states from individual tip data
                    Object.entries(response.tipStates).forEach(([tipNumber, tipData]) => {
                        if (!isNaN(parseInt(tipNumber))) {
                            formattedData.tip_states[parseInt(tipNumber)] = tipData.active;
                        }
                    });
                    
                    // Don't override with work position tip states - use individual tip data only
                    
                    // Apply the work position update with a small delay to ensure UI is ready
                    setTimeout(() => {
                        console.log('Applying work position update after delay');
                        handleWorkPositionUpdate(formattedData);
                    }, 100);
                }
            }
        }).catch(error => {
            console.error('Error loading initial state:', error);
        });
    }
}

function cacheElements() {
    // Position displays
    elements.currentPositionText = document.getElementById('current-position-text');
    elements.setpointText = document.getElementById('setpoint-text');
    
    // Buttons
    elements.upButton = document.querySelector('.button-work-position-up');
    elements.downButton = document.querySelector('.button-work-position-down');
    elements.rapidSpeedButton = document.querySelector('.button-rapid-speed');
    elements.fineSpeedButton = document.querySelector('.button-fine-speed');
    elements.setWorkPositionButton = document.querySelector('.button-set-work-position');
    
    // Cache tip elements using IDs
    for (let i = 1; i <= 8; i++) {
        const container = document.getElementById(`tip-${i}-container`);
        elements.tipElements[i] = {
            container: container,
            led: null,
            text: null,
            sliderCircle: null,
            distanceText: null,
            slider: null
        };
        
        // Get child elements
        if (container) {
            elements.tipElements[i].led = container.querySelector('.tip-led-active, .tip-led-inactive');
            elements.tipElements[i].text = container.querySelector('.tip-text-active, .tip-led-text-in-active');
            elements.tipElements[i].slider = document.getElementById(`tip-${i}-slider`);
            elements.tipElements[i].sliderCircle = container.querySelector('.slider-circle-active, .slider-circle-in-active');
            elements.tipElements[i].distanceText = document.getElementById(`tip-${i}-distance-text`);
        }
    }
}

function setupIPCListeners() {
    console.log('Setting up IPC listeners for work position screen');
    
    // Listen for element updates
    window.addEventListener('update-element', (event) => {
        const data = event.detail;
        updateElement(data.elementId, data.text);
    });
    
    // Listen for work position updates
    window.addEventListener('work-position-update', (event) => {
        const data = event.detail;
        handleWorkPositionUpdate(data);
    });
    
    // Listen for speed button updates
    window.addEventListener('update-speed-buttons', (event) => {
        const data = event.detail;
        updateSpeedButtons(data.rapid_active, data.fine_active);
    });
    
    // Listen for button state updates
    window.addEventListener('update-button-state', (event) => {
        const data = event.detail;
        updateButtonState(data.button_id, data.pressed);
    });
    
    // Listen for slider position updates
    window.addEventListener('update-slider-position', (event) => {
        const data = event.detail;
        updateSliderPosition(data.slider_id, data.percentage);
    });
    
    // Listen for tip state updates
    window.addEventListener('update-tip-state', (event) => {
        const data = event.detail;
        updateTipState(data.tipNumber, data.isActive);
    });
    
    // Listen for tip state changes from heating screen
    window.addEventListener('tip-state-changed', (event) => {
        const { tipNumber, active } = event.detail;
        updateTipState(tipNumber, active);
    });
}

// Send work position commands to controller
function sendWorkPositionCommand(command) {
    if (window.electronAPI && window.electronAPI.sendMessage) {
        window.electronAPI.sendMessage('send_to_serial', command)
            .then(response => {
                console.log('Work position command sent:', command);
            })
            .catch(error => {
                console.error('Error sending work position command:', error);
            });
    }
}

// Send button state to controller
function sendButtonStateToController(button, pressed) {
    const command = {
        type: 'WPB', // Work Position Button
        button: button,
        pressed: pressed,
        speed_mode: buttonStates.speedMode,
        timestamp: Date.now()
    };
    
    const packet = `WPB:${JSON.stringify(command)}`;
    sendWorkPositionCommand(packet);
}

// Send speed mode to controller
function sendSpeedModeToController(mode) {
    const command = {
        type: 'WPS', // Work Position Speed
        speed_mode: mode,
        timestamp: Date.now()
    };
    
    const packet = `WPS:${JSON.stringify(command)}`;
    sendWorkPositionCommand(packet);
}

// Send set work position command
function sendSetWorkPositionCommand() {
    const command = {
        type: 'WPT', // Work Position seT
        timestamp: Date.now()
    };
    
    const packet = `WPT:${JSON.stringify(command)}`;
    sendWorkPositionCommand(packet);
}

function handleMessage(message) {
    switch (message.type) {
        case 'update_element':
            updateElement(message.element_id, message.text);
            break;
            
        case 'update_speed_buttons':
            updateSpeedButtons(message.rapid_active, message.fine_active);
            break;
            
        case 'update_button_state':
            updateButtonState(message.button_id, message.pressed);
            break;
            
        case 'update_slider_position':
            updateSliderPosition(message.slider_id, message.percentage);
            break;
            
        case 'update_tip_state':
            updateTipState(message.tip_number, message.active);
            break;
            
        case 'work_position_update':
            handleWorkPositionUpdate(message.data);
            break;
    }
}

function updateElement(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
    }
}

function updateSpeedButtons(rapidActive, fineActive) {
    if (elements.rapidSpeedButton && elements.fineSpeedButton) {
        // Update button colors based on selection
        if (rapidActive) {
            elements.rapidSpeedButton.style.backgroundColor = '#3474eb';
            elements.rapidSpeedButton.querySelector('.rapid-speed').style.color = 'white';
            elements.fineSpeedButton.style.backgroundColor = '';
            elements.fineSpeedButton.querySelector('.fine-speed').style.color = '';
        } else if (fineActive) {
            elements.fineSpeedButton.style.backgroundColor = '#3474eb';
            elements.fineSpeedButton.querySelector('.fine-speed').style.color = 'white';
            elements.rapidSpeedButton.style.backgroundColor = '';
            elements.rapidSpeedButton.querySelector('.rapid-speed').style.color = '';
        }
    }
}

function updateButtonState(buttonId, pressed) {
    let button = null;
    
    // Handle both formats: 'up-button' and 'up'
    if (buttonId === 'up-button' || buttonId === 'up') {
        button = elements.upButton;
    } else if (buttonId === 'down-button' || buttonId === 'down') {
        button = elements.downButton;
    }
    
    if (button) {
        if (pressed) {
            button.classList.add('pressed');
        } else {
            button.classList.remove('pressed');
        }
    }
}

function updateSliderPosition(sliderId, percentage) {
    // Extract tip number from slider ID (e.g., "tip-1-slider" -> 1)
    const match = sliderId.match(/tip-(\d+)-slider/);
    if (match) {
        const tipNumber = parseInt(match[1]);
        const tipElement = elements.tipElements[tipNumber];
        
        if (tipElement && tipElement.sliderCircle && tipElement.slider) {
            // Get actual slider dimensions
            const sliderRect = tipElement.slider.getBoundingClientRect();
            const circleRect = tipElement.sliderCircle.getBoundingClientRect();
            
            const sliderHeight = sliderRect.height || 378; // Fallback to CSS value
            const circleHeight = circleRect.height || 45; // Fallback to CSS value
            const maxTravel = sliderHeight - circleHeight;
            
            console.log(`Slider ${tipNumber}: height=${sliderHeight}, circle=${circleHeight}, percentage=${percentage}`);
            
            // Sliders should go UP when value increases
            // At 0%, circle should be at bottom (maxTravel from top)
            // At 100%, circle should be at top (0 from top)
            const position = maxTravel * (1 - percentage / 100);
            
            // Ensure position stays within bounds
            const clampedPosition = Math.max(0, Math.min(maxTravel, position));
            
            console.log(`Position calculation: ${position} -> clamped: ${clampedPosition}`);
            
            // Since the CSS already has bottom: 0px, we need to override it
            // For 0%, stay at bottom (0px)
            // For 100%, move to top (maxTravel px from bottom)
            const bottomPosition = (percentage / 100) * maxTravel;
            
            tipElement.sliderCircle.style.position = 'absolute';
            tipElement.sliderCircle.style.bottom = `${bottomPosition}px`;
            tipElement.sliderCircle.style.top = 'auto';
            tipElement.sliderCircle.style.left = '0px';
            tipElement.sliderCircle.style.transform = 'none';
            
            console.log(`Set bottom position to ${bottomPosition}px`);
        }
    }
}

function updateTipState(tipNumber, active) {
    const tipElement = elements.tipElements[tipNumber];
    if (!tipElement || !tipElement.container) return;
    
    if (active) {
        // Change to active state
        tipElement.container.className = 'tip-slider-active';
        
        if (tipElement.led) {
            tipElement.led.className = 'tip-led-active';
        }
        if (tipElement.text) {
            tipElement.text.className = 'tip-text-active';
            tipElement.text.textContent = `Tip ${tipNumber}`;
        }
        if (tipElement.slider) {
            tipElement.slider.className = 'distance-slider-active';
        }
        if (tipElement.sliderCircle) {
            tipElement.sliderCircle.className = 'slider-circle-active';
        }
        if (tipElement.distanceText) {
            tipElement.distanceText.parentElement.className = 'slider-text-bg-active';
            tipElement.distanceText.className = 'slider-text-active';
        }
    } else {
        // Change to inactive state
        tipElement.container.className = 'tip-slider-in-active';
        
        if (tipElement.led) {
            tipElement.led.className = 'tip-led-inactive';
        }
        if (tipElement.text) {
            tipElement.text.className = 'tip-led-text-in-active';
            tipElement.text.textContent = `Tip ${tipNumber}`;
        }
        if (tipElement.slider) {
            tipElement.slider.className = 'distance-slider-in-active';
        }
        if (tipElement.sliderCircle) {
            tipElement.sliderCircle.className = 'slider-circle-in-active';
        }
        if (tipElement.distanceText) {
            tipElement.distanceText.parentElement.className = 'slider-text-bg-active2';
            tipElement.distanceText.className = 'slider-text-inactive';
        }
    }
}

function handleWorkPositionUpdate(data) {
    console.log('Work position update received:', data);
    console.log('Current position element exists:', !!elements.currentPositionText);
    console.log('Setpoint element exists:', !!elements.setpointText);
    
    // Update all work position data at once
    if (data.current_position !== undefined) {
        console.log('Updating current position to:', data.current_position);
        const currentPosText = `${parseFloat(data.current_position).toFixed(1)} mm`;
        updateElement('current-position-text', currentPosText);
        console.log('Updated current position element to:', currentPosText);
    }
    if (data.setpoint !== undefined) {
        console.log('Updating setpoint to:', data.setpoint);
        const setpointText = `${parseFloat(data.setpoint).toFixed(1)} mm`;
        updateElement('setpoint-text', setpointText);
        console.log('Updated setpoint element to:', setpointText);
    }
    if (data.speed_mode !== undefined) {
        updateSpeedButtons(data.speed_mode === 'rapid', data.speed_mode === 'fine');
    }
    
    // Update tip distances
    if (data.tip_distances) {
        console.log('Updating tip distances:', data.tip_distances);
        for (let i = 1; i <= 8; i++) {
            if (data.tip_distances[i] !== undefined) {
                updateElement(`tip-${i}-distance-text`, `${data.tip_distances[i].toFixed(1)} mm`);
                const percentage = (data.tip_distances[i] / 8.0) * 100;
                updateSliderPosition(`tip-${i}-slider`, percentage);
            }
        }
    }
    
    // Update tip states - only update if changed to prevent flashing
    if (data.tip_states) {
        console.log('Updating tip states:', data.tip_states);
        for (let i = 1; i <= 8; i++) {
            if (data.tip_states[i] !== undefined) {
                const tipElement = elements.tipElements[i];
                if (tipElement && tipElement.container) {
                    // Check current state to avoid unnecessary updates
                    const isCurrentlyActive = tipElement.container.className === 'tip-slider-active';
                    const shouldBeActive = data.tip_states[i];
                    
                    if (isCurrentlyActive !== shouldBeActive) {
                        console.log(`Setting tip ${i} to ${shouldBeActive ? 'active' : 'inactive'}`);
                        updateTipState(i, shouldBeActive);
                    }
                }
            }
        }
    }
}

function setupEventHandlers() {
    console.log('Setting up event handlers');
    
    // Speed button handlers
    if (elements.rapidSpeedButton) {
        console.log('Adding rapid speed button handler');
        elements.rapidSpeedButton.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Rapid speed button clicked');
            
            // Update UI immediately for responsiveness
            updateSpeedButtons(true, false);
            
            // Update state and send to controller
            buttonStates.speedMode = 'rapid';
            sendSpeedModeToController('rapid');
            
            // Save speed mode to JSON
            if (window.electronAPI && window.electronAPI.sendMessage) {
                window.electronAPI.sendMessage('save_work_position_speed', { speed_mode: 'rapid' });
            }
        });
    }
    
    if (elements.fineSpeedButton) {
        console.log('Adding fine speed button handler');
        elements.fineSpeedButton.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Fine speed button clicked');
            
            // Update UI immediately for responsiveness
            updateSpeedButtons(false, true);
            
            // Update state and send to controller
            buttonStates.speedMode = 'fine';
            sendSpeedModeToController('fine');
            
            // Save speed mode to JSON
            if (window.electronAPI && window.electronAPI.sendMessage) {
                window.electronAPI.sendMessage('save_work_position_speed', { speed_mode: 'fine' });
            }
        });
    }
    
    // Up/Down button handlers (momentary push buttons)
    if (elements.upButton) {
        elements.upButton.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (!buttonStates.up) {
                console.log('Up button pressed');
                buttonStates.up = true;
                elements.upButton.classList.add('pressed');
                sendButtonState('up', true);
            }
        });
        
        elements.upButton.addEventListener('mouseup', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (buttonStates.up) {
                console.log('Up button released');
                releaseButton('up');
            }
        });
        
        elements.upButton.addEventListener('mouseleave', function(e) {
            e.preventDefault();
            
            if (buttonStates.up) {
                console.log('Up button mouse leave - releasing');
                releaseButton('up');
            }
        });
        
        // Handle touch events for mobile compatibility
        elements.upButton.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (!buttonStates.up) {
                buttonStates.up = true;
                elements.upButton.classList.add('pressed');
                sendButtonState('up', true);
            }
        });
        
        elements.upButton.addEventListener('touchend', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (buttonStates.up) {
                releaseButton('up');
            }
        });
        
        // Prevent context menu
        elements.upButton.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
    }
    
    if (elements.downButton) {
        elements.downButton.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (!buttonStates.down) {
                console.log('Down button pressed');
                buttonStates.down = true;
                elements.downButton.classList.add('pressed');
                sendButtonState('down', true);
            }
        });
        
        elements.downButton.addEventListener('mouseup', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (buttonStates.down) {
                console.log('Down button released');
                releaseButton('down');
            }
        });
        
        elements.downButton.addEventListener('mouseleave', function(e) {
            e.preventDefault();
            
            if (buttonStates.down) {
                console.log('Down button mouse leave - releasing');
                releaseButton('down');
            }
        });
        
        // Handle touch events for mobile compatibility
        elements.downButton.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (!buttonStates.down) {
                buttonStates.down = true;
                elements.downButton.classList.add('pressed');
                sendButtonState('down', true);
            }
        });
        
        elements.downButton.addEventListener('touchend', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (buttonStates.down) {
                releaseButton('down');
            }
        });
        
        // Prevent context menu
        elements.downButton.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
    }
    
    // Set work position button handler
    if (elements.setWorkPositionButton) {
        elements.setWorkPositionButton.addEventListener('click', function() {
            showConfirmOverlay();
        });
    }
}



// Confirmation overlay logic
function showConfirmOverlay() {
    const overlay = document.getElementById('confirm-overlay');
    const bodyText = document.getElementById('confirm-body-text');
    const currentText = (elements.currentPositionText && elements.currentPositionText.textContent) || '0 mm';
    const setpointText = (elements.setpointText && elements.setpointText.textContent) || '0 mm';
    if (bodyText) {
        bodyText.innerHTML = `Current position is ${currentText}.<br/>If you want to set this as your work position tap "Confirm."<br/>If you want to cancel it tap "Dismiss".`;
    }
    if (!overlay) return;
    overlay.style.display = 'block';

    const confirmBtn = document.getElementById('btn-confirm');
    const dismissBtn = document.getElementById('btn-dismiss');

    const onDismiss = () => {
        hideConfirmOverlay();
        cleanup();
    };

    const onConfirm = async () => {
        // Parse current position value
        const parseMm = (t) => {
            if (!t) return 0;
            const n = parseFloat(String(t).replace('mm', '').trim());
            return isNaN(n) ? 0 : n;
        };
        const currentPositionMm = parseMm(currentText);

        // 1) Save current position as the new work position setpoint
        if (window.electronAPI && window.electronAPI.sendMessage) {
            try {
                // Save to JSON with current position as both position and setpoint
                await window.electronAPI.sendMessage('save_work_position_json', { 
                    positionMm: currentPositionMm, 
                    setpointMm: currentPositionMm 
                });
                
                // Update the UI to reflect the new setpoint
                updateElement('setpoint-text', `${currentPositionMm.toFixed(1)} mm`);
            } catch (e) {
                console.error('Failed saving work position JSON:', e);
            }
        }

        // 2) Send updated work position to controller
        const command = {
            type: 'WPU', // Work Position Update
            setpoint: currentPositionMm,
            timestamp: Date.now()
        };
        
        const packet = `WPU:${JSON.stringify(command)}`;
        sendWorkPositionCommand(packet);

        hideConfirmOverlay();
        cleanup();
    };

    const cleanup = () => {
        if (confirmBtn) confirmBtn.removeEventListener('click', onConfirm);
        if (dismissBtn) dismissBtn.removeEventListener('click', onDismiss);
    };

    if (confirmBtn) confirmBtn.addEventListener('click', onConfirm);
    if (dismissBtn) dismissBtn.addEventListener('click', onDismiss);
}

function hideConfirmOverlay() {
    const overlay = document.getElementById('confirm-overlay');
    if (overlay) overlay.style.display = 'none';
}

// Button state management helpers
function sendButtonState(button, state) {
    // Track what we're sending
    if (button === 'up') {
        buttonStates.lastSentUp = state;
    } else if (button === 'down') {
        buttonStates.lastSentDown = state;
    }
    
    // Send button state to controller
    sendButtonStateToController(button, state);
    
    // Handle continuous sending for pressed state
    if (state) {
        // Start watchdog timer for button press
        startButtonWatchdog(button);
        
        // Clear any existing interval
        if (buttonStates.continuousSendIntervals[button]) {
            clearInterval(buttonStates.continuousSendIntervals[button]);
        }
        
        // Start continuous sending every 250ms (slightly slower to avoid overwhelming serial)
        buttonStates.continuousSendIntervals[button] = setInterval(() => {
            if (buttonStates[button]) {
                console.log(`Continuous send for ${button} button`);
                sendButtonStateToController(button, true);
            } else {
                // Stop if button is no longer pressed
                clearInterval(buttonStates.continuousSendIntervals[button]);
                buttonStates.continuousSendIntervals[button] = null;
            }
        }, 250);
    } else {
        // Clear watchdog and continuous send interval
        clearButtonWatchdog(button);
        
        if (buttonStates.continuousSendIntervals[button]) {
            clearInterval(buttonStates.continuousSendIntervals[button]);
            buttonStates.continuousSendIntervals[button] = null;
        }
    }
}

function startButtonWatchdog(button) {
    // Clear any existing timer
    clearButtonWatchdog(button);
    
    // Set watchdog to auto-release after 5 seconds (safety measure)
    buttonStates.watchdogTimers[button] = setTimeout(() => {
        console.warn(`Watchdog: Auto-releasing stuck ${button} button`);
        releaseButton(button);
    }, 5000);
}

function clearButtonWatchdog(button) {
    if (buttonStates.watchdogTimers[button]) {
        clearTimeout(buttonStates.watchdogTimers[button]);
        buttonStates.watchdogTimers[button] = null;
    }
}

function releaseButton(button) {
    // Force release the button
    buttonStates[button] = false;
    
    // Update UI
    if (button === 'up' && elements.upButton) {
        elements.upButton.classList.remove('pressed');
    } else if (button === 'down' && elements.downButton) {
        elements.downButton.classList.remove('pressed');
    }
    
    // Send release message (with retry)
    sendButtonStateWithRetry(button, false);
}

async function sendButtonStateWithRetry(button, state, retries = 3) {
    for (let i = 0; i < retries; i++) {
        sendButtonState(button, state);
        
        // For release events, send multiple times to ensure delivery
        if (!state && i < retries - 1) {
            await new Promise(resolve => setTimeout(resolve, 50));
        }
    }
}

// Export for external use if needed
window.WorkPositionController = {
    updateElement,
    updateSpeedButtons,
    updateButtonState,
    updateSliderPosition,
    updateTipState,
    handleWorkPositionUpdate,
    sendWorkPositionCommand
};