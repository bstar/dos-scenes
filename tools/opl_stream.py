"""Original OPL register-stream writer; no instrument bank or music data."""
import struct
from pathlib import Path
RATE=1193182/2131
def write_opl(events, path):
    # End each loop with all keys released. Next loop begins with register state.
    end = events[-1][0] if events else 0
    events = list(events) + [(end+round(RATE/4), 0xb0+c, 0) for c in range(9)]
    out = bytearray()
    last = 0
    for tick, reg, val in events:
        delay = tick-last
        if delay < 0:
            raise ValueError('Events must be time-ordered')
        while delay > 65535:
            out += struct.pack('<HBB', 65535, 2, 0)
            delay -= 65535
        out += struct.pack('<HBB', delay, reg, val)
        last = tick
    if len(out) > 60000:
        raise ValueError(f'{len(out)} bytes exceeds DOS player 60000 byte limit')
    Path(path).write_bytes(out)
    return len(out)
