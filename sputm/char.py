#!/usr/bin/env python3
import io

from itertools import chain
from functools import partial

import numpy as np
from PIL import Image

from utils.funcutils import grouper

from typing import Set

def decode_lined_rle(data, width, height):
    datlen = len(data)

    output = [[0 for _ in range(width)] for _ in range(height)]

    pos = 0
    next_pos = pos
    for curry in range(height):
    # while pos < datlen and curry < height:
        currx = 0
        bytecount = int.from_bytes(data[next_pos:next_pos + 2], byteorder='little', signed=False)
        pos = next_pos + 2
        next_pos += bytecount + 2
        while pos < datlen and pos < next_pos:
            code = data[pos]
            pos += 1
            if code & 1:  # skip count
                currx += (code >> 1)
            else:
                count = (code >> 2) + 1
                if code & 2:  # encoded run
                    output[curry][currx:currx+count] = [data[pos]] * count
                    pos += 1
                else:  # absolute run
                    output[curry][currx:currx+count] = data[pos:pos+count]
                    pos += count
                currx += count
            assert not currx > width
    return output

def handle_bpp_char(data: bytes, width: int, height: int, bpp: int = 1):
    assert width != 0 and height != 0
    bits = ''.join(f'{x:08b}' for x in data)
    gbits = grouper(bits, bpp)
    bmap = [int(''.join(next(gbits)), 2) for _ in range(height * width)]
    char = list(grouper(bmap, width))
    # char = list(grouper(bmap, width, fillvalue=0))
    return char

def handle_char(data):
    with io.BytesIO(data) as stream:
        stream.seek(0, 2)
        dataend_real = stream.tell()
        print(dataend_real - 21)
        stream.seek(0, 0)
        dataend = int.from_bytes(stream.read(4), byteorder='little', signed=False) - 6
        print(dataend)
        datastart = 21
        version = ord(stream.read(1))
        color_map = stream.read(16)
        assert stream.tell() == datastart

        bpp = ord(stream.read(1))
        print(f'{bpp}bpp')
        decoder = partial(handle_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else decode_lined_rle

        height = ord(stream.read(1))

        nchars = int.from_bytes(stream.read(2), byteorder='little', signed=False)

        assert stream.tell() == datastart + 4
        offs = [int.from_bytes(stream.read(4), byteorder='little', signed=False) for i in range(nchars)]
        offs = [off for off in enumerate(offs) if off[1] != 0]

        index = list(zip(offs, [off[1] for off in offs[1:]] + [dataend]))
        print(len(index))
        # print(version, color_map, bpp, height, nchars, offs, stream.read())

        unique_vals: Set[int] = set()
        for (idx, off), nextoff in index:
            size = nextoff - off - 4
            assert stream.tell() == datastart + off
            width = ord(stream.read(1))
            cheight = ord(stream.read(1))
            off1 = ord(stream.read(1))
            off2 = ord(stream.read(1))
            char = decoder(stream.read(size), width, cheight)
            unique_vals |= set(chain.from_iterable(char))
            yield idx, convert_to_pil_image(char, width, cheight)
            # print(len(dt), height, width, cheight, off1, off2, bpp)
        print(unique_vals)

def convert_to_pil_image(char, width, height):
    # print('CHAR:', char)
    npp = np.array(list(char), dtype=np.uint8)
    npp.resize(height, width)
    im = Image.fromarray(npp, mode='P')
    return im

def get_bg_color(row_size, f):
    BGS = [b'0', b'n']

    def get_bg(idx):
        return BGS[f(idx) % len(BGS)]
    return get_bg

def resize_pil_image(w, h, bg, im):
    # print(bg)
    nbase = convert_to_pil_image(bytes(bg) * w * h, w, h)
    # nbase.paste(im, box=itemgetter('x1', 'y1', 'x2', 'y2')(loc))
    nbase.paste(im, box=(0, 0))
    return nbase

if __name__ == '__main__':
    import argparse
    import os

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    basename = os.path.basename(args.filename)
    with open(args.filename, 'rb') as res:
        data = sputm.assert_tag('CHAR', sputm.untag(res))
        assert res.read() == b''
        chars = handle_char(data)
        palette = [((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)]

        w = 48
        h = 48
        grid_size = 16

        enpp = np.array([[0] * w * grid_size] * h * grid_size, dtype=np.uint8)
        bim = Image.fromarray(enpp, mode='P')
        get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size))

        for idx, char in chars:
            im = resize_pil_image(w, h, get_bg(idx), char)
            bim.paste(im, box=((idx % grid_size) * w, int(idx / grid_size) * h))
        bim.putpalette(palette)
        bim.save(f'{basename}.png')
