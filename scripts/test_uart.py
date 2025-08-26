#!/usr/bin/env python3
"""
Test script for Raspberry Pi UART communication
Tests both sending and receiving on the UART port
"""

import serial
import time
import sys
import os

def list_serial_ports():
    """List available serial ports"""
    ports = []
    # Common serial port paths on Raspberry Pi
    common_ports = [
        '/dev/ttyAMA0', # Raspberry Pi 5 UART
        '/dev/serial0',
        '/dev/serial1',
        '/dev/ttyUSB0',
        '/dev/ttyUSB1',
        '/dev/ttyS0'  # Mini UART
    ]
    
    print("Checking for available serial ports...")
    for port in common_ports:
        if os.path.exists(port):
            ports.append(port)
            print(f"  Found: {port}")
    
    return ports

def test_loopback(port_path, baudrate=9600):
    """Test UART in loopback mode (TX connected to RX)"""
    print(f"\nTesting loopback on {port_path} at {baudrate} baud...")
    print("Make sure TX (GPIO 14) is connected to RX (GPIO 15) for loopback test!")
    
    try:
        # Open serial port
        ser = serial.Serial(
            port=port_path,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        
        print(f"Successfully opened {port_path}")
        
        # Clear any existing data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Test messages
        test_messages = [
            "Hello UART!",
            "Testing 123",
            "TD:{\"tips\":[{\"tip_number\":1,\"joules\":100}]}",
            "CP:3"
        ]
        
        print("\nSending test messages...")
        for msg in test_messages:
            # Send message
            ser.write((msg + '\n').encode())
            print(f"  Sent: {msg}")
            
            # Try to receive
            time.sleep(0.1)  # Small delay
            if ser.in_waiting > 0:
                received = ser.readline().decode().strip()
                print(f"  Received: {received}")
                if received == msg:
                    print("  ✓ Message matches!")
                else:
                    print("  ✗ Message mismatch!")
            else:
                print("  ✗ No data received")
            
            time.sleep(0.5)
        
        ser.close()
        print("\nLoopback test complete!")
        
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def interactive_test(port_path, baudrate=9600):
    """Interactive UART test - send and receive messages"""
    print(f"\nStarting interactive test on {port_path} at {baudrate} baud...")
    print("Type messages to send, or 'quit' to exit")
    print("Incoming messages will be displayed automatically")
    
    try:
        ser = serial.Serial(
            port=port_path,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        
        print(f"Successfully opened {port_path}")
        print("-" * 50)
        
        while True:
            # Check for incoming data
            if ser.in_waiting > 0:
                try:
                    incoming = ser.readline().decode('utf-8', errors='ignore').strip()
                    if incoming:  # Only print if there's actual content
                        print(f"<< Received: {incoming}")
                except Exception as e:
                    # Handle any decoding errors
                    raw_data = ser.read(ser.in_waiting)
                    print(f"<< Received (raw bytes): {raw_data}")
            
            # Check for user input (non-blocking)
            try:
                import select
                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                    line = input()
                    if line.lower() == 'quit':
                        break
                    ser.write((line + '\n').encode())
                    print(f">> Sent: {line}")
            except ImportError:
                # select not available on this system
                print("Enter message (or 'quit' to exit): ", end='', flush=True)
                line = input()
                if line.lower() == 'quit':
                    break
                ser.write((line + '\n').encode())
                print(f">> Sent: {line}")
            except EOFError:
                # Handle Ctrl+D or input stream closed
                print("\nInput stream closed. Exiting...")
                break
            except Exception as e:
                print(f"Input error: {e}")
                break
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
        
        ser.close()
        print("\nInteractive test ended.")
        
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        print("Check your UART connection and port settings.")
    except KeyboardInterrupt:
        print("\nTest interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"Unexpected error in interactive test: {e}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()

def main():
    print("Raspberry Pi UART Test Tool")
    print("==========================\n")
    
    # List available ports
    ports = list_serial_ports()
    
    if not ports:
        print("\nNo serial ports found!")
        print("Make sure UART is enabled on your Raspberry Pi.")
        print("Run: sudo ./scripts/setup_rpi_uart.sh")
        sys.exit(1)
    
    # Select port
    if len(ports) == 1:
        selected_port = ports[0]
        print(f"\nUsing port: {selected_port}")
    else:
        print("\nSelect a port:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port}")
        
        try:
            choice = int(input("Enter number: ")) - 1
            if 0 <= choice < len(ports):
                selected_port = ports[choice]
            else:
                print("Invalid choice!")
                sys.exit(1)
        except:
            print("Invalid input!")
            sys.exit(1)
    
    # Select test mode
    print("\nSelect test mode:")
    print("  1. Loopback test (TX connected to RX)")
    print("  2. Interactive test (communicate with device)")
    
    try:
        mode = int(input("Enter number: "))
        
        if mode == 1:
            test_loopback(selected_port)
        elif mode == 2:
            interactive_test(selected_port)
        else:
            print("Invalid choice!")
    except KeyboardInterrupt:
        print("\nTest cancelled.")
    except:
        print("Invalid input!")

if __name__ == "__main__":
    main()
