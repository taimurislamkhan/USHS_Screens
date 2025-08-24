#!/bin/bash

# USHS Screens - Raspbian OS Setup Script
# This script installs all dependencies needed to run the USHS Screens application
# on a fresh Raspbian OS installation.
#
# Usage: ./setup_raspbian.sh
# Run this script from the USHS_Screens directory after cloning the repository
#
# Note: If the script gets stuck on "waiting for cache lock", it means another
# package manager is running. The script will automatically wait and try to
# resolve this, but you can also manually stop interfering processes:
#   sudo systemctl stop unattended-upgrades
#   sudo killall apt apt-get dpkg unattended-upgrade

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

# Function to wait for apt locks and kill interfering processes
wait_for_apt() {
    local max_attempts=60  # Wait up to 5 minutes (60 * 5 seconds)
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then
            print_warning "Package manager is locked. Waiting... (attempt $((attempt + 1))/$max_attempts)"
            
            # Check for common interfering processes
            local blocking_processes=$(ps aux | grep -E "(apt|dpkg|unattended-upgrade)" | grep -v grep | awk '{print $2}')
            
            if [ ! -z "$blocking_processes" ] && [ $attempt -gt 10 ]; then
                print_warning "Found blocking processes. Attempting to stop them..."
                
                # Stop unattended upgrades
                sudo systemctl stop unattended-upgrades >/dev/null 2>&1 || true
                sudo killall unattended-upgrade-shutdown >/dev/null 2>&1 || true
                
                # Wait a bit more after stopping services
                sleep 10
            fi
            
            sleep 5
            attempt=$((attempt + 1))
        else
            return 0  # No locks found
        fi
    done
    
    # If we get here, we've waited too long
    print_error "Could not acquire package manager lock after 5 minutes"
    print_error "Please manually stop any running package managers and try again"
    print_error "You can try: sudo killall apt apt-get dpkg unattended-upgrade"
    return 1
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
wait_for_apt
if ! sudo apt update; then
    print_error "Failed to update package lists"
    exit 1
fi
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
wait_for_apt
if ! sudo apt install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libudev-dev \
    pkg-config \
    socat; then
    print_error "Failed to install build tools"
    exit 1
fi
print_success "Build tools installed successfully"

# 4. Configure npm for native modules
print_status "Configuring npm for native module compilation..."
# Set Python path for node-gyp (newer method)
export npm_config_python=python3
export PYTHON=python3
sudo npm install -g node-gyp
print_success "npm configured for native modules"

# 5. Install Xvfb for virtual display (required for Electron in headless mode)
print_status "Installing Xvfb (X Virtual Framebuffer)..."
wait_for_apt
if ! sudo apt install -y xvfb; then
    print_error "Failed to install Xvfb"
    exit 1
fi
print_success "Xvfb installed successfully"

# 6. Install additional dependencies for Electron on Raspberry Pi
print_status "Installing additional dependencies for Electron..."
wait_for_apt
if ! sudo apt install -y \
    libnss3-dev \
    libatk-bridge2.0-dev \
    libdrm2 \
    libxss1 \
    libxrandr2 \
    libasound2-dev \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libcairo2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libasound2; then
    print_error "Failed to install Electron dependencies"
    exit 1
fi

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
npm install --include=dev
print_success "Node.js dependencies (including Electron) installed successfully"

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
print_warning "If setup gets stuck on 'waiting for cache lock':"
print_warning "• Another package manager process is running"
print_warning "• Stop unattended upgrades: sudo systemctl stop unattended-upgrades"
print_warning "• Kill blocking processes: sudo killall apt apt-get dpkg unattended-upgrade"
print_warning "• Wait for automatic updates to complete, then rerun setup"
echo ""
print_warning "If you still get 'Cannot find module serialport' errors:"
print_warning "• Try running: npm install --build-from-source serialport"
print_warning "• Or run: npm rebuild"
print_warning "• Make sure build-essential and python3-dev are installed"
print_warning "• Check that node-gyp is properly configured: npm config get python"
echo ""
