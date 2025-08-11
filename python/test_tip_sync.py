#!/usr/bin/env python3
"""
Test script to verify tip active status synchronization between modbus master and slave
"""
import asyncio
import time
import json
import os
from modbus_map import get_tip_address

async def test_tip_sync():
    """Test the tip active status synchronization"""
    print("=== Tip Active Status Synchronization Test ===")
    
    # Read the current tip states from JSON
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tip_states.json')
    
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            tip_states = json.load(f)
            
        print("\nCurrent tip states from tip_states.json:")
        for i in range(1, 9):
            if str(i) in tip_states:
                active = tip_states[str(i)].get('active', False)
                print(f"  Tip {i}: {'Active' if active else 'Inactive'}")
                
        print("\nExpected Modbus addresses for tip active states:")
        for i in range(1, 9):
            addr = get_tip_address(i, 'active')
            active = tip_states[str(i)].get('active', False) if str(i) in tip_states else False
            print(f"  Tip {i}: Address {addr} should contain {1 if active else 0}")
            
    else:
        print(f"ERROR: tip_states.json not found at {json_path}")
        return
        
    print("\n=== Test Instructions ===")
    print("1. Start the modbus slave simulator:")
    print("   python python/modbus_slave_gui.py")
    print("   - Start the server in the GUI")
    print("   - Go to the 'Heating Setpoints' tab")
    print("   - Note the current checkbox states")
    
    print("\n2. Start the modbus master:")
    print("   python python/modbus_simple_ui_controller.py")
    print("   - Watch the console output for 'Writing initial tip active states...'")
    print("   - Check if it successfully writes all tip states")
    
    print("\n3. Check the modbus slave simulator:")
    print("   - The checkboxes in the 'Heating Setpoints' tab should now match the JSON file")
    print("   - All tips should be checked (active) based on current tip_states.json")
    
    print("\n4. Test updating tip states:")
    print("   - In your main app, go to heating settings and toggle a tip active state")
    print("   - The checkbox in the modbus slave simulator should update immediately")
    
    print("\n=== Expected Results ===")
    print("✓ All 8 tips should show as 'Active' (checked) in the modbus slave simulator")
    print("✓ Console should show successful writes to modbus addresses")
    print("✓ Toggling tip states in the main app should update the simulator checkboxes")

if __name__ == "__main__":
    asyncio.run(test_tip_sync())