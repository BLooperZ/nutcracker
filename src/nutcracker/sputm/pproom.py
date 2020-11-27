#!/usr/bin/env python3

import io
import os

import numpy as np

from nutcracker.sputm.index import read_index_v5tov7, read_index_he, read_file
from nutcracker.sputm.proom import (
    read_rmhd,
    read_imhd,
    read_imhd_v7,
    read_imhd_v8,
    read_room_background,
    read_room_background_v8,
    convert_to_pil_image
)

def read_room(lflf, rnam=None):
    rnam = rnam or {}

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

        for imxx in sputm.findall('IM{:02x}', rmim):
            assert imxx.tag == 'IM00', imxx.tag
            bgim = read_room_background(imxx.children[0], rwidth, rheight, zbuffers)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            zpxx = list(sputm.findall('ZP{:02x}', imxx))
            assert len(zpxx) == zbuffers - 1
            im.putpalette(palette)
            yield imxx.attribs['path'], im, zpxx
    else:
        # TODO: check for multiple IMAG in room bg (different image state)
        for imag in sputm.findall('IMAG', room):
            wrap = sputm.find('WRAP', imag)
            print(rwidth, rheight)
            bgim = read_room_background_v8(wrap.children[1], rwidth, rheight, 0)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            im.putpalette(palette)
            room_id = lflf.attribs.get('gid')
            path = f"{room_id:04d}_{rnam.get(room_id)}" if room_id in rnam else room.attribs['path']

            yield path, im, ()

def read_objects(lflf, rnam=None):
    rnam = rnam or {}

    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    # trns = sputm.find('TRNS', room).data  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).data

    for obim in sputm.findall('OBIM', room):
        imhd = sputm.find('IMHD', obim).data
        if len(imhd) == 16:
            obj_id, obj_height, obj_width = read_imhd(imhd)

            assert obj_id == obim.attribs['gid']

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
                if bgim is None:
                    continue
                im = convert_to_pil_image(bgim)
                im.putpalette(palette)
                yield imxx.attribs['path'], im
        elif len(imhd) < 80:
            # Game version == 7
            print(imhd)
            obj_id, obj_height, obj_width = read_imhd_v7(imhd)
            # assert obj_id == obim.attribs['gid'], (obj_id, obim.attribs['gid'])

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
                if bgim is None:
                    continue
                im = convert_to_pil_image(bgim)
                im.putpalette(palette)
                yield imxx.attribs['path'], im
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
                room_id = lflf.attribs.get('gid')
                path = f'{room_id:04d}_{name}' if room_id in rnam else f"{obim.attribs['path']}_{name}"
                yield path, im


def get_rooms(root):
    for elem in root:
        if elem.tag in {'LECF', 'LFLF'}:
            if elem.tag in {'LFLF'}:
                yield elem
            else:
                yield from get_rooms(elem.children)


if __name__ == '__main__':
    import argparse
    import pprint
    from typing import Dict

    from .types import Chunk
    from .index2 import read_directory
    from .index import compare_pid_off, read_rnam
    from .preset import sputm
    from .resource import detect_resource

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    basedir = os.path.basename(args.filename)

    game = detect_resource(args.filename)
    index_file, *disks = game.resources

    index = read_file(index_file, key=game.chiper_key)

    s = sputm.generate_schema(index)
    pprint.pprint(s)

    index_root = sputm(schema=s).map_chunks(index)
    index_root = list(index_root)


    for didx, disk in enumerate(disks):
        rnam, idgens = game.read_index(index_root)

        resource = read_file(disk, key=game.chiper_key)

        # # commented out, use pre-calculated index instead, as calculating is time-consuming
        # s = sputm.generate_schema(resource)
        # pprint.pprint(s)
        # root = sputm.map_chunks(resource, idgen=idgens, schema=s)

        def update_element_path(parent, chunk, offset):

            if chunk.tag == 'LOFF':
                # should not happen in HE games
                droo = idgens['LFLF']
                droo = {k: v for k, v  in droo.items() if v == (didx + 1, 0)}
                offs = dict(read_directory(chunk.data))
                droo = {k: (disk, offs[k]) for k, (disk, _)  in droo.items()}
                print(droo)
                idgens['LFLF'] = compare_pid_off(droo, 16 - game.base_fix)

            get_gid = idgens.get(chunk.tag)
            if not parent:
                gid = didx + 1
            else:
                gid = get_gid and get_gid(parent and parent.attribs['gid'], chunk.data, offset)

            base = chunk.tag + (f'_{gid:04d}' if gid is not None else '' if not get_gid else f'_o_{offset:04X}')

            dirname = parent.attribs['path'] if parent else ''
            path = os.path.join(dirname, base)
            res = {'path': path, 'gid': gid}
            return res


        root = sputm.map_chunks(resource, extra=update_element_path)
        base = os.path.join(os.path.basename(args.filename), 'IMAGES')
        os.makedirs(base, exist_ok=True)

        os.makedirs(os.path.join(base, 'backgrounds'), exist_ok=True)
        os.makedirs(os.path.join(base, 'objects'), exist_ok=True)

        paths = {}

        for lflf in get_rooms(root):
            for oidx, (path, room_bg, zpxx) in enumerate(read_room(lflf, rnam)):
                path = path.replace(os.path.sep, '_')
                # dirname = os.path.dirname(path)
                # os.makedirs(os.path.join(base, dirname), exist_ok=True)
                assert path not in paths, path
                paths[path] = True
                room_bg.save(os.path.join(base, 'backgrounds', f'{path}.png'))

            for oidx, (path, im) in enumerate(read_objects(lflf, rnam)):
                path = path.replace(os.path.sep, '_')
                # dirname = os.path.dirname(path)
                # os.makedirs(os.path.join(base, dirname), exist_ok=True)
                # while path in paths:
                #     path += 'd'
                assert not path in paths, path
                paths[path] = True
                im.save(os.path.join(base, 'objects', f'{path}.png'))
