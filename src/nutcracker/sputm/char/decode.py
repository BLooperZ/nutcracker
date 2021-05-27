#!/usr/bin/env python3
import io
import os
import struct
from functools import partial
from itertools import chain
from typing import Iterable, Iterator, NamedTuple, Sequence, Set

import numpy as np
from PIL import Image

from nutcracker.codex.bpp_codec import decode_bpp_char
from nutcracker.codex.rle import decode_lined_rle
from nutcracker.graphics import grid, image

from ..preset import sputm
from ..types import Element

CHAR_HEADER = struct.Struct('<2B2b')


class DataFrame(NamedTuple):
    width: int
    height: int
    xoff: int
    yoff: int
    data: Image.Image

    def tolist(self) -> Sequence[Sequence[int]]:
        return np.asarray(self.data).tolist()


def char_from_bytes(data: bytes, decoder: callable) -> DataFrame:
    width, cheight, xoff, yoff = CHAR_HEADER.unpack(data[: CHAR_HEADER.size])
    data = decoder(data[CHAR_HEADER.size :], width, cheight)
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


CHAR_PALETTE = [((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)]


def get_chars(root: Iterable[Element]) -> Iterator[Element]:
    for elem in root:
        if elem.tag in {'LECF', 'LFLF', 'CHAR'}:
            if elem.tag in {'CHAR'}:
                yield elem
            else:
                yield from get_chars(elem.children)


def decode_font(char: Element) -> image.TImage:
    data = sputm.assert_tag('CHAR', char)

    nchars, chars = handle_char(data)
    chars = [(idx, (char.xoff, char.yoff, char.data)) for idx, char in chars]
    bim = grid.create_char_grid(nchars, chars)
    bim.putpalette(CHAR_PALETTE)
    return bim


def decode_all_fonts(root: Iterable[Element]):
    for char in get_chars(root):
        yield os.path.basename(char.attribs['path']), decode_font(char)
