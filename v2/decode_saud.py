#!/usr/bin/env python3
import glob
import io
import os
import struct
import wave

from functools import partial

import smush
import ahdr

from typing import Iterable, Iterator, TypeVar

T = TypeVar('T')

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

def flatten(ls: Iterable[Iterable[T]]) -> Iterator[T]: 
    return (item for sublist in ls for item in sublist)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    print(files)
    for filename in files:
        with open(filename, 'rb') as res:
            basename, _ = os.path.splitext(os.path.basename(filename))
            print(basename)
            saud = smush.assert_tag('SAUD', smush.untag(res))
            assert res.read() == b''

            sound = b''
            sample_rate = 22050

            print([tag for tag, _ in smush.read_chunks(saud, align=1)])
            for tag, data in smush.read_chunks(saud, align=1):
                if tag == 'STRK':
                    print([read_le_uint16(bytes(word)) for word in ahdr.grouper(data, 2)]) 
                    continue
                if tag == 'SDAT':
                    sound = data
                    continue
                if tag == 'SMRK':
                    if data:
                        print('Mark reached')
                        print(data)
                    continue
                if tag == 'SHDR':
                    print([read_le_uint16(bytes(word)) for word in ahdr.grouper(data, 2)]) 
                    continue
            with wave.open(f'sound/SDAT_{basename}.WAV', 'w') as wav:
                # aud.write(b'\x80' * frame_audio_size[12] * frame_no)
                wav.setnchannels(1)
                wav.setsampwidth(1) 
                wav.setframerate(sample_rate)
                wav.writeframesraw(sound)
