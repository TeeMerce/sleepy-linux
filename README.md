# Sleepy Linux 💤

**Sleepy Linux** is an automated power manager for Linux workstations that use LG WebOS TVs as monitors. It handles the "Sleep" and "Wake" cycles intelligently and syncs your RGB lighting to match.

**Features:**
* **Instant Wake:** Wakes the TV immediately when you move your mouse or unlock.
* **Smart Sleep:** Powers off the TV when the screen locks or the system sleeps.
* **RGB Sync:** Automatically switches OpenRGB profiles (e.g., "On" vs "Off") to match the system state.
* **Boot/Shutdown:** Ensures the TV is on when you boot and off when you shut down.
* **Robust:** Uses Systemd User Services for reliability and "Unicast" Wake-on-LAN to prevent network issues.

## Requirements
* **OS:** Linux (Arch, Fedora, Ubuntu, Debian)
* **TV:** LG WebOS TV (Ethernet recommended)
* **Deps:** `python3`, `wakeonlan` (or `ether-wake`), `openrgb` (optional)

## Installation

1.  **Clone:**
    ```bash
    git clone [https://github.com/TeeMerce/sleepy-linux.git](https://github.com/TeeMerce/sleepy-linux.git)
    cd sleepy-linux
    ```

2.  **Install:**
    ```bash
    ./install.sh <TV_IP_ADDRESS>
    # Example: ./install.sh 10.10.10.12
    ```

3.  **Pair:**
    * The script will ask you to pair. Press **Enter** in the terminal, then click **Accept** on the TV.

## Commands

* **Manual Control:**
    ```bash
    sleepy-ctl ON
    sleepy-ctl OFF
    ```
* **Check Status:**
    ```bash
    systemctl --user status sleepy-listener
    ```

## Uninstall
```bash
./uninstall.sh