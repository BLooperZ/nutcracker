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

def read_dlfl(data):
    with io.BytesIO(data) as s:
        num = int.from_bytes(s.read(2), byteorder='little', signed=False)
        offs = [int.from_bytes(s.read(4), byteorder='little', signed=False) for i in range(num)]
        return enumerate(offs)

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
    # TODO: fix offset for FT + DIG as in the following commented line
    # res = int.from_bytes(data[12:14], byteorder='little', signed=False)
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
        elif t.tag == 'DRSC':
            drsc = dict(read_directory_leg(t.data))
            pprint.pprint(drsc)
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
        'OBIM': read_inner_uint16le,  # check gid for DIG and FT
        'OBCD': read_inner_uint16le,
        'LSCR': read_uint8le,
        'SCRP': compare_pid_off(dscr),
        'CHAR': compare_pid_off(dchr),
        'SOUN': compare_pid_off(dsou),
        'COST': compare_pid_off(dcos),
        'AKOS': compare_pid_off(dcos),
    }

def read_index_he(root):
    dtlk = None  # prevent `referenced before assignment` error
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
        elif t.tag == 'DIRT':
            dtlk = dict(read_directory_leg(t.data))
            pprint.pprint(dtlk)
        elif t.tag == 'DIRM':
            dmul = dict(read_directory_leg(t.data))
            pprint.pprint(dmul)
        elif t.tag == 'DIRR':
            drmd = dict(read_directory_leg(t.data))
            pprint.pprint(drmd)
        elif t.tag == 'DISK':
            # TODO
            # all values are `idx: (1, 0)`
            disk = dict(read_directory_leg(t.data))
            pprint.pprint(disk)
        elif t.tag == 'DLFL':
            dlfl = dict(read_dlfl(t.data))
            pprint.pprint(dlfl)
            pass
    return {
        'LFLF': counter(k for k, v  in droo.items() if v != (0, 0)),
        'OBIM': read_inner_uint16le,
        'OBCD': read_inner_uint16le,
        'LSCR': read_uint8le,
        'LSC2': read_uint8le,
        'SCRP': compare_pid_off(dscr),
        'CHAR': compare_pid_off(dchr),
        'DIGI': compare_pid_off(dsou),
        'SOUN': compare_pid_off(dsou),
        'AKOS': compare_pid_off(dcos),
        'MULT': compare_pid_off(dmul),
        'AWIZ': compare_pid_off(dmul),
        'RMDA': compare_pid_off(drmd),
        'TALK': compare_pid_off(dtlk),
    }

def read_file(path: str, key: int = 0x00) -> bytes:
    with open(path, 'rb') as res:
        return xor.read(res, key=key)


def save_tree(cfg, element, basedir='.'):
    if not element:
        return
    path = os.path.join(basedir, element.attribs['path'])
    if element.children:
        os.makedirs(path, exist_ok=True)
        for c in element.children:
            save_tree(cfg, c, basedir=basedir)
    else:
        with open(path, 'wb') as f:
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

    # # Configuration for HE games
    # index_suffix = '.HE0'
    # resource_suffix = '.HE1' # '.(a)'
    # read_index = read_index_he
    # chiper_key = 0x69
    # max_depth = 4

    # # Configuration for SCUMM v5-v6 games
    # index_suffix = '.000'
    # resource_suffix = '.001'
    # read_index = read_index_v5tov7
    # chiper_key = 0x69
    # max_depth = 4

    # Configuration for SCUMM v7 games
    index_suffix = '.LA0'
    resource_suffix = '.LA1'
    read_index = read_index_v5tov7
    chiper_key = 0x00
    max_depth = 3

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
        get_gid = idgens.get(chunk.tag)
        gid = get_gid and get_gid(parent and parent.attribs['gid'], chunk.data, offset)

        base = chunk.tag + (f'_{gid:04d}' if gid is not None else '' if not get_gid else f'_o_{offset:04X}')

        dirname = parent.attribs['path'] if parent else ''
        path = os.path.join(dirname, base)
        res = {'path': path, 'gid': gid}

        assert path not in paths, path
        paths[path] = chunk

        return res

    basedir = os.path.basename(args.filename)
    root = sputm(max_depth=max_depth).map_chunks(resource, extra=update_element_path)
    os.makedirs(basedir, exist_ok=True)
    with open(os.path.join(basedir, 'rpdump.xml'), 'w') as f:
        for t in root:
            sputm.render(t, stream=f)
            save_tree(sputm, t, basedir=basedir)
