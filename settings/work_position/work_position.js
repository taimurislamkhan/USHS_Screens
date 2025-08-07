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
    }
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
    
    // Set up periodic state sync to prevent stuck states
    setInterval(function() {
        // Only request state if we're not actively pressing buttons
        const upPressed = elements.upButton && elements.upButton.classList.contains('pressed');
        const downPressed = elements.downButton && elements.downButton.classList.contains('pressed');
        
        if (!upPressed && !downPressed) {
            requestInitialState();
        }
    }, 2000); // Sync every 2 seconds
    
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
    // Send a message to request current state
    sendMessage({
        type: 'request_work_position_state'
    });
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
    
    // Update all work position data at once
    if (data.current_position !== undefined) {
        updateElement('current-position-text', `${data.current_position.toFixed(1)} mm`);
    }
    if (data.setpoint !== undefined) {
        updateElement('setpoint-text', `${data.setpoint.toFixed(1)} mm`);
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
    
    // Update tip states
    if (data.tip_states) {
        console.log('Updating tip states:', data.tip_states);
        for (let i = 1; i <= 8; i++) {
            if (data.tip_states[i] !== undefined) {
                console.log(`Setting tip ${i} to ${data.tip_states[i] ? 'active' : 'inactive'}`);
                updateTipState(i, data.tip_states[i]);
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
            
            // Send message multiple times to ensure delivery
            for (let i = 0; i < 2; i++) {
                sendMessage({
                    type: 'set_speed_mode',
                    mode: 'rapid'
                });
                if (i < 1) {
                    await new Promise(resolve => setTimeout(resolve, 20));
                }
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
            
            // Send message multiple times to ensure delivery
            for (let i = 0; i < 2; i++) {
                sendMessage({
                    type: 'set_speed_mode',
                    mode: 'fine'
                });
                if (i < 1) {
                    await new Promise(resolve => setTimeout(resolve, 20));
                }
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
            sendMessage({
                type: 'set_work_position'
            });
        });
    }
}

function sendMessage(message) {
    // Send message to main process via IPC
    if (window.electronAPI && window.electronAPI.sendToPython) {
        window.electronAPI.sendToPython(message);
    } else {
        console.warn('IPC not available');
    }
}

// Button state management helpers
function sendButtonState(button, state) {
    // Track what we're sending
    if (button === 'up') {
        buttonStates.lastSentUp = state;
    } else if (button === 'down') {
        buttonStates.lastSentDown = state;
    }
    
    // Send the message
    sendMessage({
        type: 'button_press',
        button: button,
        state: state
    });
    
    // Start watchdog timer for button press
    if (state) {
        startButtonWatchdog(button);
    } else {
        clearButtonWatchdog(button);
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
    sendMessage
};