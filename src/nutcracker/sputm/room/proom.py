#!/usr/bin/env python3

import io
from dataclasses import dataclass
from typing import Optional

import numpy as np

from nutcracker.codex.codex import decode1
from nutcracker.codex.smap import decode_he, decode_smap, read_uint16le, read_uint32le

from ..preset import sputm


def read_room_background_v8(image, width, height, zbuffers, transparency=None):
    if image.tag == 'SMAP':
        sputm.render(image)
        bstr = sputm.findpath('BSTR/WRAP', image)
        if not bstr:
            return None
        return decode_smap(height, width, bstr.data[8:], transparency=transparency)
    elif image.tag == 'BOMP':
        with io.BytesIO(image.data) as s:
            width = read_uint32le(s)
            height = read_uint32le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    else:
        raise ValueError(f'Unknown image codec: {image.tag}')


def read_room_background(image, width, height, zbuffers, transparency=None):
    if image.tag == 'SMAP':
        return decode_smap(height, width, image.data, transparency)
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


def read_rmhd_structured(data) -> RoomHeader:
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
        transparency=transparency,
    )


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
