#!/usr/bin/env python3

import io
import os
import struct

import numpy as np
from PIL import Image

from nutcracker.sputm.index import read_index_v5tov7, read_index_he
from nutcracker.utils.fileio import write_file
from nutcracker.codex.codex import encode1, decode1
from nutcracker.codex.smap import encode_smap, fake_encode_strip, decode_smap

from .preset import sputm

def read_room_background(image, format):
    if image.tag == 'SMAP':
        return encode_smap(height, width, image.data)
    elif image.tag == 'BOMP':
        with io.BytesIO(image.data) as s:
            # pylint: disable=unused-variable
            unk = read_uint16le(s)
            width = read_uint16le(s)
            height = read_uint16le(s)
            # TODO: check if x,y or y,x
            xpad, ypad = read_uint16le(s), read_uint16le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    elif image.tag == 'BMAP':
        with io.BytesIO(image.data) as s:
            code = s.read(1)[0]
            palen = code % 10
            if 134 <= code <= 138:
                res = decode_he(s, width * height, palen)
                return np.frombuffer(res, dtype=np.uint8).reshape((height, width))
            elif 144 <= code <= 148:
                # TODO: handle transparency
                # tr = TRANSPARENCY
                res = decode_he(s, width * height, palen)
                return np.frombuffer(res, dtype=np.uint8).reshape((height, width))
            elif code == 150:
                return np.full((height, width), s.read(1)[0], dtype=np.uint8)
    else:
        print(image.tag, image.data)
        # raise ValueError(f'Unknown image codec: {tag}')

def encode_block_v8(filename, blocktype):
    im = Image.open(filename)
    npim = np.asarray(im, dtype=np.uint8)
    
    if blocktype == 'SMAP':
        smap = encode_smap(npim)
        assert np.array_equal(npim, decode_smap(*npim.shape, smap))
        # TODO: detect version, older games should return here
        # return sputm.mktag(blocktype, smap)

        num_strips = im.width // 8
        offs = smap[:num_strips * 4]
        data = smap[4 * num_strips:]
        smap_v8 = sputm.mktag(
            'BSTR',
            sputm.mktag(
                'WRAP',
                sputm.mktag('OFFS', offs) + data
            )
        )

        # verify
        chunk = sputm.mktag(blocktype, smap_v8)
        s = sputm.generate_schema(chunk)
        image = next(sputm(schema=s).map_chunks(chunk))

        bstr = sputm.findpath('BSTR/WRAP', image)
        assert np.array_equal(npim, decode_smap(*npim.shape, bstr.data[8:]))

        return smap_v8

    if blocktype == 'BOMP':
        bomp = encode1(npim)
        assert np.array_equal(npim, decode1(*npim.shape[::-1], bomp))
        # v8
        return struct.pack('<2I', *npim.shape[::-1]) + bomp
        return None

if __name__ == '__main__':
    import argparse
    import pprint
    from typing import Dict

    from .types import Chunk, Element

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('-f', '--format', default='SMAP', help='filename to read from')
    args = parser.parse_args()

    im = Image.open(args.filename)
    npim = np.asarray(im, dtype=np.uint8)

    smap = encode_smap(npim)
    assert np.array_equal(npim, decode_smap(*npim.shape, smap))

    write_file('SMAP', sputm.mktag('SMAP', smap))
