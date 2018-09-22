#!/usr/bin/env python3

import io
import struct

def untag(stream):
    while True:
        tag = stream.read(4)
        if not tag:
            break
        size = struct.unpack('>I', stream.read(4))[0]
        data = stream.read(size)
        if len(data) % 2 != 0 and stream.read(1) != b'\00':
            raise ValueError('non-zero padding between chunks')
        yield tag.decode(), data

def read_chunks(data):
    stream = io.BytesIO(data)
    return untag(stream)

def assert_tag(tag, target):
    if tag != target:
        raise ValueError('expected tag to be {target} but got {tag}'.format(target=target,tag=tag))

def read_animations(filename):
    with open(filename, 'rb') as smush_file:
        for tag, anim in untag(smush_file):
            assert_tag(tag, 'ANIM')
            yield read_chunks(anim)

def read_frames(anim):
    (htag, header), *frames = anim
    assert_tag(htag, 'AHDR')
    yield header
    for tag, frame in frames:
        assert_tag(tag, 'FRME')
        yield frame

def read_smush_file(filename):
    for anim in read_animations(filename):
        # yield read_frames(anim)
        return read_frames(anim)

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    # for anim in read_smush_file(args.filename):
    #     header, *frames = anim
    #     print(header)
    #     for frame in frames:
    #         print(frame)

    header, *frames = read_smush_file(args.filename)
    print(header)
    for frame in frames:
        print(frame)
