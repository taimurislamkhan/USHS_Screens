#!/bin/bash

# USHS Screens - Serialport Fix Script
# This script fixes common serialport module issues on Raspberry Pi
#
# Usage: ./fix_serialport.sh
# Run this script if you get "Cannot find module 'serialport'" errors

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=============================================="
echo "USHS Screens - Serialport Fix Script"
echo "=============================================="

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    print_error "package.json not found. Please run this script from the USHS_Screens directory."
    exit 1
fi

# 1. Install build dependencies if missing
print_status "Checking build dependencies..."
if ! dpkg -l | grep -q build-essential; then
    print_status "Installing build-essential..."
    sudo apt update
    sudo apt install -y build-essential python3-dev libudev-dev pkg-config
fi
print_success "Build dependencies are installed"

# 2. Configure npm
print_status "Configuring npm for native modules..."
npm config set python python3
print_success "npm configured"

# 3. Clean npm cache and node_modules
print_status "Cleaning npm cache and node_modules..."
rm -rf node_modules package-lock.json
npm cache clean --force
print_success "Cache cleaned"

# 4. Reinstall dependencies with build from source
print_status "Reinstalling dependencies..."
npm install
npm install --build-from-source serialport
npm install @serialport/parser-readline
print_success "Dependencies reinstalled"

# 5. Rebuild native modules
print_status "Rebuilding native modules..."
npm rebuild
print_success "Native modules rebuilt"

# 6. Test the installation
print_status "Testing serialport installation..."
if node -e "require('serialport'); require('@serialport/parser-readline'); console.log('Serialport modules loaded successfully!')" 2>/dev/null; then
    print_success "Serialport is working correctly!"
    echo ""
    echo "You can now run the application with:"
    echo "  npm start"
    echo ""
else
    print_error "Serialport test failed. Manual troubleshooting required."
    echo ""
    echo "Additional steps you can try:"
    echo "1. Check Node.js version: node --version (should be 16+)"
    echo "2. Check npm version: npm --version"
    echo "3. Check Python version: python3 --version"
    echo "4. Verify gcc is installed: gcc --version"
    echo ""
    echo "For more help, check the troubleshooting documentation."
    exit 1
fi

print_success "Serialport fix completed successfully!"
