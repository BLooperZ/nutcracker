#!/usr/bin/env python3

import io
import os
import struct
from typing import Sequence, NamedTuple, Optional, Iterator
from dataclasses import dataclass

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
    'DOBJ',
    'DIRI',
    'DIRR',
    'DIRS',
    'DIRN',
    'DIRC',
    'DIRF',
    'DIRM',
    'DIRT',
    'DLFL',
    'DISK',
    'SVER',
    'AARY',
    'NOTE'
}

@dataclass
class Element:
    tag: str
    attribs: dict
    children: Sequence['Element']

def findall(tag: str, root: Optional[Element]) -> Iterator[Element]:
    if not root:
        return
    for c in root.children:
        if c.tag == tag:
            yield c

def find(tag: str, root: Optional[Element]) -> Optional[Element]:
    return next(findall(tag, root), None)

def findpath(path: str, root: Optional[Element]) -> Optional[Element]:
    path = os.path.normpath(path)
    if not path or path == '.':
        return root
    dirname, basename = os.path.split(path)
    return find(basename, findpath(dirname, root))

def read_index(data, level=0, base_offset=0):
    chunks = sputm.print_chunks(sputm.read_chunks(data), level=level, base=base_offset)
    for idx, (hoff, (tag, chunk)) in enumerate(chunks):
        if tag == 'DCHR':
            with io.BytesIO(chunk) as s:
                num = int.from_bytes(s.read(2), byteorder='little', signed=False)
                rnums = [int.from_bytes(s.read(1), byteorder='little', signed=False) for i in range(num)]
                offs = [int.from_bytes(s.read(4), byteorder='little', signed=False) for i in range(num)]
                for rnum, off in zip(rnums, offs):
                    print(rnum, off)

def h(element, level=0):
    attribs = ''.join(f' {key}="{value}"' for key, value in element.attribs.items())
    indent = '    ' * level
    closing = '' if element.children else ' /'
    print(f'{indent}<{element.tag}{attribs}{closing}>')
    if element.children:
        for c in element.children:
            h(c, level=level + 1)
        print(f'{indent}</{element.tag}>')

def map_chunks(data, base_offset=0):
    chunks = sputm.read_chunks(data)
    return [Element(
        tag,
        {'offset': hoff, 'size': len(chunk), 'absolute': base_offset + hoff},
        [] if tag in LEAF_CHUNKS else map_chunks(chunk, base_offset=base_offset + hoff + 8)
    ) for hoff, (tag, chunk) in chunks]

def map_chunks_poc(data, base_offset=0):
    try:
        chunks = sputm.read_chunks(data)
        return [Element(
            tag,
            {'offset': hoff, 'size': len(chunk), 'absolute': base_offset + hoff},
            map_chunks(chunk, base_offset=base_offset + hoff + 8)
        ) for hoff, (tag, chunk) in chunks]
    except:
        return []

def create_maptree(data):
    return map_chunks_poc(data)[0]

def read_element(elem, stream):
    stream.seek(elem.attribs['absolute'], io.SEEK_SET)
    return stream.read(elem.attribs['size'])

if __name__ == '__main__':
    import argparse

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        root = create_maptree(res.read())
        for lflf in findall('LFLF', root):
            tree = findpath('RMIM/IM00', lflf)
            # print(read_element(tree, res))
            if tree:
                h(tree)

        # print('==========')
