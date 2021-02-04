#!/usr/bin/env python3

import binascii
import os
from typing import Iterable

from nutcracker.utils.fileio import read_file
from nutcracker.sputm.build import rebuild_resources


def get_all_sounds(root, abs_off=0):
    for elem in root:
        if elem.tag in {'LECF', 'LFLF', 'SOUN'}:
            if elem.tag == 'SOUN':
                yield elem.attribs['offset'] + abs_off, elem.data
            else:
                yield from get_all_sounds(
                    elem.children, abs_off=elem.attribs['offset'] + abs_off + 8
                )


def inject_sound_chunks(root, sounds):
    offset = 0
    for elem in root:
        elem.attribs['offset'] = offset
        if elem.tag in {'LECF', 'LFLF', 'SOUN'}:
            if elem.tag == 'SOUN':
                attribs = elem.attribs
                elem.data = next(sounds)
                elem.attribs = attribs
            else:
                elem.children = list(inject_sound_chunks(elem, sounds))
                elem.data = sputm.write_chunks(
                    sputm.mktag(e.tag, e.data) for e in elem.children
                )
        offset += len(elem.data) + 8
        elem.attribs['size'] = len(elem.data)
        yield elem


def read_hex(hexstr: str) -> bytes:
    return binascii.unhexlify(hexstr.encode())


def read_streams(src_dir: str, ext: str, files: Iterable[str]) -> Iterable[bytes]:
    for file in files:
        yield read_file(os.path.join(src_dir, f'{file}.{ext}'))


if __name__ == '__main__':
    import argparse
    import pprint

    from .preset import sputm
    from .resource import detect_resource
    from .index2 import read_game_resources
    from .build import update_loff

    parser = argparse.ArgumentParser(description='read smush file')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--extract', '-e', action='store_true')
    group.add_argument('--inject', '-i', action='store_true')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument(
        '--textfile', '-t', help='save strings to file', default='embedded.txt'
    )
    args = parser.parse_args()

    game = detect_resource(args.filename)
    index_file, *disks = game.resources

    index = read_file(index_file, key=game.chiper_key)

    s = sputm.generate_schema(index)
    pprint.pprint(s)

    index_root = sputm(schema=s).map_chunks(index)
    index_root = list(index_root)

    _, idgens = game.read_index(index_root)

    root = read_game_resources(game, idgens, disks, max_depth=5)

    if args.extract:
        os.makedirs('sfx_ext', exist_ok=True)
        with open(args.textfile, 'r') as voctable:
            coff = next(voctable)
            for off, stream in get_all_sounds(root):
                vname = f'{off:08x}'
                if coff.startswith(vname):
                    vname = coff[8:-1]
                    coff = next(voctable, '')
                else:
                    print(coff, 'X', vname)

                with open(os.path.join('sfx_ext', f'{vname}.voc'), 'wb') as voc:
                    voc.write(stream)

    elif args.inject:
        # TODO: use actual streams
        with open(args.textfile, 'r') as voctable:
            streams = [line[8:-1] for line in voctable]
        cstreams = (
            sputm.mktag('MPEG', cont) for cont in read_streams('sfx_hq', 'mp3', streams)
        )
        updated_resource = list(inject_sound_chunks(root, cstreams))

        basename = os.path.basename(args.filename)
        rebuild_resources(game, basename, disks, index_root, updated_resource)
