#!/bin/bash

# SSH command to connect to Raspberry Pi 5
ssh abc@192.168.19.164

# Optional: Add logging or error handling here
# Example: Check connection success/failure
if [ $? -eq 0 ]; then
    echo "Successfully connected to Raspberry Pi 5"
else
    echo "Failed to connect to Raspberry Pi 5"
fi
