#!/usr/bin/env bash
#
# sleepy-linux — installer (v3)
#
#   user service   sleepy-listener   lock/unlock + monitor wake/sleep
#   system service sleepy-shutdown   TV+RGB off on shutdown   [default ON]
#   system service sleepy-suspend    TV+RGB off on suspend    [default ON]
#   system service sleepy-boot       TV+RGB on  at boot       [default ON]
#
# Idempotent. Existing sleepy.conf + key file are preserved.
#
set -euo pipefail

SLEEPY_HOME="${SLEEPY_HOME:-$HOME/.local/share/sleepy}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UID_NUM="$(id -u)"
GID_NUM="$(id -g)"

echo "==> sleepy-linux installer (v3)"
echo "    repo   : $REPO_DIR"
echo "    target : $SLEEPY_HOME"
echo

# --- 1. Dependencies ---
echo "==> Checking dependencies..."
need=0
for cmd in python3 openrgb gdbus; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "    [ok] $cmd"
  else
    echo "    [MISSING] $cmd"; need=1
  fi
done
if python3 -m venv --help >/dev/null 2>&1; then
  echo "    [ok] python3-venv"
else
  echo "    [MISSING] python3-venv"; need=1
fi
if [ "$need" -eq 1 ]; then
  echo; echo "Install the missing packages (CachyOS/Arch):"
  echo "    sudo pacman -S python python-venv openrgb glib2"
  echo "then re-run this installer."; exit 1
fi

# --- 2. Layout ---
echo "==> Preparing $SLEEPY_HOME ..."
mkdir -p "$SLEEPY_HOME/sleepy" "$HOME/.local/bin"

# --- 3. Virtualenv + bscpylgtv ---
if [ ! -x "$SLEEPY_HOME/venv/bin/python" ]; then
  echo "==> Creating virtualenv (system-site-packages)..."
  python3 -m venv --system-site-packages "$SLEEPY_HOME/venv"
fi
echo "==> Ensuring bscpylgtv in venv..."
"$SLEEPY_HOME/venv/bin/python" -m pip install --quiet bscpylgtv
[ -x "$SLEEPY_HOME/venv/bin/bscpylgtvcommand" ] || { echo "    [ERROR] bscpylgtvcommand missing"; exit 1; }
echo "    [ok] bscpylgtvcommand"

# --- 4. Key file (user-owned, never overwritten) ---
KEYFILE="$SLEEPY_HOME/keys.sqlite"
if [ ! -e "$KEYFILE" ]; then
  if [ -f /opt/sleepy-linux/.aiopylgtv.sqlite ]; then
    echo "==> Rescuing v1 key file from /opt/sleepy-linux ..."
    cp /opt/sleepy-linux/.aiopylgtv.sqlite "$KEYFILE"
  else
    echo "==> Creating new key file (pair with the TV on first use)."
    : > "$KEYFILE"
  fi
  chown "$UID_NUM:$GID_NUM" "$KEYFILE"; chmod 600 "$KEYFILE"
else
  echo "==> Keeping existing key file"
fi

# --- 5. Config ---
CONF="$SLEEPY_HOME/sleepy.conf"
if [ ! -e "$CONF" ]; then
  if [ -f "$REPO_DIR/sleepy.conf" ]; then
    cp "$REPO_DIR/sleepy.conf" "$CONF"
  else
    cat > "$CONF" <<'EOF'
# sleepy.conf — single source of truth
TV_IP=10.10.20.25
TV_MAC=20:28:bc:71:fd:56
WOL_REPEATS=3
WOL_INTERVAL_MS=250
OPENRGB_BIN=openrgb
RGB_ON_PROFILE=On
RGB_OFF_PROFILE=Off
GUARD_SECONDS=4
EOF
  fi
  echo "==> Created $CONF"
  echo "    *** EDIT TV_IP to your TV's real address before testing ***"
else
  echo "==> Keeping existing $CONF"
fi

# --- 6. Code ---
echo "==> Installing code..."
cp "$REPO_DIR/sleepy/ctl.py"      "$SLEEPY_HOME/sleepy/ctl.py"
cp "$REPO_DIR/sleepy-listener.py" "$SLEEPY_HOME/sleepy-listener.py"
cp "$REPO_DIR/sleepy-ctl"         "$SLEEPY_HOME/sleepy-ctl"
chmod +x "$SLEEPY_HOME/sleepy-ctl"
chown "$UID_NUM:$GID_NUM" \
  "$SLEEPY_HOME/sleepy/ctl.py" \
  "$SLEEPY_HOME/sleepy-listener.py" \
  "$SLEEPY_HOME/sleepy-ctl"

# --- 7. sleepy-ctl on PATH ---
ln -sf "$SLEEPY_HOME/sleepy-ctl" "$HOME/.local/bin/sleepy-ctl"
echo "==> Linked sleepy-ctl -> $HOME/.local/bin/sleepy-ctl"

# --- 8. User service: listener (enable AND start) ---
echo "==> Installing user service sleepy-listener ..."
install -Dm644 "$REPO_DIR/sleepy-listener.service" \
  "$HOME/.config/systemd/user/sleepy-listener.service"
systemctl --user daemon-reload
systemctl --user enable sleepy-listener.service
systemctl --user start  sleepy-listener.service
echo "    [ok] listener enabled + started"

# --- 9. System services (default ON) ---
echo "==> Installing system services (default ON)..."
for unit in sleepy-shutdown sleepy-suspend sleepy-boot; do
  sudo install -Dm644 "$REPO_DIR/$unit.service" "/etc/systemd/system/$unit.service"
  sudo systemctl enable "$unit.service"
  echo "    [ok] $unit.service enabled"
done
sudo systemctl daemon-reload

# --- 10. fish PATH hint ---
if ! grep -q "fish_add_path" "$HOME/.config/fish/config.fish" 2>/dev/null; then
  echo; echo "NOTE: if 'sleepy-ctl' isn't found in fish, run once:"
  echo "    fish_add_path ~/.local/bin"
fi

echo
echo "==> DONE"
echo "    1. Edit TV_IP in $CONF if it's not your TV"
echo "    2. Verify:   sleepy-ctl detect"
echo "    3. Live:     sleepy-ctl test"
echo "    4. Lock (Super+L) / unlock to see it work"
echo
echo "    Default-on services — disable any you don't want:"
echo "      sudo systemctl disable sleepy-shutdown.service"
echo "      sudo systemctl disable sleepy-suspend.service"
echo "      sudo systemctl disable sleepy-boot.service"