#!/usr/bin/env python3
"""
Embedded Controller Simulator for USHS Screens
Simulates the cycle progress states and communicates via serial port
"""

import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
import json

class ControllerSimulator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("USHS Controller Simulator")
        self.root.geometry("800x850")
        
        # Cycle states
        self.cycle_stages = [
            "home",
            "work_position", 
            "encoder_zero",
            "heat",
            "cool",
            "cycle_complete"
        ]
        
        # Current state index (-1 means all inactive)
        self.current_state = -1
        
        # Initialize tip data (8 tips)
        self.tip_data = {}
        for i in range(1, 9):
            self.tip_data[i] = {
                'joules': tk.StringVar(value="0"),
                'distance': tk.StringVar(value="0"),
                'heat_percentage': tk.StringVar(value="0")
            }
        
        # Initialize home screen control data
        self.home_screen_data = {
            'banner_text': tk.StringVar(value="System Is Ready"),
            'processing_text': tk.StringVar(value="Processing..."),
            'spinner_active': tk.BooleanVar(value=True),
            'percentage': tk.StringVar(value="0"),
            'time_text': tk.StringVar(value="∼1m 46sec"),
            'slider_position': tk.StringVar(value="0")
        }
        
        # Initialize work position data
        self.work_position_data = {
            'current_position': tk.StringVar(value="0"),
            'setpoint': tk.StringVar(value="0"),
            'speed_mode': tk.StringVar(value="rapid"),
            'tip_distances': {}
        }
        
        # Initialize tip distances for work position
        for i in range(1, 9):
            self.work_position_data['tip_distances'][i] = tk.StringVar(value="0")
        
        # Work position button states (received from electron app)
        self.wp_button_states = {
            'up': False,
            'down': False,
            'set_work_position': False
        }
        
        # Serial connection
        self.serial_port = None
        self.serial_thread = None
        self.running = False
        
        # Packet structure:
        # TD:<json_data>  - Tip Data command
        # JSON contains:
        #   - cycle_progress: -1 to 6 (same as CP command)
        #   - tips: array of 8 tip objects with:
        #     - joules: float value
        #     - distance: float value  
        #     - heat_percentage: float value (0-100)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="USHS Controller Simulator", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Serial Port Frame
        port_frame = tk.LabelFrame(self.root, text="Serial Port", padx=5, pady=5)
        port_frame.pack(padx=10, pady=5, fill="x")
        
        # Port selection
        tk.Label(port_frame, text="Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, 
                                       width=25, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5)
        
        # Refresh button
        refresh_btn = tk.Button(port_frame, text="Refresh", 
                               command=self.refresh_ports,
                               font=("Arial", 10),
                               bg="#9E9E9E", fg="white",
                               padx=10, pady=3)
        refresh_btn.grid(row=0, column=2, padx=5)
        
        # Connect button
        self.connect_btn = tk.Button(port_frame, text="Connect", 
                                    command=self.toggle_connection,
                                    font=("Arial", 11, "bold"),
                                    bg="#4CAF50", fg="white",
                                    padx=15, pady=5)
        self.connect_btn.grid(row=1, column=1, pady=5)
        
        # Status label
        self.status_label = tk.Label(port_frame, text="Disconnected", 
                                    fg="red")
        self.status_label.grid(row=1, column=2, pady=5)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(padx=10, pady=5, fill="both", expand=True)
        
        # Create tabs
        self.setup_cycle_control_tab()
        self.setup_work_position_tab()
        
        # Log frame at the bottom
        self.setup_log_frame()
        
        # Initial setup
        self.refresh_ports()
        self.update_display()
        
    def setup_cycle_control_tab(self):
        # Create cycle control tab
        cycle_tab = ttk.Frame(self.notebook)
        self.notebook.add(cycle_tab, text="Cycle Control")
        
        # Cycle Control Frame
        control_frame = tk.LabelFrame(cycle_tab, text="Cycle Control", 
                                     padx=5, pady=5)
        control_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # Current state display
        self.state_display = tk.Label(control_frame, 
                                     text="Current State: All Inactive",
                                     font=("Arial", 10, "bold"))
        self.state_display.pack(pady=5)
        
        # Progress display - horizontal layout
        self.progress_frame = tk.Frame(control_frame)
        self.progress_frame.pack(pady=5)
        
        self.stage_labels = []
        for i, stage in enumerate(self.cycle_stages):
            label = tk.Label(self.progress_frame, 
                           text=f"{i+1}. {stage.replace('_', ' ').title()}",
                           font=("Arial", 8),
                           fg="gray", width=15)
            label.grid(row=i//3, column=i%3, padx=5, pady=2)
            self.stage_labels.append(label)
        
        # Control buttons
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=10)
        
        self.prev_btn = tk.Button(button_frame, text="◄ Previous", 
                                 command=self.previous_state,
                                 width=12, height=1,
                                 font=("Arial", 10, "bold"),
                                 bg="#4CAF50", fg="white",
                                 relief=tk.RAISED, bd=2)
        self.prev_btn.grid(row=0, column=0, padx=5)
        
        self.next_btn = tk.Button(button_frame, text="Next ►", 
                                 command=self.next_state,
                                 width=12, height=1,
                                 font=("Arial", 10, "bold"),
                                 bg="#2196F3", fg="white",
                                 relief=tk.RAISED, bd=2)
        self.next_btn.grid(row=0, column=1, padx=5)
        
        # Reset button
        reset_btn = tk.Button(control_frame, text="Reset to Inactive", 
                             command=self.reset_state,
                             font=("Arial", 9),
                             bg="#f44336", fg="white",
                             relief=tk.RAISED, bd=2,
                             padx=5, pady=2)
        reset_btn.pack(pady=5)
        
        # Tips Control Frame
        tips_frame = tk.LabelFrame(cycle_tab, text="Tip Controls", 
                                  padx=5, pady=5)
        tips_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # Create scrollable frame for tips
        canvas = tk.Canvas(tips_frame, height=200)
        scrollbar = ttk.Scrollbar(tips_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Headers
        headers_frame = tk.Frame(scrollable_frame)
        headers_frame.grid(row=0, column=0, columnspan=5, pady=2)
        tk.Label(headers_frame, text="Tip #", font=("Arial", 9, "bold"), width=6).grid(row=0, column=0)
        tk.Label(headers_frame, text="Joules (J)", font=("Arial", 9, "bold"), width=10).grid(row=0, column=1)
        tk.Label(headers_frame, text="Distance (mm)", font=("Arial", 9, "bold"), width=12).grid(row=0, column=2)
        tk.Label(headers_frame, text="Heat %", font=("Arial", 9, "bold"), width=10).grid(row=0, column=3)
        
        # Create tip controls with Spinbox
        for i in range(1, 9):
            row_frame = tk.Frame(scrollable_frame, relief=tk.RIDGE, borderwidth=1)
            row_frame.grid(row=i, column=0, columnspan=5, sticky="ew", padx=2, pady=1)
            
            # Tip number
            tk.Label(row_frame, text=f"Tip {i}", font=("Arial", 9), width=6).grid(row=0, column=0)
            
            # Joules spinbox
            joules_spin = tk.Spinbox(row_frame, textvariable=self.tip_data[i]['joules'], 
                                    from_=0, to=100, increment=0.1,
                                    width=10, font=("Arial", 9), format="%.1f")
            joules_spin.grid(row=0, column=1, padx=2)
            
            # Distance spinbox
            distance_spin = tk.Spinbox(row_frame, textvariable=self.tip_data[i]['distance'], 
                                      from_=0, to=100, increment=0.1,
                                      width=10, font=("Arial", 9), format="%.1f")
            distance_spin.grid(row=0, column=2, padx=2)
            
            # Heat percentage spinbox
            heat_spin = tk.Spinbox(row_frame, textvariable=self.tip_data[i]['heat_percentage'], 
                                  from_=0, to=100, increment=1,
                                  width=10, font=("Arial", 9), format="%.0f")
            heat_spin.grid(row=0, column=3, padx=2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Send packet button
        send_btn = tk.Button(tips_frame, text="Send Tip Data Packet", 
                            command=self.send_tip_data,
                            font=("Arial", 10, "bold"),
                            bg="#FF9800", fg="white",
                            relief=tk.RAISED, bd=2,
                            padx=10, pady=5)
        send_btn.pack(pady=5)
        
        # Home Screen Controls Frame
        home_frame = tk.LabelFrame(cycle_tab, text="Home Screen Controls", 
                                  padx=5, pady=5)
        home_frame.pack(padx=10, pady=5, fill="x")
        
        # Banner text
        tk.Label(home_frame, text="Banner Text:", font=("Arial", 9)).grid(row=0, column=0, sticky="w", padx=3, pady=2)
        banner_entry = tk.Entry(home_frame, textvariable=self.home_screen_data['banner_text'], 
                               width=30, font=("Arial", 9))
        banner_entry.grid(row=0, column=1, padx=3, pady=2)
        
        # Processing text
        tk.Label(home_frame, text="Processing Text:", font=("Arial", 9)).grid(row=1, column=0, sticky="w", padx=3, pady=2)
        processing_entry = tk.Entry(home_frame, textvariable=self.home_screen_data['processing_text'], 
                                   width=30, font=("Arial", 9))
        processing_entry.grid(row=1, column=1, padx=3, pady=2)
        
        # Spinner active checkbox
        spinner_check = tk.Checkbutton(home_frame, text="Spinner Active", 
                                      variable=self.home_screen_data['spinner_active'],
                                      font=("Arial", 9))
        spinner_check.grid(row=2, column=0, columnspan=2, sticky="w", padx=3, pady=2)
        
        # Percentage
        tk.Label(home_frame, text="Percentage (0-100):", font=("Arial", 9)).grid(row=3, column=0, sticky="w", padx=3, pady=2)
        percentage_spin = tk.Spinbox(home_frame, textvariable=self.home_screen_data['percentage'], 
                                    from_=0, to=100, increment=5,
                                    width=10, font=("Arial", 9), format="%.0f")
        percentage_spin.grid(row=3, column=1, sticky="w", padx=3, pady=2)
        
        # Time text
        tk.Label(home_frame, text="Time Text:", font=("Arial", 9)).grid(row=4, column=0, sticky="w", padx=3, pady=2)
        time_entry = tk.Entry(home_frame, textvariable=self.home_screen_data['time_text'], 
                             width=15, font=("Arial", 9))
        time_entry.grid(row=4, column=1, sticky="w", padx=3, pady=2)
        
        # Slider position
        tk.Label(home_frame, text="Slider Position (0-100):", font=("Arial", 9)).grid(row=5, column=0, sticky="w", padx=3, pady=2)
        slider_spin = tk.Spinbox(home_frame, textvariable=self.home_screen_data['slider_position'], 
                                from_=0, to=100, increment=5,
                                width=10, font=("Arial", 9), format="%.0f")
        slider_spin.grid(row=5, column=1, sticky="w", padx=3, pady=2)
    
    def setup_work_position_tab(self):
        # Create work position tab
        wp_tab = ttk.Frame(self.notebook)
        self.notebook.add(wp_tab, text="Work Position")
        
        # Work Position Data Frame
        data_frame = tk.LabelFrame(wp_tab, text="Work Position Data", 
                                  padx=5, pady=5)
        data_frame.pack(padx=10, pady=5, fill="x")
        
        # Current position and setpoint
        tk.Label(data_frame, text="Current Position (mm):", font=("Arial", 9)).grid(row=0, column=0, sticky="w", padx=3, pady=2)
        current_pos_spin = tk.Spinbox(data_frame, textvariable=self.work_position_data['current_position'], 
                                     from_=0, to=100, increment=0.1,
                                     width=10, font=("Arial", 9), format="%.1f")
        current_pos_spin.grid(row=0, column=1, padx=3, pady=2)
        
        tk.Label(data_frame, text="Setpoint (mm):", font=("Arial", 9)).grid(row=1, column=0, sticky="w", padx=3, pady=2)
        setpoint_spin = tk.Spinbox(data_frame, textvariable=self.work_position_data['setpoint'], 
                                   from_=0, to=100, increment=0.1,
                                   width=10, font=("Arial", 9), format="%.1f")
        setpoint_spin.grid(row=1, column=1, padx=3, pady=2)
        
        # Speed mode
        tk.Label(data_frame, text="Speed Mode:", font=("Arial", 9)).grid(row=2, column=0, sticky="w", padx=3, pady=2)
        speed_frame = tk.Frame(data_frame)
        speed_frame.grid(row=2, column=1, sticky="w", padx=3, pady=2)
        tk.Radiobutton(speed_frame, text="Rapid", variable=self.work_position_data['speed_mode'], 
                      value="rapid", font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Radiobutton(speed_frame, text="Fine", variable=self.work_position_data['speed_mode'], 
                      value="fine", font=("Arial", 9)).pack(side=tk.LEFT, padx=(20, 0))
        
        # Tip Distances Frame
        tip_distances_frame = tk.LabelFrame(wp_tab, text="Tip Distances", 
                                           padx=5, pady=5)
        tip_distances_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # Create scrollable frame for tip distances
        canvas = tk.Canvas(tip_distances_frame, height=150)
        scrollbar = ttk.Scrollbar(tip_distances_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create tip distance controls
        for i in range(1, 9):
            row_frame = tk.Frame(scrollable_frame, relief=tk.RIDGE, borderwidth=1)
            row_frame.grid(row=i-1, column=0, sticky="ew", padx=2, pady=1)
            
            # Tip number
            tk.Label(row_frame, text=f"Tip {i}:", font=("Arial", 9), width=6).grid(row=0, column=0)
            
            # Distance spinbox (0-8mm)
            distance_spin = tk.Spinbox(row_frame, textvariable=self.work_position_data['tip_distances'][i], 
                                      from_=0, to=8, increment=0.1,
                                      width=10, font=("Arial", 9), format="%.1f")
            distance_spin.grid(row=0, column=1, padx=2)
            
            tk.Label(row_frame, text="mm", font=("Arial", 9)).grid(row=0, column=2, padx=2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Send work position data button
        send_wp_btn = tk.Button(tip_distances_frame, text="Send Work Position Data", 
                               command=self.send_work_position_data,
                               font=("Arial", 10, "bold"),
                               bg="#2196F3", fg="white",
                               relief=tk.RAISED, bd=2,
                               padx=10, pady=5)
        send_wp_btn.pack(pady=5)
        
        # Button States Display Frame
        button_states_frame = tk.LabelFrame(wp_tab, text="Received Button States", 
                                           padx=5, pady=5)
        button_states_frame.pack(padx=10, pady=5, fill="x")
        
        # Create button state indicators
        self.wp_button_indicators = {}
        
        button_frame = tk.Frame(button_states_frame)
        button_frame.pack(pady=5)
        
        # Up button indicator
        up_frame = tk.Frame(button_frame)
        up_frame.grid(row=0, column=0, padx=10)
        tk.Label(up_frame, text="UP", font=("Arial", 9, "bold")).pack()
        self.wp_button_indicators['up'] = tk.Label(up_frame, text="●", font=("Arial", 20), fg="gray")
        self.wp_button_indicators['up'].pack()
        
        # Down button indicator
        down_frame = tk.Frame(button_frame)
        down_frame.grid(row=0, column=1, padx=10)
        tk.Label(down_frame, text="DOWN", font=("Arial", 9, "bold")).pack()
        self.wp_button_indicators['down'] = tk.Label(down_frame, text="●", font=("Arial", 20), fg="gray")
        self.wp_button_indicators['down'].pack()
        
        # Set Work Position button indicator
        set_frame = tk.Frame(button_frame)
        set_frame.grid(row=0, column=2, padx=10)
        tk.Label(set_frame, text="SET WORK\nPOSITION", font=("Arial", 9, "bold")).pack()
        self.wp_button_indicators['set_work_position'] = tk.Label(set_frame, text="●", font=("Arial", 20), fg="gray")
        self.wp_button_indicators['set_work_position'].pack()
        
        # Speed mode display
        speed_frame = tk.Frame(button_frame)
        speed_frame.grid(row=0, column=3, padx=20)
        tk.Label(speed_frame, text="SPEED MODE", font=("Arial", 9, "bold")).pack()
        self.speed_mode_label = tk.Label(speed_frame, text="RAPID", font=("Arial", 10), fg="blue")
        self.speed_mode_label.pack()
        
    def setup_log_frame(self):
        # Log frame
        log_frame = tk.LabelFrame(self.root, text="Communication Log", 
                                 padx=5, pady=5)
        log_frame.pack(padx=10, pady=5, fill="x")
        
        # Log text with scrollbar
        log_scroll = tk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=4, width=50, 
                               yscrollcommand=log_scroll.set, font=("Arial", 8))
        self.log_text.pack(fill="x")
        log_scroll.config(command=self.log_text.yview)
        
    def refresh_ports(self):
        """Refresh available serial ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        # Add virtual ports for testing
        if '/tmp/ttyV0' not in ports:
            ports.append('/tmp/ttyV0')
        if '/tmp/ttyV1' not in ports:
            ports.append('/tmp/ttyV1')
            
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
            
    def toggle_connection(self):
        """Connect or disconnect serial port"""
        if self.serial_port and self.serial_port.is_open:
            self.disconnect()
        else:
            self.connect()
            
    def connect(self):
        """Connect to serial port"""
        port = self.port_var.get()
        if not port:
            self.log("No port selected")
            return
            
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=0.1,
                write_timeout=0.1
            )
            self.running = True
            self.serial_thread = threading.Thread(target=self.serial_handler)
            self.serial_thread.daemon = True
            self.serial_thread.start()
            
            self.connect_btn.config(text="Disconnect", bg="#f44336")
            self.status_label.config(text="Connected", fg="green")
            self.log(f"Connected to {port}")
            
            # Send initial state
            self.send_state()
            
        except Exception as e:
            self.log(f"Connection error: {e}")
            self.status_label.config(text="Error", fg="red")
            
    def disconnect(self):
        """Disconnect serial port"""
        self.running = False
        if self.serial_thread:
            self.serial_thread.join(timeout=1)
            
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            
        self.serial_port = None
        self.connect_btn.config(text="Connect", bg="#4CAF50")
        self.status_label.config(text="Disconnected", fg="red")
        self.log("Disconnected")
        
    def serial_handler(self):
        """Handle serial communication in background thread"""
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                # Read incoming data (if any)
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode().strip()
                    if data:
                        self.root.after(0, self.log, f"Received: {data}")
                        self.root.after(0, self.handle_received_data, data)
            except Exception as e:
                self.root.after(0, self.log, f"Serial error: {e}")
                self.root.after(0, self.disconnect)
                break
                
            time.sleep(0.01)
    
    def handle_received_data(self, data):
        """Handle data received from the Electron app"""
        try:
            # Parse the command
            colonIndex = data.find(':')
            if colonIndex != -1:
                command = data[:colonIndex]
                payload = data[colonIndex + 1:]
                
                if command == 'WPB':  # Work Position Button
                    button_data = json.loads(payload)
                    button = button_data.get('button')
                    pressed = button_data.get('pressed')
                    
                    if button in self.wp_button_states:
                        self.wp_button_states[button] = pressed
                        # Update UI indicator
                        if button in self.wp_button_indicators:
                            color = "green" if pressed else "gray"
                            self.wp_button_indicators[button].config(fg=color)
                            
                    self.log(f"Button {button}: {'Pressed' if pressed else 'Released'}")
                    
                elif command == 'WPS':  # Work Position Speed
                    speed_data = json.loads(payload)
                    speed_mode = speed_data.get('speed_mode')
                    
                    if speed_mode in ['rapid', 'fine']:
                        self.work_position_data['speed_mode'].set(speed_mode)
                        self.speed_mode_label.config(text=speed_mode.upper())
                        
                    self.log(f"Speed mode: {speed_mode}")
                    
                elif command == 'WPT':  # Work Position seT
                    self.log("Set Work Position command received")
                    # Flash the indicator
                    self.wp_button_indicators['set_work_position'].config(fg="green")
                    self.root.after(500, lambda: self.wp_button_indicators['set_work_position'].config(fg="gray"))
                    
        except Exception as e:
            self.log(f"Error handling received data: {e}")
            
    def send_state(self):
        """Send current state via serial (now sends full tip data packet)"""
        # Use the new tip data packet format which includes cycle progress
        self.send_tip_data()
                
    def next_state(self):
        """Move to next state"""
        if self.current_state < 6:
            self.current_state += 1
            self.update_display()
            self.send_state()
            
    def previous_state(self):
        """Move to previous state"""
        if self.current_state > -1:
            self.current_state -= 1
            self.update_display()
            self.send_state()
            
    def reset_state(self):
        """Reset to all inactive"""
        self.current_state = -1
        self.update_display()
        self.send_state()
        
    def update_display(self):
        """Update UI to reflect current state"""
        # Update state display
        if self.current_state == -1:
            self.state_display.config(text="Current State: All Inactive")
        elif self.current_state == 6:
            self.state_display.config(text="Current State: Cycle Complete")
        else:
            stage_name = self.cycle_stages[self.current_state].replace('_', ' ').title()
            self.state_display.config(text=f"Current State: {stage_name}")
            
        # Update stage labels
        for i, label in enumerate(self.stage_labels):
            if self.current_state == -1:
                # All inactive
                label.config(fg="gray", font=("Arial", 8))
            elif i < self.current_state:
                # Done (green)
                label.config(fg="green", font=("Arial", 8, "bold"))
            elif i == self.current_state and self.current_state < 6:
                # Active (blue)
                label.config(fg="blue", font=("Arial", 8, "bold"))
            else:
                # Inactive (gray)
                label.config(fg="gray", font=("Arial", 8))
                
        # Update button states
        self.prev_btn.config(state="normal" if self.current_state > -1 else "disabled")
        self.next_btn.config(state="normal" if self.current_state < 6 else "disabled")
        
    def send_tip_data(self):
        """Send tip data packet with all tip values and cycle progress"""
        if self.serial_port and self.serial_port.is_open:
            try:
                # Build tip data array
                tips = []
                self.cachedTipStates = {}  # Cache tip states for work position
                
                for i in range(1, 9):
                    try:
                        joules = float(self.tip_data[i]['joules'].get() or 0)
                        distance = float(self.tip_data[i]['distance'].get() or 0)
                        heat_percentage = float(self.tip_data[i]['heat_percentage'].get() or 0)
                    except ValueError:
                        joules = distance = heat_percentage = 0
                        
                    tips.append({
                        'tip_number': i,
                        'joules': joules,
                        'distance': distance,
                        'heat_percentage': heat_percentage
                    })
                    
                    # Cache tip state (active if heat_percentage > 0)
                    self.cachedTipStates[str(i)] = {'active': heat_percentage > 0}
                
                # Get home screen data
                try:
                    percentage = float(self.home_screen_data['percentage'].get() or 0)
                    slider_position = float(self.home_screen_data['slider_position'].get() or 0)
                except ValueError:
                    percentage = slider_position = 0
                
                # Build packet data
                packet_data = {
                    'cycle_progress': self.current_state,
                    'tips': tips,
                    'home_screen': {
                        'banner_text': self.home_screen_data['banner_text'].get(),
                        'processing_text': self.home_screen_data['processing_text'].get(),
                        'spinner_active': self.home_screen_data['spinner_active'].get(),
                        'percentage': percentage,
                        'time_text': self.home_screen_data['time_text'].get(),
                        'slider_position': slider_position
                    }
                }
                
                # Send as JSON packet
                packet = f"TD:{json.dumps(packet_data)}\n"
                bytes_written = self.serial_port.write(packet.encode())
                self.serial_port.flush()
                self.log(f"Sent: TD packet ({bytes_written} bytes)")
                
                # Log detailed data for debugging
                self.log(f"  Cycle Progress: {self.current_state}")
                self.log(f"  Home Screen - Banner: {self.home_screen_data['banner_text'].get()}")
                self.log(f"  Home Screen - Processing: {self.home_screen_data['processing_text'].get()}")
                self.log(f"  Home Screen - Spinner: {self.home_screen_data['spinner_active'].get()}")
                self.log(f"  Home Screen - Percentage: {percentage}%")
                self.log(f"  Home Screen - Time: {self.home_screen_data['time_text'].get()}")
                self.log(f"  Home Screen - Slider: {slider_position}%")
                for tip in tips:
                    self.log(f"  Tip {tip['tip_number']}: {tip['joules']}J, {tip['distance']}mm, {tip['heat_percentage']}%")
                    
            except Exception as e:
                self.log(f"Send error: {e}")
        else:
            self.log("Port not open, cannot send")
    
    def send_work_position_data(self):
        """Send work position data packet"""
        if self.serial_port and self.serial_port.is_open:
            try:
                # Build work position data
                wp_data = {
                    'current_position': float(self.work_position_data['current_position'].get() or 0),
                    'setpoint': float(self.work_position_data['setpoint'].get() or 0),
                    'speed_mode': self.work_position_data['speed_mode'].get(),
                    'tip_distances': {}
                }
                
                # Add tip distances (tip states are managed separately in the heating screen)
                for i in range(1, 9):
                    wp_data['tip_distances'][i] = float(self.work_position_data['tip_distances'][i].get() or 0)
                
                # Send as WP packet
                packet = f"WP:{json.dumps(wp_data)}\n"
                bytes_written = self.serial_port.write(packet.encode())
                self.serial_port.flush()
                self.log(f"Sent: WP packet ({bytes_written} bytes)")
                
                # Log details
                self.log(f"  Current Position: {wp_data['current_position']}mm")
                self.log(f"  Setpoint: {wp_data['setpoint']}mm")
                self.log(f"  Speed Mode: {wp_data['speed_mode']}")
                self.log(f"  Packet content: {json.dumps(wp_data, separators=(',', ':'))}")
                for i in range(1, 9):
                    if wp_data['tip_distances'][i] > 0:
                        self.log(f"  Tip {i}: {wp_data['tip_distances'][i]}mm")
                    
            except Exception as e:
                self.log(f"Send error: {e}")
        else:
            self.log("Port not open, cannot send")
    
    def log(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
    def run(self):
        """Start the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """Clean up on window close"""
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    simulator = ControllerSimulator()
    simulator.run()
