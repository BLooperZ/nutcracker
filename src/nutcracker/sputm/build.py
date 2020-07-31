#!/usr/bin/env python3

import io
import glob
import itertools
import os
from typing import Iterable

from nutcracker.chiper import xor
from nutcracker.sputm.index import read_index_v5tov7, read_index_he, read_file, read_directory_leg as read_dir, read_dlfl

def write_file(path: str, data: bytes, key: int = 0x00) -> bytes:
    with open(path, 'wb') as res:
        return xor.write(res, data, key=key)

if __name__ == '__main__':
    import argparse
    import pprint
    from typing import Dict

    from .preset import sputm
    from .types import Chunk, Element

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('dirname', help='directory to read from')
    parser.add_argument('--ref', required=True, help='filename to read from')
    args = parser.parse_args()

    # Configuration for HE games
    index_suffix = '.HE0'
    resource_suffix = '.HE1' # '.(a)'
    read_index = read_index_he
    chiper_key = 0x69
    max_depth = 4

    # # Configuration for SCUMM v5-v6 games
    # index_suffix = '.000'
    # resource_suffix = '.001'
    # read_index = read_index_v5tov7
    # chiper_key = 0x69
    # max_depth = 4

    # # Configuration for SCUMM v7 games
    # index_suffix = '.LA0'
    # resource_suffix = '.LA1'
    # read_index = read_index_v5tov7
    # chiper_key = 0x00
    # max_depth = 3

    index = read_file(args.ref + index_suffix, key=chiper_key)

    s = sputm.generate_schema(index)
    pprint.pprint(s)

    index_root = list(sputm(schema=s).map_chunks(index))

    idgens = read_index(index_root)

    resource = read_file(args.ref + resource_suffix, key=chiper_key)

    # # commented out, use pre-calculated index instead, as calculating is time-consuming
    # s = sputm.generate_schema(resource)
    # pprint.pprint(s)
    # root = sputm.map_chunks(resource, idgen=idgens, schema=s)

    paths: Dict[str, Chunk] = {}

    def update_element_path(parent, chunk, offset):
        get_gid = idgens.get(chunk.tag)
        gid = get_gid and get_gid(parent and parent.attribs['gid'], chunk.data, offset)

        base = chunk.tag + (f'_{gid:04d}' if gid is not None else '' if not get_gid else f'_o_{offset:04X}')

        dirname = parent.attribs['path'] if parent else ''
        path = os.path.join(dirname, base)
        res = {'path': path, 'gid': gid}

        assert path not in paths, path
        paths[path] = chunk

        return res

    root = sputm(max_depth=max_depth).map_chunks(resource, extra=update_element_path)
    files = set(glob.iglob(f'{args.dirname}/**/*', recursive=True))
    assert None not in files

    def update_element(elements, files):
        offset = 0
        for elem in elements:
            elem.attribs['offset'] = offset
            full_path = os.path.join(args.dirname, elem.attribs.get('path'))
            if full_path in files:
                print(elem.attribs.get('path'))
                if os.path.isfile(full_path):
                    attribs = elem.attribs
                    elem = next(sputm.map_chunks(read_file(full_path)))
                    elem.attribs = attribs
                else:
                    elem.children = list(update_element(elem, files))
                    elem.data = sputm.write_chunks(sputm.mktag(e.tag, e.data) for e in elem.children)
            offset += len(elem.data) + 8
            elem.attribs['size'] = len(elem.data)
            yield elem

    updated_resource = list(update_element(root, files))
    write_file(
        f'{args.dirname}{resource_suffix}',
        sputm.write_chunks(sputm.mktag(e.tag, e.data) for e in updated_resource),
        key=chiper_key
    )

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


    dirmap = {
        'RMDA': dirr,
        'SCRP': dirs,
        'DIGI': dirn,
        'SOUN': dirn,
        'AKOS': dirc,
        'CHAR': dirf,
        'MULT': dirm,
        'AWIZ': dirm,
    }

    for t in updated_resource:
        # sputm.render(t)
        for lflf in sputm.findall('LFLF', t):
            diri[lflf.attribs['gid']] = (lflf.attribs['gid'], 0)
            dlfl[lflf.attribs['gid']] = lflf.attribs['offset'] + 16
            for elem in lflf:
                if elem.tag in dirmap and elem.attribs.get('gid'):
                    dirmap[elem.tag][elem.attribs['gid']] = (lflf.attribs['gid'], elem.attribs['offset'])

    def write_dlfl(index):
        yield len(index).to_bytes(2, byteorder='little', signed=False)
        yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in index.values())

    def write_dir(index):
        yield len(index).to_bytes(2, byteorder='little', signed=False)
        rooms, offsets = zip(*index.values())
        yield b''.join(room.to_bytes(1, byteorder='little', signed=False) for room in rooms)
        yield b''.join(off.to_bytes(4, byteorder='little', signed=False) for off in offsets)

    def bind_directory_changes(read, write, orig, mapping):
        bound = {**dict(read(orig)), **mapping}
        data = b''.join(write(bound))
        return data + orig[len(data):]

    def build_index(root: Iterable[Element]): 
        for elem in root:
            tag, data = elem.tag, elem.data
            if tag == 'DIRI':
                data = bind_directory_changes(read_dir, write_dir, elem.data, diri)
            if tag == 'DIRR':
                data = bind_directory_changes(read_dir, write_dir, elem.data, dirr)
            if tag == 'DIRS':
                data = bind_directory_changes(read_dir, write_dir, elem.data, dirs)
            if tag == 'DIRN':
                data = bind_directory_changes(read_dir, write_dir, elem.data, dirn)
            if tag == 'DIRC':
                data = bind_directory_changes(read_dir, write_dir, elem.data, dirc)
            if tag == 'DIRF':
                data = bind_directory_changes(read_dir, write_dir, elem.data, dirf)
            if tag == 'DIRM':
                data = bind_directory_changes(read_dir, write_dir, elem.data, dirm)
            if tag == 'DLFL':
                data = bind_directory_changes(read_dlfl, write_dlfl, elem.data, dlfl)
            yield sputm.mktag(tag, data)

    write_file(
        f'{args.dirname}{index_suffix}',
        sputm.write_chunks(build_index(index_root)),
        key=chiper_key
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
