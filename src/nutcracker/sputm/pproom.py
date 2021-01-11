#!/usr/bin/env python3

import io
import os

import numpy as np

from .index import read_index_v5tov7, read_index_he, read_file
from .proom import (
    read_rmhd,
    read_rmhd_structured,
    read_imhd,
    read_imhd_v7,
    read_imhd_v8,
    read_room_background,
    read_room_background_v8,
    convert_to_pil_image
)

from .preset import sputm


def read_room_settings(lflf):
    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    header = read_rmhd_structured(sputm.find('RMHD', room).data)
    trns = sputm.find('TRNS', room)
    if trns:
        assert header.transparency is None
        header.transparency = sputm.find('TRNS', room).data  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).data

    rmim = sputm.find('RMIM', room) or sputm.find('RMIM', lflf)
    rmih = sputm.find('RMIH', rmim)
    if rmih:
        # 'Game Version < 7'
        assert header.zbuffers is None
        assert len(rmih.data) == 2
        header.zbuffers = 1 + int.from_bytes(rmih.data, signed=False, byteorder='little')
        assert 1 <= header.zbuffers <= 8

    return header, palette, room, rmim or sputm.find('IMAG', room)

def read_room(header, rmim):
    if rmim.tag == 'RMIM':
        # 'Game Version < 7'
        for imxx in sputm.findall('IM{:02x}', rmim):
            assert imxx.tag == 'IM00', imxx.tag
            bgim = read_room_background(imxx.children[0], header.width, header.height, header.zbuffers)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            zpxx = list(sputm.findall('ZP{:02x}', imxx))
            assert len(zpxx) == header.zbuffers - 1

            path = imxx.attribs['path']
            yield path, im, zpxx
    else:
        # TODO: check for multiple IMAG in room bg (different image state)
        assert rmim.tag == 'IMAG'
        wrap = sputm.find('WRAP', rmim)
        assert len(wrap.children) == 2, len(wrap.children)

        for imxx in wrap.children[1:]:
            assert imxx.attribs['gid'] == 1, imxx.attribs['gid']

            chunk = sputm.mktag(imxx.tag, imxx.data)
            s = sputm.generate_schema(chunk)
            image = next(sputm(schema=s).map_chunks(chunk))

            bgim = read_room_background_v8(image, header.width, header.height, header.zbuffers)
            if bgim is None:
                continue
            im = convert_to_pil_image(bgim)
            zpxx = ()
            zpln = sputm.findpath('ZPLN/WRAP', image)
            if zpln:
                zpxx = [zpln]

            path = imxx.attribs['path']

            yield path, im, zpxx

def read_objects(room):
    for obim in sputm.findall('OBIM', room):
        imhd = sputm.find('IMHD', obim).data
        if len(imhd) == 16:
            obj_id, obj_height, obj_width, obj_x, obj_y = read_imhd(imhd)

            assert obj_id == obim.attribs['gid']

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
                if bgim is None:
                    continue
                im = convert_to_pil_image(bgim)

                path = imxx.attribs['path']
                name = f'{obj_id:04d}_{imxx.tag}'

                yield path, name, im, obj_x, obj_y
        elif len(imhd) < 80:
            # Game version == 7
            print(imhd)
            obj_id, obj_height, obj_width, obj_x, obj_y = read_imhd_v7(imhd)
            # assert obj_id == obim.attribs['gid'], (obj_id, obim.attribs['gid'])  # assertion breaks on HE games

            for imxx in sputm.findall('IM{:02x}', obim):
                bgim = read_room_background(imxx.children[0], obj_width, obj_height, 0)
                if bgim is None:
                    continue
                im = convert_to_pil_image(bgim)

                path = imxx.attribs['path']
                obj_id = obim.attribs['gid']
                name = f'{obj_id:04d}_{imxx.tag}'

                yield path, name, im, obj_x, obj_y
        else:
            # Game version == 8
            obj_name, obj_height, obj_width, obj_x, obj_y = read_imhd_v8(imhd)
            print(obj_name, obj_height, obj_width)
            for idx, imag in enumerate(sputm.findall('IMAG', obim)):
                assert idx == 0
                wrap = sputm.find('WRAP', imag)
                for iidx, bomp in enumerate(wrap.children[1:]):

                    chunk = sputm.mktag(bomp.tag, bomp.data)
                    s = sputm.generate_schema(chunk)
                    image = next(sputm(schema=s).map_chunks(chunk))

                    bgim = read_room_background_v8(image, obj_width, obj_height, 0)
                    im = convert_to_pil_image(bgim)

                    path = bomp.attribs['path']
                    name = f'{obj_name}_{iidx:04d}'

                    yield path, name, im, obj_x, obj_y


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
    from .index2 import read_directory, read_game_resources
    from .index import compare_pid_off, read_rnam
    from .resource import detect_resource
    from nutcracker.graphics.frame import resize_pil_image

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

    rnam, idgens = game.read_index(index_root)

    root = read_game_resources(game, idgens, disks, max_depth=None)

    base = os.path.join(os.path.basename(args.filename), 'IMAGES')
    os.makedirs(base, exist_ok=True)

    os.makedirs(os.path.join(base, 'backgrounds'), exist_ok=True)
    os.makedirs(os.path.join(base, 'objects'), exist_ok=True)
    os.makedirs(os.path.join(base, 'objects_layers'), exist_ok=True)

    for t in root:
        paths = {}

        for lflf in get_rooms(t):
            header, palette, room, rmim = read_room_settings(lflf)
            room_bg = None
            room_id = lflf.attribs.get('gid')

            for path, room_bg, zpxx in read_room(header, rmim):
                room_bg.putpalette(palette)

                path = f"{room_id:04d}_{rnam.get(room_id)}" if room_id in rnam else path

                path = path.replace(os.path.sep, '_')
                # dirname = os.path.dirname(path)
                # os.makedirs(os.path.join(base, dirname), exist_ok=True)
                assert path not in paths, path
                paths[path] = True
                room_bg.save(os.path.join(base, 'backgrounds', f'{path}.png'))

            for path, name, im, obj_x, obj_y in read_objects(room):
                im.putpalette(palette)

                path = f'{room_id:04d}_{name}' if room_id in rnam else path

                path = path.replace(os.path.sep, '_')
                # dirname = os.path.dirname(path)
                # os.makedirs(os.path.join(base, dirname), exist_ok=True)
                # while path in paths:
                #     path += 'd'
                assert not path in paths, (path, paths)
                paths[path] = True
                im.save(os.path.join(base, 'objects', f'{path}.png'))

                if room_bg:
                    im_layer = resize_pil_image(*room_bg.size, 39, im, {'x1': obj_x, 'y1': obj_y})
                    im_layer.putpalette(palette)
                    im_layer.save(os.path.join(base, 'objects_layers', f'{path}.png'))
