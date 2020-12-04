#!/usr/bin/env python3

import io
import glob
import itertools
import os
from typing import Iterable

from nutcracker.chiper import xor
from nutcracker.sputm.index import (
    read_file,
    read_directory_leg as read_dir,
    read_directory_leg_v8 as read_dir_v8,
    read_dlfl,
)

from .preset import sputm
from .types import Chunk, Element

def write_file(path: str, data: bytes, key: int = 0x00) -> bytes:
    with open(path, 'wb') as res:
        return xor.write(res, data, key=key)

def write_dlfl(index):
    yield len(index).to_bytes(2, byteorder='little', signed=False)
    yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in index.values())

def write_dir(index):
    yield len(index).to_bytes(2, byteorder='little', signed=False)
    rooms, offsets = zip(*index.values())
    yield b''.join(room.to_bytes(1, byteorder='little', signed=False) for room in rooms)
    yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in offsets)

def write_dir_v8(index):
    yield len(index).to_bytes(4, byteorder='little', signed=False)
    rooms, offsets = zip(*index.values())
    yield b''.join(room.to_bytes(1, byteorder='little', signed=False) for room in rooms)
    yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in offsets)


def bind_directory_changes(read, write, orig, mapping):
    bound = {**dict(read(orig)), **mapping}
    data = b''.join(write(bound))
    return data + orig[len(data):]

def make_index_from_resource(resource, ref, base_fix: int = 0):
    maxs = {}
    diri = {}
    dirr = {}
    dirs = {}
    dirn = {}
    dirc = {}
    dirf = {}
    dirm = {}
    dlfl = {}
    rnam = {}
    dobj = {}
    aary = {}


    resmap = {
        'RMDA': dirr,
        'SCRP': dirs,
        'DIGI': dirn,
        'SOUN': dirn,
        'AKOS': dirc,
        'CHAR': dirf,
        'MULT': dirm,
        'AWIZ': dirm,
        'COST': dirc,
    }

    dirmap = {
        # Humoungus Entertainment games
        'DIRI': diri,
        'DIRR': dirr,
        'DIRS': dirs,
        'DIRN': dirn,
        'DIRC': dirc,
        'DIRF': dirf,
        'DIRM': dirm,
        # LucasArts SCUMM games
        'DSCR': dirs,
        'DSOU': dirn,
        'DCOS': dirc,
        'DCHR': dirf,
    }

    for t in resource:
        # sputm.render(t)
        for lflf in sputm.findall('LFLF', t):
            diri[lflf.attribs['gid']] = (lflf.attribs['gid'], 0)
            dlfl[lflf.attribs['gid']] = lflf.attribs['offset'] + 16
            for elem in lflf:
                if elem.tag in resmap and elem.attribs.get('gid'):
                    resmap[elem.tag][elem.attribs['gid']] = (lflf.attribs['gid'], elem.attribs['offset'] + base_fix)

    def build_index(root: Iterable[Element]): 
        for elem in root:
            tag, data = elem.tag, elem.data

            reader, writer = (read_dir_v8, write_dir_v8) if base_fix == 8 else (read_dir, write_dir)

            if tag == 'DLFL':
                data = bind_directory_changes(read_dlfl, write_dlfl, elem.data, dlfl)
            if tag in dirmap:
                data = bind_directory_changes(reader, writer, elem.data, dirmap[tag])

            yield sputm.mktag(tag, data)

    return build_index(ref)

def update_element(basedir, elements, files):
    offset = 0
    for elem in elements:
        elem.attribs['offset'] = offset
        full_path = os.path.join(basedir, elem.attribs.get('path'))
        if full_path in files:
            print(elem.attribs.get('path'))
            if os.path.isfile(full_path):
                attribs = elem.attribs
                elem = next(sputm.map_chunks(read_file(full_path)))
                elem.attribs = attribs
            else:
                elem.children = list(update_element(basedir, elem, files))
                elem.data = sputm.write_chunks(sputm.mktag(e.tag, e.data) for e in elem.children)
        offset += len(elem.data) + 8
        elem.attribs['size'] = len(elem.data)
        yield elem


if __name__ == '__main__':
    import argparse
    from typing import Dict

    from .types import Chunk
    from .resource import detect_resource
    from .index import compare_pid_off
    from .index2 import read_directory

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('dirname', help='directory to read from')
    parser.add_argument('--ref', required=True, help='filename to read from')
    args = parser.parse_args()

    game = detect_resource(args.ref)
    index_file, *disks = game.resources

    index = read_file(index_file, key=game.chiper_key)

    s = sputm.generate_schema(index)

    index_root = sputm(schema=s).map_chunks(index)
    index_root = list(index_root)

    reses = []

    basename = os.path.basename(os.path.normpath(args.dirname))

    for didx, disk in enumerate(disks):
        _, idgens = game.read_index(index_root)

        resource = read_file(disk, key=game.chiper_key)

        # # commented out, use pre-calculated index instead, as calculating is time-consuming
        # s = sputm.generate_schema(resource)
        # pprint.pprint(s)
        # root = sputm.map_chunks(resource, idgen=idgens, schema=s)

        paths: Dict[str, Chunk] = {}

        def update_element_path(parent, chunk, offset):

            if chunk.tag == 'LOFF':
                # should not happen in HE games

                offs = dict(read_directory(chunk.data))

                # # to ignore cloned rooms
                # droo = idgens['LFLF']
                # droo = {k: v for k, v  in droo.items() if v == (didx + 1, 0)}
                # droo = {k: (disk, offs[k]) for k, (disk, _)  in droo.items()}

                droo = {k: (didx + 1, v) for k, v  in offs.items()}
                idgens['LFLF'] = compare_pid_off(droo, 16 - game.base_fix)

            get_gid = idgens.get(chunk.tag)
            if not parent:
                gid = didx + 1
            else:
                gid = get_gid and get_gid(parent and parent.attribs['gid'], chunk.data, offset)

            base = chunk.tag + (f'_{gid:04d}' if gid is not None else '' if not get_gid else f'_o_{offset:04X}')

            dirname = parent.attribs['path'] if parent else ''
            path = os.path.join(dirname, base)

            if path in paths:
                path += 'd'
            assert path not in paths, path
            paths[path] = chunk

            res = {'path': path, 'gid': gid}
            return res

        root = sputm(max_depth=game.max_depth).map_chunks(resource, extra=update_element_path)

        basedir = os.path.join(f'{args.dirname}', f'DISK_{1+didx:04d}')

        files = set(glob.iglob(f'{basedir}/**/*', recursive=True))
        assert None not in files

        updated_resource = list(update_element(basedir, root, files))

        # Update LOFF chunk if exists
        for t in updated_resource:
            loff = sputm.find('LOFF', t)
            if loff:
                rooms = list(sputm.findall('LFLF', t))
                with io.BytesIO() as stream:
                    stream.write(bytes([len(rooms)]))
                    for room in rooms:
                        room_id = room.attribs['gid']
                        room_off = room.attribs['offset'] + 16 - game.base_fix
                        stream.write(room_id.to_bytes(1, byteorder='little', signed=False))
                        stream.write(room_off.to_bytes(4, byteorder='little', signed=False))
                    loff_data = stream.getvalue()
                assert len(loff.data) == len(loff_data)
                loff.data = loff_data

        _, ext = os.path.splitext(disk)
        write_file(
            f'{basename}{ext}',
            sputm.write_chunks(sputm.mktag(e.tag, e.data) for e in updated_resource),
            key=game.chiper_key
        )
        reses += updated_resource

    _, ext = os.path.splitext(index_file)
    write_file(
        f'{basename}{ext}',
        sputm.write_chunks(make_index_from_resource(reses, index_root, game.base_fix)),
        key=game.chiper_key
    )

### REFERENCE
# <MAXS ---- path="MAXS" />
# <DIRI ---- path="DIRI" />
# <DIRR ---- path="DIRR" />
# <DIRS ---- path="DIRS" />
# <DIRN ---- path="DIRN" />
# <DIRC ---- path="DIRC" />
# <DIRF ---- path="DIRF" />
# <DIRM ---- path="DIRM" />
# <DLFL ---- path="DLFL" />
# <RNAM ---- path="RNAM" />
# <DOBJ ---- path="DOBJ" />
# <AARY ---- path="AARY" />