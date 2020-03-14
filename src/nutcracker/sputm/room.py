#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

import numpy as np

from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.codex.codex import decode1

from .preset import sputm

TRANSPARENCY = 255

def read_uint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def read_uint32le(stream):
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)

def to_byte(num):
    return bytes([num % 256])

def create_bitsream(stream):
    sd = stream.read()
    bits = ''.join(f'{x:08b}'[::-1] for x in sd)
    return (int(x) for x in bits)

def collect_bits(bitstream, count):
    # TODO: check if special handling needed when count > 8
    return int(''.join(str(next(bitstream)) for _ in range(count))[::-1], 2)

def decode_basic(stream, decoded_size, palen):
    sub = 1

    with io.BytesIO() as out:

        color = stream.read(1)[0]
        bitstream = create_bitsream(stream)
        out.write(to_byte(color))

        while out.tell() < decoded_size:
            if next(bitstream):
                if next(bitstream):
                    if next(bitstream):
                        sub = -sub
                    color -= sub
                else:
                    color = collect_bits(bitstream, palen)
                    sub = 1
            out.write(to_byte(color))
        return out.getvalue()

def decode_complex(stream, decoded_size, palen):
    with io.BytesIO() as out:

        color = stream.read(1)[0]
        bitstream = create_bitsream(stream)
        out.write(to_byte(color))

        while out.tell() < decoded_size:
            if next(bitstream):
                if next(bitstream):
                    shift = collect_bits(bitstream, 3) - 4
                    if shift != 0:
                        color += shift
                    else:
                        ln = collect_bits(bitstream, 8) - 1
                        out.write(to_byte(color) * ln)
                else:
                    color = collect_bits(bitstream, palen)
            out.write(to_byte(color))
        return out.getvalue()

def decode_raw(stream, decoded_size, width):
    res = stream.read(decoded_size)
    print(stream.read())
    return res

def unknown_decoder(*args):
    raise ValueError('Unknown Decoder')

def decode_he(stream, decoded_size, palen):
    delta_color = [-4, -3, -2, -1, 1, 2, 3, 4]

    with io.BytesIO() as out:

        color = stream.read(1)[0]
        bitstream = create_bitsream(stream)
        out.write(to_byte(color))

        while out.tell() < decoded_size:
            if next(bitstream):
                if next(bitstream):
                    color += delta_color[collect_bits(bitstream, 3)]
                else:
                    color = collect_bits(bitstream, palen)
            out.write(to_byte(color))
        return out.getvalue()

def get_method_info(code):
    direction = 'HORIZONTAL'
    if 0x03 <= code <= 0x12 or 0x22 <= code <= 0x26:
    # if 3 <= code <= 18 or 34 <= code <= 38:
        direction = 'VERTICAL'

    method = unknown_decoder
    if code in (0x01, 0x95):
    # if code in (1, 149):
        assert direction == 'HORIZONTAL'
        method = decode_raw
    elif 0x0e <= code <= 0x30:
    # elif 14 <= code <= 48:
        method = decode_basic
    elif 0x40 <= code <= 0x80:
    # elif 64 <= code <=128:
        assert direction == 'HORIZONTAL'
        method = decode_complex
    elif 0x86 <= code <= 0x94:
    # elif 134 <= code <=148:
        method = decode_he
    print(method)

    tr = None
    if 0x22 <= code <= 0x30 or 0x54 <= code <= 0x80 or code >= 0x8f:
    # if 34 <= code <= 48 or 84 <= code <= 128 or code >= 143:
        tr = TRANSPARENCY

    palen = code % 10

    # assert 0 <= palen <= 8
    return method, direction, tr, palen

def fake_encode_strip(data, height, width):
    with io.BytesIO() as s:
        s.write(b'\01')
        s.write(bytes(data))
        return s.getvalue()

def parse_strip(height, width, data):
    print((height, width))
    with io.BytesIO(data) as s:
        code = s.read(1)[0]
        print(code)

        decode_method, direction, tr, palen = get_method_info(code)
        # TODO: handle transparency
        # assert not tr

        # try:

        decoded = decode_method(s, width * height, palen)  # [:width * height]

        # if decode_method == decode_basic:
        #     with io.BytesIO(decoded) as dec_stream:
        #         print(decoded)
        #         print(data[1:])
        #         assert encode_basic(dec_stream, height, palen, 8) == data[1:]

        # Verify nothing left in stream
        assert not s.read()

        order = 'C' if direction == 'HORIZONTAL' else 'F'
        return np.frombuffer(decoded, dtype=np.uint8).reshape((height, width), order=order)
        # # return np.zeros((height, 8), dtype=np.uint8)

        # except Exception as exc:
        #     logging.exception(exc)
        #     return np.zeros((height, width), dtype=np.uint8)

def read_strip(stream, offset, end):
    stream.seek(offset, io.SEEK_SET)
    return stream.read(end - offset)

def decode_smap(height, width, data):
    strip_width = 8

    if width == 0 or height == 0:
        return None

    num_strips = width // strip_width
    with io.BytesIO(data) as s:
        offs = [(read_uint32le(s) - 8)  for _ in range(num_strips)]
        index = list(zip(offs, offs[1:] + [len(data)]))
        print(s.tell(), index[0])

    strips = (data[offset:end] for offset, end in index)
    return np.hstack([parse_strip(height, strip_width, data) for data in strips])

def read_room_background(rdata, width, height, zbuffers):
    image, *zplanes = sputm.drop_offsets(sputm.print_chunks(sputm.read_chunks(rdata), level=2))
    # print(smap)
    for c in zplanes:
        pass

    tag, data = image
    if tag == 'SMAP':
        return decode_smap(height, width, data)
    elif tag == 'BOMP':
        with io.BytesIO(data) as s:
            unk = read_uint16le(s)
            width = read_uint16le(s)
            height = read_uint16le(s)
            # TODO: check if x,y or y,x
            xpad, ypad = read_uint16le(s), read_uint16le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    elif tag == 'BMAP':
        with io.BytesIO(data) as s:
            code = s.read(1)[0]
            palen = code % 10
            if 134 <= code <= 138:
                res = decode_he(s, width * height, palen)
                return np.frombuffer(res, dtype=np.uint8).reshape((height, width))
            elif 144 <= code <= 148:
                tr = TRANSPARENCY
                res = decode_he(s, width * height, palen)
                return np.frombuffer(res, dtype=np.uint8).reshape((height, width))
            elif code == 150:
                return np.full((height, width), s.read(1)[0], dtype=np.uint8)
    else:
        print(tag, data)
        # raise ValueError(f'Unknown image codec: {tag}')

def decode_rmim(data, width, height):
    rchunks = sputm.drop_offsets(
        sputm.print_chunks(sputm.read_chunks(data), level=1)
    )

    rmih = sputm.assert_tag('RMIH', next(rchunks))
    assert len(rmih) == 2
    zbuffers = 1 + int.from_bytes(rmih, signed=False, byteorder='little')
    assert 1 <= zbuffers <= 8

    image_data = sputm.assert_tag('IM00', next(rchunks))
    roombg = read_room_background(image_data, width, height, zbuffers)
    assert not list(rchunks)
    return convert_to_pil_image(roombg)

def parse_room_noimgs(room):
    chunks = sputm.print_chunks(sputm.read_chunks(room))
    transparent = 255  # default
    for cidx, (off, (tag, data)) in enumerate(chunks):
        if tag == 'RMHD':
            # only for games < v7
            assert len(data) == 6, 'Game Version < 7'
            rwidth = int.from_bytes(data[:2], signed=False, byteorder='little')
            rheight = int.from_bytes(data[2:4], signed=False, byteorder='little')
            robjects = int.from_bytes(data[4:], signed=False, byteorder='little')
        if tag == 'TRNS':
            transparent = data[0]
        if tag == 'CLUT':
            palette = data
        if tag == 'PALS':
            rchunks = sputm.print_chunks(sputm.read_chunks(data), level=2)
            for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                if rtag == 'WRAP':
                    wchunks = sputm.print_chunks(sputm.read_chunks(rdata), level=3)
                    for widx, (woff, (wtag, wdata)) in enumerate(wchunks):
                        if wtag == 'OFFS':
                            pass
                        if wtag == 'APAL':
                            palette = wdata
    return {'palette': palette, 'transparent': transparent, 'width': rwidth, 'height': rheight}

if __name__ == '__main__':
    import argparse

    from .preset import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        room = sputm.assert_tag('ROOM', sputm.untag(res))
        assert res.read() == b''
        # chunks = (assert_tag('LFLF', chunk) for chunk in read_chunks(tlkb))
        chunks = sputm.print_chunks(sputm.read_chunks(room))
        transparent = 255  # default
        for cidx, (off, (tag, data)) in enumerate(chunks):
            if tag == 'RMHD':
                # only for games < v7
                assert len(data) == 6, 'Game Version < 7'
                rwidth = int.from_bytes(data[:2], signed=False, byteorder='little')
                rheight = int.from_bytes(data[2:4], signed=False, byteorder='little')
                robjects = int.from_bytes(data[4:], signed=False, byteorder='little')
            if tag == 'TRNS':
                transparent = data[0]
            if tag == 'CLUT':
                palette = data
            if tag == 'PALS':
                rchunks = sputm.print_chunks(sputm.read_chunks(data), level=2)
                for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                    if rtag == 'WRAP':
                        wchunks = sputm.print_chunks(sputm.read_chunks(rdata), level=3)
                        for widx, (woff, (wtag, wdata)) in enumerate(wchunks):
                            if wtag == 'OFFS':
                                pass
                            if wtag == 'APAL':
                                palette = wdata
            if tag == 'RMIM':
                im = decode_rmim(data, rwidth, rheight)
                im.putpalette(palette)
                im.save(f'room_{os.path.basename(args.filename)}.png')
            if tag == 'OBIM':
                assert palette
                rchunks = sputm.print_chunks(sputm.read_chunks(data), level=1)
                curr_obj = 0
                for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                    if rtag == 'IMHD':
                        with io.BytesIO(rdata) as stream:
                            obj_id = read_uint16le(stream)
                            obj_num_imnn = read_uint16le(stream)
                            # should be per imnn, but at least 1
                            obj_nums_zpnn = read_uint16le(stream)
                            obj_flags = stream.read(1)[0]
                            obj_unknown = stream.read(1)[0]
                            obj_x = read_uint16le(stream)
                            obj_y = read_uint16le(stream)
                            obj_width = read_uint16le(stream)
                            obj_height = read_uint16le(stream)
                            obj_hotspots = stream.read()
                            if obj_hotspots:
                                # TODO: read hotspots
                                pass
                    if rtag == f'IM{1 + curr_obj:02d}':
                        print(rtag)
                        roombg = read_room_background(rdata, obj_width, obj_height, None)
                        im = convert_to_pil_image(roombg)
                        im.putpalette(palette)
                        im.save(f'obj_{cidx:05d}_{ridx:05d}_{rtag}_{os.path.basename(args.filename)}.png')
                        curr_obj += 1
                assert curr_obj == obj_num_imnn, (curr_obj, obj_num_imnn)
        # save raw
        print('==========')
