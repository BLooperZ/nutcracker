#!/usr/bin/env python3

import io
import os

import numpy as np

from nutcracker.utils.fileio import read_file, write_file
from .proom import (
    read_imhd,
    read_imhd_v7,
    read_imhd_v8,
)
from .pproom import (
    read_room_settings,
    get_rooms,
)
from .encode_image import encode_block

def read_room(header, rmim):
    if rmim.tag == 'RMIM':
        # 'Game Version < 7'
        for imxx in sputm.findall('IM{:02x}', rmim):
            assert imxx.tag == 'IM00', imxx.tag
            yield from imxx.children
    else:
        # TODO: check for multiple IMAG in room bg (different image state)
        assert rmim.tag == 'IMAG'
        wrap = sputm.find('WRAP', rmim)
        assert len(wrap.children) == 2, len(wrap.children)
        yield from wrap.children[1:]

def read_objects(room):
    for obim in sputm.findall('OBIM', room):
        imhd = sputm.find('IMHD', obim).data
        if len(imhd) == 16:
            obj_id, obj_height, obj_width, obj_x, obj_y = read_imhd(imhd)

            assert obj_id == obim.attribs['gid']

            for imxx in sputm.findall('IM{:02x}', obim):
                path = imxx.attribs['path']
                name = f'{obj_id:04d}_{imxx.tag}'

                yield path, name, imxx.children[0], obj_x, obj_y
        elif len(imhd) < 80:
            # Game version == 7
            print(imhd)
            obj_id, obj_height, obj_width, obj_x, obj_y = read_imhd_v7(imhd)
            # assert obj_id == obim.attribs['gid'], (obj_id, obim.attribs['gid'])  # assertion breaks on HE games

            for imxx in sputm.findall('IM{:02x}', obim):
                path = imxx.attribs['path']
                name = f'{obj_id:04d}_{imxx.tag}'

                yield path, name, imxx.children[0], obj_x, obj_y
        else:
            # Game version == 8
            obj_name, obj_height, obj_width, obj_x, obj_y = read_imhd_v8(imhd)
            for idx, imag in enumerate(sputm.findall('IMAG', obim)):
                assert idx == 0
                wrap = sputm.find('WRAP', imag)
                for iidx, bomp in enumerate(wrap.children[1:]):

                    path = bomp.attribs['path']
                    name = f'{obj_name}_{iidx:04d}'

                    yield path, name, bomp, obj_x, obj_y


if __name__ == '__main__':
    import argparse
    import pprint
    from typing import Dict

    from .types import Chunk
    from .index2 import read_directory, read_game_resources
    from .index import compare_pid_off, read_rnam
    from .preset import sputm
    from .resource import detect_resource
    from nutcracker.image import resize_pil_image

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('dirname', help='directory to read from')
    parser.add_argument('--ref', required=True, help='filename to read from')
    args = parser.parse_args()

    game = detect_resource(args.ref)
    index_file, *disks = game.resources

    index = read_file(index_file, key=game.chiper_key)

    s = sputm.generate_schema(index)
    pprint.pprint(s)

    index_root = sputm(schema=s).map_chunks(index)
    index_root = list(index_root)

    rnam, idgens = game.read_index(index_root)

    root = read_game_resources(game, idgens, disks, max_depth=None)

    base = os.path.join(args.dirname, 'IMAGES')

    for t in root:
        for lflf in get_rooms(t):
            header, palette, room, rmim = read_room_settings(lflf)
            room_bg = None
            room_id = lflf.attribs.get('gid')

            for imxx in read_room(header, rmim):

                im_path = f"{room_id:04d}_{rnam.get(room_id)}" if room_id in rnam else path
                im_path = im_path.replace(os.path.sep, '_')
                im_path = os.path.join(base, 'backgrounds', f'{im_path}.png')
                if os.path.exists(im_path):
                    res_path = os.path.join(args.dirname, imxx.attribs['path'])
                    encoded = encode_block(im_path, imxx.tag)
                    if encoded:
                        os.makedirs(os.path.dirname(res_path), exist_ok=True)
                        write_file(
                            res_path,
                            encoded
                        )
                    print((im_path, res_path, imxx.tag))

            for path, name, imxx, obj_x, obj_y in read_objects(room):

                im_path = f'{room_id:04d}_{name}' if room_id in rnam else path
                im_path = im_path.replace(os.path.sep, '_')
                im_path = os.path.join(base, 'objects', f'{im_path}.png')

                if os.path.exists(im_path):
                    res_path = os.path.join(args.dirname, imxx.attribs['path'])
                    encoded = encode_block(im_path, imxx.tag)
                    if encoded:
                        # TODO: fix OFFS when inside WRAP
                        # maybe should avoid flattening the generator
                        os.makedirs(os.path.dirname(res_path), exist_ok=True)
                        write_file(
                            res_path,
                            encoded
                        )
                    print((im_path, res_path, imxx.tag))
