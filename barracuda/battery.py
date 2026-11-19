import time
from statistics import median

from .device import NoReceiver, headset


def read_battery():
    """Return battery data from an accessible 1532:0550 receiver, or None."""

    samples = []
    level = None
    charging = None
    try:
        with headset() as receiver:
            def customer_data(command):
                # Barracuda X customer-data GET, documented by BatteryHub's driver.
                try:
                    data = receiver.customer(command)
                except (OSError, RuntimeError):
                    return None
                return data[0] if data else None

            level = customer_data(0x21)
            cable = customer_data(0x2A)
            if cable in (0, 1):
                charging = bool(cable)
            if level is None or level > 100:
                level = None
                for _ in range(3):
                    response = receiver.query(6, 1, 0, 49)
                    if response[12] == 0 and len(response) >= 15:
                        voltage = int.from_bytes(response[13:15], 'little')
                        if 2500 <= voltage <= 4500:
                            samples.append(voltage)
                    time.sleep(.35)
    except NoReceiver:
        return None
    except (OSError, RuntimeError):
        pass

    estimated = level is None
    if estimated and samples:
        # Voltage curve from BatteryTray's BarracudaProtocol.
        curve = [3300, 3680, 3750, 3790, 3830, 3870, 3910, 3960, 4050, 4122, 4160]
        voltage = median(samples)
        for index, (low, high) in enumerate(zip(curve, curve[1:])):
            if voltage < high:
                level = index * 10 + int(10 * max(0, voltage - low) / (high - low))
                break
        else:
            level = 100

    if level is not None:
        return dict(percent=level, charging=charging, estimated=estimated)
    return None
