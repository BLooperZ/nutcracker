#!/usr/bin/env python3

import io
import os

import numpy as np

from nutcracker.codex.codex import decode1
from .room import decode_smap, convert_to_pil_image, decode_he, read_uint16le

def read_room_background(image, width, height, zbuffers):
    data = image.read()
    if image.tag == 'SMAP':
        return decode_smap(height, width, data)
    elif image.tag == 'BOMP':
        with io.BytesIO(data) as s:
            # pylint: disable=unused-variable
            unk = read_uint16le(s)
            width = read_uint16le(s)
            height = read_uint16le(s)
            # TODO: check if x,y or y,x
            xpad, ypad = read_uint16le(s), read_uint16le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    elif image.tag == 'BMAP':
        with io.BytesIO(data) as s:
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
        print(tag, data)
        # raise ValueError(f'Unknown image codec: {tag}')

def read_rmhd(data):
    assert len(data) == 6, 'Game Version < 7'
    rwidth = int.from_bytes(data[:2], signed=False, byteorder='little')
    rheight = int.from_bytes(data[2:4], signed=False, byteorder='little')
    robjs = int.from_bytes(data[4:], signed=False, byteorder='little')
    return rwidth, rheight, robjs

def read_room(lflf):
    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    rwidth, rheight, _ = read_rmhd(sputm.find('RMHD', room).read())
    trns = sputm.find('TRNS', room).read()  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).read()

    rmim = sputm.find('RMIM', room) or sputm.find('RMIM', lflf)
    rmih = sputm.find('RMIH', rmim).read()
    assert len(rmih) == 2
    zbuffers = 1 + int.from_bytes(rmih, signed=False, byteorder='little')
    assert 1 <= zbuffers <= 8

    imxx = sputm.find('IM00', rmim)
    im = convert_to_pil_image(
        read_room_background(imxx.children[0], rwidth, rheight, zbuffers)
    )
    zpxx = list(sputm.findall('ZP{:02x}', imxx))
    assert len(zpxx) == zbuffers - 1
    im.putpalette(palette)
    return im

def read_imhd(data):
    # pylint: disable=unused-variable
    with io.BytesIO(data) as stream:
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
        return obj_height, obj_width

def read_objects(lflf):
    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    trns = sputm.find('TRNS', room).read()  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).read()

    for obj_idx, obim in enumerate(sputm.findall('OBIM', room)):
        obj_height, obj_width = read_imhd(sputm.find('IMHD', obim).read())

        for imxx in sputm.findall('IM{:02x}', obim):
            im = convert_to_pil_image(
                read_room_background(imxx.children[0], obj_width, obj_height, 0)
            )
            im.putpalette(palette)
            yield obj_idx, imxx.tag, im

if __name__ == '__main__':
    import argparse
    import pprint

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        root = next(sputm.map_chunks(res), None)
        assert root
        assert root.tag == 'LECF', root.tag
        for idx, lflf in enumerate(sputm.findall('LFLF', root)):
            read_room(lflf).save(f'ROOM_{idx:04d}_BG.png')

            for obj_idx, tag, im in read_objects(lflf):
                im.save(f'ROOM_{idx:04d}_OBIM_{obj_idx:04d}_{tag}.png')

            # for lflf in sputm.findall('LFLF', t):
            #     tree = sputm.findpath('ROOM/OBIM/IM{:02x}', lflf)
            #     sputm.render(tree)

        print('==========')
