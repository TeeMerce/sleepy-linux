#!/usr/bin/env python3
"""sleepy-listener.py — v3

Watches GNOME's screen-lock state AND monitor power state, drives TV + RGB:

  ScreenSaver locked             -> off   (TV off + RGB off)
  ScreenSaver unlocked           -> on    (TV on  + RGB on)
  Monitor wake  (PowerSave=0)    -> on    (mouse/keyboard -> show lock screen)
  Monitor sleep (PowerSave=1)
      + still locked after GUARD -> off   (re-switch off if not logged in)
      + unlocked                 -> ignore

- Event-driven (D-Bus signals), no polling.
- Lock state via org.gnome.ScreenSaver.GetActive() (method, not the
  IsLocked property — that doesn't exist on modern GNOME).
- One-shot `openrgb --profile` (no background server needed).
- TV on/off via sleepy-ctl (WOL + bscpylgtv power_off).
- Never acts on the initial lock state.
"""
import os
import subprocess
import sys

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

INSTALL_PATH = os.path.expanduser(os.environ.get("SLEEPY_HOME", "~/.local/share/sleepy"))
CTL = os.path.join(INSTALL_PATH, "sleepy-ctl")
CONF = os.path.join(INSTALL_PATH, "sleepy.conf")


def load_conf():
    cfg = {"GUARD_SECONDS": 4.0}
    try:
        with open(CONF) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k in cfg:
                    try:
                        cfg[k] = float(v)
                    except ValueError:
                        pass
                else:
                    cfg[k] = v
    except FileNotFoundError:
        pass
    return cfg


def ensure_dbus():
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if xdg:
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={xdg}/bus"


def run_ctl(action):
    try:
        subprocess.run([CTL, action], timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[sleepy] -> {action}", flush=True)
    except Exception as e:
        print(f"[sleepy] {action} failed: {e}", flush=True)


class Sleepy:
    def __init__(self, bus, cfg):
        self.bus = bus
        self.cfg = cfg
        self.locked = False

    def get_locked(self):
        try:
            res = self.bus.call_sync(
                "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver", "GetActive",
                None, GLib.VariantType("(b)"),
                Gio.DBusCallFlags.NONE, -1, None,
            )
            return bool(res.unpack()[0])
        except Exception:
            return None

    def set_locked(self, locked):
        if locked == self.locked:
            return
        self.locked = locked
        print(f"[sleepy] ScreenSaver {'locked' if locked else 'unlocked'}", flush=True)
        run_ctl("off" if locked else "on")

    def on_power_save(self, mode):
        if mode == 0:
            print("[sleepy] Monitor wake -> on", flush=True)
            run_ctl("on")
        elif self.locked:
            print("[sleepy] Monitor sleep (locked) -> guard", flush=True)
            GLib.timeout_add_seconds(int(self.cfg["GUARD_SECONDS"]), self.check_guard)
        else:
            print("[sleepy] Monitor sleep (unlocked) -> ignored", flush=True)

    def check_guard(self):
        if self.locked:
            print("[sleepy] Guard: still locked -> off", flush=True)
            run_ctl("off")
        else:
            print("[sleepy] Guard: unlocked -> ignored", flush=True)
        return False  # one-shot

    def on_saver(self, *args):
        try:
            connection, sender, obj_path, iface, sig, params, user_data = args
            if sig == "ActiveChanged" and iface == "org.gnome.ScreenSaver":
                self.set_locked(params.unpack()[0])
        except Exception as e:
            print(f"[sleepy] saver error: {e}", flush=True)

    def on_props(self, *args):
        try:
            connection, sender, obj_path, iface, sig, params, user_data = args
            if sig == "PropertiesChanged" and iface == "org.freedesktop.DBus.Properties":
                prop_iface, changed, _ = params.unpack()
                if prop_iface == "org.gnome.Mutter.DisplayConfig" and "PowerSaveMode" in changed:
                    self.on_power_save(changed["PowerSaveMode"])
        except Exception as e:
            print(f"[sleepy] props error: {e}", flush=True)

    def start(self):
        initial = self.get_locked()
        if initial is None:
            print("[sleepy] FATAL: cannot read lock state "
                  "(org.gnome.ScreenSaver missing?)", flush=True)
            sys.exit(1)
        self.locked = initial  # baseline — never act on it
        print(f"[sleepy] v3 started (initial={'locked' if initial else 'unlocked'}, "
              f"guard={self.cfg['GUARD_SECONDS']}s)", flush=True)

        self.bus.signal_subscribe(
            None, "org.gnome.ScreenSaver", "ActiveChanged",
            "/org/gnome/ScreenSaver", None, Gio.DBusSignalFlags.NONE,
            self.on_saver, None,
        )
        self.bus.signal_subscribe(
            None, "org.freedesktop.DBus.Properties", "PropertiesChanged",
            "/org/gnome/Mutter/DisplayConfig", None, Gio.DBusSignalFlags.NONE,
            self.on_props, None,
        )


def main():
    ensure_dbus()
    cfg = load_conf()
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    Sleepy(bus, cfg).start()
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()