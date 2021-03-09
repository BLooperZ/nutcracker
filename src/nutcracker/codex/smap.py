import io
from typing import Sequence

import numpy as np


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
    assert count <= 8
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
    elif 0x0E <= code <= 0x30:
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
    if 0x22 <= code <= 0x30 or 0x54 <= code <= 0x80 or code >= 0x8F:
        # if 34 <= code <= 48 or 84 <= code <= 128 or code >= 143:
        tr = TRANSPARENCY

    palen = code % 10

    # assert 0 <= palen <= 8
    return method, direction, tr, palen


def fake_encode_strip(data, height, width):
    with io.BytesIO() as s:
        s.write(b'\x95')
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
        return np.frombuffer(decoded, dtype=np.uint8).reshape(
            (height, width), order=order
        )
        # # return np.zeros((height, 8), dtype=np.uint8)

        # except Exception as exc:
        #     logging.exception(exc)
        #     return np.zeros((height, width), dtype=np.uint8)


def decode_smap(height: int, width: int, data: bytes) -> Sequence[Sequence[int]]:
    strip_width = 8

    if width == 0 or height == 0:
        return None

    num_strips = width // strip_width
    with io.BytesIO(data) as s:
        offs = [(read_uint32le(s) - 8) for _ in range(num_strips)]

    index = list(zip(offs, offs[1:] + [len(data)]))

    strips = (data[offset:end] for offset, end in index)
    return np.hstack([parse_strip(height, strip_width, data) for data in strips])


def encode_smap(image: Sequence[Sequence[int]]) -> bytes:
    strip_width = 8

    height, width = image.shape
    print(height, width)
    num_strips = width // strip_width
    strips = [fake_encode_strip(s, *s.shape) for s in np.hsplit(image, num_strips)]
    with io.BytesIO() as stream:
        offset = 8 + 4 * len(strips)
        for strip in strips:
            stream.write(offset.to_bytes(4, byteorder='little', signed=False))
            offset += len(strip)
        return stream.getvalue() + b''.join(strips)
