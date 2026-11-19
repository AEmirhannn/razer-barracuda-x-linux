import binascii
import fcntl
import os
import pathlib
import select
import time
from statistics import median

def read_battery():
    """Return battery data from an accessible 1532:0550 receiver, or None."""
    for device in pathlib.Path('/sys/class/hidraw').glob('hidraw*'):
        try:
            if 'HID_ID=0003:00001532:00000550' not in (device / 'device/uevent').read_text():
                continue
            fd = os.open('/dev/' + device.name, os.O_RDWR | os.O_NONBLOCK)
            break
        except OSError:
            continue
    else:
        return None

    # Serialize access with other cooperating readers.
    fcntl.flock(fd, fcntl.LOCK_EX)
    seq = 0
    def query(group, *body, customer_id=None):
        nonlocal seq
        seq += 1
        payload = bytes([0x50, 0x41, group, seq, *body])
        frame = bytearray(bytes([2, 128, len(payload), 0, 0]) + payload)
        frame.extend(bytes(64 - len(frame)))
        frame[3:5] = binascii.crc_hqx(frame, 0).to_bytes(2, 'little')
        for _ in range(5):
            os.write(fd, frame)
            status = bytearray(64)
            status[0] = 2
            fcntl.ioctl(fd, 0xC040480A, status, True)
            if status[1] == ord('O'):
                break
            if status[1] != ord('F'):
                raise RuntimeError(f'Unexpected dongle status {status[:4].hex()}')
            time.sleep(.05)
        else:
            raise TimeoutError('Dongle stayed busy')

        end = time.monotonic() + 2
        stream = bytearray()
        while time.monotonic() < end and select.select([fd], [], [], max(0, end-time.monotonic()))[0]:
            report = os.read(fd, 64)
            if len(report) < 2 or report[0] != 2 or report[1] > len(report) - 2:
                continue
            stream.extend(report[2:2 + report[1]])
            while len(stream) >= 10:
                if stream[:2] != b'PI':
                    del stream[0]
                    continue
                size = 10 + int.from_bytes(stream[8:10], 'little')
                if len(stream) < size:
                    break
                msg = stream[:size]
                del stream[:size]
                if customer_id is not None:
                    if (len(msg) >= 14 and msg[2] == 8 and
                            msg[10:12] == bytes([customer_id, 1]) and msg[12] >= 1):
                        return msg
                elif len(msg) >= 13 and msg[10:12] == bytes([group, 128 | seq]):
                    return msg
        raise TimeoutError(f'No response for command {group:#04x}')


    def customer_data(command):
        # Barracuda X customer-data GET, documented by BatteryHub's driver.
        try:
            return query(8, 3, command, 0, 0, customer_id=command)[13]
        except (OSError, RuntimeError):
            return None


    samples = []
    level = None
    charging = None
    try:
        if query(14, 2, 225, 1)[12] == 0:
            level = customer_data(0x21)
            cable = customer_data(0x2A)
            if cable in (0, 1):
                charging = bool(cable)
            if level is None or level > 100:
                level = None
                for _ in range(3):
                    response = query(6, 1, 0, 49)
                    if response[12] == 0 and len(response) >= 15:
                        voltage = int.from_bytes(response[13:15], 'little')
                        if 2500 <= voltage <= 4500:
                            samples.append(voltage)
                    time.sleep(.35)
    except (OSError, RuntimeError):
        pass
    finally:
        try:
            query(14, 2, 225, 0)
        except (OSError, RuntimeError):
            pass
        os.close(fd)

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
