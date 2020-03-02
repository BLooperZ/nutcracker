#!/usr/bin/env python3

import io
import itertools
import os
from nutcracker.chiper import xor

def read_directory_leg(data):
    with io.BytesIO(data) as s:
        num = int.from_bytes(s.read(2), byteorder='little', signed=False)
        rnums = [int.from_bytes(s.read(1), byteorder='little', signed=False) for i in range(num)]
        offs = [int.from_bytes(s.read(4), byteorder='little', signed=False) for i in range(num)]
        return enumerate(zip(rnums, offs))

def read_rnam(data, key=0xFF):
    with io.BytesIO(data) as s:
        while True:
            rnum = int.from_bytes(s.read(1), byteorder='little', signed=False)
            if not rnum:
                break
            name = xor.read(s, 9, key=key).split(b'\0')[0].decode()
            yield rnum, name

def read_anam(data):
    with io.BytesIO(data) as s:
        num = int.from_bytes(s.read(2), byteorder='little', signed=False)
        names = [s.read(9).split(b'\0')[0].decode() for i in range(num)]
        return enumerate(names)

# def read_directory(data):
#     with io.BytesIO(data) as s:
#         num = int.from_bytes(s.read(2), byteorder='little', signed=False)
#         merged = [(
#             int.from_bytes(s.read(1), byteorder='little', signed=False),
#             int.from_bytes(s.read(4), byteorder='little', signed=False)
#         ) for i in range(num)]
#         print(enumerate(merged))

def counter(it):
    def inner(pid, data, off):
        return next(it)
    return inner

def read_inner_uint16le(pid, data, off):
    res = int.from_bytes(data[8:10], byteorder='little', signed=False)
    return res

def read_uint8le(pid, data, off):
    res = int.from_bytes(data[:1], byteorder='little', signed=False)
    return res

def compare_pid_off(directory):
    def inner(pid, data, off):
        return next((k for k, v in directory.items() if v == (pid, off)), None)
    return inner

def read_index_v5tov7(root):
    for t in root:
        sputm.render(t)
        if t.tag == 'RNAM':
            rnam = dict(read_rnam(t.data, key=0xFF))
            pprint.pprint(rnam)
        elif t.tag == 'MAXS':
            print('MAXS not yet supported')
        elif t.tag == 'DROO':
            droo = dict(read_directory_leg(t.data))
            pprint.pprint(droo)
        elif t.tag == 'DSCR':
            dscr = dict(read_directory_leg(t.data))
            pprint.pprint(dscr)
        elif t.tag == 'DSOU':
            dsou = dict(read_directory_leg(t.data))
            pprint.pprint(dsou)
        elif t.tag == 'DCOS':
            dcos = dict(read_directory_leg(t.data))
            pprint.pprint(dcos)
        elif t.tag == 'DCHR':
            dchr = dict(read_directory_leg(t.data))
            pprint.pprint(dchr)
        elif t.tag == 'DOBJ':
            print('DOBJ not yet supported')
        elif t.tag == 'ANAM':
            anam = dict(read_anam(t.data))
            pprint.pprint(anam)
    return {
        'LFLF': counter(k for k, v  in droo.items() if v != (0, 0)),
        'OBIM': read_inner_uint16le,
        'OBCD': read_inner_uint16le,
        'LSCR': read_uint8le,
        'SCRP': compare_pid_off(dscr),
        'CHAR': compare_pid_off(dchr),
        'SOUN': compare_pid_off(dsou),
        'COST': compare_pid_off(dcos),
        'AKOS': counter(itertools.count(1))  # TODO
    }

def read_index_he(root):
    for t in root:
        sputm.render(t)
        if t.tag == 'RNAM':
            rnam = dict(read_rnam(t.data, key=0x00))
            pprint.pprint(rnam)
        elif t.tag == 'MAXS':
            print('MAXS not yet supported')
        elif t.tag == 'DIRI':
            droo = dict(read_directory_leg(t.data))
            pprint.pprint(droo)
        elif t.tag == 'DIRS':
            dscr = dict(read_directory_leg(t.data))
            pprint.pprint(dscr)
        elif t.tag == 'DIRC':
            dcos = dict(read_directory_leg(t.data))
            pprint.pprint(dcos)
        elif t.tag == 'DIRF':
            dchr = dict(read_directory_leg(t.data))
            pprint.pprint(dchr)
        elif t.tag == 'DIRN':
            dsou = dict(read_directory_leg(t.data))
            pprint.pprint(dsou)
    return {
        'LFLF': counter(k for k, v  in droo.items() if v != (0, 0)),
        'OBIM': read_inner_uint16le,
        'OBCD': read_inner_uint16le,
        'LSCR': read_uint8le,
        'SCRP': compare_pid_off(dscr),
        'CHAR': compare_pid_off(dchr),
        'SOUN': compare_pid_off(dsou),
        'COST': compare_pid_off(dcos),
        'AKOS': counter(itertools.count(1))  # TODO
    }

def read_file(path: str, key: int = 0x00) -> bytes:
    with open(path, 'rb') as res:
        return xor.read(res, key=key)


def save_tree(cfg, element):
    if not element:
        return
    if element.children:
        os.makedirs(element.attribs['path'], exist_ok=True)
        for c in element.children:
            save_tree(cfg, c)
    else:
        with open(element.attribs['path'], 'wb') as f:
            f.write(cfg.mktag(element.tag, element.data))


if __name__ == '__main__':
    import argparse
    import pprint
    from typing import Dict

    from .preset import sputm
    from .types import Chunk

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    # Configuration for HE games
    # index_suffix = '.HE0'
    # resource_suffix = '.(a)'
    # read_index = read_index_he
    # chiper_key = 0x69

    # Configuration for SCUMM v5-v6 games
    index_suffix = '.000'
    resource_suffix = '.001'
    read_index = read_index_v5tov7
    chiper_key = 0x69

    # # Configuration for SCUMM v7 games
    # index_suffix = '.LA0'
    # resource_suffix = '.LA1'
    # read_index = read_index_v5tov7
    # chiper_key = 0x00

    index = read_file(args.filename + index_suffix, key=chiper_key)

    s = sputm.generate_schema(index)
    pprint.pprint(s)

    root = sputm(schema=s).map_chunks(index)

    idgens = read_index(root)

    resource = read_file(args.filename + resource_suffix, key=chiper_key)

    # # commented out, use pre-calculated index instead, as calculating is time-consuming
    # s = sputm.generate_schema(resource)
    # pprint.pprint(s)
    # root = sputm.map_chunks(resource, idgen=idgens, schema=s)

    paths: Dict[str, Chunk] = {}

    def update_element_path(parent, chunk, offset):
        gid = idgens.get(chunk.tag)
        gid = gid and gid(parent and parent.attribs['gid'], chunk.data, offset)

        base = chunk.tag + (f'_{gid:04d}' if gid else '')

        dirname = parent.attribs['path'] if parent else ''
        path = os.path.join(dirname, base)
        res = {'path': path, 'gid': gid}

        assert path not in paths
        paths[path] = chunk

        return res

    root = sputm(max_depth=4).map_chunks(resource, extra=update_element_path)
    with open('rpdump.xml', 'w') as f:
        for t in root:
            sputm.render(t, stream=f)
            save_tree(sputm, t)
