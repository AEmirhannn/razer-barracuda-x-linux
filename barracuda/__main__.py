import argparse
import json
import os
from pathlib import Path
import sys
import time

from .battery import read_battery

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


def main():
    parser = argparse.ArgumentParser(prog="barracudactl")
    parser.add_argument("command", choices=["serve", "battery"])
    parser.add_argument("--json", action="store_true", help="Return machine-readable battery data")
    args = parser.parse_args()
    path = runtime_file()
    if args.command == "serve":
        serve(path)
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
