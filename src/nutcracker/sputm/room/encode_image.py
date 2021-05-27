#!/usr/bin/env python3

import struct

import numpy as np
from PIL import Image

from nutcracker.codex.codex import decode1, encode1
from nutcracker.codex.smap import decode_smap, encode_smap
from nutcracker.utils.fileio import write_file

from ..preset import sputm


def encode_block_v8(filename, blocktype, version=8):
    im = Image.open(filename)
    npim = np.asarray(im, dtype=np.uint8)

    if blocktype == 'SMAP':
        smap = encode_smap(npim)
        assert np.array_equal(npim, decode_smap(*npim.shape, smap))
        # TODO: detect version, older games should return here
        if version < 8:
            return smap

        num_strips = im.width // 8
        offs = smap[: num_strips * 4]
        data = smap[4 * num_strips :]
        smap_v8 = sputm.mktag(
            'BSTR', sputm.mktag('WRAP', sputm.mktag('OFFS', offs) + data)
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

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('-f', '--format', default='SMAP', help='filename to read from')
    args = parser.parse_args()

    im = Image.open(args.filename)
    npim = np.asarray(im, dtype=np.uint8)

    smap = encode_smap(npim)
    assert np.array_equal(npim, decode_smap(*npim.shape, smap))

    write_file('SMAP', sputm.mktag('SMAP', smap))
