#!/bin/bash

# USHS Screens - Raspbian OS Setup Script
# This script installs all dependencies needed to run the USHS Screens application
# on a fresh Raspbian OS installation.
#
# Usage: ./setup_raspbian.sh
# Run this script from the USHS_Screens directory after cloning the repository

set -e  # Exit on any error

echo "=============================================="
echo "USHS Screens - Raspbian OS Setup Script"
echo "=============================================="

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

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root. Run as regular user with sudo privileges."
    exit 1
fi

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    print_error "package.json not found. Please run this script from the USHS_Screens directory."
    exit 1
fi

print_status "Starting setup process for Raspbian OS..."

# 1. Update system packages
print_status "Updating system package lists..."
sudo apt update
print_success "Package lists updated"

# 2. Install Node.js and npm
print_status "Installing Node.js and npm..."

# Check if Node.js is already installed and get version
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_warning "Node.js is already installed: $NODE_VERSION"
    
    # Check if version is compatible (v16 or higher recommended for Electron)
    NODE_MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
    if [ "$NODE_MAJOR_VERSION" -lt 16 ]; then
        print_warning "Node.js version is too old. Installing newer version..."
        # Remove old version
        sudo apt remove -y nodejs npm
        INSTALL_NODE=true
    else
        print_success "Node.js version is compatible"
        INSTALL_NODE=false
    fi
else
    INSTALL_NODE=true
fi

if [ "$INSTALL_NODE" = true ]; then
    # Install Node.js 18.x LTS (recommended for Raspberry Pi)
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
    
    # Verify installation
    if command -v node &> /dev/null && command -v npm &> /dev/null; then
        NODE_VERSION=$(node --version)
        NPM_VERSION=$(npm --version)
        print_success "Node.js installed successfully: $NODE_VERSION"
        print_success "npm installed successfully: $NPM_VERSION"
    else
        print_error "Failed to install Node.js and npm"
        exit 1
    fi
fi

# 3. Install build tools for native modules (serialport, etc.)
print_status "Installing build tools for native module compilation..."
sudo apt install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libudev-dev \
    pkg-config
print_success "Build tools installed successfully"

# 4. Configure npm for native modules
print_status "Configuring npm for native module compilation..."
npm config set python python3
npm install -g node-gyp
print_success "npm configured for native modules"

# 5. Install Xvfb for virtual display (required for Electron in headless mode)
print_status "Installing Xvfb (X Virtual Framebuffer)..."
sudo apt install -y xvfb
print_success "Xvfb installed successfully"

# 6. Install additional dependencies for Electron on Raspberry Pi
print_status "Installing additional dependencies for Electron..."
sudo apt install -y \
    libnss3-dev \
    libatk-bridge2.0-dev \
    libdrm2 \
    libxss1 \
    libgconf-2-4 \
    libxrandr2 \
    libasound2-dev \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo1 \
    libdrm2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0

print_success "Additional Electron dependencies installed"

# 7. Install Python dependencies (if needed for the python controller simulator)
print_status "Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Python virtual environment created"
fi

source venv/bin/activate
if [ -f "python/requirements.txt" ]; then
    pip install -r python/requirements.txt
    print_success "Python dependencies installed"
fi
deactivate

# 8. Install Node.js project dependencies
print_status "Installing Node.js project dependencies..."
npm install
print_success "Node.js dependencies installed successfully"

# 9. Rebuild native modules for ARM architecture
print_status "Rebuilding native modules for Raspberry Pi..."
npm rebuild
print_success "Native modules rebuilt successfully"

# 9.1. Verify serialport installation
print_status "Verifying serialport installation..."
if node -e "require('serialport'); require('@serialport/parser-readline'); console.log('OK')" 2>/dev/null; then
    print_success "Serialport module verified successfully"
else
    print_warning "Serialport verification failed. Attempting to reinstall..."
    npm uninstall serialport @serialport/parser-readline
    npm install serialport@^12.0.0 @serialport/parser-readline@^12.0.0
    npm rebuild
    
    # Test again
    if node -e "require('serialport'); require('@serialport/parser-readline'); console.log('OK')" 2>/dev/null; then
        print_success "Serialport module installed successfully after retry"
    else
        print_error "Failed to install serialport module. Manual intervention may be required."
        echo "You may need to run: npm install --build-from-source serialport"
    fi
fi

# 10. Set up permissions and make scripts executable
print_status "Setting up permissions..."
chmod +x *.sh
if [ -d "scripts" ]; then
    chmod +x scripts/*.sh
fi
print_success "Permissions set"

# 11. Create a launcher script for easy startup
print_status "Creating launcher script..."
cat > start_ushs_headless.sh << 'EOF'
#!/bin/bash

# USHS Screens Headless Launcher
# This script starts the USHS Screens application in headless mode using Xvfb

cd "$(dirname "$0")"

echo "Starting USHS Screens application..."
echo "WebSocket server will be available on port 8080"

# Start with virtual display
xvfb-run -a --server-args="-screen 0 1024x768x24" npm start
EOF

chmod +x start_ushs_headless.sh
print_success "Launcher script created: start_ushs_headless.sh"

# 12. Create a desktop launcher script (if running with desktop environment)
print_status "Creating desktop launcher script..."
cat > start_ushs_desktop.sh << 'EOF'
#!/bin/bash

# USHS Screens Desktop Launcher
# This script starts the USHS Screens application with desktop GUI

cd "$(dirname "$0")"

echo "Starting USHS Screens application with GUI..."

# Check if DISPLAY is set
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

npm start
EOF

chmod +x start_ushs_desktop.sh
print_success "Desktop launcher script created: start_ushs_desktop.sh"

# 13. Final system configuration
print_status "Performing final system configuration..."

# Increase virtual memory for better Electron performance on Pi
if ! grep -q "gpu_mem=64" /boot/config.txt; then
    echo "gpu_mem=64" | sudo tee -a /boot/config.txt
    print_success "GPU memory split configured"
fi

# Enable hardware acceleration if available
if ! grep -q "dtoverlay=vc4-kms-v3d" /boot/config.txt; then
    echo "dtoverlay=vc4-kms-v3d" | sudo tee -a /boot/config.txt
    print_success "Hardware acceleration enabled"
fi

print_success "Setup completed successfully!"

echo ""
echo "=============================================="
echo "SETUP COMPLETE!"
echo "=============================================="
echo ""
echo "Your USHS Screens application is now ready to run."
echo ""
echo "To start the application:"
echo ""
echo "• For headless mode (SSH/no display):"
echo "  ./start_ushs_headless.sh"
echo ""
echo "• For desktop mode (with GUI):"
echo "  ./start_ushs_desktop.sh"
echo ""
echo "• Manual start:"
echo "  npm start                    (requires display)"
echo "  xvfb-run -a npm start       (headless mode)"
echo ""
echo "The WebSocket server will be available on port 8080"
echo ""
echo "Note: Some configuration changes require a reboot to take effect."
echo "Consider rebooting your Raspberry Pi before first use."
echo ""
print_warning "If you encounter any issues, make sure your Raspberry Pi has:"
print_warning "• At least 1GB of RAM (2GB+ recommended)"
print_warning "• Sufficient power supply (3A+ recommended)"
print_warning "• Updated firmware (sudo rpi-update)"
echo ""
print_warning "If you still get 'Cannot find module serialport' errors:"
print_warning "• Try running: npm install --build-from-source serialport"
print_warning "• Or run: npm rebuild"
print_warning "• Make sure build-essential and python3-dev are installed"
print_warning "• Check that node-gyp is properly configured: npm config get python"
echo ""
