#!/usr/bin/env python3
import io
import struct
from itertools import chain
from functools import partial
from typing import Set, NamedTuple

import numpy as np
from PIL import Image

from nutcracker.codex.rle import decode_lined_rle
from nutcracker.graphics import image
from .bpp_codec import decode_bpp_char


class DataFrame(NamedTuple):
    width: int
    height: int
    xoff: int
    yoff: int
    data: Image.Image

    def tolist(self):
        return np.asarray(self.data).tolist()


char_header = struct.Struct('<4b')


def char_from_bytes(data, decoder):
    width, cheight, xoff, yoff = char_header.unpack(data[: char_header.size])
    data = decoder(data[char_header.size :], width, cheight)
    return DataFrame(
        width=width,
        height=cheight,
        xoff=xoff,
        yoff=yoff,
        data=image.convert_to_pil_image(data, size=(width, cheight)),
    )


def read_chars(stream, index, bpp):
    decoder = (
        partial(decode_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else decode_lined_rle
    )
    unique_vals: Set[int] = set()
    for (idx, off), nextoff in index:
        assert stream.tell() == off
        data = stream.read(nextoff - off)
        char = char_from_bytes(data, decoder)

        if not (char.xoff == 0 and char.yoff == 0):
            print('OFFSET', idx, char.xoff, char.yoff, char.width, char.height)

        # assert cheight + yoff <= height, (cheight, yoff, height)

        unique_vals |= set(chain.from_iterable(char.tolist()))
        yield idx, char

    assert stream.read() == b''
    print(unique_vals)


def handle_char(data):
    header_size = 21

    header = data[:header_size]
    char_data = data[header_size:]

    dataend_real = len(char_data)

    with io.BytesIO(header) as header_stream:
        dataend = (
            int.from_bytes(header_stream.read(4), byteorder='little', signed=False) - 6
        )
        print(dataend)
        # assert dataend == dataend_real - datastart  # true for SOMI, not true for HE
        version = ord(header_stream.read(1))
        print(version)
        color_map = header_stream.read(16)  # noqa: F841
        assert header_stream.tell() == header_size

    print(dataend, dataend_real)

    with io.BytesIO(char_data) as stream:
        bpp = ord(stream.read(1))
        print(f'{bpp}bpp')
        assert bpp in {0, 1, 2, 4, 8}, bpp

        height = ord(stream.read(1))  # noqa: F841

        nchars = int.from_bytes(stream.read(2), byteorder='little', signed=False)

        assert stream.tell() == 4

        offs = [
            int.from_bytes(stream.read(4), byteorder='little', signed=False)
            for i in range(nchars)
        ]
        offs = [off for off in enumerate(offs) if off[1] != 0]

        index = list(zip(offs, [off[1] for off in offs[1:]] + [dataend_real]))
        print(len(index))
        # print(version, color_map, bpp, height, nchars)

        frames = list(read_chars(stream, index, bpp))
        assert stream.read() == b''
        return nchars, frames


if __name__ == '__main__':
    import argparse
    import os
    import glob

    from nutcracker.graphics import grid
    from nutcracker.utils.funcutils import flatten

    from .preset import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    print(files)
    for filename in files:

        basename = os.path.basename(filename)
        with open(filename, 'rb') as res:
            data = sputm.assert_tag('CHAR', sputm.untag(res))
            assert res.read() == b''

            nchars, chars = handle_char(data)
            palette = [((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)]

            chars = [(idx, (char.xoff, char.yoff, char.data)) for idx, char in chars]

            bim = grid.create_char_grid(nchars, chars)
            bim.putpalette(palette)
            bim.save(f'{basename}.png')
            print(f'saved {basename}.png')
