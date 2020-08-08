#!/usr/bin/env python3

import io
import os

import numpy as np

from nutcracker.sputm.index import read_index_v5tov7, read_index_he, read_file
from nutcracker.sputm.proom import read_rmhd, read_imhd, read_room_background, convert_to_pil_image

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
            assert idx == 0
            print(rwidth, rheight)
            bgim = read_room_background_v8(wrap.children[1], rwidth, rheight, 0)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            im.putpalette(palette)
            yield imag.attribs['path'], im, ()

def read_objects(lflf):
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
                im = convert_to_pil_image(bgim)
                im.putpalette(palette)
                yield imxx.attribs['path'], im
        elif len(imhd) < 80:
            # Game version == 7
            obj_id, obj_height, obj_width = read_imhd_v7(imhd)

            assert obj_id == obim.attribs['gid']

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
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
                yield imag.attribs['path'], im


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

    from .preset import sputm
    from .types import Chunk, Element

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    # # Configuration for HE games
    # index_suffix = '.HE0'
    # resource_suffix = '.HE1'
    # # resource_suffix = '.(a)'
    # read_index = read_index_he
    # chiper_key = 0x69

    # Configuration for SCUMM v5-v6 games
    index_suffix = '.000'
    resource_suffix = '.001'
    read_index = read_index_v5tov7
    chiper_key = 0x69

    index = read_file(args.filename + index_suffix, key=chiper_key)

    s = sputm.generate_schema(index)

    index_root = list(sputm(schema=s).map_chunks(index))

    idgens = read_index(index_root)

    resource = read_file(args.filename + resource_suffix, key=chiper_key)

    def update_element_path(parent, chunk, offset):
        get_gid = idgens.get(chunk.tag)
        gid = get_gid and get_gid(parent and parent.attribs['gid'], chunk.data, offset)

        base = chunk.tag + (f'_{gid:04d}' if gid is not None else '' if not get_gid else f'_o_{offset:04X}')

        dirname = parent.attribs['path'] if parent else ''
        path = os.path.join(dirname, base)
        res = {'path': path, 'gid': gid}

        return res

    root = sputm.map_chunks(resource, extra=update_element_path)
    base = os.path.join(os.path.basename(args.filename), 'IMAGES')
    os.makedirs(base, exist_ok=True)

    paths = {}

    for lflf in get_rooms(root):
        for oidx, (path, room_bg, zpxx) in enumerate(read_room(lflf)):
            path = path.replace(os.path.sep, '_')
            # dirname = os.path.dirname(path)
            # os.makedirs(os.path.join(base, dirname), exist_ok=True)
            assert not path in paths
            paths[path] = True
            room_bg.save(os.path.join(base, f'{path}.png'))

        for oidx, (path, im) in enumerate(read_objects(lflf)):
            path = path.replace(os.path.sep, '_')
            # dirname = os.path.dirname(path)
            # os.makedirs(os.path.join(base, dirname), exist_ok=True)
            assert not path in paths
            paths[path] = True
            im.save(os.path.join(base, f'{path}.png'))
