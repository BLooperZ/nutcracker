#!/usr/bin/env python3\
import os
from struct import Struct
from typing import NamedTuple
from nutcracker.kernel.structured import StructuredTuple
from nutcracker.sputm.costume.akos import decode32
from nutcracker.utils.funcutils import flatten

from nutcracker.sputm.room.pproom import get_rooms, read_room_settings
from nutcracker.sputm.tree import open_game_resource

from ..preset import sputm


class WizHeader(NamedTuple):
    comp: int
    width: int
    height: int


WIZ_HEADER = StructuredTuple(('comp', 'width', 'height'), Struct('<3I'), WizHeader)


def read_wiz_header(data: bytes):
    return WIZ_HEADER.unpack_from(data)


def read_awiz_resource(awiz, room_palette):
    print(awiz.children)
    # awiz = iter(awiz)
    rgbs = sputm.find('RGBS', awiz)
    cnvs = sputm.find('CNVS', awiz)
    relo = sputm.find('RELO', awiz)
    wizh = sputm.find('WIZH', awiz)
    wizd = sputm.find('WIZD', awiz)
    comp, width, height = read_wiz_header(wizh.data)
    print(comp, width, height)
    palette = rgbs.data if rgbs is not None else room_palette
    if comp == 1:
        im = decode32(width, height, None, wizd.data)
        im.putpalette(palette)
        return im
    else:
        raise ValueError(comp)


if __name__ == '__main__':
    import argparse
    import glob
    import os

    from nutcracker.utils.fileio import read_file

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    args = parser.parse_args()

    files = sorted(set(flatten(glob.iglob(r) for r in args.files)))
    print(files)
    for filename in files:

        print(filename)

        gameres = open_game_resource(filename)
        basename = gameres.basename

        root = gameres.read_resources(
            # schema=narrow_schema(
            #     SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'PALS'}
            # )
        )

        os.makedirs(f'AWIZ_out/{basename}', exist_ok=True)

        for t in root:

            for lflf in get_rooms(t):
                print(lflf, lflf.attribs['path'])
                _, palette, _, _ = read_room_settings(lflf)

                for awiz in sputm.findall('AWIZ', lflf):
                    print(awiz, awiz.attribs["path"])

                    im = read_awiz_resource(awiz, palette)
                    im.save(f'AWIZ_out/{basename}/{os.path.basename(lflf.attribs["path"])}_{os.path.basename(awiz.attribs["path"])}.png')

                for mult in sputm.findall('MULT', lflf):
                    wrap = sputm.find('WRAP', mult)
                    for awiz in wrap.children[1:]:
                        im = read_awiz_resource(awiz, palette)
                        im.save(f'AWIZ_out/{basename}/{os.path.basename(lflf.attribs["path"])}_{os.path.basename(mult.attribs["path"])}_{os.path.basename(awiz.attribs["path"])}.png')
