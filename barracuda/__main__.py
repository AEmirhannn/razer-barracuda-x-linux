import argparse
import json
import os
from pathlib import Path
import sys
import time

from .battery import read_battery
from .device import NoReceiver
from .settings import BANDS, SettingsError, read_settings, write_setting

INTERVAL = 60


def runtime_file():
    return Path(os.environ["XDG_RUNTIME_DIR"]) / "razer-barracuda-x" / "battery.json"


def serve(path):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    staging = path.with_suffix(".tmp")
    while True:
        started = time.monotonic()
        try:
            battery = read_battery()
        except OSError as error:
            print(f"Battery read failed: {error}", file=sys.stderr)
            battery = None
        payload = {"updated_monotonic": time.monotonic(), "battery": battery}
        staging.write_text(json.dumps(payload) + "\n")
        staging.replace(path)
        time.sleep(max(0, INTERVAL - (time.monotonic() - started)))


def show_settings(as_json):
    settings = read_settings()
    if as_json:
        print(json.dumps(settings))
        return
    idle = settings["idle_minutes"]
    print(f"EQ:           {settings['eq']}")
    print("Custom bands: " + "  ".join(f"{hz}:{level:+d}" for hz, level in zip(BANDS, settings["bands"])))
    print(f"Idle off:     {'never' if idle == 0 else f'{idle} min'}")
    print(f"DND:          {'on' if settings['dnd'] else 'off'}")


def main():
    parser = argparse.ArgumentParser(prog="barracudactl")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Run the battery service")
    battery = commands.add_parser("battery", help="Print the latest battery reading")
    battery.add_argument("--json", action="store_true", help="Return machine-readable battery data")
    settings = commands.add_parser("settings", help="Read onboard headset settings")
    settings.add_argument("--json", action="store_true", help="Return machine-readable settings")
    setter = commands.add_parser(
        "set", help="Change an onboard headset setting",
        description="eq default|game|music|movie|custom; bands L1..L10 (-5..5, 31 Hz to 16 kHz); "
                    "idle never|5|15|30|45|60; dnd on|off")
    setter.add_argument("name", choices=["eq", "bands", "idle", "dnd"])
    setter.add_argument("values", nargs="+")
    args = parser.parse_args()
    path = runtime_file()
    if args.command == "serve":
        serve(path)
        return 0

    if args.command in ("settings", "set"):
        try:
            if args.command == "set":
                write_setting(args.name, args.values)
            show_settings(getattr(args, "json", False))
        except NoReceiver as error:
            print(f"{error}. Check the udev rule and replug the receiver.", file=sys.stderr)
            return 1
        except (OSError, RuntimeError) as error:
            print(error, file=sys.stderr)
            return 1
        return 0

    try:
        payload = json.loads(path.read_text())
        age = time.monotonic() - payload["updated_monotonic"]
        battery = payload["battery"] if 0 <= age < 2 * INTERVAL else None
    except (OSError, ValueError, KeyError, TypeError):
        battery = None

    if args.json:
        print(json.dumps(battery))
    elif battery:
        estimate = " (estimate)" if battery["estimated"] else ""
        charging = {True: " · charging", False: "", None: " · charging status unknown"}
        print(f"{battery['percent']}%{estimate}{charging[battery['charging']]}")
    else:
        print("Battery unavailable. Check the headset and the user service.", file=sys.stderr)
    return 0 if battery else 1


if __name__ == "__main__":
    sys.exit(main())
