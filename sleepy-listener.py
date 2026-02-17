#!/usr/bin/env python3
import gi
import subprocess
import shutil
import time
import sys
# Import the OpenRGB client library
from openrgb import OpenRGBClient

gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

# --- CONFIGURATION ---
PATH_CTL = "/opt/sleepy-linux/sleepy-ctl"
CMD_TV_ON = [PATH_CTL, "ON"]
CMD_TV_OFF = [PATH_CTL, "OFF"]

# --- STATE TRACKING ---
is_locked = False 

def run_bg(cmd_list):
    try:
        if cmd_list[0] and shutil.which(cmd_list[0]):
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error running {cmd_list}: {e}")

def set_rgb_profile(profile_name):
    """Connects to OpenRGB Server and sets profile silently"""
    try:
        client = OpenRGBClient() # Connects to localhost:6742 by default
        client.load_profile(profile_name)
        print(f"RGB: Loaded profile '{profile_name}'")
    except Exception as e:
        # If server is not running, we fail silently to avoid crashing the whole listener
        print(f"RGB Error (Is OpenRGB Server running?): {e}")

def trigger_wake():
    print("ACTION: Wake -> TV ON + RGB ON")
    run_bg(CMD_TV_ON)
    set_rgb_profile("On")

def trigger_sleep():
    print("ACTION: Sleep -> TV OFF + RGB OFF")
    run_bg(CMD_TV_OFF)
    set_rgb_profile("Off")

def check_sleep_guard():
    global is_locked
    if is_locked:
        print(f"GUARD: Still Locked after 4s -> Executing Sleep")
        trigger_sleep()
    else:
        print(f"GUARD: System is Unlocked -> Ignoring Sleep Signal")
    return False

def on_signal(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
    global is_locked
    try:
        if signal_name == "ActiveChanged" and interface_name == "org.gnome.ScreenSaver":
            is_locked = parameters.unpack()[0]
            if is_locked:
                print("SIGNAL: Screen Locked")
                trigger_sleep()
            else:
                print("SIGNAL: Screen Unlocked")
                trigger_wake()

        elif signal_name == "PropertiesChanged" and interface_name == "org.freedesktop.DBus.Properties":
            iface, changed_props, _ = parameters.unpack()
            if iface == "org.gnome.Mutter.DisplayConfig" and "PowerSaveMode" in changed_props:
                power_mode = changed_props["PowerSaveMode"]
                if power_mode == 0:
                    print("SIGNAL: Monitor Wake")
                    trigger_wake()
                elif is_locked:
                    print("SIGNAL: Monitor Sleep (While Locked) -> Starting 4s Guard...")
                    GLib.timeout_add_seconds(4, check_sleep_guard)
                else:
                    print("SIGNAL: Monitor Sleep (While Unlocked) -> Ignored")
    except Exception as e:
        print(f"Signal Error: {e}")

def get_initial_state(connection):
    global is_locked
    try:
        result = connection.call_sync(
            "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver",
            "GetActive", None, GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, -1, None
        )
        is_locked = result.unpack()[0]
        print(f"STARTUP: Initial state is {'LOCKED' if is_locked else 'UNLOCKED'}")
    except Exception:
        pass

def main():
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    get_initial_state(connection)

    connection.signal_subscribe(None, "org.gnome.ScreenSaver", "ActiveChanged", "/org/gnome/ScreenSaver", None, Gio.DBusSignalFlags.NONE, on_signal, None)
    connection.signal_subscribe(None, "org.freedesktop.DBus.Properties", "PropertiesChanged", "/org/gnome/Mutter/DisplayConfig", None, Gio.DBusSignalFlags.NONE, on_signal, None)

    print("Sleepy Linux Listener (Server Edition) Running...")
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()