#!/usr/bin/env python3
"""
Modbus Slave GUI for USHS UI Controller
========================================

This provides a GUI interface for the Modbus slave that holds all UI values.
Uses virtual serial port for communication.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import asyncio
import time
import random
import os
import sys
import json
from datetime import datetime

from pymodbus.server import StartAsyncSerialServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer

from modbus_map import *

class ModbusSlaveGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("USHS Modbus Slave Simulator")
        self.root.geometry("1200x800")
        
        # Server state
        self.server_running = False
        self.server_task = None
        self.update_thread = None
        self.stop_event = threading.Event()
        
        # Default serial settings
        self.serial_config = {
            'port': '/tmp/vserial1',  # Virtual serial port
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1,
            'timeout': 1
        }
        
        # Slave configuration
        self.slave_id = 1
        self.update_rate = 30  # Hz
        
        # Data store
        self.data_store = None
        self.context = None
        
        # Create GUI
        self.create_widgets()
        
        # Initialize data
        self.initialize_data()
        
        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Initialize work position variables to ensure they exist
        if not hasattr(self, 'current_position'):
            self.current_position = tk.DoubleVar(value=0.0)
        if not hasattr(self, 'setpoint'):
            self.setpoint = tk.DoubleVar(value=0.0)
        if not hasattr(self, 'speed_mode'):
            self.speed_mode = tk.IntVar(value=0)
        if not hasattr(self, 'up_button'):
            self.up_button = tk.BooleanVar(value=False)
        if not hasattr(self, 'down_button'):
            self.down_button = tk.BooleanVar(value=False)
        if not hasattr(self, 'tip_distances'):
            self.tip_distances = {i: tk.DoubleVar(value=0.0) for i in range(1, 9)}
        
    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # === Connection Settings Frame ===
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Serial port
        ttk.Label(conn_frame, text="Serial Port:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.port_var = tk.StringVar(value=self.serial_config['port'])
        port_entry = ttk.Entry(conn_frame, textvariable=self.port_var, width=20)
        port_entry.grid(row=0, column=1, padx=(0, 20))
        
        # Baudrate
        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.baudrate_var = tk.IntVar(value=self.serial_config['baudrate'])
        baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate_var, 
                                      values=[9600, 19200, 38400, 57600, 115200], width=10)
        baudrate_combo.grid(row=0, column=3, padx=(0, 20))
        
        # Parity
        ttk.Label(conn_frame, text="Parity:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.parity_var = tk.StringVar(value=self.serial_config['parity'])
        parity_combo = ttk.Combobox(conn_frame, textvariable=self.parity_var, 
                                    values=['N', 'E', 'O'], width=5)
        parity_combo.grid(row=0, column=5, padx=(0, 20))
        
        # Data bits
        ttk.Label(conn_frame, text="Data Bits:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.bytesize_var = tk.IntVar(value=self.serial_config['bytesize'])
        bytesize_combo = ttk.Combobox(conn_frame, textvariable=self.bytesize_var, 
                                      values=[7, 8], width=5)
        bytesize_combo.grid(row=1, column=1, padx=(0, 20))
        
        # Stop bits
        ttk.Label(conn_frame, text="Stop Bits:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        self.stopbits_var = tk.IntVar(value=self.serial_config['stopbits'])
        stopbits_combo = ttk.Combobox(conn_frame, textvariable=self.stopbits_var, 
                                      values=[1, 2], width=5)
        stopbits_combo.grid(row=1, column=3, padx=(0, 20))
        
        # Slave ID
        ttk.Label(conn_frame, text="Slave ID:").grid(row=1, column=4, sticky=tk.W, padx=(0, 5))
        self.slave_id_var = tk.IntVar(value=self.slave_id)
        slave_id_spin = ttk.Spinbox(conn_frame, from_=1, to=247, textvariable=self.slave_id_var, width=5)
        slave_id_spin.grid(row=1, column=5, padx=(0, 20))
        
        # Update rate
        ttk.Label(conn_frame, text="Update Rate (Hz):").grid(row=1, column=6, sticky=tk.W, padx=(0, 5))
        self.update_rate_var = tk.IntVar(value=self.update_rate)
        update_rate_spin = ttk.Spinbox(conn_frame, from_=1, to=100, textvariable=self.update_rate_var, width=5)
        update_rate_spin.grid(row=1, column=7)
        
        # Start/Stop button
        self.start_button = ttk.Button(conn_frame, text="Start Server", command=self.toggle_server)
        self.start_button.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # Status label
        self.status_label = ttk.Label(conn_frame, text="Server Stopped", foreground="red")
        self.status_label.grid(row=2, column=2, columnspan=4, pady=(10, 0))
        
        # === Data Display Frame ===
        data_frame = ttk.Frame(main_frame)
        data_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        data_frame.columnconfigure(0, weight=1)
        data_frame.columnconfigure(1, weight=1)
        data_frame.rowconfigure(0, weight=1)
        
        # Create notebook for organized display
        self.notebook = ttk.Notebook(data_frame)
        self.notebook.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Tips tab
        self.tips_frame = self.create_tips_tab()
        self.notebook.add(self.tips_frame, text="Tips")
        
        # Progress tab
        self.progress_frame = self.create_progress_tab()
        self.notebook.add(self.progress_frame, text="Progress States")
        
        # General UI tab
        self.general_frame = self.create_general_tab()
        self.notebook.add(self.general_frame, text="General UI")
        
        # Work Position tab
        self.work_position_frame = self.create_work_position_tab()
        self.notebook.add(self.work_position_frame, text="Work Position")
        
        # Log tab
        self.log_frame = self.create_log_tab()
        self.notebook.add(self.log_frame, text="Log")
        
        # === Control Buttons Frame ===
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(control_frame, text="Randomize All", command=self.randomize_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Reset All", command=self.reset_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Save Config", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Load Config", command=self.load_config).pack(side=tk.LEFT, padx=5)
        
    def create_tips_tab(self):
        """Create the tips display tab"""
        tips_frame = ttk.Frame(self.notebook)
        
        # Create scrollable frame
        canvas = tk.Canvas(tips_frame)
        scrollbar = ttk.Scrollbar(tips_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create tip controls
        self.tip_widgets = {}
        
        for i in range(1, 9):
            frame = ttk.LabelFrame(scrollable_frame, text=f"Tip {i}", padding="10")
            frame.grid(row=(i-1)//2, column=(i-1)%2, padx=10, pady=5, sticky=(tk.W, tk.E))
            
            self.tip_widgets[i] = {}
            
            # Active checkbox
            self.tip_widgets[i]['active'] = tk.BooleanVar(value=True if i <= 4 else False)
            ttk.Checkbutton(frame, text="Active", variable=self.tip_widgets[i]['active'],
                           command=lambda i=i: self.update_tip_data(i)).grid(row=0, column=0, columnspan=2, sticky=tk.W)
            
            # Progress
            ttk.Label(frame, text="Progress:").grid(row=1, column=0, sticky=tk.W)
            self.tip_widgets[i]['progress'] = tk.IntVar(value=random.randint(0, 100))
            progress_scale = ttk.Scale(frame, from_=0, to=100, variable=self.tip_widgets[i]['progress'],
                                     command=lambda v, i=i: self.update_tip_data(i))
            progress_scale.grid(row=1, column=1, sticky=(tk.W, tk.E))
            self.tip_widgets[i]['progress_label'] = ttk.Label(frame, text="0%")
            self.tip_widgets[i]['progress_label'].grid(row=1, column=2)
            
            # Joules
            ttk.Label(frame, text="Joules:").grid(row=2, column=0, sticky=tk.W)
            self.tip_widgets[i]['joules'] = tk.DoubleVar(value=random.uniform(0, 100))
            joules_spin = ttk.Spinbox(frame, from_=0, to=999.9, increment=0.1, 
                                     textvariable=self.tip_widgets[i]['joules'],
                                     command=lambda i=i: self.update_tip_data(i))
            joules_spin.grid(row=2, column=1, sticky=(tk.W, tk.E))
            
            # Distance
            ttk.Label(frame, text="Distance (mm):").grid(row=3, column=0, sticky=tk.W)
            self.tip_widgets[i]['distance'] = tk.DoubleVar(value=random.uniform(0, 10))
            distance_spin = ttk.Spinbox(frame, from_=0, to=99.999, increment=0.001, 
                                       textvariable=self.tip_widgets[i]['distance'],
                                       command=lambda i=i: self.update_tip_data(i))
            distance_spin.grid(row=3, column=1, sticky=(tk.W, tk.E))
            
            frame.columnconfigure(1, weight=1)
            
        return tips_frame
        
    def create_progress_tab(self):
        """Create the progress states tab"""
        progress_frame = ttk.Frame(self.notebook, padding="20")
        
        self.progress_widgets = {}
        states = ['home', 'work_position', 'encoder_zero', 'heat', 'cool', 'cycle_complete']
        
        for i, state in enumerate(states):
            # Format state names for display
            display_name = state.replace('_', ' ').title()
            ttk.Label(progress_frame, text=f"{display_name}:").grid(row=i, column=0, sticky=tk.W, pady=5)
            
            self.progress_widgets[state] = tk.IntVar(value=0)
            radio_frame = ttk.Frame(progress_frame)
            radio_frame.grid(row=i, column=1, sticky=tk.W, pady=5)
            
            ttk.Radiobutton(radio_frame, text="Inactive", variable=self.progress_widgets[state], 
                           value=0, command=lambda s=state: self.update_progress_data(s)).pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(radio_frame, text="Active", variable=self.progress_widgets[state], 
                           value=1, command=lambda s=state: self.update_progress_data(s)).pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(radio_frame, text="Done", variable=self.progress_widgets[state], 
                           value=2, command=lambda s=state: self.update_progress_data(s)).pack(side=tk.LEFT, padx=5)
            
        # Set initial states
        self.progress_widgets['home'].set(2)  # Done
        self.progress_widgets['work_position'].set(1)  # Active
        
        return progress_frame
        
    def create_general_tab(self):
        """Create the general UI tab"""
        general_frame = ttk.Frame(self.notebook, padding="20")
        
        # Time
        time_frame = ttk.LabelFrame(general_frame, text="Time", padding="10")
        time_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        ttk.Label(time_frame, text="Minutes:").grid(row=0, column=0, sticky=tk.W)
        self.time_minutes = tk.IntVar(value=0)
        minutes_spin = ttk.Spinbox(time_frame, from_=0, to=999, textvariable=self.time_minutes,
                                  command=self.update_general_data)
        minutes_spin.grid(row=0, column=1, padx=(5, 20))
        
        ttk.Label(time_frame, text="Seconds:").grid(row=0, column=2, sticky=tk.W)
        self.time_seconds = tk.IntVar(value=0)
        seconds_spin = ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.time_seconds,
                                  command=self.update_general_data)
        seconds_spin.grid(row=0, column=3, padx=5)
        
        # Slider
        slider_frame = ttk.LabelFrame(general_frame, text="Slider", padding="10")
        slider_frame.grid(row=1, column=0, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        self.slider_percentage = tk.IntVar(value=50)
        slider_scale = ttk.Scale(slider_frame, from_=0, to=100, variable=self.slider_percentage,
                               command=lambda v: self.update_general_data())
        slider_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.slider_label = ttk.Label(slider_frame, text="50%")
        self.slider_label.grid(row=0, column=1, padx=10)
        
        slider_frame.columnconfigure(0, weight=1)
        
        # Text strings
        text_frame = ttk.LabelFrame(general_frame, text="Text Strings", padding="10")
        text_frame.grid(row=2, column=0, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        ttk.Label(text_frame, text="Banner Text:").grid(row=0, column=0, sticky=tk.W)
        self.banner_text = tk.StringVar(value="USHS System Active")
        banner_entry = ttk.Entry(text_frame, textvariable=self.banner_text, width=40)
        banner_entry.grid(row=0, column=1, padx=5)
        banner_entry.bind('<KeyRelease>', lambda e: self.update_text_data())
        
        ttk.Label(text_frame, text="Processing Text:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.processing_text = tk.StringVar(value="Processing...")
        processing_entry = ttk.Entry(text_frame, textvariable=self.processing_text, width=40)
        processing_entry.grid(row=1, column=1, padx=5, pady=(5, 0))
        processing_entry.bind('<KeyRelease>', lambda e: self.update_text_data())
        
        general_frame.columnconfigure(0, weight=1)
        
        return general_frame
    
    def create_work_position_tab(self):
        """Create the work position control tab"""
        work_frame = ttk.Frame(self.notebook, padding="10")
        
        # Position controls
        pos_frame = ttk.LabelFrame(work_frame, text="Position Control", padding="10")
        pos_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        # Current position
        ttk.Label(pos_frame, text="Current Position (mm):").grid(row=0, column=0, sticky=tk.W)
        self.current_position = tk.DoubleVar(value=0.0)
        current_spin = ttk.Spinbox(pos_frame, from_=0, to=100, increment=0.1, 
                                  textvariable=self.current_position, width=10)
        current_spin.grid(row=0, column=1, padx=5)
        current_spin.bind('<KeyRelease>', lambda e: self.update_work_position_data())
        current_spin.bind('<ButtonRelease-1>', lambda e: self.update_work_position_data())
        
        # Setpoint
        ttk.Label(pos_frame, text="Setpoint (mm):").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.setpoint = tk.DoubleVar(value=0.0)
        setpoint_spin = ttk.Spinbox(pos_frame, from_=0, to=100, increment=0.1, 
                                   textvariable=self.setpoint, width=10)
        setpoint_spin.grid(row=1, column=1, padx=5, pady=(5, 0))
        setpoint_spin.bind('<KeyRelease>', lambda e: self.update_work_position_data())
        setpoint_spin.bind('<ButtonRelease-1>', lambda e: self.update_work_position_data())
        
        # Speed mode
        speed_frame = ttk.LabelFrame(work_frame, text="Speed Mode", padding="10")
        speed_frame.grid(row=0, column=1, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        self.speed_mode = tk.IntVar(value=0)  # 0=rapid, 1=fine
        ttk.Radiobutton(speed_frame, text="Rapid Speed", variable=self.speed_mode, 
                       value=0, command=self.update_work_position_data).pack(anchor=tk.W)
        ttk.Radiobutton(speed_frame, text="Fine Speed", variable=self.speed_mode, 
                       value=1, command=self.update_work_position_data).pack(anchor=tk.W, pady=(5, 0))
        
        # Button states
        button_frame = ttk.LabelFrame(work_frame, text="Button States", padding="10")
        button_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        self.up_button = tk.BooleanVar(value=False)
        self.down_button = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(button_frame, text="Up Button Pressed", 
                       variable=self.up_button, 
                       command=self.update_work_position_data).grid(row=0, column=0, sticky=tk.W)
        ttk.Checkbutton(button_frame, text="Down Button Pressed", 
                       variable=self.down_button, 
                       command=self.update_work_position_data).grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        # Tip distances
        tips_frame = ttk.LabelFrame(work_frame, text="Tip Distances", padding="10")
        tips_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky=(tk.W, tk.E))
        
        self.tip_distances = {}
        
        for i in range(1, 9):
            row = (i - 1) // 4
            col = (i - 1) % 4
            
            ttk.Label(tips_frame, text=f"Tip {i} (mm):").grid(row=row*2, column=col, sticky=tk.W, padx=(10, 5))
            self.tip_distances[i] = tk.DoubleVar(value=0.0)
            
            # Create scale for visual feedback
            scale = ttk.Scale(tips_frame, from_=0, to=8, orient=tk.VERTICAL, 
                            variable=self.tip_distances[i], length=100,
                            command=lambda v, tip=i: self.update_tip_distance(tip))
            scale.grid(row=row*2+1, column=col, padx=(10, 5), pady=(5, 10))
            
            # Display value
            label = ttk.Label(tips_frame, text="0.0")
            label.grid(row=row*2+2, column=col, padx=(10, 5))
            
            # Store label for updates
            setattr(self, f'tip_{i}_distance_label', label)
        
        work_frame.columnconfigure(0, weight=1)
        work_frame.columnconfigure(1, weight=1)
        
        return work_frame
        
    def create_log_tab(self):
        """Create the log display tab"""
        log_frame = ttk.Frame(self.notebook, padding="10")
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        button_frame = ttk.Frame(log_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(button_frame, text="Auto-scroll", variable=self.autoscroll_var).pack(side=tk.LEFT, padx=5)
        
        return log_frame
        
    def initialize_data(self):
        """Initialize the Modbus data store"""
        # Create data blocks
        # Using a large block to cover all our addresses (0-1300)
        block = ModbusSequentialDataBlock(0, [0] * 1300)
        
        self.data_store = ModbusSlaveContext(
            di=block,
            co=block,
            hr=block,  # Holding registers - main data store
            ir=block
        )
        
        self.context = ModbusServerContext(slaves={self.slave_id: self.data_store}, single=False)
        
        # Initialize with current GUI values
        self.update_all_modbus_data()
        
    def update_all_modbus_data(self):
        """Update all Modbus registers from GUI values"""
        if not self.data_store:
            return
            
        # Update system config
        self.data_store.setValues(3, SYSTEM_CONFIG['baudrate'], [self.baudrate_var.get()])
        parity_map = {'N': 0, 'E': 1, 'O': 2}
        self.data_store.setValues(3, SYSTEM_CONFIG['parity'], [parity_map[self.parity_var.get()]])
        self.data_store.setValues(3, SYSTEM_CONFIG['stopbits'], [self.stopbits_var.get()])
        self.data_store.setValues(3, SYSTEM_CONFIG['bytesize'], [self.bytesize_var.get()])
        self.data_store.setValues(3, SYSTEM_CONFIG['slave_id'], [self.slave_id_var.get()])
        self.data_store.setValues(3, SYSTEM_CONFIG['update_rate'], [self.update_rate_var.get()])
        
        # Update all tips
        for i in range(1, 9):
            self.update_tip_data(i)
            
        # Update progress states
        for state in self.progress_widgets:
            self.update_progress_data(state)
            
        # Update general UI
        self.update_general_data()
        
        # Update text data
        self.update_text_data()
        
        # Update work position data
        self.update_work_position_data()
        
        # Update all tip distances
        for i in range(1, 9):
            self.update_tip_distance(i)
        
    def update_tip_data(self, tip_num):
        """Update Modbus registers for a specific tip"""
        if not self.data_store or tip_num not in self.tip_widgets:
            return
            
        widgets = self.tip_widgets[tip_num]
        
        # Update active state
        addr = get_tip_address(tip_num, 'active')
        self.data_store.setValues(3, addr, [1 if widgets['active'].get() else 0])
        
        # Update progress
        addr = get_tip_address(tip_num, 'progress')
        progress = widgets['progress'].get()
        self.data_store.setValues(3, addr, [progress])
        widgets['progress_label'].config(text=f"{progress}%")
        
        # Update joules (scaled by 10)
        addr = get_tip_address(tip_num, 'joules')
        joules = int(widgets['joules'].get() * 10)
        self.data_store.setValues(3, addr, [joules])
        
        # Update distance (32-bit, scaled by 1000)
        addr = get_tip_address(tip_num, 'distance')
        distance_regs = float_to_registers(widgets['distance'].get(), 1000)
        self.data_store.setValues(3, addr, distance_regs)
        
        self.log(f"Updated Tip {tip_num} data")
        
    def update_progress_data(self, state_name):
        """Update Modbus register for a progress state"""
        if not self.data_store or state_name not in self.progress_widgets:
            return
            
        addr = get_progress_address(state_name)
        value = self.progress_widgets[state_name].get()
        self.data_store.setValues(3, addr, [value])
        
        self.log(f"Updated progress state '{state_name}' to {value}")
        
    def update_general_data(self):
        """Update general UI Modbus registers"""
        if not self.data_store:
            return
            
        # Update time
        addr = get_general_ui_address('time_minutes')
        self.data_store.setValues(3, addr, [self.time_minutes.get()])
        
        addr = get_general_ui_address('time_seconds')
        self.data_store.setValues(3, addr, [self.time_seconds.get()])
        
        # Update slider
        addr = get_general_ui_address('slider_percentage')
        percentage = int(self.slider_percentage.get())
        self.data_store.setValues(3, addr, [percentage])
        self.slider_label.config(text=f"{percentage}%")
        
        self.log("Updated general UI data")
        
    def update_text_data(self):
        """Update text string Modbus registers"""
        if not self.data_store:
            return
            
        # Update banner text
        addr = TEXT_STRINGS['banner_text']
        registers = string_to_registers(self.banner_text.get())
        self.data_store.setValues(3, addr, registers)
        
        # Update processing text
        addr = TEXT_STRINGS['processing_text']
        registers = string_to_registers(self.processing_text.get())
        self.data_store.setValues(3, addr, registers)
        
        self.log("Updated text data")
    
    def update_work_position_data(self):
        """Update work position Modbus registers"""
        if not self.data_store:
            return
        
        # Update current position
        addr = get_work_position_address('current_position')
        registers = float_to_registers(self.current_position.get(), 100)  # Scale by 100
        self.data_store.setValues(3, addr, registers)
        
        # Update setpoint
        addr = get_work_position_address('setpoint')
        registers = float_to_registers(self.setpoint.get(), 100)
        self.data_store.setValues(3, addr, registers)
        
        # Update speed mode
        addr = get_work_position_address('speed_mode')
        self.data_store.setValues(3, addr, [self.speed_mode.get()])
        
        # Update button states
        addr = get_work_position_address('up_button_state')
        self.data_store.setValues(3, addr, [1 if self.up_button.get() else 0])
        
        addr = get_work_position_address('down_button_state')
        self.data_store.setValues(3, addr, [1 if self.down_button.get() else 0])
        
        self.log("Updated work position data")
    
    def update_tip_distance(self, tip_number):
        """Update individual tip distance"""
        if not self.data_store:
            return
        
        distance = self.tip_distances[tip_number].get()
        
        # Update the label
        label = getattr(self, f'tip_{tip_number}_distance_label')
        label.config(text=f"{distance:.1f}")
        
        # Update Modbus registers
        addr = get_work_position_tip_distance_address(tip_number)
        registers = float_to_registers(distance, 100)  # Scale by 100
        self.data_store.setValues(3, addr, registers)
        
        self.log(f"Updated tip {tip_number} distance: {distance:.1f} mm")
        
    def toggle_server(self):
        """Start or stop the Modbus server"""
        if not self.server_running:
            self.start_server()
        else:
            self.stop_server()
            
    def start_server(self):
        """Start the Modbus RTU server"""
        try:
            # Update configuration
            self.serial_config['port'] = self.port_var.get()
            self.serial_config['baudrate'] = self.baudrate_var.get()
            self.serial_config['bytesize'] = self.bytesize_var.get()
            self.serial_config['parity'] = self.parity_var.get()
            self.serial_config['stopbits'] = self.stopbits_var.get()
            self.slave_id = self.slave_id_var.get()
            self.update_rate = self.update_rate_var.get()
            
            # Reinitialize data store with new slave ID if needed
            self.initialize_data()
            
            # Start server in separate thread
            self.stop_event.clear()
            self.server_thread = threading.Thread(target=self.run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Start update thread
            self.update_thread = threading.Thread(target=self.update_loop)
            self.update_thread.daemon = True
            self.update_thread.start()
            
            self.server_running = True
            self.start_button.config(text="Stop Server")
            self.status_label.config(text=f"Server Running on {self.serial_config['port']}", foreground="green")
            
            self.log(f"Server started on {self.serial_config['port']} at {self.serial_config['baudrate']} baud")
            
        except Exception as e:
            messagebox.showerror("Server Error", f"Failed to start server: {str(e)}")
            self.log(f"ERROR: Failed to start server: {str(e)}")
            
    def stop_server(self):
        """Stop the Modbus server"""
        self.stop_event.set()
        self.server_running = False
        
        # Wait for threads to stop
        if self.server_thread:
            self.server_thread.join(timeout=2)
        if self.update_thread:
            self.update_thread.join(timeout=2)
            
        self.start_button.config(text="Start Server")
        self.status_label.config(text="Server Stopped", foreground="red")
        
        self.log("Server stopped")
        
    def run_server(self):
        """Run the Modbus server (in separate thread)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def serve():
            try:
                # Create and configure the server
                server = await StartAsyncSerialServer(
                    context=self.context,
                    framer=ModbusRtuFramer,
                    port=self.serial_config['port'],
                    baudrate=self.serial_config['baudrate'],
                    bytesize=self.serial_config['bytesize'],
                    parity=self.serial_config['parity'],
                    stopbits=self.serial_config['stopbits'],
                    timeout=self.serial_config['timeout']
                )
                
                # Run until stop event
                while not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
                    
                # Shutdown server
                await server.shutdown()
                
            except Exception as e:
                self.log(f"Server error: {str(e)}")
                
        loop.run_until_complete(serve())
        loop.close()
        
    def update_loop(self):
        """Update loop for refreshing data at specified rate"""
        last_update = time.time()
        update_interval = 1.0 / self.update_rate
        
        while not self.stop_event.is_set():
            current_time = time.time()
            
            if current_time - last_update >= update_interval:
                # Read work position data from Modbus and update GUI
                self.read_work_position_from_modbus()
                
                # Update all Modbus data
                self.update_all_modbus_data()
                last_update = current_time
                
            time.sleep(0.001)  # Small sleep to prevent CPU hogging
    
    def read_work_position_from_modbus(self):
        """Read work position data from Modbus registers and update GUI"""
        if not self.data_store:
            return
            
        try:
            # Read speed mode
            addr = get_work_position_address('speed_mode')
            value = self.data_store.getValues(3, addr, 1)[0]
            if value != self.speed_mode.get():
                self.speed_mode.set(value)
                # Trigger UI update for radio buttons
                self.master.update_idletasks()
            
            # Read button states (momentary buttons)
            addr = get_work_position_address('up_button_state')
            value = self.data_store.getValues(3, addr, 1)[0]
            current_state = self.up_button.get()
            if bool(value) != current_state:
                self.up_button.set(bool(value))
                # Force UI update for better responsiveness
                self.master.update_idletasks()
            
            addr = get_work_position_address('down_button_state')
            value = self.data_store.getValues(3, addr, 1)[0]
            current_state = self.down_button.get()
            if bool(value) != current_state:
                self.down_button.set(bool(value))
                # Force UI update for better responsiveness
                self.master.update_idletasks()
                
        except Exception as e:
            # Silently ignore errors to avoid spamming logs
            pass
            
    def randomize_all(self):
        """Randomize all values"""
        # Randomize tips
        for i in range(1, 9):
            widgets = self.tip_widgets[i]
            widgets['active'].set(random.choice([True, False]))
            widgets['progress'].set(random.randint(0, 100))
            widgets['joules'].set(round(random.uniform(0, 100), 1))
            widgets['distance'].set(round(random.uniform(0, 10), 3))
            
        # Randomize progress states
        for state in self.progress_widgets:
            self.progress_widgets[state].set(random.randint(0, 2))
            
        # Randomize general UI
        self.time_minutes.set(random.randint(0, 59))
        self.time_seconds.set(random.randint(0, 59))
        self.slider_percentage.set(random.randint(0, 100))
        
        # Randomize work position data
        self.current_position.set(round(random.uniform(0, 50), 1))
        self.setpoint.set(round(random.uniform(0, 50), 1))
        self.speed_mode.set(random.randint(0, 1))
        
        # Randomize tip distances
        for i in range(1, 9):
            self.tip_distances[i].set(round(random.uniform(0, 8), 1))
            self.update_tip_distance(i)
        
        # Update all data
        self.update_all_modbus_data()
        
    def reset_all(self):
        """Reset all values to defaults"""
        # Reset tips
        for i in range(1, 9):
            widgets = self.tip_widgets[i]
            widgets['active'].set(True if i <= 4 else False)
            widgets['progress'].set(0)
            widgets['joules'].set(0.0)
            widgets['distance'].set(0.0)
            
        # Reset progress states
        for state in self.progress_widgets:
            self.progress_widgets[state].set(0)
        self.progress_widgets['home'].set(2)
        self.progress_widgets['work_position'].set(1)
        
        # Reset general UI
        self.time_minutes.set(0)
        self.time_seconds.set(0)
        self.slider_percentage.set(50)
        self.banner_text.set("USHS System Active")
        self.processing_text.set("Processing...")
        
        # Reset work position data
        self.current_position.set(0.0)
        self.setpoint.set(0.0)
        self.speed_mode.set(0)  # Rapid
        self.up_button.set(False)
        self.down_button.set(False)
        
        # Reset tip distances
        for i in range(1, 9):
            self.tip_distances[i].set(0.0)
            self.update_tip_distance(i)
        
        # Update all data
        self.update_all_modbus_data()
        
    def save_config(self):
        """Save current configuration to file"""
        config = {
            'serial': self.serial_config,
            'slave_id': self.slave_id,
            'update_rate': self.update_rate,
            'tips': {},
            'progress_states': {},
            'general_ui': {
                'time_minutes': self.time_minutes.get(),
                'time_seconds': self.time_seconds.get(),
                'slider_percentage': self.slider_percentage.get(),
                'banner_text': self.banner_text.get(),
                'processing_text': self.processing_text.get()
            }
        }
        
        # Save tip data
        for i in range(1, 9):
            widgets = self.tip_widgets[i]
            config['tips'][i] = {
                'active': widgets['active'].get(),
                'progress': widgets['progress'].get(),
                'joules': widgets['joules'].get(),
                'distance': widgets['distance'].get()
            }
            
        # Save progress states
        for state in self.progress_widgets:
            config['progress_states'][state] = self.progress_widgets[state].get()
            
        # Write to file
        try:
            with open('modbus_slave_config.json', 'w') as f:
                json.dump(config, f, indent=2)
            self.log("Configuration saved to modbus_slave_config.json")
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
            
    def load_config(self):
        """Load configuration from file"""
        try:
            with open('modbus_slave_config.json', 'r') as f:
                config = json.load(f)
                
            # Load serial config
            if 'serial' in config:
                self.serial_config.update(config['serial'])
                self.port_var.set(self.serial_config['port'])
                self.baudrate_var.set(self.serial_config['baudrate'])
                self.bytesize_var.set(self.serial_config['bytesize'])
                self.parity_var.set(self.serial_config['parity'])
                self.stopbits_var.set(self.serial_config['stopbits'])
                
            # Load slave config
            if 'slave_id' in config:
                self.slave_id_var.set(config['slave_id'])
            if 'update_rate' in config:
                self.update_rate_var.set(config['update_rate'])
                
            # Load tip data
            if 'tips' in config:
                for i, tip_data in config['tips'].items():
                    i = int(i)
                    if i in self.tip_widgets:
                        widgets = self.tip_widgets[i]
                        widgets['active'].set(tip_data['active'])
                        widgets['progress'].set(tip_data['progress'])
                        widgets['joules'].set(tip_data['joules'])
                        widgets['distance'].set(tip_data['distance'])
                        
            # Load progress states
            if 'progress_states' in config:
                for state, value in config['progress_states'].items():
                    if state in self.progress_widgets:
                        self.progress_widgets[state].set(value)
                        
            # Load general UI
            if 'general_ui' in config:
                gui = config['general_ui']
                self.time_minutes.set(gui.get('time_minutes', 0))
                self.time_seconds.set(gui.get('time_seconds', 0))
                self.slider_percentage.set(gui.get('slider_percentage', 50))
                self.banner_text.set(gui.get('banner_text', "USHS System Active"))
                self.processing_text.set(gui.get('processing_text', "Processing..."))
                
            # Update all data
            self.update_all_modbus_data()
            
            self.log("Configuration loaded from modbus_slave_config.json")
            messagebox.showinfo("Success", "Configuration loaded successfully!")
            
        except FileNotFoundError:
            messagebox.showerror("Error", "Configuration file not found!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")
            
    def log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        
        if self.autoscroll_var.get():
            self.log_text.see(tk.END)
            
    def clear_log(self):
        """Clear the log text"""
        self.log_text.delete(1.0, tk.END)
        
    def on_closing(self):
        """Handle window closing"""
        if self.server_running:
            result = messagebox.askyesno("Confirm Exit", 
                                       "Server is still running. Stop server and exit?")
            if result:
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()
            
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


if __name__ == "__main__":
    app = ModbusSlaveGUI()
    app.run()