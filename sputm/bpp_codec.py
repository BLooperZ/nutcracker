#!/usr/bin/env python3
import io

from utils.funcutils import grouper, flatten

from typing import Sequence

def decode_bpp_char(data: bytes, width: int, height: int, bpp: int = 1) -> Sequence[Sequence[int]]:
    assert width != 0 and height != 0
    bits = ''.join(f'{x:08b}' for x in data)
    gbits = grouper(bits, bpp)
    bmap = [int(''.join(next(gbits)), 2) for _ in range(height * width)]
    char = list(grouper(bmap, width))
    # char = list(grouper(bmap, width, fillvalue=0))
    return char

def encode_bpp_char(bmap: Sequence[Sequence[int]], bpp = 1) -> bytes:
    # height = len(bmap)
    # width = len(bmap[0])
    bits = flatten(''.join(f'{x:0{bpp}b}' for x in flatten(bmap)))
    gbits = grouper(bits, 8)
    data = bytes(int(''.join(byte), 2) for byte in gbits)
    # assert len(data) == width * height * 8 // bpp
    return data
