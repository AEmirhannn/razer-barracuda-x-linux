# Razer Barracuda X for Linux

A Linux user service and command-line utility for the Razer Barracuda X (2022), model RZ04-04430, using the YS-Tech 2.4 GHz USB receiver (1532:0550).

The service polls once a minute. It prefers the headset's reported battery percentage and cable status, using voltage to estimate the percentage if the native reading fails. Frontends can read the latest result through the CLI without making their own USB requests.

## Install

Requires Linux with systemd, udev and Python 3. These instructions assume a local desktop session with systemd-logind.

```sh
sudo install -m 0644 packaging/70-barracuda-battery.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Unplug and reconnect the **USB receiver** to apply the permission rule. It grants access to the active local user for this receiver. The service itself runs without root.

```sh
./install.sh
~/.local/bin/barracudactl battery
~/.local/bin/barracudactl battery --json
```

The installer enables the user service at login, including after reboot. Check its status with `systemctl --user status razer-barracuda-x.service`. Turn on the headset in 2.4 GHz mode before querying. Allow up to a minute for the first reading after connecting.

## Use from another application

Call `barracudactl battery --json`. A reading looks like:

```json
{"percent":82,"charging":false,"estimated":false}
```

`charging` reflects the headset's cable flag, and can be `null` if the flag is unavailable. `estimated` indicates the voltage fallback. When no fresh reading exists, the command prints `null` and exits with status 1.

Only the 1532:0550 receiver is supported. The first utility is battery reporting.

## Credits

- [BatteryHub's Barracuda driver](https://github.com/krisgfx9/Wireless-Device-Battery-Monitor/blob/main/src/drivers/razer_headset.cpp) documents the native percentage and cable queries.
- [BatteryTray](https://github.com/qu1ncky/BatteryTray) documents the USB framing and provides the voltage curve. Its [MIT notice](LICENSES/BatteryTray-MIT.txt) is included.

Distributed under [GPL-3.0](LICENSE).
