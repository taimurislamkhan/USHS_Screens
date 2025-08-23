const { SerialPort } = require('serialport');
const { ReadlineParser } = require('@serialport/parser-readline');
const EventEmitter = require('events');

class SerialHandler extends EventEmitter {
  constructor() {
    super();
    this.port = null;
    this.parser = null;
    this.isConnected = false;
    this.autoReconnect = true;
    this.reconnectInterval = null;
    this.portPath = null;
  }

  async listPorts() {
    try {
      const ports = await SerialPort.list();
      // Add virtual ports if they exist
      const virtualPorts = ['/tmp/ttyV0', '/tmp/ttyV1'];
      
      const portList = ports.map(port => ({
        path: port.path,
        manufacturer: port.manufacturer || 'Unknown',
        serialNumber: port.serialNumber || 'Unknown'
      }));

      // Check if virtual ports exist and add them
      for (const vPort of virtualPorts) {
        try {
          // Try to check if the port exists
          const exists = require('fs').existsSync(vPort);
          if (exists) {
            portList.push({
              path: vPort,
              manufacturer: 'Virtual',
              serialNumber: 'Virtual Serial Port'
            });
          }
        } catch (e) {
          // Ignore errors
        }
      }

      return portList;
    } catch (error) {
      console.error('Error listing ports:', error);
      return [];
    }
  }

  connect(path, baudRate = 9600) {
    return new Promise((resolve, reject) => {
      if (this.isConnected) {
        this.disconnect();
      }

      this.portPath = path;

      try {
        this.port = new SerialPort({
          path: path,
          baudRate: baudRate,
          autoOpen: false
        });

        this.parser = this.port.pipe(new ReadlineParser({ delimiter: '\n' }));

        // Set up event handlers
        this.port.on('open', () => {
          console.log(`Serial port ${path} opened`);
          this.isConnected = true;
          this.emit('connected', path);
          
          // Clear any reconnect interval
          if (this.reconnectInterval) {
            clearInterval(this.reconnectInterval);
            this.reconnectInterval = null;
          }
          
          resolve();
        });

        this.port.on('error', (err) => {
          console.error('Serial port error:', err);
          this.emit('error', err);
          this.handleDisconnection();
          reject(err);
        });

        this.port.on('close', () => {
          console.log('Serial port closed');
          this.handleDisconnection();
        });

        this.parser.on('data', (data) => {
          this.handleData(data);
        });

        // Open the port
        this.port.open();

      } catch (error) {
        console.error('Error creating serial port:', error);
        reject(error);
      }
    });
  }

  disconnect() {
    this.autoReconnect = false;
    
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }

    if (this.port && this.port.isOpen) {
      this.port.close((err) => {
        if (err) {
          console.error('Error closing port:', err);
        }
      });
    }

    this.isConnected = false;
    this.emit('disconnected');
  }

  handleDisconnection() {
    this.isConnected = false;
    this.emit('disconnected');

    // Set up auto-reconnect if enabled
    if (this.autoReconnect && this.portPath && !this.reconnectInterval) {
      console.log('Setting up auto-reconnect...');
      this.reconnectInterval = setInterval(() => {
        if (!this.isConnected) {
          console.log('Attempting to reconnect...');
          this.connect(this.portPath).catch(err => {
            console.log('Reconnect failed:', err.message);
          });
        }
      }, 5000); // Try every 5 seconds
    }
  }

  handleData(data) {
    console.log('Serial data received:', data); // Debug log
    try {
      // Parse the packet
      const colonIndex = data.indexOf(':');
      
      if (colonIndex !== -1) {
        const command = data.substring(0, colonIndex);
        const value = data.substring(colonIndex + 1).trim();
        
        switch (command) {
          case 'CP': // Cycle Progress (legacy)
            const stateIndex = parseInt(value);
            console.log('Cycle progress command received, state:', stateIndex); // Debug log
            this.emit('cycleProgress', stateIndex);
            break;
            
          case 'TD': // Tip Data (new format)
            try {
              const tipData = JSON.parse(value);
              console.log('Tip data command received:', tipData); // Debug log
              console.log('Number of tips:', tipData.tips ? tipData.tips.length : 0);
              
              // Emit cycle progress from tip data
              if (tipData.cycle_progress !== undefined) {
                console.log('Emitting cycle progress:', tipData.cycle_progress);
                this.emit('cycleProgress', tipData.cycle_progress);
              }
              
              // Emit tip data
              if (tipData.tips) {
                console.log('Emitting tip data for', tipData.tips.length, 'tips');
                this.emit('tipData', tipData.tips);
              }
              
              // Emit home screen data
              if (tipData.home_screen) {
                console.log('Emitting home screen data:', tipData.home_screen);
                this.emit('homeScreenData', tipData.home_screen);
              }
            } catch (jsonError) {
              console.error('Error parsing TD JSON:', jsonError);
              console.error('Raw value was:', value);
            }
            break;
            
          case 'WP': // Work Position data from controller
            try {
              const wpData = JSON.parse(value);
              console.log('Work position data received:', wpData);
              this.emit('workPositionData', wpData);
            } catch (jsonError) {
              console.error('Error parsing WP JSON:', jsonError);
              console.error('Raw value was:', value);
            }
            break;
            
          // Add more commands here as needed
          default:
            console.log('Unknown command:', command);
        }
      }
    } catch (error) {
      console.error('Error parsing data:', error);
    }
  }

  send(data) {
    if (this.port && this.port.isOpen) {
      this.port.write(data + '\n', (err) => {
        if (err) {
          console.error('Error writing to serial port:', err);
          this.emit('error', err);
        }
      });
    } else {
      console.error('Serial port is not open');
    }
  }

  setAutoReconnect(enabled) {
    this.autoReconnect = enabled;
    
    if (!enabled && this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }
  }
}

module.exports = SerialHandler;
