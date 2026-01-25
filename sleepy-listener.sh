#!/bin/bash
# Sleepy Linux - Event Listener
# Monitors DBus for Lock/Unlock and Monitor Sleep events.

RGB_BIN=$(command -v openrgb || echo "/usr/bin/openrgb")

# Monitor DBus signals
dbus-monitor --session "type='signal',interface='org.gnome.ScreenSaver',member='ActiveChanged'" \
"type='method_call',interface='org.gnome.Mutter.DisplayConfig',member='SetPowerSaveMode'" | \
while read -r line; do
    
    # EVENT: WAKE (Monitor wakes OR Screen unlocks)
    if echo "$line" | grep -qE "boolean false|uint32 0"; then
        /opt/sleepy-linux/sleepy-ctl ON &
        $RGB_BIN --profile "On" >/dev/null 2>&1 &

    # EVENT: SLEEP (Screen locks)
    elif echo "$line" | grep -q "boolean true"; then
        /opt/sleepy-linux/sleepy-ctl OFF &
        $RGB_BIN --profile "Off" >/dev/null 2>&1 &
    fi
    
done