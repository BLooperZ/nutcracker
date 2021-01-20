#!/usr/bin/env python3

import struct
import zlib
from typing import Iterable, Iterator

from nutcracker.utils.fileio import write_file
from nutcracker.smush import anim
from nutcracker.smush.types import Element
from nutcracker.smush.preset import smush
from nutcracker.smush.decode import open_anim_file

UINT32BE = struct.Struct('>I')


def compress_frame_data(frame: Element) -> Iterator[bytes]:
    first_fobj = True
    for comp in frame.children:
        if comp.tag == 'FOBJ' and first_fobj:
            first_fobj = False
            decompressed_size = UINT32BE.pack(len(comp.data))
            compressed = zlib.compress(comp.data, 9)
            yield smush.mktag('ZFOB', decompressed_size + compressed)
            continue
        if comp.tag == 'PSAD':
            # print('skipping sound stream')
            continue
        else:
            first_fobj = first_fobj and comp.tag != 'ZFOB'
            yield smush.mktag(comp.tag, comp.data)
            continue


def compress_frames(frames: Iterable[Element]) -> Iterator[bytes]:
    for frame in frames:
        yield smush.mktag('FRME', smush.write_chunks(compress_frame_data(frame)))


def strip_compress_san(root: Element) -> bytes:
    header, frames = anim.parse(root)
    compressed_frames = compress_frames(frames)
    return anim.compose(header, compressed_frames)


if __name__ == '__main__':
    import argparse
    import glob
    import os

    from nutcracker.utils.funcutils import flatten

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--map', '-m', action='store_true')
    parser.add_argument('--target', '-t', help='target directory', default='out')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))

    for filename in files:
        basename = os.path.basename(filename)
        print(f'Compressing file: {basename}')
        root = open_anim_file(filename)
        if args.map:
            smush.render(root)
            continue

        compressed = strip_compress_san(root)
        os.makedirs(args.target, exist_ok=True)
        write_file(os.path.join(args.target, basename), compressed)
