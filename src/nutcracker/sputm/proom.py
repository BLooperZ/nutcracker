#!/usr/bin/env python3

import io
import os

from .room import decode_smap, convert_to_pil_image, read_room_background

def read_room_background(image, width, height, zbuffers):
    data = image.data.read()
    if image.tag == 'SMAP':
        return decode_smap(height, width, data)
    elif image.tag == 'BOMP':
        with io.BytesIO(data) as s:
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
                tr = TRANSPARENCY
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
    rwidth, rheight, _ = read_rmhd(sputm.find('RMHD', room).data.read())
    trns = sputm.find('TRNS', room).data.read()
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).data.read()

    rmim = sputm.find('RMIM', room) or sputm.find('RMIM', lflf)
    rmih = sputm.find('RMIH', rmim).data.read()
    assert len(rmih) == 2
    zbuffers = 1 + int.from_bytes(rmih, signed=False, byteorder='little')
    assert 1 <= zbuffers <= 8

    imxx = sputm.find('IM00', rmim)
    im = convert_to_pil_image(
        read_room_background(imxx.children[0], rwidth, rheight, 0)
    )
    zpxx = list(sputm.findall('ZP{:02x}', imxx))
    assert len(zpxx) == zbuffers - 1
    im.putpalette(palette)
    return im

if __name__ == '__main__':
    import argparse
    import pprint

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        root = next(sputm.map_chunks(res), None)
        assert root.tag == 'LECF', root.tag
        for idx, lflf in enumerate(sputm.findall('LFLF', root)):
            read_room(lflf).save(f'ROOM_{idx:04d}_BG.png')

            # for lflf in sputm.findall('LFLF', t):
            #     tree = sputm.findpath('ROOM/OBIM/IM{:02x}', lflf)
            #     sputm.render(tree)

        print('==========')
