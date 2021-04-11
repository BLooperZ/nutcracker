#!/usr/bin/env python3
from typing import Sequence

from nutcracker.utils.funcutils import flatten, grouper


def decode_bpp_char(
    data: bytes, width: int, height: int, bpp: int = 1
) -> Sequence[Sequence[int]]:
    assert width != 0 and height != 0
    # print([f'{x:08b}' for x in data])
    bits = ''.join(f'{x:08b}' for x in data)
    gbits = grouper(bits, bpp)
    bmap = [int(''.join(next(gbits)), 2) for _ in range(height * width)]

    char = list(grouper(bmap, width))

    left = [int(''.join(gb), 2) for gb in gbits]  # why there is still data left?
    # print('DATA', data)
    # print('CHAR', char)
    print('LEFT', left, height, width)

    # char += list(grouper(left, width, fillvalue=0))

    # char = list(grouper(bmap, width, fillvalue=0))
    # encoded = encode_bpp_char(char, bpp=bpp)
    # assert encoded == data, (encoded, data)
    return char


def encode_bpp_char(bmap: Sequence[Sequence[int]], bpp: int = 1) -> bytes:
    # height = len(bmap)
    # width = len(bmap[0])
    fbits = flatten(''.join(f'{x:0{bpp}b}' for x in flatten(bmap)))
    bits = list(fbits)
    gbits = grouper(bits, 8, fillvalue='0')
    # gbits = list(gbits)
    # print([''.join(x) for x in gbits])
    data = bytes(int(''.join(byte), 2) for byte in gbits)
    # assert len(data) == width * height * 8 // bpp
    print(len(bits) % 8)
    extra = b'\0' if len(bits) % 8 == 0 else b''
    return data + extra
