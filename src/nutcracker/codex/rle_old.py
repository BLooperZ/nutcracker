import io
import itertools
from typing import Sequence

from nutcracker.utils import funcutils

def encode_groups(groups):
    old_abs = b''
    for group in groups:
        assert len(group) > 0
        print(group)
        if set(group) == {0}:
            yield old_abs + (2 * len(group) + 1).to_bytes(1, byteorder='little', signed=False)
            old_abs = b''
        else:
            absolute = (4 * (len(group) - 1)).to_bytes(1, byteorder='little', signed=False) + bytes(group)
            encoded = (4 * (len(group) - 1) + 2).to_bytes(1, byteorder='little', signed=False) + bytes(group[:1])
            print(absolute, encoded)
            if len(encoded) + len(old_abs) < 1 + len(old_abs[1:] + absolute[1:]):
                yield old_abs + encoded
                old_abs = b''
            elif old_abs:
                    new_abs = old_abs[1:] + absolute[1:]
                    old_abs = (4 * (len(new_abs) - 1)).to_bytes(1, byteorder='little', signed=False) + new_abs
            else:
                old_abs = absolute
    if old_abs:
        yield old_abs

def encode_lined_rle(bmap: Sequence[Sequence[int]]) -> bytes:
    print('======================')
    with io.BytesIO() as stream:
        for line in bmap:
            print(line)
            if set(line) == {0}:
                stream.write(b'\00\00')
                continue

            grouped = [list(group) for c, group in itertools.groupby(line)]
            print(grouped)

            linedata = b''.join(encode_groups(grouped))
            sized = len(linedata).to_bytes(2, byteorder='little', signed=False) + linedata
            stream.write(sized)
            print('encode', sized)
        return stream.getvalue()

def decode_rle_group(line, width):
    out = [0 for _ in range(width)]
    currx = 0
    with io.BytesIO(line) as stream:
        while stream.tell() < len(line) and currx < width:
            code = ord(stream.read(1))
            if code & 1:  # skip count
                currx += (code >> 1)
            else:
                count = (code >> 2) + 1
                out[currx:currx+count] = stream.read(1) * count if code & 2 else stream.read(count)
                currx += count
    return out

def decode_lined_rle(data, width, height, verify=True):
    with io.BytesIO(data) as stream:
        lines = [
            stream.read(
                int.from_bytes(stream.read(2), signed=False, byteorder='little')
            ) for _ in range(height)
        ]
    output = [decode_rle_group(line, width) for line in lines]
    if verify:
        encoded = encode_lined_rle(output)
        assert encoded == data, (encoded, data)
    return output
