#!/usr/bin/env python3

import builtins
import io
import struct

from contextlib import contextmanager
from functools import partial

def untag(stream):
    tag = stream.read(4)
    if not tag:
        return None
    size = struct.unpack('>I', stream.read(4))[0]
    data = stream.read(size)
    if len(data) % 2 != 0 and stream.read(1) != b'\00':
        raise ValueError('non-zero padding between chunks')
    return tag.decode(), data

def read_chunks(data):
    with io.BytesIO(data) as stream:
        chunks = iter(lambda: untag(stream), None)
        for chunk in chunks:
            yield chunk

def get_chunk_offset(stream, off):
    stream.seek(off)
    return untag(stream)

def assert_tag(target, chunk):
    tag, data = chunk
    if tag != target:
        raise ValueError('expected tag to be {target} but got {tag}'.format(target=target,tag=tag))
    return data

assert_frame = partial(assert_tag, 'FRME')

def read_animations(filename):
    with builtins.open(filename, 'rb') as smush_file:
        anim = assert_tag('ANIM', untag(smush_file))
        return io.BytesIO(anim)

class SmushFile:
    def __init__(self, filename):
        self.filename = filename
        self._stream = read_animations(self.filename)
        self.index = [self._stream.tell() for _ in iter(lambda: untag(self._stream), None)][:-1]
        self.header = assert_tag('AHDR', get_chunk_offset(self._stream, 0))

    def __enter__(self):
        return self

    # def __next__(self):
    #     tag, frame = untag(self._stream)
    #     assert_tag(tag, 'FRME')
    #     return frame

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [assert_frame(get_chunk_offset(self._stream, off)) for off in self.index[i]]
        return assert_frame(get_chunk_offset(self._stream, self.index[i]))

    def __iter__(self):
        with read_animations(self.filename) as stream:
            for off in self.index:
                yield assert_frame(get_chunk_offset(stream, off))

    def __exit__(self, type, value, traceback):
        return self._stream.close()

@contextmanager
def open(*args, **kwargs):
    yield SmushFile(*args, **kwargs)

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    from ahdr import parse_header
    with SmushFile(args.filename) as smush_file:
        print(parse_header(smush_file.header))
        # for frame in smush_file:
        #     print(frame)

        # print(next(smush_file))
        print(smush_file[-1])
        print(smush_file[-1:])
