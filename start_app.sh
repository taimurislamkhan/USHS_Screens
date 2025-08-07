#!/bin/bash
# Convenience script to start the app from the root directory
cd "$(dirname "$0")"
./scripts/start_modbus_app.sh "$@"