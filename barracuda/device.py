import binascii
import contextlib
import fcntl
import os
import pathlib
import select
import time

HID_ID = 'HID_ID=0003:00001532:00000550'


class NoReceiver(OSError):
    """No accessible 1532:0550 receiver."""


class Receiver:
    """Framed requests to the receiver's vendor HID interface."""

    def __init__(self, fd):
        self.fd = fd
        self.seq = 0

    def query(self, group, *body, customer_id=None):
        self.seq = self.seq % 127 + 1
        seq = self.seq
        payload = bytes([0x50, 0x41, group, seq, *body])
        frame = bytearray(bytes([2, 128, len(payload), 0, 0]) + payload)
        frame.extend(bytes(64 - len(frame)))
        frame[3:5] = binascii.crc_hqx(frame, 0).to_bytes(2, 'little')
        for _ in range(5):
            os.write(self.fd, frame)
            status = bytearray(64)
            status[0] = 2
            fcntl.ioctl(self.fd, 0xC040480A, status, True)
            if status[1] == ord('O'):
                break
            if status[1] != ord('F'):
                raise RuntimeError(f'Unexpected dongle status {status[:4].hex()}')
            time.sleep(.05)
        else:
            raise TimeoutError('Dongle stayed busy')

        end = time.monotonic() + 2
        stream = bytearray()
        while time.monotonic() < end and select.select([self.fd], [], [], max(0, end-time.monotonic()))[0]:
            report = os.read(self.fd, 64)
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
                    # Op 01 is a reply. Op 02 notifications are ignored.
                    if (len(msg) >= 13 and msg[2] == 8 and
                            msg[10:12] == bytes([customer_id, 1]) and
                            len(msg) >= 13 + msg[12]):
                        return bytes(msg[13:13 + msg[12]])
                elif len(msg) >= 13 and msg[10:12] == bytes([group, 128 | seq]):
                    return msg
        raise TimeoutError(f'No response for command {group:#04x}')

    def customer(self, command, *data):
        """Send a customer-data request (family 8) and return the reply data.

        A GET is `command 00 00`. A SET is `command|0x80 00 LEN DATA`,
        answered with a status byte. Framing documented by BatteryHub's driver
        and leag/razer-barracuda.
        """
        return self.query(8, 3 + len(data), command, 0, len(data), *data,
                          customer_id=command)


@contextlib.contextmanager
def headset():
    """Open the receiver and route requests to the headset.

    Raises NoReceiver if no accessible receiver exists. The local route is
    always restored on exit.
    """
    for device in pathlib.Path('/sys/class/hidraw').glob('hidraw*'):
        try:
            if HID_ID not in (device / 'device/uevent').read_text():
                continue
            fd = os.open('/dev/' + device.name, os.O_RDWR | os.O_NONBLOCK)
            break
        except OSError:
            continue
    else:
        raise NoReceiver('Receiver 1532:0550 not found or not accessible')

    try:
        # Serialize access with other cooperating readers.
        fcntl.flock(fd, fcntl.LOCK_EX)
        receiver = Receiver(fd)
        try:
            if receiver.query(14, 2, 225, 1)[12] != 0:
                raise RuntimeError('Headset route unavailable. Is the headset on?')
            yield receiver
        finally:
            try:
                receiver.query(14, 2, 225, 0)
            except (OSError, RuntimeError):
                pass
    finally:
        os.close(fd)
