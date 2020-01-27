#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

import numpy as np

from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.codex.codex import decode1

TRANSPARENCY = 255

def read_uint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def read_uint32le(stream):
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)

def create_bitsream(stream):
    sd = stream.read()
    bits = ''.join(f'{x:08b}'[::-1] for x in sd)
    return (int(x) for x in bits)

def get_bits(bitstream, count):
    # TODO: check if special handling needed when count > 8
    return int(''.join(str(next(bitstream)) for _ in range(count))[::-1], 2)

def decode_basic(stream, height, palen, *args):
    color = stream.read(1)[0]
    sub = 1

    bitstream = create_bitsream(stream)

    with io.BytesIO() as out:
        out.write(bytes([color % 256]))
        while out.tell() < 8 * height:
            if next(bitstream) == 1:
                if next(bitstream) == 1:
                    if next(bitstream) == 1:
                        sub = -sub
                    color -= sub
                else:
                    color = get_bits(bitstream, palen)
                    sub = 1
            out.write(bytes([color % 256]))
        return out.getvalue()

def decode_complex(stream, height, palen, *args):
    color = stream.read(1)[0]
    sub = 1

    bitstream = create_bitsream(stream)

    with io.BytesIO() as out:
        out.write(bytes([color % 256]))
        while out.tell() < 8 * height:
            if next(bitstream) == 1:
                if next(bitstream) == 1:
                    shift = get_bits(bitstream, 3) - 4
                    if shift != 0:
                        color += shift
                    else:
                        ln = get_bits(bitstream, 8) - 1
                        out.write(bytes([color % 256]) * ln)
                else:
                    color = get_bits(bitstream, palen)
            out.write(bytes([color % 256]))
        return out.getvalue()

def decode_raw(stream, height, *args):
    res = stream.read(8 * height)
    print(stream.read())
    return res

def unknown_decoder(*args):
    raise ValueError('Unknown Decoder')

def decode_he(stream, height, palen, width):
    raise NotImplementedError('WIP')
    # delta_color = [-4, -3, -2, -1, 1, 2, 3, 4]

    # color = stream.read(1)[0]
    # sub = 1

    # bitstream = create_bitsream(stream)

    # with io.BytesIO() as out:
    #     out.write(bytes([color % 256]))
    #     while out.tell() < 8 * height:
    #         if next(bitstream) == 1:
    #             if next(bitstream) == 1:
    #                 shift = get_bits(bitstream, 3) - 4
    #                 if shift != 0:
    #                     color += delta_color[shift % 7]
    #             else:
    #                 color = get_bits(bitstream, palen)
    #     return out.getvalue()

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

    pals = [0x0e, 0x18, 0x22, 0x2c, 0x40, 0x54, 0x68, 0x7c]
    ln = ((code - (p - 4)) for p in pals if p <= code <= p + 4)
    palen = next(ln, 255)
    # assert 0 <= palen <= 8
    return method, direction, tr, palen

def read_strip(data, height, width):
    with io.BytesIO(data) as s:
        code = s.read(1)[0]
        print(code)

        decode_method, direction, tr, palen = get_method_info(code)
        # TODO: handle transparency

        # assert not tr
        decoded = decode_method(s, height, palen, width)

        # Verify nothing left in stream
        assert not s.read()

        order = 'C' if direction == 'HORIZONTAL' else 'F'
        return np.frombuffer(decoded, dtype=np.uint8).reshape((height, 8), order=order)

def read_room_background(data, width, height, zbuffers):
    image, *zplanes = sputm.drop_offsets(sputm.print_chunks(sputm.read_chunks(rdata), level=2))
    # print(smap)
    for c in zplanes:
        pass

    tag, data = image
    if tag == 'SMAP':
        strips = width // 8
        with io.BytesIO(data) as s:
            # slen = read_uint32le(s)
            # print(slen)
            offs = [(read_uint32le(s) - 8)  for _ in range(strips)]
            index = list(zip(offs, offs[1:] + [len(data)]))
            imarr = []
            for num, (offset, end) in enumerate(index):
                s.seek(offset, io.SEEK_SET)
                strip_data = s.read(end - offset)
                ni = read_strip(strip_data, height, width)
                imarr.append(ni)
            print(index)
            return np.hstack(imarr)
            # print(s.read())
    elif tag == 'BOMP':
        with io.BytesIO(data) as s:
            unk = read_uint16le(s)
            width = read_uint16le(s)
            height = read_uint16le(s)
            # TODO: check if x,y or y,x
            xpad, ypad = read_uint16le(s), read_uint16le(s)
            im = decode1(width, height, s.read())
        return np.asarray(im, dtype=np.uint8)
    else:
        raise ValueError('Unknown image codec')

if __name__ == '__main__':
    import argparse

    from . import sputm

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
                assert palette
                rchunks = sputm.print_chunks(sputm.read_chunks(data), level=1)
                zbuffers = None
                for ridx, (roff, (rtag, rdata)) in enumerate(rchunks):
                    if rtag == 'RMIH':
                        assert len(rdata) == 2
                        zbuffers = 1 + int.from_bytes(rdata, signed=False, byteorder='little')
                        assert 1 <= zbuffers <= 8
                    if rtag == 'IM00':
                        assert zbuffers
                        roombg = read_room_background(data, rwidth, rheight, zbuffers)
                        im = convert_to_pil_image(roombg)
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
                            # assert not stream.read()
                    if rtag == f'IM{1 + curr_obj:02d}':
                        print(rtag)
                        roombg = read_room_background(data, obj_width, obj_height, None)
                        im = convert_to_pil_image(roombg)
                        im.putpalette(palette)
                        im.save(f'obj_{cidx:05d}_{ridx:05d}_{rtag}_{os.path.basename(args.filename)}.png')
                        curr_obj += 1
                assert curr_obj == obj_num_imnn, (curr_obj, obj_num_imnn)
        # save raw
        print('==========')
