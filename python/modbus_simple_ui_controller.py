#!/usr/bin/env python3
"""
Modbus-enabled Simple UI Controller for USHS
============================================

This extends the simple UI controller to read values from a Modbus slave
instead of using internal values.
"""

import asyncio
import websockets
import json
import time
from datetime import datetime
from pymodbus.client import AsyncModbusSerialClient
from pymodbus.transaction import ModbusRtuFramer

from modbus_map import *
import websockets.exceptions
import os

class ModbusSimpleUSHSController:
    def __init__(self, serial_port='/tmp/vserial1', baudrate=1000000, slave_id=1):
        """Initialize the Modbus UI controller"""
        self.websocket = None
        self.connected = False
        
        # Modbus configuration
        self.serial_config = {
            'port': serial_port,
            'baudrate': baudrate,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1,
            'timeout': 1
        }
        self.slave_id = slave_id
        self.modbus_client = None
        
        # Update rate
        self.update_interval = 0.02  # 20ms (50Hz) for maximum responsiveness
        
        # Cache for previous values to detect changes
        self.previous_values = {}
        
        # Button state tracking for immediate writes
        self.button_write_queue = asyncio.Queue()
        self.last_button_states = {
            'up': False,
            'down': False,
            'speed_mode': 0
        }

        # Manual controls cache
        self.manual_heating_buttons = {i: False for i in range(1, 9)}
        self.manual_cooling_on = False
        self.manual_platen_mm = 0.0
        
        # Initialize all properties with default values
        self._initialize_properties()
        
        # Load tip states from JSON file
        self._load_tip_states_from_json()
        
        # Heartbeat counter for periodic sync
        self.heartbeat_counter = 0
        self.heartbeat_interval = 100  # Every 100 cycles (2 seconds at 50Hz)
        
    def _load_tip_states_from_json(self):
        """Load tip active states from tip_states.json"""
        try:
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tip_states.json')
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    tip_states = json.load(f)
                    for i in range(1, 9):
                        if str(i) in tip_states:
                            setattr(self, f'tip{i}_active', tip_states[str(i)].get('active', False))
                            print(f"Loaded tip {i} active state: {tip_states[str(i)].get('active', False)}")
            else:
                print("tip_states.json not found, using defaults")
        except Exception as e:
            print(f"Error loading tip states from JSON: {e}")
    
    async def write_initial_tip_states(self):
        """Write initial tip active states from JSON to Modbus slave"""
        if not self.modbus_client:
            return
            
        try:
            print("Writing initial tip active states to Modbus slave...")
            for i in range(1, 9):
                addr = get_tip_address(i, 'active')
                active_state = getattr(self, f'tip{i}_active', False)
                value = 1 if active_state else 0
                
                result = await self.modbus_client.write_register(addr, value, slave=self.slave_id)
                if result.isError():
                    print(f"Error writing initial tip {i} active state to Modbus: {result}")
                else:
                    print(f"Successfully wrote initial tip {i} active state {value} to Modbus address {addr}")
                    
        except Exception as e:
            print(f"Error writing initial tip states to Modbus: {e}")
    
    async def _heartbeat_sync_tip_states(self):
        """Periodically sync all tip active states to ensure reliability"""
        if not self.modbus_client:
            return
            
        try:
            # Write all tip active states as a heartbeat sync
            for i in range(1, 9):
                addr = get_tip_address(i, 'active')
                active_state = getattr(self, f'tip{i}_active', False)
                value = 1 if active_state else 0
                
                result = await self.modbus_client.write_register(addr, value, slave=self.slave_id)
                if result.isError():
                    print(f"Heartbeat sync error for tip {i}: {result}")
                    
            print("Heartbeat sync of tip active states completed")
        except Exception as e:
            print(f"Error in heartbeat sync: {e}")
        
    def _initialize_properties(self):
        """Initialize all UI properties"""
        # Tips (1-8)
        for i in range(1, 9):
            setattr(self, f'tip{i}_active', False)
            setattr(self, f'tip{i}_progress', 0)
            setattr(self, f'tip{i}_joules', 0.0)
            setattr(self, f'tip{i}_distance', 0.0)
            
        # Progress states
        self.progress_home = 'inactive'
        self.progress_work_position = 'inactive'
        self.progress_encoder_zero = 'inactive'
        self.progress_heat = 'inactive'
        self.progress_cool = 'inactive'
        self.progress_cycle_complete = 'inactive'
        
        # General UI
        self.time_minutes = 1
        self.time_seconds = 46
        self.slider_percentage = 0
        
        # Text strings
        self.banner_text = "System Is Ready"
        self.processing_text = "Processing..."
        self.progress_text = "Processing..."  # For home-cycle-progress-text
        
        # Work position data
        self.current_position = 0.0
        self.setpoint = 0.0
        self.speed_mode = 0  # 0=rapid, 1=fine
        self.up_button_state = False
        self.down_button_state = False
        
        # Work position tip distances (1-8)
        self.work_tip_distances = {i: 0.0 for i in range(1, 9)}
        
        # Heating setpoints (1-8)
        self.heating_energy_setpoints = {i: 0.0 for i in range(1, 9)}
        self.heating_distance_setpoints = {i: 0.0 for i in range(1, 9)}
        self.heating_heat_start_delay_setpoints = {i: 0.0 for i in range(1, 9)}

        # Monitor screen states
        self.monitor_left_start = False
        self.monitor_right_start = False
        self.monitor_estop_active = False
        self.monitor_home_switch = False
        self.monitor_pressure_ok = False
        self.monitor_pressure_psi = 0
        
    async def connect_modbus(self):
        """Connect to Modbus slave"""
        try:
            self.modbus_client = AsyncModbusSerialClient(
                **self.serial_config,
                framer=ModbusRtuFramer
            )
            
            connected = await self.modbus_client.connect()
            if connected:
                print(f"✅ Connected to Modbus slave on {self.serial_config['port']}")
                print(f"🔗 Using slave ID: {self.slave_id}")
                
                # Test write to verify connection
                test_addr = get_heating_energy_address(1)  # Should be 1500
                test_high, test_low = float_to_registers(99.9, scale=10)
                print(f"🧪 Test write to addr {test_addr}: high={test_high}, low={test_low}")
                test_result = await self.modbus_client.write_registers(test_addr, [test_high, test_low], slave=self.slave_id)
                if test_result.isError():
                    print(f"❌ Test write failed: {test_result}")
                else:
                    print(f"✅ Test write successful!")
                
                # Write initial tip active states from JSON to Modbus slave
                await self.write_initial_tip_states()
                
                return True
            else:
                print(f"❌ Failed to connect to Modbus slave on {self.serial_config['port']}")
                return False
                
        except Exception as e:
            print(f"Modbus connection error: {e}")
            return False
            
    async def disconnect_modbus(self):
        """Disconnect from Modbus slave"""
        if self.modbus_client:
            self.modbus_client.close()
            print("Disconnected from Modbus slave")
            
    async def read_modbus_data(self):
        """Read all data from Modbus slave"""
        if not self.modbus_client:
            return False
            
        try:
            # Read tips data
            for i in range(1, 9):
                base_addr = TIP_BASE_ADDRESSES[i]
                
                # Read 4 registers for each tip (progress, joules, distance[2])
                # NOTE: Active state is NOT read from Modbus - it comes from JSON file
                # Skip the active register at offset 0, start from offset 1 (progress)
                result = await self.modbus_client.read_holding_registers(
                    base_addr + 1, 4, slave=self.slave_id
                )
                
                if not result.isError():
                    # Parse tip data (skipping active state)
                    # DO NOT set tip active state from Modbus
                    setattr(self, f'tip{i}_progress', result.registers[0])  # Progress
                    setattr(self, f'tip{i}_joules', result.registers[1] / 10.0)  # Joules
                    
                    # Distance is 32-bit (2 registers)
                    distance = registers_to_float([result.registers[2], result.registers[3]], 1000)
                    setattr(self, f'tip{i}_distance', distance)
                    
            # Read progress states
            result = await self.modbus_client.read_holding_registers(
                PROGRESS_STATES['home'], 6, slave=self.slave_id
            )
            
            if not result.isError():
                state_map = {0: 'inactive', 1: 'active', 2: 'done'}
                self.progress_home = state_map.get(result.registers[0], 'inactive')
                self.progress_work_position = state_map.get(result.registers[1], 'inactive')
                self.progress_encoder_zero = state_map.get(result.registers[2], 'inactive')
                self.progress_heat = state_map.get(result.registers[3], 'inactive')
                self.progress_cool = state_map.get(result.registers[4], 'inactive')
                self.progress_cycle_complete = state_map.get(result.registers[5], 'inactive')
                
            # Read general UI
            result = await self.modbus_client.read_holding_registers(
                GENERAL_UI['time_minutes'], 3, slave=self.slave_id
            )
            
            if not result.isError():
                self.time_minutes = result.registers[0]
                self.time_seconds = result.registers[1]
                self.slider_percentage = result.registers[2]
                
            # Read banner text
            result = await self.modbus_client.read_holding_registers(
                TEXT_STRINGS['banner_text'], 20, slave=self.slave_id
            )
            
            if not result.isError():
                text = registers_to_string(result.registers)
                if text.strip():  # Only update if not empty
                    self.banner_text = text
                
            # Read processing text
            result = await self.modbus_client.read_holding_registers(
                TEXT_STRINGS['processing_text'], 20, slave=self.slave_id
            )
            
            if not result.isError():
                text = registers_to_string(result.registers)
                if text.strip():  # Only update if not empty
                    self.processing_text = text
            
            # Read work position data
            result = await self.modbus_client.read_holding_registers(
                WORK_POSITION['current_position'], 8, slave=self.slave_id
            )
            
            if not result.isError():
                # Current position (2 registers, 32-bit)
                self.current_position = registers_to_float([result.registers[0], result.registers[1]], 100)
                
                # Setpoint (2 registers, 32-bit)
                self.setpoint = registers_to_float([result.registers[2], result.registers[3]], 100)
                
                # Speed mode (1 register)
                self.speed_mode = result.registers[4]
                
                # Button states (1 register each)
                self.up_button_state = bool(result.registers[5])
                self.down_button_state = bool(result.registers[6])
            
            # Read work position tip distances
            result = await self.modbus_client.read_holding_registers(
                WORK_POSITION_TIP_BASE, 16, slave=self.slave_id  # 8 tips * 2 registers each
            )
            
            if not result.isError():
                for i in range(1, 9):
                    base_idx = (i - 1) * 2
                    distance = registers_to_float(
                        [result.registers[base_idx], result.registers[base_idx + 1]], 100
                    )
                    self.work_tip_distances[i] = distance
                    
            # Read heating energy setpoints
            result = await self.modbus_client.read_holding_registers(
                HEATING_ENERGY_BASE, 16, slave=self.slave_id  # 8 tips * 2 registers each
            )
            
            if not result.isError():
                for i in range(1, 9):
                    base_idx = (i - 1) * 2
                    energy = registers_to_float(
                        [result.registers[base_idx], result.registers[base_idx + 1]], 10
                    )
                    self.heating_energy_setpoints[i] = energy
                    
            # Read heating distance setpoints
            result = await self.modbus_client.read_holding_registers(
                HEATING_DISTANCE_BASE, 16, slave=self.slave_id  # 8 tips * 2 registers each
            )
            
            if not result.isError():
                for i in range(1, 9):
                    base_idx = (i - 1) * 2
                    distance = registers_to_float(
                        [result.registers[base_idx], result.registers[base_idx + 1]], 1000
                    )
                    self.heating_distance_setpoints[i] = distance
            
            # Read heating heat start delay setpoints
            result = await self.modbus_client.read_holding_registers(
                HEATING_HEAT_START_DELAY_BASE, 16, slave=self.slave_id  # 8 tips * 2 registers each
            )
            
            if not result.isError():
                for i in range(1, 9):
                    base_idx = (i - 1) * 2
                    heat_start_delay = registers_to_float(
                        [result.registers[base_idx], result.registers[base_idx + 1]], 1000
                    )
                    self.heating_heat_start_delay_setpoints[i] = heat_start_delay

            # Read monitor screen registers
            try:
                result = await self.modbus_client.read_holding_registers(
                    get_monitor_address('pressure_psi'), 6, slave=self.slave_id
                )
                if not result.isError():
                    self.monitor_pressure_psi = int(result.registers[0])
                    self.monitor_left_start = bool(result.registers[1])
                    self.monitor_right_start = bool(result.registers[2])
                    self.monitor_estop_active = bool(result.registers[3])
                    self.monitor_home_switch = bool(result.registers[4])
                    self.monitor_pressure_ok = bool(result.registers[5])
            except Exception as e:
                # Non-fatal; continue loop
                pass

            # Note: manual controls (heating/cooling button states) are write-only from UI.
            # We do not read them back to avoid overriding the UI's source of truth.
            # Platen mm is already read earlier from WORK_POSITION current_position.
                
            return True
            
        except Exception as e:
            print(f"Error reading Modbus data: {e}")
            return False
            
    async def connect(self, uri="ws://localhost:8080"):
        """Connect to the Electron app via WebSocket"""
        try:
            self.websocket = await websockets.connect(uri)
            self.connected = True
            print(f"Connected to WebSocket at {uri}")
            
            # Also connect to Modbus
            await self.connect_modbus()
            
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            return False
            
    async def disconnect(self):
        """Disconnect from WebSocket and Modbus"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print("Disconnected from WebSocket")
            
        await self.disconnect_modbus()
            
    async def _send_message(self, message_type, **data):
        """Send a message to the Electron app"""
        if not self.connected or not self.websocket:
            return False
            
        message = {
            "type": message_type,
            **data
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            self.connected = False
            return False
            
    def _has_value_changed(self, key, value):
        """Check if a value has changed since last update"""
        if key not in self.previous_values:
            self.previous_values[key] = value
            return True
            
        if self.previous_values[key] != value:
            self.previous_values[key] = value
            return True
            
        return False
        
    async def send_all_current_values(self):
        """Send all current values to the UI (used on page load/reconnect)"""
        # Send critical visible elements first
        
        # 1. Send progress states first (most visible)
        progress_states = {
            'home': self.progress_home,
            'work_position': self.progress_work_position,
            'encoder_zero': self.progress_encoder_zero,
            'heat': self.progress_heat,
            'cool': self.progress_cool,
            'cycle_complete': self.progress_cycle_complete
        }
        await self._send_message("update_progress_states", states=progress_states)
        
        # 2. Send text elements first (most visible)
        await self._send_message("update_element", 
                               element_id="home-cycle-progress-text", 
                               property="textContent", 
                               value=self.processing_text)
        
        await self._send_message("update_element", 
                               element_id="home-text-percent", 
                               property="textContent", 
                               value=f"{self.slider_percentage}%")
        
        await self._send_message("update_element", 
                               element_id="home-text-time", 
                               property="textContent", 
                               value=f"∼{self.time_minutes}m {self.time_seconds:02d}sec")
        
        await self._send_message("update_element", 
                               element_id="home-banner-text", 
                               property="textContent", 
                               value=self.banner_text)
        
        # 3. Send tip states
        for i in range(1, 9):
            await self._send_message("update_tip_state", 
                                   tip_number=i, 
                                   is_active=getattr(self, f'tip{i}_active'))
            
            # Send progress
            progress_key = f'tip{i}_progress'
            if i <= 4:
                element_id = f"tip-{i}-progress-{'active' if getattr(self, f'tip{i}_active') else 'in-active'}"
            else:
                element_id = f"tip-{i}-progress-in-active"
            await self._send_message("update_progress_bar", 
                                   element_id=element_id, 
                                   progress=getattr(self, progress_key))
            
            # Send joules - with correct element IDs
            joules_text = f"{getattr(self, f'tip{i}_joules'):.1f} J"
            if i <= 4:
                # For tips 1-4, always use -active
                joules_element_id = f"tip-{i}-joules-active"
            else:
                # For tips 5-8, always use -in-active
                joules_element_id = f"tip-{i}-joules-in-active"
                
            await self._send_message("update_element", 
                                   element_id=joules_element_id, 
                                   property="textContent", 
                                   value=joules_text)
            
            # Send distance - with correct element IDs
            distance_text = f"{getattr(self, f'tip{i}_distance'):.1f} mm"
            if i <= 4:
                # For tips 1-4, always use -active
                distance_element_id = f"tip-{i}-distance-active"
            else:
                # For tips 5-8, always use -in-active
                distance_element_id = f"tip-{i}-distance-in-active"
                
            await self._send_message("update_element", 
                                   element_id=distance_element_id, 
                                   property="textContent", 
                                   value=distance_text)
        
    async def update_changed_values(self):
        """Update only values that have changed"""
        # Update tips
        for i in range(1, 9):
            # Check active state
            active_key = f'tip{i}_active'
            if self._has_value_changed(active_key, getattr(self, active_key)):
                await self._send_message("update_tip_state", 
                                       tip_number=i, 
                                       is_active=getattr(self, active_key))
                
                # Also write to Modbus continuously for reliability
                if self.modbus_client:
                    try:
                        addr = get_tip_address(i, 'active')
                        value = 1 if getattr(self, active_key) else 0
                        result = await self.modbus_client.write_register(addr, value, slave=self.slave_id)
                        if result.isError():
                            print(f"Error writing tip {i} active state to Modbus: {result}")
                        else:
                            print(f"Continuously wrote tip {i} active state {value} to Modbus")
                    except Exception as e:
                        print(f"Error in continuous tip {i} active write: {e}")
                
            # Check progress
            progress_key = f'tip{i}_progress'
            if self._has_value_changed(progress_key, getattr(self, progress_key)):
                # For tips 5-8, always use "in-active" in the element ID
                if i <= 4:
                    element_id = f"tip-{i}-progress-{'active' if getattr(self, f'tip{i}_active') else 'in-active'}"
                else:
                    element_id = f"tip-{i}-progress-in-active"
                await self._send_message("update_progress_bar", 
                                       element_id=element_id, 
                                       progress=getattr(self, progress_key))
                
            # Check joules
            joules_key = f'tip{i}_joules'
            if self._has_value_changed(joules_key, getattr(self, joules_key)):
                joules_text = f"{getattr(self, joules_key):.1f} J"
                if i <= 4:
                    # For tips 1-4, always use -active
                    element_id = f"tip-{i}-joules-active"
                else:
                    # For tips 5-8, always use -in-active
                    element_id = f"tip-{i}-joules-in-active"
                    
                await self._send_message("update_element", 
                                       element_id=element_id, 
                                       property="textContent",
                                       value=joules_text)
                
            # Check distance
            distance_key = f'tip{i}_distance'
            if self._has_value_changed(distance_key, getattr(self, distance_key)):
                distance_text = f"{getattr(self, distance_key):.1f} mm"
                if i <= 4:
                    # For tips 1-4, always use -active
                    element_id = f"tip-{i}-distance-active"
                else:
                    # For tips 5-8, always use -in-active
                    element_id = f"tip-{i}-distance-in-active"
                    
                await self._send_message("update_element", 
                                       element_id=element_id, 
                                       property="textContent",
                                       value=distance_text)
                
        # Update progress states
        progress_map = {
            'home': self.progress_home,
            'work_position': self.progress_work_position,
            'encoder_zero': self.progress_encoder_zero,
            'heat': self.progress_heat,
            'cool': self.progress_cool,
            'cycle_complete': self.progress_cycle_complete
        }
        
        if self._has_value_changed('progress_states', progress_map):
            await self._send_message("update_progress_states", states=progress_map)
            
        # Update time
        time_str = f"∼{self.time_minutes}m {self.time_seconds:02d}sec"
        if self._has_value_changed('time', time_str):
            await self._send_message("update_element", 
                                   element_id="home-text-time", 
                                   property="textContent",
                                   value=time_str)
            
        # Update slider and percentage
        if self._has_value_changed('slider', self.slider_percentage):
            await self._send_message("update_slider", position=self.slider_percentage)
            await self._send_message("update_element", 
                                   element_id="home-text-percent", 
                                   property="textContent",
                                   value=f"{self.slider_percentage}%")
            
        # Update banner text
        if self._has_value_changed('banner_text', self.banner_text):
            await self._send_message("update_element", 
                                   element_id="home-banner-text", 
                                   property="textContent",
                                   value=self.banner_text)
            
        # Update processing text
        if self._has_value_changed('processing_text', self.processing_text):
            await self._send_message("update_element", 
                                   element_id="home-cycle-progress-text", 
                                   property="textContent",
                                   value=self.processing_text)
        
        # Update work position data (if on work position screen)
        work_position_data = {
            'current_position': self.current_position,
            'setpoint': self.setpoint,
            'speed_mode': 'rapid' if self.speed_mode == 0 else 'fine',
            'up_button': self.up_button_state,
            'down_button': self.down_button_state,
            'tip_distances': self.work_tip_distances.copy(),
            'tip_states': {i: getattr(self, f'tip{i}_active') for i in range(1, 9)}
        }
        
        if self._has_value_changed('work_position', work_position_data):
            await self._send_message("work_position_update", data=work_position_data)
            
        # Send tip data for home screen (live values)
        tips_data = {}
        for i in range(1, 9):
            tips_data[i] = {
                'active': getattr(self, f'tip{i}_active'),
                'joules': getattr(self, f'tip{i}_joules'),
                'distance': getattr(self, f'tip{i}_distance'),
                'progress': getattr(self, f'tip{i}_progress')
            }
        
        modbus_data = {
            'tips': tips_data
        }
        
        if self._has_value_changed('tips_data', tips_data):
            await self._send_message("modbus_update", payload=modbus_data)
            
        # Send heating setpoint data for heating screen
        heating_data = {}
        for i in range(1, 9):
            heating_data[i] = {
                'energy': self.heating_energy_setpoints[i],
                'distance': self.heating_distance_setpoints[i],
                'heat_start_delay': self.heating_heat_start_delay_setpoints[i]
            }
        
        heating_modbus_data = {
            'heating_setpoints': heating_data
        }
        
        if self._has_value_changed('heating_data', heating_data):
            await self._send_message("heating_update", payload=heating_modbus_data)
            print(f"Sent heating setpoints update: {heating_data}")

        # Send monitor screen update
        monitor_payload = {
            'states': {
                'left_start': self.monitor_left_start,
                'right_start': self.monitor_right_start,
                'estop_active': self.monitor_estop_active,
                'home_switch': self.monitor_home_switch,
                'pressure_ok': self.monitor_pressure_ok,
            },
            'pressure_psi': int(self.monitor_pressure_psi),
        }
        if self._has_value_changed('monitor_payload', monitor_payload):
            await self._send_message("monitor_update", payload=monitor_payload)
        
        # Periodic heartbeat sync of tip active states for reliability
        self.heartbeat_counter += 1
        if self.heartbeat_counter >= self.heartbeat_interval:
            self.heartbeat_counter = 0
            await self._heartbeat_sync_tip_states()

        # Always forward manual controls snapshot to UI to avoid missed states
        # Throttle platen updates and avoid flicker by rounding to 0.1mm
        # Also include up/down states for visual feedback
        if not hasattr(self, '_manual_controls_tick'):
            self._manual_controls_tick = 0
        self._manual_controls_tick += 1
        display_platen = round(float(self.current_position), 1)
        manual_payload = {
            'platen_mm': display_platen,
            'up_pressed': bool(self.up_button_state),
            'down_pressed': bool(self.down_button_state),
        }
        # Reduce send rate: only send when changed OR every 5 cycles (~10 Hz if base is 50 Hz)
        should_send_manual = self._has_value_changed('manual_controls_payload', manual_payload) or (self._manual_controls_tick % 5 == 0)
        if should_send_manual:
            await self._send_message("manual_controls_update", payload=manual_payload)
            
    async def handle_incoming_message(self, message_data):
        """Handle messages from the UI"""
        try:
            msg_type = message_data.get('type')
            
            if msg_type == 'set_speed_mode':
                # Update speed mode - queue for immediate write
                mode = message_data.get('mode')
                if mode == 'rapid':
                    speed_value = 0
                elif mode == 'fine':
                    speed_value = 1
                else:
                    return
                
                # Queue immediate write
                await self.button_write_queue.put({
                    'type': 'speed_mode',
                    'value': speed_value
                })
                    
            elif msg_type == 'button_press':
                # Momentary up/down button states (write-only)
                button = message_data.get('button')
                state = bool(message_data.get('state', False))
                if button == 'up':
                    self.up_button_state = state
                elif button == 'down':
                    self.down_button_state = state
                if button in ['up', 'down']:
                    await self.button_write_queue.put({'type': button, 'value': state})
                    
            elif msg_type == 'set_work_position':
                # Set work position command
                if self.modbus_client:
                    addr = get_work_position_address('set_position_cmd')
                    await self.modbus_client.write_register(addr, 1, slave=self.slave_id)

            elif msg_type == 'manual_heat_button':
                # Heating button toggle
                tip = int(message_data.get('tip', 0))
                state = bool(message_data.get('state', False))
                if 1 <= tip <= 8:
                    self.manual_heating_buttons[tip] = state
                    if self.modbus_client:
                        try:
                            addr = get_manual_heating_button_address(tip)
                            await self.modbus_client.write_register(addr, 1 if state else 0, slave=self.slave_id)
                        except Exception as e:
                            print(f"Error writing manual heat button {tip}: {e}")

            elif msg_type == 'manual_cooling':
                state = bool(message_data.get('state', False))
                self.manual_cooling_on = state
                if self.modbus_client:
                    try:
                        addr = get_manual_cooling_address()
                        await self.modbus_client.write_register(addr, 1 if state else 0, slave=self.slave_id)
                    except Exception as e:
                        print(f"Error writing manual cooling: {e}")
                    
            elif msg_type == 'request_all_values':
                # Send all current values when page loads/reconnects
                # Don't read fresh data first - use cached values for speed
                await self.send_all_current_values()
                # Then read fresh data in background
                asyncio.create_task(self.read_modbus_data())
                
            elif msg_type == 'request_work_position_state':
                # Force read latest data from Modbus
                await self.read_modbus_data()
                
                # Send current work position state
                work_position_data = {
                    'current_position': self.current_position,
                    'setpoint': self.setpoint,
                    'speed_mode': 'rapid' if self.speed_mode == 0 else 'fine',
                    'up_button': self.up_button_state,
                    'down_button': self.down_button_state,
                    'tip_distances': self.work_tip_distances.copy(),
                    'tip_states': {i: getattr(self, f'tip{i}_active') for i in range(1, 9)}
                }
                await self._send_message("work_position_update", data=work_position_data)
                
            elif msg_type == 'update_tip_active':
                # Update tip active state from heating screen
                tip_number = message_data.get('tipNumber')
                active = message_data.get('active', False)
                
                if tip_number and 1 <= tip_number <= 8:
                    # Update local state immediately
                    setattr(self, f'tip{tip_number}_active', active)
                    print(f"Updated tip {tip_number} active state to {active}")
                    
                    # Write to Modbus for the slave to know
                    if self.modbus_client:
                        addr = get_tip_address(tip_number, 'active')
                        value = 1 if active else 0
                        result = await self.modbus_client.write_register(addr, value, slave=self.slave_id)
                        if result.isError():
                            print(f"Error writing tip {tip_number} active state to Modbus: {result}")
                        else:
                            print(f"Successfully wrote tip {tip_number} active state {value} to Modbus address {addr}")
                    
                    # The JSON file is already updated by the main process
                    
            elif msg_type == 'update_heating_energy':
                # Write heating energy setpoint to Modbus
                tip_number = message_data.get('tipNumber')
                value = message_data.get('value', 0.0)
                
                if tip_number and 1 <= tip_number <= 8 and self.modbus_client:
                    addr = get_heating_energy_address(tip_number)
                    high, low = float_to_registers(value, scale=10)
                    result = await self.modbus_client.write_registers(addr, [high, low], slave=self.slave_id)
                    if result.isError():
                        print(f"❌ WRITE FAILED: Tip {tip_number} energy {value}J to addr {addr}: {result}")
                    else:
                        print(f"✅ WROTE: Tip {tip_number} energy {value}J to addr {addr} [regs: {high},{low}]")
                else:
                    print(f"❌ CANNOT WRITE: tip={tip_number}, client={self.modbus_client is not None}")
                        
            elif msg_type == 'update_heating_distance':
                # Write heating distance setpoint to Modbus
                tip_number = message_data.get('tipNumber')
                value = message_data.get('value', 0.0)
                
                if tip_number and 1 <= tip_number <= 8 and self.modbus_client:
                    addr = get_heating_distance_address(tip_number)
                    high, low = float_to_registers(value, scale=1000)
                    result = await self.modbus_client.write_registers(addr, [high, low], slave=self.slave_id)
                    if result.isError():
                        print(f"❌ WRITE FAILED: Tip {tip_number} distance {value}mm to addr {addr}: {result}")
                    else:
                        print(f"✅ WROTE: Tip {tip_number} distance {value}mm to addr {addr} [regs: {high},{low}]")
                else:
                    print(f"❌ CANNOT WRITE: tip={tip_number}, client={self.modbus_client is not None}")
                        
            elif msg_type == 'update_heating_heat_start_delay':
                # Write heating heat start delay setpoint to Modbus
                tip_number = message_data.get('tipNumber')
                value = message_data.get('value', 0.0)
                
                if tip_number and 1 <= tip_number <= 8 and self.modbus_client:
                    addr = get_heating_heat_start_delay_address(tip_number)
                    high, low = float_to_registers(value, scale=1000)
                    result = await self.modbus_client.write_registers(addr, [high, low], slave=self.slave_id)
                    if result.isError():
                        print(f"❌ WRITE FAILED: Tip {tip_number} heat start delay {value}sec to addr {addr}: {result}")
                    else:
                        print(f"✅ WROTE: Tip {tip_number} heat start delay {value}sec to addr {addr} [regs: {high},{low}]")
                else:
                    print(f"❌ CANNOT WRITE: tip={tip_number}, client={self.modbus_client is not None}")

            elif msg_type == 'update_configuration':
                # Write a configuration counter to Modbus
                key = message_data.get('key')
                value = message_data.get('value', 0.0)

                if self.modbus_client and key:
                    try:
                        # Determine scale by key
                        if key in ['weld_time', 'cool_time']:
                            scale = 100
                        elif key in ['pulse_energy']:
                            scale = 10
                        else:
                            scale = 1000
                        addr = get_configuration_address(key)
                        high, low = float_to_registers(value, scale=scale)
                        result = await self.modbus_client.write_registers(addr, [high, low], slave=self.slave_id)
                        if result.isError():
                            print(f"❌ WRITE FAILED: Config {key}={value} to addr {addr}: {result}")
                        else:
                            print(f"✅ WROTE: Config {key}={value} to addr {addr} [regs: {high},{low}] scale={scale}")
                    except Exception as e:
                        print(f"❌ Error writing configuration {key}: {e}")
                    
            elif msg_type == 'request_heating_values':
                # Send current heating setpoint values
                # Force read from Modbus first
                await self.read_modbus_data()
                
                # Send heating setpoint data
                heating_data = {}
                for i in range(1, 9):
                    heating_data[i] = {
                        'energy': self.heating_energy_setpoints[i],
                        'distance': self.heating_distance_setpoints[i]
                    }
                
                await self._send_message("heating_update", payload={'heating_setpoints': heating_data})
                print(f"Sent heating update: {heating_data}")
                    
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def listen_for_messages(self):
        """Listen for incoming WebSocket messages"""
        try:
            while self.connected:
                message = await self.websocket.recv()
                data = json.loads(message)
                await self.handle_incoming_message(data)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            print(f"Error in message listener: {e}")
    
    async def process_button_writes(self):
        """Process immediate button writes from the queue"""
        while True:
            try:
                # Wait for button write request
                write_request = await self.button_write_queue.get()
                
                if not self.modbus_client:
                    continue
                
                write_type = write_request['type']
                value = write_request['value']
                
                # Perform immediate write with retry
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        if write_type == 'speed_mode':
                            addr = get_work_position_address('speed_mode')
                            await self.modbus_client.write_register(addr, value, slave=self.slave_id)
                            self.speed_mode = value
                            self.last_button_states['speed_mode'] = value
                            print(f"Speed mode written: {value}")
                            
                        elif write_type == 'up':
                            addr = get_work_position_address('up_button_state')
                            await self.modbus_client.write_register(addr, 1 if value else 0, slave=self.slave_id)
                            self.up_button_state = value
                            self.last_button_states['up'] = value
                            print(f"Up button state written: {value}")
                            
                        elif write_type == 'down':
                            addr = get_work_position_address('down_button_state')
                            await self.modbus_client.write_register(addr, 1 if value else 0, slave=self.slave_id)
                            self.down_button_state = value
                            self.last_button_states['down'] = value
                            print(f"Down button state written: {value}")
                        
                        # Success - break retry loop
                        break
                        
                    except Exception as e:
                        print(f"Button write error (retry {retry+1}/{max_retries}): {e}")
                        if retry < max_retries - 1:
                            await asyncio.sleep(0.01)  # Short delay before retry
                        
            except Exception as e:
                print(f"Error in button write processor: {e}")
                await asyncio.sleep(0.1)
            
    async def run_update_loop(self):
        """Main update loop - reads from Modbus and updates UI"""
        print("Starting Modbus update loop...")
        
        # Start concurrent tasks
        listener_task = asyncio.create_task(self.listen_for_messages())
        button_writer_task = asyncio.create_task(self.process_button_writes())
        
        try:
            while self.connected:
                try:
                    # Read data from Modbus
                    success = await self.read_modbus_data()
                    
                    if success:
                        # Update UI with changed values
                        await self.update_changed_values()
                        
                        # Verify button states and fix any discrepancies
                        await self.verify_button_states()
                    else:
                        print("Failed to read Modbus data")
                        
                    # Wait for next update cycle
                    await asyncio.sleep(self.update_interval)
                    
                except Exception as e:
                    print(f"Error in update loop: {e}")
                    await asyncio.sleep(1)  # Wait a bit before retrying
        finally:
            # Cancel tasks if they're still running
            listener_task.cancel()
            button_writer_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
            try:
                await button_writer_task
            except asyncio.CancelledError:
                pass
    
    async def verify_button_states(self):
        """Verify button states match expected values and fix if needed"""
        # Check if button states from Modbus match what we expect
        if self.up_button_state != self.last_button_states.get('up', False):
            # Mismatch - rewrite the correct state
            await self.button_write_queue.put({
                'type': 'up',
                'value': self.last_button_states.get('up', False)
            })
            
        if self.down_button_state != self.last_button_states.get('down', False):
            # Mismatch - rewrite the correct state
            await self.button_write_queue.put({
                'type': 'down',
                'value': self.last_button_states.get('down', False)
            })
            
        if self.speed_mode != self.last_button_states.get('speed_mode', 0):
            # Mismatch - rewrite the correct state
            await self.button_write_queue.put({
                'type': 'speed_mode',
                'value': self.last_button_states.get('speed_mode', 0)
            })
                



async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Modbus Simple UI Controller')
    parser.add_argument('--port', default='/tmp/vserial1', help='Serial port for Modbus')
    parser.add_argument('--baudrate', type=int, default=1000000, help='Baudrate for Modbus')
    parser.add_argument('--slave-id', type=int, default=1, help='Modbus slave ID')
    parser.add_argument('--websocket', default='ws://localhost:8080', help='WebSocket URI')
    
    args = parser.parse_args()
    
    # Create and run controller
    controller = ModbusSimpleUSHSController(
        serial_port=args.port,
        baudrate=args.baudrate,
        slave_id=args.slave_id
    )
    
    try:
        # Connect with specified websocket URI
        connected = await controller.connect(args.websocket)
        if not connected:
            print("Failed to connect to WebSocket")
            return
            
        # Run the update loop
        await controller.run_update_loop()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await controller.disconnect()


if __name__ == "__main__":
    asyncio.run(main())