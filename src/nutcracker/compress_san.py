import itertools
import os
import struct
import subprocess
import sys
import zlib
from typing import List, IO

from nutcracker.smush import anim, ahdr
from nutcracker.smush.preset import smush

def compress_frame_data(frame):
    first_fobj = True
    for _, (tag, chunk) in frame:
        if tag == 'FOBJ' and first_fobj:
            first_fobj = False
            decompressed_size = struct.pack('>I', len(chunk))
            compressed = zlib.compress(chunk, 9)
            yield smush.mktag('ZFOB', decompressed_size + compressed)
            continue
        if tag == 'PSAD':
            print('skipping sound stream')
            continue
        else:
            yield smush.mktag(tag, chunk)
            continue

def compress_frames(frames):
    for frame in frames:
        compressed = smush.write_chunks(compress_frame_data(frame))
        yield smush.mktag('FRME', compressed)

def strip_compress_san(res: IO[bytes]) -> bytes:
    header, frames = anim.parse(res)
    frames = (smush.print_chunks(frame, level=1) for frame in frames)
    compressed_frames = compress_frames(frames)
    return anim.compose(header, compressed_frames)

if __name__ == '__main__':
    import argparse
    from nutcracker.utils import funcutils
    import glob

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--target', '-t', help='target directory', default='out')
    args = parser.parse_args()

    files = set(funcutils.flatten(glob.iglob(r) for r in args.files))
    print(files)
    for filename in files:
        basename = os.path.basename(filename)
        output_dir = os.path.join(args.target, basename)
        os.makedirs(output_dir, exist_ok=True)
        print(f'Compressing file: {basename}')
        with open(filename, 'rb') as res:
            data = strip_compress_san(res)
        with open(os.path.join(output_dir, basename), 'wb') as out:
            out.write(data)
        print(os.path.join(output_dir, basename))
