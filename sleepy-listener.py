#!/usr/bin/env python3
import gi
import subprocess
import shutil

# Ensure we use GObject for DBus
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

# --- CONFIGURATION ---
PATH_CTL = "/opt/sleepy-linux/sleepy-ctl"
PATH_RGB = shutil.which("openrgb") or "/usr/bin/openrgb"

CMD_TV_ON = [PATH_CTL, "ON"]
CMD_TV_OFF = [PATH_CTL, "OFF"]
CMD_RGB_ON = [PATH_RGB, "--profile", "On"]
CMD_RGB_OFF = [PATH_RGB, "--profile", "Off"]

def run_bg(cmd_list):
    """Run a command in the background without waiting"""
    try:
        # Check if executable exists (mainly for OpenRGB)
        if cmd_list[0] and shutil.which(cmd_list[0]):
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error running {cmd_list}: {e}")

def trigger_wake():
    print("Event: Wake -> TV ON + RGB ON")
    run_bg(CMD_TV_ON)
    run_bg(CMD_RGB_ON)

def trigger_sleep():
    print("Event: Sleep -> TV OFF + RGB OFF")
    run_bg(CMD_TV_OFF)
    run_bg(CMD_RGB_OFF)

def on_signal(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
    """Callback for DBus signals"""
    try:
        # 1. Screen Lock Status Changed (ActiveChanged)
        # This is the MASTER control for SLEEP.
        if signal_name == "ActiveChanged" and interface_name == "org.gnome.ScreenSaver":
            is_locked = parameters.unpack()[0]
            if is_locked:
                trigger_sleep()
            else:
                trigger_wake()

        # 2. Power Mode Changed (PropertiesChanged on DisplayConfig)
        # We ONLY use this to WAKE (Mouse Wiggle). We ignore "Sleep" signals here 
        # because they cause conflicts during unlock/resolution changes.
        elif signal_name == "PropertiesChanged" and interface_name == "org.freedesktop.DBus.Properties":
            iface, changed_props, _ = parameters.unpack()
            if iface == "org.gnome.Mutter.DisplayConfig" and "PowerSaveMode" in changed_props:
                power_mode = changed_props["PowerSaveMode"]
                # 0 = On, 1+ = Standby/Suspend/Off
                if power_mode == 0:
                    trigger_wake()
                # ELSE: Do nothing. Let the Screen Saver lock handle the sleep.

    except Exception as e:
        print(f"Signal Error: {e}")

def main():
    # Connect to Session Bus
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    # Subscribe to ScreenSaver
    connection.signal_subscribe(
        None, "org.gnome.ScreenSaver", "ActiveChanged", "/org/gnome/ScreenSaver", None, 
        Gio.DBusSignalFlags.NONE, on_signal, None
    )

    # Subscribe to Mutter DisplayConfig (PowerSaveMode)
    connection.signal_subscribe(
        None, "org.freedesktop.DBus.Properties", "PropertiesChanged", "/org/gnome/Mutter/DisplayConfig", None,
        Gio.DBusSignalFlags.NONE, on_signal, None
    )

    print("Sleepy Linux Python Listener Running...")
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()