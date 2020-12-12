#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

import numpy as np

from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.codex.codex import decode1
from nutcracker.codex.smap import decode_smap, read_uint32le, read_uint16le

from .preset import sputm


def read_room_background_v8(image, width, height, zbuffers):
    if image.tag == 'SMAP':
        sputm.render(image)
        bstr = sputm.findpath('BSTR/WRAP', image)
        if not bstr:
            return None
        return decode_smap(height, width, bstr.data[8:])
    elif image.tag == 'BOMP':
        with io.BytesIO(image.data) as s:
            width = read_uint32le(s)
            height = read_uint32le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    else:
        raise ValueError(f'Unknown image codec: {image.tag}')


def read_room_background(rdata, width, height, zbuffers):
    image, *zplanes = sputm.drop_offsets(sputm.print_chunks(sputm.read_chunks(rdata), level=2))
    # print(smap)
    for c in zplanes:
        pass

    tag, data = image
    if tag == 'SMAP':
        return decode_smap(height, width, data)
    elif tag == 'BOMP':
        with io.BytesIO(data) as s:
            unk = read_uint16le(s)
            width = read_uint16le(s)
            height = read_uint16le(s)
            # TODO: check if x,y or y,x
            xpad, ypad = read_uint16le(s), read_uint16le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    elif tag == 'BMAP':
        with io.BytesIO(data) as s:
            code = s.read(1)[0]
            palen = code % 10
            if 134 <= code <= 138:
                res = decode_he(s, width * height, palen)
                return np.frombuffer(res, dtype=np.uint8).reshape((height, width))
            elif 144 <= code <= 148:
                tr = TRANSPARENCY
                res = decode_he(s, width * height, palen)
                return np.frombuffer(res, dtype=np.uint8).reshape((height, width))
            elif code == 150:
                return np.full((height, width), s.read(1)[0], dtype=np.uint8)
    else:
        print(tag, data)
        # raise ValueError(f'Unknown image codec: {tag}')

def decode_rmim(data, width, height):
    rchunks = sputm.drop_offsets(
        sputm.print_chunks(sputm.read_chunks(data), level=1)
    )

    rmih = sputm.assert_tag('RMIH', next(rchunks))
    assert len(rmih) == 2
    zbuffers = 1 + int.from_bytes(rmih, signed=False, byteorder='little')
    assert 1 <= zbuffers <= 8

    image_data = sputm.assert_tag('IM00', next(rchunks))
    roombg = read_room_background(image_data, width, height, zbuffers)
    assert not list(rchunks)
    return convert_to_pil_image(roombg)

def parse_room_noimgs(room):
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
        if tag == 'PALS':
            rchunks = sputm.print_chunks(sputm.read_chunks(data), level=2)
            for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                if rtag == 'WRAP':
                    wchunks = sputm.print_chunks(sputm.read_chunks(rdata), level=3)
                    for widx, (woff, (wtag, wdata)) in enumerate(wchunks):
                        if wtag == 'OFFS':
                            pass
                        if wtag == 'APAL':
                            palette = wdata
    return {'palette': palette, 'transparent': transparent, 'width': rwidth, 'height': rheight}

if __name__ == '__main__':
    import argparse

    from .preset import sputm

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
            if tag == 'PALS':
                rchunks = sputm.print_chunks(sputm.read_chunks(data), level=2)
                for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                    if rtag == 'WRAP':
                        wchunks = sputm.print_chunks(sputm.read_chunks(rdata), level=3)
                        for widx, (woff, (wtag, wdata)) in enumerate(wchunks):
                            if wtag == 'OFFS':
                                pass
                            if wtag == 'APAL':
                                palette = wdata
            if tag == 'RMIM':
                im = decode_rmim(data, rwidth, rheight)
                im.putpalette(palette)
                im.save(f'room_{os.path.basename(args.filename)}.png')
            if tag == 'OBIM':
                assert palette
                rchunks = sputm.print_chunks(sputm.read_chunks(data), level=1)
                curr_obj = 0
                for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                    if rtag == 'IMHD':
                        with io.BytesIO(rdata) as stream:
                            obj_id = read_uint16le(stream)
                            obj_num_imnn = read_uint16le(stream)
                            # should be per imnn, but at least 1
                            obj_nums_zpnn = read_uint16le(stream)
                            obj_flags = stream.read(1)[0]
                            obj_unknown = stream.read(1)[0]
                            obj_x = read_uint16le(stream)
                            obj_y = read_uint16le(stream)
                            obj_width = read_uint16le(stream)
                            obj_height = read_uint16le(stream)
                            obj_hotspots = stream.read()
                            if obj_hotspots:
                                # TODO: read hotspots
                                pass
                    if rtag == f'IM{1 + curr_obj:02d}':
                        print(rtag)
                        roombg = read_room_background(rdata, obj_width, obj_height, None)
                        im = convert_to_pil_image(roombg)
                        im.putpalette(palette)
                        im.save(f'obj_{cidx:05d}_{ridx:05d}_{rtag}_{os.path.basename(args.filename)}.png')
                        curr_obj += 1
                assert curr_obj == obj_num_imnn, (curr_obj, obj_num_imnn)
        # save raw
        print('==========')
