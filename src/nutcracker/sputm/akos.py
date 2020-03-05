#!/usr/bin/env python3
import io
import os
import struct
from functools import partial

from nutcracker.utils.funcutils import grouper, flatten

from typing import Iterator, NamedTuple, Sequence, Tuple

from nutcracker.kernel.types import Element

class AkosHeader(NamedTuple):
    unk_1: int
    flags: int
    unk_2: int
    num_anims: int
    unk_3: int
    codec: int

def akos_header_from_bytes(data: bytes) -> AkosHeader:
    with io.BytesIO(data) as stream:
        unk_1 = int.from_bytes(stream.read(2), signed=False, byteorder='little')
        flags = ord(stream.read(1))
        unk_2 = ord(stream.read(1))
        num_anims = int.from_bytes(stream.read(2), signed=False, byteorder='little')
        unk_3 = int.from_bytes(stream.read(2), signed=False, byteorder='little')
        codec = int.from_bytes(stream.read(2), signed=False, byteorder='little')
    return AkosHeader(
        unk_1=unk_1,
        flags=flags,
        unk_2=unk_2,
        num_anims=num_anims,
        unk_3=unk_3,
        codec=codec
    )

def akof_from_bytes(data: bytes) -> Iterator[Tuple[int, int]]:
    with io.BytesIO(data) as stream:
        while True:
            entry = stream.read(6)
            if not entry:
                break
            cd_off = int.from_bytes(entry[0:4], signed=False, byteorder='little')
            ci_off = int.from_bytes(entry[4:6], signed=False, byteorder='little')
            print(cd_off, ci_off)
            yield cd_off, ci_off

def check_tag(target: str, elem: Element):
    if not elem:
        raise ValueError(f'no 4CC header')
    if elem.tag != target:
        raise ValueError(f'expected tag to be {target} but got {elem.tag}')
    return elem

if __name__ == '__main__':
    import argparse

    from .preset import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        resource = res.read()

    # akos = check_tag('AKOS', next(sputm.map_chunks(resource)))
    akos = sputm.find('AKOS', sputm.map_chunks(resource))
    # akos = iter(akos)
    akhd = akos_header_from_bytes(sputm.find('AKHD', akos).data)

    # colors
    akpl = sputm.find('AKPL', akos)
    rgbs = sputm.find('RGBS', akos)
    palette = tuple(zip(akpl, rgbs))
    print(palette)

    # scripts?
    aksq = sputm.find('AKSQ', akos)
    # akch = sputm.find('AKCH', akos)

    # image
    akof = list(akof_from_bytes(sputm.find('AKOF', akos).data))
    akci = sputm.find('AKCI', akos)
    akcd = sputm.find('AKCD', akos)
    akct = sputm.find('AKCT', akos)

    print(akof, akci, akcd)

    ends = akof[1:] + [(len(akcd.data), len(akci.data))]
    for (cd_start, ci_start), (cd_end, ci_end) in zip(akof, ends):
        ci = akci.data[ci_start:ci_end]
        print(len(ci))
        cd = akcd.data[cd_start:cd_end]
        print(cd, ci)
