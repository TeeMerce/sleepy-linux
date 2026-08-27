#!/usr/bin/env python3
"""sleepy ctl — v3.2

  sleepy-ctl on          TV on (WOL) + RGB on   [RGB runs in parallel with WOL]
  sleepy-ctl off         RGB off + TV off (webOS power_off, 1 retry)
  sleepy-ctl rgb on|off  RGB only
  sleepy-ctl test        static checks + live ON -> OFF cycle
  sleepy-ctl detect      print resolved config

v3.2: sleepy.conf parser strips inline comments; TV_IP is validated so a
      malformed value warns instead of crashing WOL / breaking power_off.
"""
import argparse
import os
import shutil
import socket
import subprocess
import time

INSTALL_PATH = os.path.expanduser(os.environ.get("SLEEPY_HOME", "~/.local/share/sleepy"))
CONF = os.path.join(INSTALL_PATH, "sleepy.conf")
KEYFILE = os.path.join(INSTALL_PATH, "keys.sqlite")
VENV_BIN = os.path.join(INSTALL_PATH, "venv", "bin")


def load_conf():
    cfg = {
        "TV_IP": "", "TV_MAC": "",
        "WOL_REPEATS": "3", "WOL_INTERVAL_MS": "250",
        "OPENRGB_BIN": "openrgb",
        "RGB_ON_PROFILE": "On", "RGB_OFF_PROFILE": "Off",
    }
    try:
        with open(CONF) as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()   # drop inline + full-line comments
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return cfg


def valid_ip(ip):
    parts = (ip or "").split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def openrgb_bin(cfg):
    return shutil.which(cfg.get("OPENRGB_BIN", "openrgb")) or cfg.get("OPENRGB_BIN", "openrgb")


def broadcast_ip(cfg):
    ip = cfg.get("TV_IP") or ""
    if valid_ip(ip):
        a, b, c, _ = ip.split(".")
        return f"{a}.{b}.{c}.255"
    return "255.255.255.255"


def wol(cfg):
    try:
        mac = [int(x, 16) for x in cfg["TV_MAC"].split(":")]
        if len(mac) != 6:
            raise ValueError("need 6 hex octets")
    except (KeyError, ValueError) as e:
        print(f"[sleepy] WOL failed: bad TV_MAC ({e})", flush=True)
        return
    ip = cfg.get("TV_IP") or ""
    if ip and not valid_ip(ip):
        print(f"[sleepy] WARNING: TV_IP looks invalid ({ip!r}) — broadcast only", flush=True)
        ip = ""
    pkt = b"\xff" * 6 + bytes(mac) * 16
    bcast = broadcast_ip(cfg)
    try:
        repeats = max(1, int(cfg.get("WOL_REPEATS", 3)))
        interval = max(0, int(cfg.get("WOL_INTERVAL_MS", 250))) / 1000.0
    except ValueError:
        repeats, interval = 3, 0.25
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        for i in range(repeats):
            if ip:
                try:
                    s.sendto(pkt, (ip, 9))
                except OSError as e:
                    print(f"[sleepy] WOL unicast send failed ({e})", flush=True)
            try:
                s.sendto(pkt, (bcast, 9))
            except OSError as e:
                print(f"[sleepy] WOL broadcast send failed ({e})", flush=True)
            if i < repeats - 1 and interval:
                time.sleep(interval)
    finally:
        s.close()
    print(f"[sleepy] WOL sent ({repeats}x -> {ip or bcast}:9)", flush=True)


def set_rgb(cfg, profile):
    binpath = openrgb_bin(cfg)
    try:
        r = subprocess.run([binpath, "--profile", profile], timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            print(f"[sleepy] RGB -> {profile}", flush=True)
        else:
            print(f"[sleepy] RGB '{profile}' failed (rc={r.returncode})", flush=True)
    except Exception as e:
        print(f"[sleepy] RGB '{profile}' failed: {e}", flush=True)


def power_off(cfg):
    ip = cfg.get("TV_IP") or ""
    if not ip:
        print("[sleepy] TV power_off skipped: TV_IP not set in sleepy.conf", flush=True)
        return
    if not valid_ip(ip):
        print(f"[sleepy] TV power_off skipped: TV_IP looks invalid ({ip!r})", flush=True)
        return
    bsc = os.path.join(VENV_BIN, "bscpylgtvcommand")
    for attempt in (1, 2):
        try:
            r = subprocess.run([bsc, "-p", KEYFILE, ip, "power_off"],
                               timeout=30, capture_output=True)
            if r.returncode == 0:
                print("[sleepy] TV power_off OK", flush=True)
                return
            print(f"[sleepy] power_off attempt {attempt} rc={r.returncode}: "
                  f"{r.stderr.decode(errors='replace').strip()}", flush=True)
        except Exception as e:
            print(f"[sleepy] power_off attempt {attempt} error: {e}", flush=True)
        if attempt == 1:
            time.sleep(2)
    print("[sleepy] TV power_off FAILED (TV may still be on)", flush=True)


def cmd_on(cfg):
    # RGB in parallel with the WOL repeats -> wake feels instant
    binpath = openrgb_bin(cfg)
    profile = cfg.get("RGB_ON_PROFILE", "On")
    rgb = subprocess.Popen([binpath, "--profile", profile],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wol(cfg)
    try:
        rc = rgb.wait(timeout=60)
        if rc == 0:
            print(f"[sleepy] RGB -> {profile}", flush=True)
        else:
            print(f"[sleepy] RGB '{profile}' failed (rc={rc})", flush=True)
    except Exception as e:
        print(f"[sleepy] RGB '{profile}' failed: {e}", flush=True)


def cmd_off(cfg):
    set_rgb(cfg, cfg.get("RGB_OFF_PROFILE", "Off"))   # immediate visual feedback
    power_off(cfg)


def cmd_rgb(cfg, state):
    key = "RGB_ON_PROFILE" if state.lower() == "on" else "RGB_OFF_PROFILE"
    set_rgb(cfg, cfg.get(key, state))


def cmd_test(cfg):
    print("== static checks ==")
    ip = cfg.get("TV_IP") or ""
    ip_note = "" if (not ip or valid_ip(ip)) else "   <-- INVALID (fix sleepy.conf)"
    print(f"  TV_IP            : {ip or 'MISSING'}{ip_note}")
    print(f"  TV_MAC           : {cfg.get('TV_MAC') or 'MISSING'}")
    print(f"  openrgb          : {shutil.which(cfg.get('OPENRGB_BIN','openrgb')) or 'NOT FOUND'}")
    bsc = os.path.join(VENV_BIN, "bscpylgtvcommand")
    print(f"  bscpylgtvcommand : {bsc if os.path.exists(bsc) else 'NOT FOUND'}")
    print(f"  keyfile          : {KEYFILE if os.path.exists(KEYFILE) else 'MISSING'}")
    print("== live cycle: ON -> 3s -> OFF ==")
    cmd_on(cfg)
    time.sleep(3)
    cmd_off(cfg)


def cmd_detect(cfg):
    ip = cfg.get("TV_IP") or ""
    print(f"INSTALL_PATH : {INSTALL_PATH}")
    print(f"TV_IP        : {ip or 'MISSING'}{'   <-- INVALID' if ip and not valid_ip(ip) else ''}")
    print(f"TV_MAC       : {cfg.get('TV_MAC')}")
    print(f"WOL          : {cfg.get('WOL_REPEATS')}x @ {cfg.get('WOL_INTERVAL_MS')}ms "
          f"-> {ip or broadcast_ip(cfg)}:9 + {broadcast_ip(cfg)}:9")
    print(f"openrgb      : {shutil.which(cfg.get('OPENRGB_BIN','openrgb')) or 'NOT FOUND'}")
    print(f"RGB profiles : on={cfg.get('RGB_ON_PROFILE')}  off={cfg.get('RGB_OFF_PROFILE')}")
    bsc = os.path.join(VENV_BIN, "bscpylgtvcommand")
    print(f"bscpylgtv    : {bsc if os.path.exists(bsc) else 'NOT FOUND'}")
    print(f"keyfile      : {KEYFILE} ({'exists' if os.path.exists(KEYFILE) else 'missing'})")


def main():
    p = argparse.ArgumentParser(prog="sleepy-ctl")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("on", help="TV on + RGB on")
    sub.add_parser("off", help="RGB off + TV off")
    rgbp = sub.add_parser("rgb", help="RGB only")
    rgbp.add_argument("state", choices=["on", "off"])
    sub.add_parser("test", help="static checks + live cycle")
    sub.add_parser("detect", help="print resolved config")
    args = p.parse_args()
    cfg = load_conf()

    if args.cmd == "on":
        cmd_on(cfg)
    elif args.cmd == "off":
        cmd_off(cfg)
    elif args.cmd == "rgb":
        cmd_rgb(cfg, args.state)
    elif args.cmd == "test":
        cmd_test(cfg)
    elif args.cmd == "detect":
        cmd_detect(cfg)


if __name__ == "__main__":
    main()