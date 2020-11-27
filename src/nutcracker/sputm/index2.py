#!/usr/bin/env python3

import io
import itertools
import os
import pprint
import operator
from functools import partial
from itertools import takewhile

from nutcracker.chiper import xor
from .preset import sputm
from .index import save_tree, read_file, compare_pid_off

def read_directory(data):
    with io.BytesIO(data) as s:
        num = int.from_bytes(s.read(1), byteorder='little', signed=False)
        merged = [(
            int.from_bytes(s.read(1), byteorder='little', signed=False),
            int.from_bytes(s.read(4), byteorder='little', signed=False)
        ) for i in range(num)]
        return merged

if __name__ == '__main__':
    import argparse
    from typing import Dict

    from .types import Chunk
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

    # os.makedirs(basedir, exist_ok=True)
    # with open(os.path.join(basedir, 'index.xml'), 'w') as f:
    #     for t in index_root:
    #         sputm.render(t, stream=f)
    #         print(t, t.data)

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

            if path in paths:
                path += 'd'
            assert path not in paths, path
            paths[path] = chunk

            res = {'path': path, 'gid': gid}
            return res


        disk_dir = os.path.join(basedir, f'DISK_{1+didx:04d}')

        root = sputm(max_depth=game.max_depth).map_chunks(resource, extra=update_element_path)
        os.makedirs(disk_dir, exist_ok=True)
        with open(os.path.join(disk_dir, 'rpdump.xml'), 'w') as f:
            for t in root:
                sputm.render(t, stream=f)
                save_tree(sputm, t, basedir=disk_dir)
