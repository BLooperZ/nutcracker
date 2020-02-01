#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

LEAF_CHUNKS = {
    'LOFF',
    'RMHD',
    'CYCL',
    'TRNS',
    'EPAL',
    'BOXD',
    'BOXM',
    'CLUT',
    'SCAL',
    'RMIH',
    'SMAP',
    'ZP01',
    'ZP02',
    'ZP03',
    'IMHD',
    'CDHD',
    'VERB',
    'OBNA',
    'EXCD',
    'ENCD',
    'NLSC',
    'LSCR',
    'SCRP',
    'SOUN',
    'COST',
    'CHAR',
    'BOMP',
    'BMAP',
    'OFFS',
    'APAL',
    'LSC2',
    'HSHD',
    'SDAT',
    'AKHD',
    'AKPL',
    'RGBS',
    'AKSQ',
    'AKCH',
    'AKOF',
    'AKCI',
    'AKCD',
    'AKLC',
    'WIZH',
    'WIZD',
    'CNVS',
    'SPOT',
    'RELO',
    'POLD',
    'AKST',
    'AKCT',
    'SP2C',
    'SPLF',
    'CLRS',
    'IMGL',
    'NAME',
    'STOF',
    'SQLC',
    'SIZE',
    'AKFO',
    'SBNG',
    'RNAM',
    'MAXS',
    'DROO',
    'DSCR',
    'DSOU',
    'DCOS',
    'DCHR',
    'DOBJ'
}

def map_chunks(data, level=0, base_offset=0):
    chunks = sputm.print_chunks(sputm.read_chunks(data), level=level, base=base_offset)
    for idx, (hoff, (tag, chunk)) in enumerate(chunks):
        if tag not in LEAF_CHUNKS:
            map_chunks(chunk, level=level + 1, base_offset=hoff + 8)

if __name__ == '__main__':
    import argparse

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        map_chunks(res.read())
        print('==========')
