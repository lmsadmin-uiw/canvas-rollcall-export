#!/bin/bash
# =============================================================================
# Canvas Roll Call Attendance Export - Linux Server Setup Script
# =============================================================================
# This script installs all dependencies required to run the attendance export
# script on a Linux server (Ubuntu/Debian).
#
# Run with: sudo bash setup_server.sh
#
# What this script installs:
#   - Python 3 and pip (if not already installed)
#   - Google Chrome (stable)
#   - ChromeDriver (matching Chrome version)
#   - Python packages: requests, selenium
#
# Author: Jon Whitney, Office of Teaching, Learning & Technology
# Institution: University of the Incarnate Word
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "  Canvas Attendance Export - Server Setup"
echo "============================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (use sudo)${NC}"
    echo "Usage: sudo bash setup_server.sh"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
    echo -e "${GREEN}Detected OS:${NC} $PRETTY_NAME"
else
    echo -e "${RED}ERROR: Cannot detect OS. This script supports Ubuntu/Debian.${NC}"
    exit 1
fi

# Verify supported OS
if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
    echo -e "${YELLOW}WARNING: This script is designed for Ubuntu/Debian.${NC}"
    echo "You may need to modify commands for your distribution."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "------------------------------------------------------------"
echo "Step 1: Updating package lists..."
echo "------------------------------------------------------------"
apt-get update

echo ""
echo "------------------------------------------------------------"
echo "Step 2: Installing Python 3 and pip..."
echo "------------------------------------------------------------"
apt-get install -y python3 python3-pip python3-venv

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}Installed:${NC} $PYTHON_VERSION"

echo ""
echo "------------------------------------------------------------"
echo "Step 3: Installing Google Chrome..."
echo "------------------------------------------------------------"

# Check if Chrome is already installed
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo -e "${GREEN}Chrome already installed:${NC} $CHROME_VERSION"
else
    echo "Downloading Google Chrome..."
    
    # Install dependencies
    apt-get install -y wget gnupg
    
    # Add Google's signing key
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
    
    # Add Chrome repository
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
    
    # Install Chrome
    apt-get update
    apt-get install -y google-chrome-stable
    
    CHROME_VERSION=$(google-chrome --version)
    echo -e "${GREEN}Installed:${NC} $CHROME_VERSION"
fi

echo ""
echo "------------------------------------------------------------"
echo "Step 4: Installing ChromeDriver..."
echo "------------------------------------------------------------"

# Get Chrome major version
CHROME_MAJOR_VERSION=$(google-chrome --version | grep -oP '\d+' | head -1)
echo "Chrome major version: $CHROME_MAJOR_VERSION"

# For Chrome 115+, use the new Chrome for Testing endpoints
if [ "$CHROME_MAJOR_VERSION" -ge 115 ]; then
    echo "Using Chrome for Testing API for ChromeDriver..."
    
    # Get the latest ChromeDriver version for this Chrome version
    CHROMEDRIVER_URL="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR_VERSION}"
    CHROMEDRIVER_VERSION=$(curl -s "$CHROMEDRIVER_URL")
    
    if [ -z "$CHROMEDRIVER_VERSION" ]; then
        echo -e "${YELLOW}Could not find exact match, trying latest stable...${NC}"
        CHROMEDRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE")
    fi
    
    echo "ChromeDriver version: $CHROMEDRIVER_VERSION"
    
    # Download ChromeDriver
    DOWNLOAD_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip"
    
    echo "Downloading from: $DOWNLOAD_URL"
    apt-get install -y unzip
    wget -q -O /tmp/chromedriver.zip "$DOWNLOAD_URL"
    
    # Extract and install
    unzip -o /tmp/chromedriver.zip -d /tmp/
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/
    chmod +x /usr/local/bin/chromedriver
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64
    
else
    # For older Chrome versions, use the old endpoint
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR_VERSION}")
    
    echo "ChromeDriver version: $CHROMEDRIVER_VERSION"
    
    wget -q -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
    unzip -o /tmp/chromedriver.zip -d /usr/local/bin/
    chmod +x /usr/local/bin/chromedriver
    rm /tmp/chromedriver.zip
fi

# Verify ChromeDriver installation
CHROMEDRIVER_INSTALLED=$(chromedriver --version)
echo -e "${GREEN}Installed:${NC} $CHROMEDRIVER_INSTALLED"

echo ""
echo "------------------------------------------------------------"
echo "Step 5: Installing Python packages..."
echo "------------------------------------------------------------"

# Install Python packages globally (for cron compatibility)
# --ignore-installed handles cases where system packages conflict with pip
pip3 install --break-system-packages --ignore-installed requests selenium

# Verify installations
echo ""
echo "Verifying Python packages..."
python3 -c "import requests; print(f'  requests: {requests.__version__}')"
python3 -c "import selenium; print(f'  selenium: {selenium.__version__}')"

echo ""
echo "------------------------------------------------------------"
echo "Step 6: Setting up script directory..."
echo "------------------------------------------------------------"

# Create directory for the script if it doesn't exist
SCRIPT_DIR="/opt/canvas-attendance"
if [ ! -d "$SCRIPT_DIR" ]; then
    mkdir -p "$SCRIPT_DIR"
    echo -e "${GREEN}Created directory:${NC} $SCRIPT_DIR"
else
    echo -e "${GREEN}Directory exists:${NC} $SCRIPT_DIR"
fi

# Set permissions
chmod 755 "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo -e "${GREEN}  SETUP COMPLETE!${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Copy your attendance_export.py script to:"
echo "     $SCRIPT_DIR/attendance_export.py"
echo ""
echo "  2. Add your API credentials to the script:"
echo "     - ADMIN_API_TOKEN"
echo "     - USER_ID"
echo ""
echo "  3. Test the script manually:"
echo "     python3 $SCRIPT_DIR/attendance_export.py"
echo ""
echo "  4. Set up the cron job (run: crontab -e):"
echo "     # Run daily at 6:00 AM"
echo "     0 6 * * * /usr/bin/python3 $SCRIPT_DIR/attendance_export.py >> $SCRIPT_DIR/attendance.log 2>&1"
echo ""
echo "------------------------------------------------------------"
echo "Installed versions:"
echo "------------------------------------------------------------"
echo "  Python:       $(python3 --version 2>&1 | cut -d' ' -f2)"
echo "  Chrome:       $(google-chrome --version | cut -d' ' -f3)"
echo "  ChromeDriver: $(chromedriver --version | cut -d' ' -f2)"
echo "  requests:     $(python3 -c 'import requests; print(requests.__version__)')"
echo "  selenium:     $(python3 -c 'import selenium; print(selenium.__version__)')"
echo "------------------------------------------------------------"
echo ""
