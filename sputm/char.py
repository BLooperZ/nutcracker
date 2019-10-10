#!/usr/bin/env python3
import io
import struct

from itertools import chain
from functools import partial

import numpy as np
from PIL import Image

from utils.funcutils import grouper
from .bpp_codec import decode_bpp_char
from codex.rle import decode_lined_rle
from graphics import image

from typing import Set

def read_chars(stream, index, decoder):
    unique_vals: Set[int] = set()
    for (idx, off), nextoff in index:
        size = nextoff - off - 4
        assert stream.tell() == off
        width = ord(stream.read(1))
        cheight = ord(stream.read(1))
        xoff = int.from_bytes(stream.read(1), byteorder='little', signed=True)
        yoff = int.from_bytes(stream.read(1), byteorder='little', signed=True)
        if not (xoff == 0 and yoff == 0):
            print('OFFSET', idx, xoff, yoff)
        # assert cheight + yoff <= height, (cheight, yoff, height)
        bchar = stream.read(size)
        char = decoder(bchar, width, cheight)
        unique_vals |= set(chain.from_iterable(char))
        yield idx, (xoff, yoff, image.convert_to_pil_image(char, size=(width, cheight)))
        # print(len(dt), height, width, cheight, off1, off2, bpp)
    assert stream.read() == b''
    print(unique_vals)

def handle_char(data):
    header_size = 21

    header = data[:header_size]
    char_data = data[header_size:]

    dataend_real = len(char_data)

    with io.BytesIO(header) as header_stream:
        dataend = int.from_bytes(header_stream.read(4), byteorder='little', signed=False) - 6
        print(dataend)
        # assert dataend == dataend_real - datastart  # true for e.g SOMI, not true for HE
        version = ord(header_stream.read(1))
        print(version)
        color_map = header_stream.read(16)
        assert header_stream.tell() == header_size

    print(dataend, dataend_real)

    with io.BytesIO(char_data) as stream:
        bpp = ord(stream.read(1))
        assert bpp in (1, 2, 4, 8)
        print(f'{bpp}bpp')
        decoder = partial(decode_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else decode_lined_rle

        height = ord(stream.read(1))

        nchars = int.from_bytes(stream.read(2), byteorder='little', signed=False)

        assert stream.tell() == 4

        offs = [int.from_bytes(stream.read(4), byteorder='little', signed=False) for i in range(nchars)]
        offs = [off for off in enumerate(offs) if off[1] != 0]

        index = list(zip(offs, [off[1] for off in offs[1:]] + [dataend_real]))
        print(len(index))
        # print(version, color_map, bpp, height, nchars)

        frames = list(read_chars(stream, index, decoder))
        assert stream.read() == b''
        return nchars, frames

if __name__ == '__main__':
    import argparse
    import os

    from graphics import grid
    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    basename = os.path.basename(args.filename)
    with open(args.filename, 'rb') as res:
        data = sputm.assert_tag('CHAR', sputm.untag(res))
        assert res.read() == b''

        nchars, chars = handle_char(data)
        palette = [((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)]

        bim = grid.create_char_grid(nchars, chars)
        bim.putpalette(palette)
        bim.save(f'{basename}.png')
