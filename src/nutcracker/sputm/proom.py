#!/usr/bin/env python3

import io
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from nutcracker.codex.codex import decode1
from .preset import sputm
from .room import decode_smap, convert_to_pil_image, decode_he, read_uint16le, read_uint32le, read_strip, parse_strip, read_room_background_v8

def read_room_background(image, width, height, zbuffers):
    if image.tag == 'SMAP':
        return decode_smap(height, width, image.data)
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

@dataclass
class RoomHeader:
    width: int
    height: int
    robjs: int
    version: Optional[int] = None
    zbuffers: Optional[int] = None
    transparency: Optional[int] = None

def read_rmhd_structured(data):
    version = None
    zbuffers = None
    transparency = None
    if len(data) == 6:
        # 'Game Version < 7'
        rwidth = int.from_bytes(data[:2], signed=False, byteorder='little')
        rheight = int.from_bytes(data[2:4], signed=False, byteorder='little')
        robjs = int.from_bytes(data[4:], signed=False, byteorder='little')
    elif len(data) == 10:
        # 'Game Version == 7'
        version = int.from_bytes(data[:4], signed=False, byteorder='little')
        rwidth = int.from_bytes(data[4:6], signed=False, byteorder='little')
        rheight = int.from_bytes(data[6:8], signed=False, byteorder='little')
        robjs = int.from_bytes(data[8:], signed=False, byteorder='little')
    else:
        # 'Game Version == 8'
        assert len(data) == 24
        version = int.from_bytes(data[:4], signed=False, byteorder='little')
        rwidth = int.from_bytes(data[4:8], signed=False, byteorder='little')
        rheight = int.from_bytes(data[8:12], signed=False, byteorder='little')
        robjs = int.from_bytes(data[12:16], signed=False, byteorder='little')
        zbuffers = int.from_bytes(data[16:20], signed=False, byteorder='little')
        transparency = int.from_bytes(data[20:24], signed=False, byteorder='little')
    return RoomHeader(
        width=rwidth,
        height=rheight,
        robjs=robjs,
        version=version,
        zbuffers=zbuffers,
        transparency=transparency
    )

def read_rmhd(data):
    print(data)
    if len(data) == 6:
        # 'Game Version < 7'
        rwidth = int.from_bytes(data[:2], signed=False, byteorder='little')
        rheight = int.from_bytes(data[2:4], signed=False, byteorder='little')
        robjs = int.from_bytes(data[4:], signed=False, byteorder='little')
    elif len(data) == 10:
        # 'Game Version == 7'
        version = int.from_bytes(data[:4], signed=False, byteorder='little')
        rwidth = int.from_bytes(data[4:6], signed=False, byteorder='little')
        rheight = int.from_bytes(data[6:8], signed=False, byteorder='little')
        robjs = int.from_bytes(data[8:], signed=False, byteorder='little')
    else:
        # 'Game Version == 8'
        assert len(data) == 24
        version = int.from_bytes(data[:4], signed=False, byteorder='little')
        rwidth = int.from_bytes(data[4:8], signed=False, byteorder='little')
        rheight = int.from_bytes(data[8:12], signed=False, byteorder='little')
        robjs = int.from_bytes(data[12:16], signed=False, byteorder='little')
        zbuffers = int.from_bytes(data[16:20], signed=False, byteorder='little')
        transparency = int.from_bytes(data[20:24], signed=False, byteorder='little')
    return rwidth, rheight, robjs

def read_room(lflf):
    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    rwidth, rheight, _ = read_rmhd(sputm.find('RMHD', room).data)
    # trns = sputm.find('TRNS', room).data  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).data

    rmim = sputm.find('RMIM', room) or sputm.find('RMIM', lflf)
    rmih = sputm.find('RMIH', rmim)
    if rmih:
        # 'Game Version < 7'
        assert len(rmih.data) == 2
        zbuffers = 1 + int.from_bytes(rmih.data, signed=False, byteorder='little')
        assert 1 <= zbuffers <= 8

        for idx, imxx in enumerate(sputm.findall('IM{:02x}', rmim)):
            assert idx == 0, idx
            assert imxx.tag == 'IM00', imxx.tag
            bgim = read_room_background(imxx.children[0], rwidth, rheight, zbuffers)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            zpxx = list(sputm.findall('ZP{:02x}', imxx))
            assert len(zpxx) == zbuffers - 1
            im.putpalette(palette)
            yield idx, im, zpxx
    else:
        # TODO: check for multiple IMAG in room bg (different image state)
        for idx, imag in enumerate(sputm.findall('IMAG', room)):
            wrap = sputm.find('WRAP', imag)
            assert idx == 0
            print(rwidth, rheight)
            bgim = read_room_background_v8(wrap.children[1], rwidth, rheight, 0)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            im.putpalette(palette)
            yield idx, im, ()

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
        return obj_id, obj_height, obj_width, obj_x, obj_y

def read_imhd_v7(data):
    # pylint: disable=unused-variable
    with io.BytesIO(data) as stream:
        version = read_uint32le(stream)
        obj_id = read_uint16le(stream)
        image_count = read_uint16le(stream)
        obj_x = read_uint16le(stream)
        obj_y = read_uint16le(stream)
        obj_width = read_uint16le(stream)
        obj_height = read_uint16le(stream)
        obj_unknown = stream.read(3)
        actor_dir = stream.read(1)[0]
        num_hotspots = read_uint16le(stream)
        obj_hotspots = stream.read()
        if obj_hotspots:
            # TODO: read hotspots
            pass
        return obj_id, obj_height, obj_width, obj_x, obj_y

def read_imhd_v8(data):
    # pylint: disable=unused-variable
    with io.BytesIO(data) as stream:
        name = stream.read(40).split(b'\0')[0].decode()
        version = read_uint32le(stream)
        image_count = read_uint32le(stream)
        obj_x = read_uint32le(stream)
        obj_y = read_uint32le(stream)
        obj_width = read_uint32le(stream)
        obj_height = read_uint32le(stream)
        actor_dir = read_uint32le(stream)
        flags = read_uint32le(stream)
        obj_hotspots = stream.read()
        if obj_hotspots:
            # TODO: read hotspots
            pass
        return name, obj_height, obj_width, obj_x, obj_y

def read_objects(lflf):
    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    # trns = sputm.find('TRNS', room).data  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).data

    for obim in sputm.findall('OBIM', room):
        imhd = sputm.find('IMHD', obim).data
        if len(imhd) == 16:
            obj_id, obj_height, obj_width = read_imhd(imhd)

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
                im = convert_to_pil_image(bgim)
                im.putpalette(palette)
                yield obj_id, imxx.tag, im
        elif len(imhd) < 80:
            # Game version == 7
            obj_id, obj_height, obj_width = read_imhd_v7(imhd)

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
                im = convert_to_pil_image(bgim)
                im.putpalette(palette)
                yield obj_id, imxx.tag, im
        else:
            # Game version == 8
            name, obj_height, obj_width = read_imhd_v8(imhd)
            print(name, obj_height, obj_width)
            for idx, imag in enumerate(sputm.findall('IMAG', obim)):
                assert idx == 0
                iim = sputm.find('WRAP', imag)
                bgim = read_room_background_v8(iim.children[1], obj_width, obj_height, 0)
                im = convert_to_pil_image(bgim)
                im.putpalette(palette)
                yield 0, f'{name}_STATE_{idx}', im

if __name__ == '__main__':
    import argparse
    import pprint

    from nutcracker.chiper import xor

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        resource = xor.read(res, key=int(args.chiper_key, 16))

    root = sputm.find('LECF', sputm.map_chunks(resource))
    assert root
    for idx, lflf in enumerate(sputm.findall('LFLF', root)):
        for oidx, (bg_idx, room_bg, zpxx) in enumerate(read_room(lflf)):
            room_bg.save(f'LFLF_{1 + idx:04d}_ROOM_RMIM_{bg_idx:04d}_{oidx:04d}.png')

        for oidx, (obj_idx, tag, im) in enumerate(read_objects(lflf)):
            im.save(f'LFLF_{1 + idx:04d}_ROOM_OBIM_{obj_idx:04d}_{tag}_{oidx:04d}.png')

        # for lflf in sputm.findall('LFLF', t):
        #     tree = sputm.findpath('ROOM/OBIM/IM{:02x}', lflf)
        #     sputm.render(tree)

    print('==========')
