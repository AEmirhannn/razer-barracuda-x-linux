"""Onboard headset settings over the 1532:0550 receiver.

Commands and value encodings come from leag/razer-barracuda (documented on
1532:0552). The same family-8 GET/SET requests answer on 1532:0550.
"""
from .device import headset

PRESETS = {'default': 0, 'game': 7, 'music': 8, 'movie': 9, 'custom': 255}
STANDBY = (0, 5, 15, 30, 45, 60)
BANDS = ('31', '62', '125', '250', '500', '1k', '2k', '4k', '8k', '16k')

EQ, CUSTOM_BANDS, DND, IDLE = 0x13, 0x15, 0x27, 0x2C


class SettingsError(RuntimeError):
    pass


def _get(receiver, command, size):
    data = receiver.customer(command)
    if len(data) != size:
        raise SettingsError(f'Unexpected reply for setting {command:#04x}: {data.hex()}')
    return data


def _set(receiver, command, data):
    status = receiver.customer(command | 0x80, *data)
    if status != b'\x00':
        raise SettingsError(f'Headset rejected setting {command:#04x} (status {status.hex()})')
    if _get(receiver, command, len(data)) != bytes(data):
        raise SettingsError(f'Headset did not keep setting {command:#04x}')


def _decode(command, data):
    if command == EQ:
        names = {value: name for name, value in PRESETS.items()}
        return names.get(data[0], data[0])
    if command == CUSTOM_BANDS:
        return [value - 5 for value in data]
    if command == DND:
        return bool(data[0])
    return data[0]


def read_settings():
    with headset() as receiver:
        return {
            'eq': _decode(EQ, _get(receiver, EQ, 1)),
            'bands': _decode(CUSTOM_BANDS, _get(receiver, CUSTOM_BANDS, 10)),
            'idle_minutes': _decode(IDLE, _get(receiver, IDLE, 1)),
            'dnd': _decode(DND, _get(receiver, DND, 1)),
        }


def encode(name, values):
    """Validate a CLI setting and return (command, data bytes)."""
    if name == 'eq' and len(values) == 1 and values[0] in PRESETS:
        return EQ, [PRESETS[values[0]]]
    if name == 'bands' and len(values) == len(BANDS):
        try:
            levels = [int(value) for value in values]
        except ValueError:
            levels = []
        if len(levels) == len(BANDS) and all(-5 <= level <= 5 for level in levels):
            return CUSTOM_BANDS, [level + 5 for level in levels]
    if name == 'idle' and len(values) == 1:
        minutes = 0 if values[0] == 'never' else int(values[0]) if values[0].isdigit() else None
        if minutes in STANDBY:
            return IDLE, [minutes]
    if name == 'dnd' and len(values) == 1 and values[0] in ('on', 'off'):
        return DND, [int(values[0] == 'on')]
    raise SettingsError(USAGE[name])


USAGE = {
    'eq': 'eq takes one of: ' + ', '.join(PRESETS),
    'bands': 'bands takes 10 levels from -5 to 5 for ' + ' '.join(BANDS) + ' Hz',
    'idle': 'idle takes never, ' + ', '.join(str(m) for m in STANDBY[1:]) + ' (minutes)',
    'dnd': 'dnd takes on or off',
}


def write_setting(name, values):
    command, data = encode(name, values)
    with headset() as receiver:
        _set(receiver, command, data)
