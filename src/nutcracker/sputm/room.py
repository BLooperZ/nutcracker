#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

def read_uint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def read_room_background(data, width, height, zbuffers):
    smap, *zplanes = sputm.print_chunks(sputm.read_chunks(rdata), level=2)
    # print(smap)
    for c in zplanes:
        pass

    smap_data = sputm.assert_tag('SMAP', smap[1])

    strips = width // 8
    with io.BytesIO(smap_data) as s:
        slen = read_uint16le(s)
        read_uint16le(s)
        print(slen)
        offs = [(read_uint16le(s), read_uint16le(s))  for _ in range(strips - 1)]
        print(offs)
        # print(s.read())
    exit(1)


if __name__ == '__main__':
    import argparse

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        room = sputm.assert_tag('ROOM', sputm.untag(res))
        assert res.read() == b''
        # chunks = (assert_tag('LFLF', chunk) for chunk in read_chunks(tlkb))
        chunks = sputm.print_chunks(sputm.read_chunks(room))
        transparent = 255  # default
        for cidx, (off, (tag, data)) in enumerate(chunks):
            if tag == 'RMHD':
                # only for games < v7
                assert len(data) == 6, 'Game Version < 7'
                rwidth = int.from_bytes(data[:2], signed=False, byteorder='little')
                rheight = int.from_bytes(data[2:4], signed=False, byteorder='little')
                robjects = int.from_bytes(data[4:], signed=False, byteorder='little')
            if tag == 'TRNS':
                transparent = data[0]
            if tag == 'CLUT':
                palette = data
            if tag == 'RMIM':
                assert palette
                rchunks = sputm.print_chunks(sputm.read_chunks(data), level=1)
                zbuffers = None
                for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                    if rtag == 'RMIH':
                        assert len(rdata) == 2
                        zbuffers = 1 + int.from_bytes(rdata, signed=False, byteorder='little')
                        assert 1 <= zbuffers <= 8
                    if rtag == 'IM00':
                        assert zbuffers
                        roombg = read_room_background(data, rwidth, rheight, zbuffers)
        # save raw
        print('==========')
