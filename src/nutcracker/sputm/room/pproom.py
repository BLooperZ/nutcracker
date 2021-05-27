#!/usr/bin/env python3

import os

import numpy as np
from PIL import Image

from nutcracker.graphics import image

from ..preset import sputm
from .proom import (
    convert_to_pil_image,
    read_imhd,
    read_imhd_v7,
    read_imhd_v8,
    read_rmhd_structured,
    read_room_background,
    read_room_background_v8,
)


def read_room_settings(lflf):
    room = sputm.find('ROOM', lflf) or sputm.find('RMDA', lflf)
    header = read_rmhd_structured(sputm.find('RMHD', room).data)
    trns = sputm.find('TRNS', room)
    if trns:
        assert header.transparency is None
        header.transparency = sputm.find(
            'TRNS', room
        ).data  # pylint: disable=unused-variable
    palette = (sputm.find('CLUT', room) or sputm.findpath('PALS/WRAP/APAL', room)).data

    rmim = sputm.find('RMIM', room) or sputm.find('RMIM', lflf)
    rmih = sputm.find('RMIH', rmim)
    if rmih:
        # 'Game Version < 7'
        assert header.zbuffers is None
        assert len(rmih.data) == 2
        header.zbuffers = 1 + int.from_bytes(
            rmih.data, signed=False, byteorder='little'
        )
        assert 1 <= header.zbuffers <= 8

    return header, palette, room, rmim or sputm.find('IMAG', room)


def read_room(header, rmim):
    if rmim.tag == 'RMIM':
        # 'Game Version < 7'
        for imxx in sputm.findall('IM{:02x}', rmim):
            assert imxx.tag == 'IM00', imxx.tag
            bgim = read_room_background(
                imxx.children[0], header.width, header.height, header.zbuffers
            )
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

            bgim = read_room_background_v8(
                image, header.width, header.height, header.zbuffers
            )
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


EGA = (
    (0, 0, 0),
    (0, 0, 170),
    (0, 170, 0),
    (0, 170, 170),
    (170, 0, 0),
    (170, 0, 170),
    (170, 85, 0),
    (170, 170, 170),
    (85, 85, 85),
    (85, 85, 255),
    (85, 255, 85),
    (85, 255, 255),
    (255, 85, 85),
    (255, 85, 255),
    (255, 255, 85),
    (255, 255, 255),
)
EGA = np.asarray(EGA, dtype=np.uint8)

if __name__ == '__main__':
    import argparse

    from nutcracker.graphics.frame import resize_pil_image

    from ..tree import open_game_resource, narrow_schema
    from ..schema import SCHEMA

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--ega', action='store_true', help='output is in EGA mode')
    args = parser.parse_args()

    filename = args.filename

    gameres = open_game_resource(filename)
    basename = gameres.basename

    root = gameres.read_resources(
        # schema=narrow_schema(
        #     SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'PALS'}
        # )
    )

    rnam = gameres.rooms

    base = os.path.join(basename, 'IMAGES')
    os.makedirs(base, exist_ok=True)

    os.makedirs(os.path.join(base, 'backgrounds'), exist_ok=True)
    os.makedirs(os.path.join(base, 'objects'), exist_ok=True)
    os.makedirs(os.path.join(base, 'objects_layers'), exist_ok=True)

    for t in root:
        paths = {}

        for lflf in get_rooms(t):
            header, palette, room, rmim = read_room_settings(lflf)
            epal = sputm.find('EPAL', room)
            if epal:
                egapal = np.frombuffer(epal.data, dtype=np.uint8)
            room_bg = None
            room_id = lflf.attribs.get('gid')

            for path, room_bg, zpxx in read_room(header, rmim):
                if args.ega and epal:
                    room_bg = np.asarray(room_bg)
                    room_bg1 = egapal[room_bg] % 16
                    room_bg2 = egapal[room_bg] // 16
                    room_bg3 = np.copy(room_bg1)
                    room_bg4 = np.copy(room_bg2)
                    room_bg3[::2, :] = room_bg2[::2, :]
                    room_bg4[::2, :] = room_bg1[::2, :]
                    room_bg = np.dstack([room_bg3, room_bg4]).reshape(
                        room_bg.shape[0], room_bg.shape[1] * 2
                    )
                    room_bg = np.repeat(room_bg, 2, axis=0)
                    # print(room_bg.shape)
                    room_bg = Image.fromarray(EGA[np.asarray(room_bg)])
                else:
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
                    im_layer = resize_pil_image(
                        *room_bg.size, 39, im, image.ImagePosition(x1=obj_x, y1=obj_y)
                    )
                    im_layer.putpalette(palette)
                    im_layer.save(os.path.join(base, 'objects_layers', f'{path}.png'))
