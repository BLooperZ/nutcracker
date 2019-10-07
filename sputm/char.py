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
from image.base import convert_to_pil_image

from typing import Set

def handle_char(data):
    with io.BytesIO(data) as stream:
        stream.seek(0, 2)
        dataend_real = stream.tell()
        print(dataend_real - 21)
        stream.seek(0, 0)
        dataend = int.from_bytes(stream.read(4), byteorder='little', signed=False) - 6
        print(dataend)
        datastart = 21
        # assert dataend == dataend_real - datastart  # true for e.g SOMI, not true for HE
        version = ord(stream.read(1))
        print(version)
        color_map = stream.read(16)
        assert stream.tell() == datastart

        bpp = ord(stream.read(1))
        assert bpp in (1, 2, 4, 8)
        print(f'{bpp}bpp')
        decoder = partial(decode_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else decode_lined_rle

        height = ord(stream.read(1))

        nchars = int.from_bytes(stream.read(2), byteorder='little', signed=False)

        yield nchars

        assert stream.tell() == datastart + 4


        offs = [int.from_bytes(stream.read(4), byteorder='little', signed=False) for i in range(nchars)]
        offs = [off for off in enumerate(offs) if off[1] != 0]

        index = list(zip(offs, [off[1] for off in offs[1:]] + [dataend_real - datastart]))
        print(len(index))
        # print(version, color_map, bpp, height, nchars)

        unique_vals: Set[int] = set()
        for (idx, off), nextoff in index:
            size = nextoff - off - 4
            assert stream.tell() == datastart + off
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
            yield idx, (xoff, yoff, convert_to_pil_image(char, size=(width, cheight)))
            print(cheight, yoff, height)
            # print(len(dt), height, width, cheight, off1, off2, bpp)
        assert stream.read() == b''
        print(unique_vals)
        # stream.seek(dataend, 0)
        # # print(stream.read())
        # # exit(1)

if __name__ == '__main__':
    import argparse
    import os

    from image import grid
    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    basename = os.path.basename(args.filename)
    with open(args.filename, 'rb') as res:
        data = sputm.assert_tag('CHAR', sputm.untag(res))
        assert res.read() == b''

        nchars, *chars = list(handle_char(data))
        palette = [((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)]

        bim = grid.create_char_grid(nchars, chars)
        bim.putpalette(palette)
        bim.save(f'{basename}.png')
