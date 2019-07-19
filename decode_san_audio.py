#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

import smush

from ahdr import parse_header

FLAG_UNSIGNED = 1 << 0
FLAG_16BITS = 1 << 1
FLAG_LITTLE_ENDIAN = 1 << 2

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

def read_le_uint32(f):
    return struct.unpack('<I', f[:4])[0]

def handle_sound_buffer(track_id, index, max_frames, flags, vol, pan, chunk, size, frame_no):
    fname = f'sound/PSAD_{track_id:04d}.RAW'
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
    print(chunk[-10:])
    if index == 0:
        print(f'track_id:{track_id}, max_frames:{max_frames}, flags:{flags}, vol:{vol}, pan:{pan}')     
        print(f'unsigned: {flags & FLAG_UNSIGNED}')
        print(f'16bit: {flags & FLAG_16BITS}')
        print(f'le: {flags & FLAG_LITTLE_ENDIAN}')
    handle_sound_buffer(track_id, index, max_frames, flags, vol, pan, chunk[10:], len(chunk) - 10, frame_no)

def verify_nframes(frames, nframes):
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with smush.open(args.filename) as smush_file:
        header = parse_header(smush_file.header)
        frames = verify_nframes(smush_file, header['nframes'])
        frames = (list(smush.read_chunks(frame)) for frame in frames)

        for idx, frame in enumerate(frames):
            print(f'{idx} - {[tag for tag, _ in frame]}')

            for tag, chunk in frame:
                if tag == 'PSAD':
                    handle_sound_frame(chunk, idx)
                else:
                    continue         
