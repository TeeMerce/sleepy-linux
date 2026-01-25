#!/bin/bash
# Sleepy Linux - Installer (Python Edition)
# Usage: ./install.sh <TV_IP_ADDRESS>

set -e

# === CONFIGURATION ===
TV_IP="$1"
INSTALL_PATH="/opt/sleepy-linux"
SERVICE_PATH="/etc/systemd/system"
USER_SERVICE_PATH="$HOME/.config/systemd/user"
MAC="20:28:bc:71:fd:56" 

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# === PRE-FLIGHT CHECKS ===
if [ -z "$TV_IP" ]; then 
    echo -e "${RED}Usage: $0 <TV_IP_ADDRESS>${NC}"
    exit 1
fi

if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Do NOT run as root. Run as your normal user.${NC}"
   exit 1
fi

echo -e "${BLUE}=== Installing Sleepy Linux (Python Edition) ===${NC}"

# 1. Install Dependencies (Arch/CachyOS)
if command -v pacman &> /dev/null; then
    echo -e "${BLUE}Checking system dependencies...${NC}"
    # python-gobject is required for the listener
    if ! pacman -Qi python-gobject >/dev/null 2>&1; then
        echo "Installing python-gobject..."
        sudo pacman -S --noconfirm --needed python-gobject
    fi
    # wakeonlan
    if ! command -v wakeonlan &> /dev/null; then
        echo "Installing wakeonlan..."
        sudo pacman -S --noconfirm --needed wakeonlan
    fi
fi

# 2. Clean Old Installs
sudo rm -rf "$INSTALL_PATH"
sudo mkdir -p "$INSTALL_PATH"
sudo chown "$USER:$USER" "$INSTALL_PATH"

# 3. Python VENV (for bscpylgtv)
echo -e "${BLUE}Installing bscpylgtv...${NC}"
python3 -m venv "$INSTALL_PATH/venv"
"$INSTALL_PATH/venv/bin/pip" install --upgrade pip bscpylgtv >/dev/null 2>&1

# 4. Install Control Script (sleepy-ctl)
echo -e "${BLUE}Installing sleepy-ctl...${NC}"
cp sleepy-ctl "$INSTALL_PATH/sleepy-ctl"
WOL_CMD="/usr/bin/wakeonlan -i $TV_IP $MAC"
sed -i "s|REPLACE_IP|$TV_IP|g" "$INSTALL_PATH/sleepy-ctl"
sed -i "s|REPLACE_WOL|$WOL_CMD|g" "$INSTALL_PATH/sleepy-ctl"
chmod +x "$INSTALL_PATH/sleepy-ctl"
sudo ln -sf "$INSTALL_PATH/sleepy-ctl" /usr/local/bin/sleepy-ctl

# 5. Install Python Listener (sleepy-listener.py)
echo -e "${BLUE}Installing Python listener...${NC}"
cp sleepy-listener.py "$INSTALL_PATH/sleepy-listener.py"
chmod +x "$INSTALL_PATH/sleepy-listener.py"

# 6. System Services (Boot/Shutdown)
echo -e "${BLUE}Configuring Boot/Shutdown services...${NC}"
TEMP_DIR=$(mktemp -d)
sed "s|PWR_OFF_CMD|$INSTALL_PATH/sleepy-ctl OFF|g" sleepy-shutdown.service > "$TEMP_DIR/sleepy-shutdown.service"
sed "s|PWR_ON_CMD|$INSTALL_PATH/sleepy-ctl ON|g" sleepy-boot.service > "$TEMP_DIR/sleepy-boot.service"

sudo cp "$TEMP_DIR/sleepy-shutdown.service" "$SERVICE_PATH/"
sudo cp "$TEMP_DIR/sleepy-boot.service" "$SERVICE_PATH/"
sudo systemctl daemon-reload
sudo systemctl enable sleepy-boot.service sleepy-shutdown.service
rm -rf "$TEMP_DIR"

# 7. User Service (The Listener)
echo -e "${BLUE}Configuring User Listener Service...${NC}"
mkdir -p "$USER_SERVICE_PATH"
cp sleepy-listener.service "$USER_SERVICE_PATH/"
sed -i "s|EXEC_PATH|$INSTALL_PATH/sleepy-listener.py|g" "$USER_SERVICE_PATH/sleepy-listener.service"

systemctl --user daemon-reload
systemctl --user enable --now sleepy-listener.service

# 8. Handshake
echo
echo -e "${GREEN}=== PAIRING REQUIRED ===${NC}"
echo "Turn your TV ON manually now."
echo "Press ENTER below, then immediately click 'ACCEPT' on the TV."
read -p "Press Enter..."
"$INSTALL_PATH/venv/bin/bscpylgtvcommand" -p "$INSTALL_PATH/.aiopylgtv.sqlite" "$TV_IP" button INFO >/dev/null 2>&1 || true

echo
echo -e "${GREEN}Sleepy Linux Installed! 💤${NC}"