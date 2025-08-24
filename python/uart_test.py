#!/usr/bin/env python3
"""
Simple UART Test Script for Raspberry Pi 5
Continuously sends "hello world" via UART on GPIO 14 (TX) and 15 (RX)
Uses /dev/serial0 which maps to the primary UART on GPIO 14/15
"""

import serial
import time
import sys

def main():
    # UART configuration for Raspberry Pi 5
    # /dev/serial0 is the primary UART on GPIO 14/15
    uart_port = "/dev/serial0"
    baud_rate = 115200
    
    print(f"UART Test Script for Raspberry Pi 5")
    print(f"Port: {uart_port}")
    print(f"Baud Rate: {baud_rate}")
    print(f"GPIO Pins: TX=14, RX=15")
    print("Sending 'hello world' continuously...")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        # Initialize UART connection
        uart = serial.Serial(
            port=uart_port,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
            write_timeout=1
        )
        
        print(f"Successfully opened {uart_port}")
        
        # Counter for messages
        message_count = 0
        
        # Main loop - send "hello world" continuously
        while True:
            message_count += 1
            message = f"hello world #{message_count}\n"
            
            # Send the message
            uart.write(message.encode('utf-8'))
            uart.flush()  # Ensure data is sent immediately
            
            # Print status
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] Sent: {message.strip()}")
            
            # Wait 1 second before next message
            time.sleep(1)
            
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure UART is enabled in raspi-config")
        print("2. Check if the serial console is disabled")
        print("3. Verify UART permissions (add user to dialout group)")
        print("4. Try different port like /dev/ttyS0 or /dev/ttyAMA0")
        sys.exit(1)
        
    except PermissionError as e:
        print(f"Permission error: {e}")
        print("Try running with sudo or add your user to the dialout group:")
        print("sudo usermod -a -G dialout $USER")
        print("Then log out and log back in")
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n" + "-" * 50)
        print(f"Test stopped by user. Sent {message_count} messages.")
        print("UART test completed.")
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
        
    finally:
        # Clean up
        try:
            if 'uart' in locals() and uart.is_open:
                uart.close()
                print("UART port closed.")
        except:
            pass

if __name__ == "__main__":
    main()
