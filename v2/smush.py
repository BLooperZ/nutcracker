#!/usr/bin/env python3

import builtins
import io
import struct

import logging

from functools import partial

from typing import AnyStr, IO, Iterator, Optional, overload, Sequence, Tuple, Union

def untag(stream: IO[bytes]) -> Optional[Tuple[str, bytes]]:
    tag = stream.read(4)
    if not tag:
        return None
    size = struct.unpack('>I', stream.read(4))[0]
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f'got EOF while reading chunk {tag}: expected {size}, got {len(data)}')
    return tag.decode(), data

def calc_align(pos: int, align: int):
    return (align - pos % align) % align

def align_stream(stream: IO[bytes], align: int = 2):
    pos = stream.tell()
    if pos % align == 0:
        return
    pad = stream.read(calc_align(pos, align))
    if pad and set(pad) != {0}:
        raise ValueError(f'non-zero padding between chunks: {pad}')

def read_chunks_stream(stream: IO[bytes], align: int = 2) -> Iterator[Tuple[str, bytes]]:
    chunks = iter(partial(untag, stream), None)
    for chunk in chunks:
        assert chunk
        align_stream(stream, align=align)
        yield chunk

def read_chunks(data: bytes, align: int = 2) -> Iterator[Tuple[str, bytes]]:
    with io.BytesIO(data) as stream:
        for chunk in read_chunks_stream(stream, align=align):
            yield chunk

def get_chunk_offset(stream: IO[bytes], off: int) -> Optional[Tuple[str, bytes]]:
    stream.seek(off)
    return untag(stream)

def assert_tag(target: str, chunk: Optional[Tuple[str, bytes]]) -> bytes:
    if not chunk:
        raise ValueError(f'no 4cc header')
    tag, data = chunk
    if tag != target:
        raise ValueError(f'expected tag to be {target} but got {tag}')
    return data

assert_frame = partial(assert_tag, 'FRME')

def read_animations(filename: AnyStr) -> IO[bytes]:
    with builtins.open(filename, 'rb') as smush_file:
        anim = assert_tag('ANIM', untag(smush_file))
        assert smush_file.read() == b''
        return io.BytesIO(anim)

class SmushFile:
    def __init__(self, filename: str):
        self.filename = filename
        self._stream = read_animations(self.filename)
        self.index = [self._stream.tell() for _ in read_chunks_stream(self._stream)][:-1]
        self.header = assert_tag('AHDR', get_chunk_offset(self._stream, 0))

    def __enter__(self):
        return self

    # def __next__(self):
    #     chunk = untag(self._stream)
    #     frame = assert_frame(chunk)
    #     align_stream(self._stream)
    #     return frame

    @overload
    def __getitem__(self, i: int) -> bytes: ...
    @overload
    def __getitem__(self, i: slice) -> Sequence[bytes]: ...
    # implementation:
    def __getitem__(self, i: Union[int, slice]) -> Union[bytes, Sequence[bytes]]:
        if isinstance(i, slice):
            return [assert_frame(get_chunk_offset(self._stream, off)) for off in self.index[i]]
        return assert_frame(get_chunk_offset(self._stream, self.index[i]))

    def __iter__(self) -> Iterator[bytes]:
        with read_animations(self.filename) as stream:
            for off in self.index:
                yield assert_frame(get_chunk_offset(stream, off))

    def __exit__(self, type, value, traceback):
        return self._stream.close()

def open(*args, **kwargs) -> SmushFile:
    return SmushFile(*args, **kwargs)

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
