#!/usr/bin/env python3
import io
import os
import struct
import glob
from functools import partial

from nutcracker.utils import funcutils

FLAG_UNSIGNED = 1 << 0
FLAG_16BITS = 1 << 1
FLAG_LITTLE_ENDIAN = 1 << 2

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

def handle_sound_buffer(track_id, index, max_frames, flags, vol, pan, chunk, frame_no):
    fname = f'sound/PSAD_{track_id:04d}.SAD'
    mode = 'ab' if index != 0 else 'wb'
    with open(fname, mode) as aud:
        aud.write(chunk)

def handle_sound_frame(chunk, frame_no):
    track_id = read_le_uint16(chunk)
    index = read_le_uint16(chunk[2:])
    max_frames = read_le_uint16(chunk[4:])
    flags = read_le_uint16(chunk[6:])
    vol = chunk[8]
    pan = chunk[9]
    if index == 0:
        print(f'track_id:{track_id}, max_frames:{max_frames}, flags:{flags}, vol:{vol}, pan:{pan}')     
        print(f'unsigned: {flags & FLAG_UNSIGNED}')
        print(f'16bit: {flags & FLAG_16BITS}')
        print(f'le: {flags & FLAG_LITTLE_ENDIAN}')
    return track_id, index, max_frames, flags, vol, pan, chunk[10:], frame_no

def verify_nframes(frames, nframes):
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

if __name__ == '__main__':
    import argparse

    from nutcracker.smush import anim
    from nutcracker.smush import smush

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--target', '-t', help='target directory', default='sound')
    args = parser.parse_args()


    basename = os.path.basename(args.filename)
    output_dir = os.path.join(args.target, basename)
    os.makedirs(output_dir, exist_ok=True)
    print(f'Decoding file: {basename}')
    with open(args.filename, 'rb') as res:

        header, frames = anim.parse(res)

        for idx, frame in enumerate(frames):
            for _, (tag, chunk) in smush.print_chunks(frame, level=1):
                if tag == 'PSAD':
                    track_id, index, max_frames, flags, vol, pan, chunk, frame_no = handle_sound_frame(chunk, idx)
                    fname = os.path.join(output_dir, f'PSAD_{track_id:04d}.SAD')
                    mode = 'ab' if index != 0 else 'wb'
                    with open(fname, mode) as aud:
                        aud.write(chunk)
                else:
                    continue
