#!/usr/bin/env python3
import io
import os
import struct
from functools import partial

from nutcracker.utils.funcutils import grouper, flatten

from typing import Iterator, NamedTuple, Sequence, Tuple

class AkosHeader(NamedTuple):
    unk_1: int
    flags: int
    unk_2: int
    num_anims: int
    unk_3: int
    codec: int

def assert_stop_iter(iter: Iterator) -> None:
    for chunk in chunks:
        raise ValueError(f'expected EOF, got {chunk}')

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

if __name__ == '__main__':
    import argparse

    from .preset import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        akos = sputm.assert_tag('AKOS', sputm.untag(res))
        assert res.read() == b''
        # chunks = (assert_tag('LFLF', chunk) for chunk in read_chunks(tlkb))
        chunks = sputm.drop_offsets(sputm.read_chunks(akos))
        akhd = akos_header_from_bytes(sputm.assert_tag('AKHD', next(chunks)))
        print(akhd)

        # colors
        akpl = sputm.assert_tag('AKPL', next(chunks))
        rgbs = grouper(sputm.assert_tag('RGBS', next(chunks)), 3)
        palette = tuple(zip(akpl, rgbs))
        print(palette)

        # scripts?
        aksq = sputm.assert_tag('AKSQ', next(chunks))
        akch = sputm.assert_tag('AKCH', next(chunks))

        # image
        akof = list(akof_from_bytes(sputm.assert_tag('AKOF', next(chunks))))
        akci = sputm.assert_tag('AKCI', next(chunks))
        akcd = sputm.assert_tag('AKCD', next(chunks))
        ends = akof[1:] + [(len(akcd), len(akci))]
        for (cd_start, ci_start), (cd_end, ci_end) in zip(akof, ends):
            ci = akci[ci_start:ci_end]
            # print(len(ci))
            cd = akcd[cd_start:cd_end]
            # print(cd, ci)

        assert_stop_iter(chunks)
