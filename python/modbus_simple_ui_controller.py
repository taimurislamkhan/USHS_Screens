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

class ModbusSimpleUSHSController:
    def __init__(self, serial_port='/tmp/vserial2', baudrate=9600, slave_id=1):
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
        
        # Initialize all properties with default values
        self._initialize_properties()
        
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
        
    async def connect_modbus(self):
        """Connect to Modbus slave"""
        try:
            self.modbus_client = AsyncModbusSerialClient(
                **self.serial_config,
                framer=ModbusRtuFramer
            )
            
            connected = await self.modbus_client.connect()
            if connected:
                print(f"Connected to Modbus slave on {self.serial_config['port']}")
                return True
            else:
                print(f"Failed to connect to Modbus slave on {self.serial_config['port']}")
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
                
                # Read 5 registers for each tip (active, progress, joules, distance[2])
                result = await self.modbus_client.read_holding_registers(
                    base_addr, 5, slave=self.slave_id
                )
                
                if not result.isError():
                    # Parse tip data
                    setattr(self, f'tip{i}_active', bool(result.registers[0]))
                    setattr(self, f'tip{i}_progress', result.registers[1])
                    setattr(self, f'tip{i}_joules', result.registers[2] / 10.0)
                    
                    # Distance is 32-bit (2 registers)
                    distance = registers_to_float([result.registers[3], result.registers[4]], 1000)
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
                # Update button states - queue for immediate write
                button = message_data.get('button')
                state = message_data.get('state', False)
                
                if button in ['up', 'down']:
                    # Queue immediate write
                    await self.button_write_queue.put({
                        'type': button,
                        'value': state
                    })
                    
            elif msg_type == 'set_work_position':
                # Set work position command
                if self.modbus_client:
                    addr = get_work_position_address('set_position_cmd')
                    await self.modbus_client.write_register(addr, 1, slave=self.slave_id)
                    
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
    parser.add_argument('--port', default='/tmp/vserial2', help='Serial port for Modbus')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baudrate for Modbus')
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