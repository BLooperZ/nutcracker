#!/usr/bin/env python3
import io
import struct

from functools import partial

import smush

from ahdr import parse_header

frame_audio_size = {
    12: 7352 // 2,
	10: 8802 // 2
}

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

def read_le_uint32(f):
    return struct.unpack('<I', f[:4])[0]

def handle_sound_buffer(track_id, index, max_frames, flags, vol, pan, chunk, size, frame_no):
    fname = f'sound/PSAD_{track_id:04d}.RAW'
    mode = 'ab' if index != 0 else 'wb'
    with open(fname, mode) as aud:
        # aud.write(b'\x80' * frame_audio_size[12] * frame_no)
        aud.write(chunk)
    # if index == 0:
    #     print('first length', len(chunk))
    #     with open(fname, 'wb') as aud:
    #         # aud.write(b'\x80' * frame_audio_size[12] * frame_no)
    #         aud.write(chunk)
        # c_stream = io.BytesIO(chunk)
        # saud = smush.assert_tag('SAUD', smush.untag(c_stream))
        # assert c_stream.read() == b''
        # for tag, data in smush.read_chunks(saud):
        #     if tag == 'SDAT':
        #         print('first length', len(data))
        #         with open(fname, 'wb') as aud:
        #             # aud.write(b'\x80' * frame_audio_size[12] * frame_no)
        #             aud.write(data)
        #     elif tag == 'STRK':
        #         print(data)
        #     else:
        #         raise ValueError(f'Unknown audio tag: {tag}')
    # else:
    #     print('other length', len(chunk))
    #     with open(fname, 'ab') as aud:
    #         aud.write(chunk)

def old_untag(stream):
    tag = stream.read(4)
    if not tag:
        return None
    size = struct.unpack('>I', stream.read(4))[0]
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f'got EOF while reading chunk: expected {size}, got {len(data)}')
    return tag.decode(), data

def old_read_chunks(data: bytes):
    with io.BytesIO(data) as stream:
        chunks = iter(partial(old_untag, stream), None)
        for chunk in chunks:
            assert chunk
            yield chunk

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        saud = smush.assert_tag('SAUD', smush.untag(res))
        assert res.read() == b''
        # print([tag for tag, _ in old_read_chunks(saud)])
        for tag, data in old_read_chunks(saud):
            print(tag)
