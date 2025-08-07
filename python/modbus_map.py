"""
Modbus Address Map for USHS UI Controller
==========================================

This defines the Modbus register addresses for all UI elements.
Using Holding Registers (Function Code 03/06/16)

Address Range Organization:
- 0-99: System/Control registers
- 100-199: Tip 1 data
- 200-299: Tip 2 data
- 300-399: Tip 3 data
- 400-499: Tip 4 data
- 500-599: Tip 5 data
- 600-699: Tip 6 data
- 700-799: Tip 7 data
- 800-899: Tip 8 data
- 1000-1099: Progress states
- 1100-1199: Time and general UI
- 1200-1299: Banner and text strings
- 1300-1399: Work position data
- 1400-1499: Work position tip distances
"""

# System Configuration Registers (0-99)
SYSTEM_CONFIG = {
    'baudrate': 0,          # 9600, 19200, 38400, 57600, 115200
    'parity': 1,            # 0=None, 1=Even, 2=Odd
    'stopbits': 2,          # 1 or 2
    'bytesize': 3,          # 7 or 8
    'slave_id': 4,          # 1-247
    'update_rate': 5,       # Update rate in Hz (1-100)
}

# Tip Data Structure (repeated for tips 1-8)
# Each tip uses 100 addresses starting at base_address
TIP_OFFSET = {
    'active': 0,            # 0=inactive, 1=active (1 register)
    'progress': 1,          # 0-100 (1 register) - Progress percentage
    'joules': 2,            # Joules * 10 (to handle decimals) (1 register)
    'distance': 3,          # Distance * 1000 (mm with 3 decimals) (2 registers, 32-bit)
}

# Tip Base Addresses
TIP_BASE_ADDRESSES = {
    1: 100,
    2: 200,
    3: 300,
    4: 400,
    5: 500,
    6: 600,
    7: 700,
    8: 800,
}

# Progress States (1000-1099)
PROGRESS_STATES = {
    'home': 1000,           # 0=inactive, 1=active, 2=done
    'work_position': 1001,
    'encoder_zero': 1002,
    'heat': 1003,
    'cool': 1004,
    'cycle_complete': 1005,
}

# Time and General UI (1100-1199)
GENERAL_UI = {
    'time_minutes': 1100,   # Minutes (1 register)
    'time_seconds': 1101,   # Seconds (1 register)
    'slider_percentage': 1102,  # 0-100 (1 register)
}

# Banner and Text Strings (1200-1299)
# Strings are stored as multiple registers (2 chars per register)
TEXT_STRINGS = {
    'banner_text': 1200,    # 20 registers (40 chars max)
    'processing_text': 1220, # 20 registers (40 chars max)
}

# Work Position Data (1300-1399)
WORK_POSITION = {
    'current_position': 1300,    # Current position in mm * 100 (2 registers, 32-bit)
    'setpoint': 1302,           # Setpoint in mm * 100 (2 registers, 32-bit)
    'speed_mode': 1304,         # 0=rapid, 1=fine (1 register)
    'up_button_state': 1305,    # 0=released, 1=pressed (1 register)
    'down_button_state': 1306,  # 0=released, 1=pressed (1 register)
    'set_position_cmd': 1307,   # Command to set work position (1 register)
}

# Work Position Tip Distances (1400-1499)
# Each tip uses 2 registers for distance (32-bit float)
WORK_POSITION_TIP_BASE = 1400
WORK_POSITION_TIP_OFFSET = 2  # 2 registers per tip for distance

# Helper functions for address calculation
def get_tip_address(tip_number, parameter):
    """Get the Modbus address for a specific tip parameter"""
    if tip_number not in TIP_BASE_ADDRESSES:
        raise ValueError(f"Invalid tip number: {tip_number}")
    if parameter not in TIP_OFFSET:
        raise ValueError(f"Invalid parameter: {parameter}")
    
    return TIP_BASE_ADDRESSES[tip_number] + TIP_OFFSET[parameter]

def get_progress_address(state_name):
    """Get the Modbus address for a progress state"""
    if state_name not in PROGRESS_STATES:
        raise ValueError(f"Invalid progress state: {state_name}")
    return PROGRESS_STATES[state_name]

def get_general_ui_address(parameter):
    """Get the Modbus address for general UI parameters"""
    if parameter not in GENERAL_UI:
        raise ValueError(f"Invalid general UI parameter: {parameter}")
    return GENERAL_UI[parameter]

def get_work_position_address(parameter):
    """Get the Modbus address for work position parameters"""
    if parameter not in WORK_POSITION:
        raise ValueError(f"Invalid work position parameter: {parameter}")
    return WORK_POSITION[parameter]

def get_work_position_tip_distance_address(tip_number):
    """Get the Modbus address for work position tip distance"""
    if not 1 <= tip_number <= 8:
        raise ValueError(f"Invalid tip number: {tip_number}")
    return WORK_POSITION_TIP_BASE + (tip_number - 1) * WORK_POSITION_TIP_OFFSET

# Data conversion helpers
def float_to_registers(value, scale=1000):
    """Convert float to 2 registers (32-bit) with scaling"""
    scaled = int(value * scale)
    high = (scaled >> 16) & 0xFFFF
    low = scaled & 0xFFFF
    return [high, low]

def registers_to_float(registers, scale=1000):
    """Convert 2 registers to float with scaling"""
    value = (registers[0] << 16) | registers[1]
    return value / scale

def string_to_registers(text, max_length=40):
    """Convert string to register array (2 chars per register)"""
    text = text[:max_length].ljust(max_length, '\0')
    registers = []
    for i in range(0, len(text), 2):
        char1 = ord(text[i]) if i < len(text) else 0
        char2 = ord(text[i+1]) if i+1 < len(text) else 0
        registers.append((char1 << 8) | char2)
    return registers

def registers_to_string(registers):
    """Convert register array to string"""
    text = ""
    for reg in registers:
        char1 = (reg >> 8) & 0xFF
        char2 = reg & 0xFF
        if char1: text += chr(char1)
        if char2: text += chr(char2)
    return text.rstrip('\0')

# Packet definitions for efficient reading
MODBUS_READ_PACKETS = [
    # Packet 1: System config (6 registers)
    {'name': 'system_config', 'start': 0, 'count': 6},
    
    # Packet 2-9: Tip data (5 registers each)
    {'name': 'tip1', 'start': 100, 'count': 5},
    {'name': 'tip2', 'start': 200, 'count': 5},
    {'name': 'tip3', 'start': 300, 'count': 5},
    {'name': 'tip4', 'start': 400, 'count': 5},
    {'name': 'tip5', 'start': 500, 'count': 5},
    {'name': 'tip6', 'start': 600, 'count': 5},
    {'name': 'tip7', 'start': 700, 'count': 5},
    {'name': 'tip8', 'start': 800, 'count': 5},
    
    # Packet 10: Progress states (6 registers)
    {'name': 'progress_states', 'start': 1000, 'count': 6},
    
    # Packet 11: General UI (3 registers)
    {'name': 'general_ui', 'start': 1100, 'count': 3},
    
    # Packet 12: Banner text (20 registers)
    {'name': 'banner_text', 'start': 1200, 'count': 20},
    
    # Packet 13: Processing text (20 registers)
    {'name': 'processing_text', 'start': 1220, 'count': 20},
    
    # Packet 14: Work position data (8 registers)
    {'name': 'work_position', 'start': 1300, 'count': 8},
    
    # Packet 15: Work position tip distances (16 registers - 8 tips * 2 registers each)
    {'name': 'work_position_tips', 'start': 1400, 'count': 16},
]