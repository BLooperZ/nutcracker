import io
import itertools
from typing import Sequence, Mapping

from utils import funcutils

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

def decode_lined_rle(data, width, height):
    print('======================')
    datlen = len(data)

    print('DATA:', data, height)

    output = [[0 for _ in range(width)] for _ in range(height)]

    pos = 0
    next_pos = pos
    for curry in range(height):
    # while pos < datlen and curry < height:
        currx = 0
        bytecount = int.from_bytes(data[next_pos:next_pos + 2], byteorder='little', signed=False)
        print('decode', data[pos:pos+bytecount + 2])
        pos = next_pos + 2
        next_pos += bytecount + 2
        while pos < datlen and pos < next_pos:
            code = data[pos]
            pos += 1
            print(code)
            if code & 1:  # skip count
                print('skip', code >> 1)
                currx += (code >> 1)
            else:
                count = (code >> 2) + 1
                if code & 2:  # encoded run
                    print('encoded', count, [data[pos]] * count)
                    output[curry][currx:currx+count] = [data[pos]] * count
                    pos += 1
                else:  # absolute run
                    print('absolute', count, data[pos:pos+count])
                    output[curry][currx:currx+count] = data[pos:pos+count]
                    pos += count
                currx += count
            assert not currx > width
    encoded = encode_lined_rle(output)
    print((data, encoded))
    assert encoded == data, (encoded, data)
    return output
