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
    def inner(pid, stream, off):
        return next(it)
    return inner

def read_inner_uint16le(pid, stream, off):
    stream.seek(8, io.SEEK_CUR)
    res = int.from_bytes(stream.read(2), byteorder='little', signed=False)
    stream.seek(-10, io.SEEK_CUR)
    return res

def read_uint8le(pid, stream, off):
    res = int.from_bytes(stream.read(1), byteorder='little', signed=False)
    stream.seek(-1, io.SEEK_CUR)
    return res

def compare_pid_off(directory):
    def inner(pid, stream, off):
        return next((k for k, v in directory.items() if v == (pid, off)), None)
    return inner

def read_index_v5tov7(root):
    for t in root:
        sputm.render(t)
        if t.tag == 'RNAM':
            rnam = dict(read_rnam(t.read(), key=0xFF))
            pprint.pprint(rnam)
        elif t.tag == 'MAXS':
            print('MAXS not yet supported')
        elif t.tag == 'DROO':
            droo = dict(read_directory_leg(t.read()))
            pprint.pprint(droo)
        elif t.tag == 'DSCR':
            dscr = dict(read_directory_leg(t.read()))
            pprint.pprint(dscr)
        elif t.tag == 'DSOU':
            dsou = dict(read_directory_leg(t.read()))
            pprint.pprint(dsou)
        elif t.tag == 'DCOS':
            dcos = dict(read_directory_leg(t.read()))
            pprint.pprint(dcos)
        elif t.tag == 'DCHR':
            dchr = dict(read_directory_leg(t.read()))
            pprint.pprint(dchr)
        elif t.tag == 'DOBJ':
            print('DOBJ not yet supported')
        elif t.tag == 'ANAM':
            anam = dict(read_anam(t.read()))
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
            rnam = dict(read_rnam(t.read(), key=0x00))
            pprint.pprint(rnam)
        elif t.tag == 'MAXS':
            print('MAXS not yet supported')
        elif t.tag == 'DIRI':
            droo = dict(read_directory_leg(t.read()))
            pprint.pprint(droo)
        elif t.tag == 'DIRS':
            dscr = dict(read_directory_leg(t.read()))
            pprint.pprint(dscr)
        elif t.tag == 'DIRC':
            dcos = dict(read_directory_leg(t.read()))
            pprint.pprint(dcos)
        elif t.tag == 'DIRF':
            dchr = dict(read_directory_leg(t.read()))
            pprint.pprint(dchr)
        elif t.tag == 'DIRN':
            dsou = dict(read_directory_leg(t.read()))
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

if __name__ == '__main__':
    import argparse
    import pprint

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    # Configuration for HE games
    index_suffix = '.HE0.xor'
    resource_suffix = '.(a).xor'
    read_index = read_index_he

    # # Configuration for SCUMM v5-v6 games
    # index_suffix = '.000.xor'
    # resource_suffix = '.001.xor'
    # read_index = read_index_v5tov7

    # # Configuration for SCUMM v7 games
    # index_suffix = '.LA0'
    # resource_suffix = '.LA1'
    # read_index = read_index_v5tov7

    with open(args.filename + index_suffix, 'rb') as res:

        s = sputm.generate_schema(res)
        pprint.pprint(s)
        res.seek(0, io.SEEK_SET)

        root = sputm.map_chunks(res, schema=s)

        idgens = read_index(root)

    with open(args.filename + resource_suffix, 'rb') as res:

        # # commented out, use pre-calculated index instead, as calculating is time-consuming
        # s = sputm.generate_schema(res)
        # pprint.pprint(s)
        # res.seek(0, io.SEEK_SET)
        # root = sputm.map_chunks(res, idgen=idgens, schema=s)

        root = sputm.map_chunks(res, idgen=idgens)
        for t in root:
            sputm.render(t)
