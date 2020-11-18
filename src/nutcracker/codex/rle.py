import io
import itertools
from typing import Sequence

from nutcracker.utils import funcutils

def encode_groups(groups):
    old_abs = b''
    for group in groups:
        assert len(group) > 0
        if set(group) == {0}:
            while len(group) > 127:
                yield old_abs + (255).to_bytes(1, byteorder='little', signed=False)
                old_abs = b''
                group = group[127:]
            yield old_abs + (2 * len(group) + 1).to_bytes(1, byteorder='little', signed=False)
            old_abs = b''
        else:
            absolute = bytes(group)
            encoded = bytes(group[:1])
            if 1 + len(encoded) + len(old_abs) < 1 + len(old_abs[1:] + absolute):
                yield old_abs + (4 * (len(group) - 1) + 2).to_bytes(1, byteorder='little', signed=False) + encoded
                old_abs = b''
            else:
                new_abs = old_abs[1:] + absolute
                while len(new_abs) > 64:
                    yield (252).to_bytes(1, byteorder='little', signed=False) + new_abs[:64]
                    old_abs = b''
                    new_abs = new_abs[64:]
                old_abs = (4 * (len(new_abs) - 1)).to_bytes(1, byteorder='little', signed=False) + new_abs
    if old_abs:
        yield old_abs

def encode_lined_rle(bmap: Sequence[Sequence[int]]) -> bytes:
    with io.BytesIO() as stream:
        for line in bmap:
            if set(line) == {0}:
                stream.write(b'\00\00')
                continue

            grouped = [list(group) for c, group in itertools.groupby(line)]

            linedata = b''.join(encode_groups(grouped))
            sized = len(linedata).to_bytes(2, byteorder='little', signed=False) + linedata
            stream.write(sized)
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

def decode_rle_group_gen(line, width):
    with io.BytesIO(line) as stream:
        while stream.tell() < len(line):
            code = ord(stream.read(1))
            if code & 1:  # skip count
                yield (code, [0] * (code >> 1))
            else:
                count = (code >> 2) + 1
                yield (code, list(stream.read(1) * count if code & 2 else stream.read(count)))

def to_byte(num):
    return bytes([num])

def encode_rle_groups(groups):
    buf = []
    for group in groups:
        assert len(group) > 0
        if set(group) == {0}:
            if buf:
                yield (4 * (len(buf) - 1), list(buf))
                buf = []
            while len(group) > 127:
                yield (2 * 127 + 1, [0] * 127)
                group = group[127:]
                if group:
                    yield (2 * 1 + 1, [0])
                    group = group[1:]
            if group:
                yield (2 * len(group) + 1, group)
        else:
            raw = 1 + len(buf) + len(group)
            encoded = 1 + len(buf) + 2
            # print(buf, group)
            if raw < encoded or (buf and raw == encoded):
                buf += group
                while len(buf) > 64:
                    yield (4 * (64 - 1), buf[:64])
                    buf = buf[64:]
            else:
                if buf:
                    yield (4 * (len(buf) - 1), list(buf))
                    buf = []
                while len(group) > 64:
                    yield (4 * (64 - 1) + 2, group[:64])
                    group = group[64:]
                yield (4 * (len(group) - 1) + 2, group)
    if buf:
        yield (4 * (len(buf) - 1), list(buf))

def decode_lined_rle(data, width, height, verify=True):
    with io.BytesIO(data) as stream:
        lines = [
            stream.read(
                int.from_bytes(stream.read(2), signed=False, byteorder='little')
            ) for _ in range(height)
        ]
    output = [decode_rle_group(line, width) for line in lines]
    output2 = [list(decode_rle_group_gen(line, width)) for line in lines]

    for l, o in zip(lines, output2):
        g = [list(group) for c, group in itertools.groupby(b''.join(bytes(oo) for _, oo in o))]
        e = [t for t in encode_rle_groups(g)]
        if e != o: 
            print('ORIG', list(l))
            print('REGROUPED', g)
            print('OGROUPS', o)
            print('ENCODED', e)
    if verify:
        encoded = encode_lined_rle(output)

        with io.BytesIO(encoded) as stream:
            elines = [
                stream.read(
                    int.from_bytes(stream.read(2), signed=False, byteorder='little')
                ) for _ in range(height)
            ]
        for l, e in zip(lines, elines):
            print('ORIG', list(l))
            print('RES', list(e))
            assert l == e

        assert encoded == data, (encoded, data)
    return output
