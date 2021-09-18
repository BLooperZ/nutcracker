import io
import itertools
from typing import Sequence

import numpy as np

from nutcracker.utils.funcutils import grouper

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
                        # print(f'SHIFT {shift}')
                        color += shift
                    else:
                        ln = collect_bits(bitstream, 8) - 1
                        out.write(to_byte(color) * ln)
                        # print(f'LARGE GROUP {ln + 1}')
                else:
                    color = collect_bits(bitstream, palen)
                    # print(f'NEW COLOR {color}')
            # else:
            #     print('SMALL GROUP')
            out.write(to_byte(color))

        return out.getvalue()


def encode_basic(data, palen):
    bits = []
    color = data[0]
    sub = 1
    for curr in data[1:]:
        if curr == color:
            bits.extend([0])
        elif color - curr == sub:
            # print(f'SHIFT {curr - color}')
            bits.extend([1, 1, 0])
        elif curr - color == sub:
            # print(f'SHIFT {curr - color}')
            bits.extend([1, 1, 1])
            sub = -sub
        else:
            # print(f'NEW COLOR {curr}')
            bits.extend([1, 0])
            bits.extend(int(x) for x in f'{curr:0{palen}b}'[::-1])
            sub = 1
        color = curr

    gbits = grouper((str(x) for x in bits), 8, fillvalue='0')
    return data[:1] + bytes(int(''.join(byte)[::-1], 2) for byte in gbits)



def encode_complex(data, palen):
    bits = []
    grouped = (list(group) for _, group in itertools.groupby(data))
    color = None
    for currs in grouped:
        curr = currs[0]
        currs = currs[1:]
        assert curr != color
        if not bits:
            bits.extend(int(x) for x in f'{curr:08b}'[::-1])
        elif -4 <= curr - color < 4:
            # print(f'SHIFT {curr - color}')
            bits.extend([1, 1])
            bits.extend(int(x) for x in f'{curr - color + 4:03b}'[::-1])
        else:
            # print(f'NEW COLOR {curr}')
            bits.extend([1, 0])
            bits.extend(int(x) for x in f'{curr:0{palen}b}'[::-1])
        color = curr

        if currs:
            for group in grouper(currs, 255):
                group = [x for x in group if x is not None]
                if len(group) > 12:  # 12 in v6+ (dig, samnmax, dott (code 108)), 255 in v5? (atlantis, monkey2 (code 68))
                    bits.extend([1, 1, 0, 0, 1])
                    bits.extend(int(x) for x in f'{len(group):08b}'[::-1])
                    # print(f'LARGE GROUP {len(group)}')
                else:
                    # for _ in range(len(group)):
                    #     print('SMALL GROUP')
                    bits.extend([0] * len(group)) 

    gbits = grouper((str(x) for x in bits), 8, fillvalue='0')
    return bytes(int(''.join(byte)[::-1], 2) for byte in gbits)


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



def encode_he(data, palen):
    delta_color = [-4, -3, -2, -1, 1, 2, 3, 4]

    bits = []
    color = data[0]
    for curr in data[1:]:
        if curr == color:
            bits.extend([0])
        elif curr - color in delta_color:
            # print(f'SHIFT {curr - color}')
            bits.extend([1, 1])
            bits.extend(int(x) for x in f'{delta_color.index(curr - color):03b}'[::-1])
        else:
            # print(f'NEW COLOR {curr}')
            bits.extend([1, 0])
            bits.extend(int(x) for x in f'{curr:0{palen}b}'[::-1])
        color = curr

    gbits = grouper((str(x) for x in bits), 8, fillvalue='0')
    return data[:1] + bytes(int(''.join(byte)[::-1], 2) for byte in gbits)


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

    tr = None
    if 0x22 <= code <= 0x30 or 0x54 <= code <= 0x80 or code >= 0x8F:
        # if 34 <= code <= 48 or 84 <= code <= 128 or code >= 143:
        tr = TRANSPARENCY

    palen = code % 10

    # assert 0 <= palen <= 8
    return method, direction, tr, palen


def fake_encode_strip(data, height, width):
    print(f'==============={0xBB in data}===================')
    with io.BytesIO() as s:
        s.write(b'\x95' if 0xBB in data else b'\x01')
        s.write(bytes(data))
        return s.getvalue()


def encode_raw(data, *args):
    return data

def encode_strip(data, height, width, code):
    method, direction, tr, palen = get_method_info(code)
    data = bytes(data) if direction == 'HORIZONTAL' else bytes(data.T)
    if method == decode_complex:
        encode_method = encode_complex
    elif method == decode_basic:
        encode_method = encode_basic
    elif method == decode_he:
        encode_method = encode_he
    else:
        assert code in {0x01, 0x95}
        encode_method = encode_raw
    with io.BytesIO() as s:
        s.write(bytes([code]))
        encoded = encode_method(data, palen)
        with io.BytesIO(encoded) as vstream:
            assert method(vstream, height * width, palen) == data
        s.write(bytes(encoded))
        return s.getvalue()


def parse_strip(height, width, data, transparency=None):
    print((height, width))
    with io.BytesIO(data) as s:
        code = s.read(1)[0]

        decode_method, direction, tr, palen = get_method_info(code)
        # TODO: handle transparency
        # assert not tr
        if tr is not None:
            tr = transparency

        print(code, decode_method, direction, tr, palen, sep=' === ')

        # try:

        decoded = decode_method(s, width * height, palen)  # [:width * height]

        # if decode_method == decode_basic:
        #     with io.BytesIO(decoded) as dec_stream:
        #         print(decoded)
        #         print(data[1:])
        #         assert encode_basic(dec_stream, height, palen, 8) == data[1:]


        if decode_method in {decode_complex, decode_basic, decode_he}:
            if decode_method == decode_complex:
                encode_method = encode_complex
            elif decode_method == decode_basic:
                encode_method = encode_basic
            elif decode_method == decode_he:
                encode_method = encode_he
            else:
                raise ValueError('should not have got here')

            print('=====================')
            encoded = encode_method(decoded, palen)
            print('---------------------')
            with io.BytesIO(encoded) as e:
                assert decode_method(e, width * height, palen) == decoded

            pos = s.tell()
            s.seek(1, 0)
            orig = s.read()

            # s.seek(1, 0)
            # obits = list(create_bitsream(s))

            # print('O', obits)

            print(pos - 1, len(orig), len(encoded))
            if orig[:len(encoded)] != encoded:
                print('ORIG', orig)
                print('ENCODED', encoded)
                exit(1)
            elif len(orig) > len(encoded):
                assert encoded + b'\x00' == orig
            s.seek(pos)

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


def decode_smap(height: int, width: int, data: bytes, transparency: bytes = None) -> Sequence[Sequence[int]]:
    strip_width = 8

    if width == 0 or height == 0:
        return None

    num_strips = width // strip_width
    with io.BytesIO(data) as s:
        offs = [(read_uint32le(s) - 8) for _ in range(num_strips)]

    index = list(zip(offs, offs[1:] + [len(data)]))

    strips = (data[offset:end] for offset, end in index)
    return np.hstack([parse_strip(height, strip_width, data, transparency) for data in strips])


def extract_smap_codes(height: int, width: int, data: bytes) -> Sequence[int]:
    strip_width = 8

    if width == 0 or height == 0:
        return None

    num_strips = width // strip_width
    with io.BytesIO(data) as s:
        offs = [(read_uint32le(s) - 8) for _ in range(num_strips)]

    index = list(zip(offs, offs[1:] + [len(data)]))
    return [data[offset] for offset, _ in index]


def encode_smap(image: Sequence[Sequence[int]], codes=None) -> bytes:
    strip_width = 8

    height, width = image.shape
    print(height, width)
    num_strips = width // strip_width
    if codes:
        print('CODES', codes)
        strips = [encode_strip(s, *s.shape, code) for s, code in zip(np.hsplit(image, num_strips), codes)]
    else:
        print('NO CODES')
        strips = [fake_encode_strip(s, *s.shape) for s in np.hsplit(image, num_strips)]
    with io.BytesIO() as stream:
        offset = 8 + 4 * len(strips)
        for strip in strips:
            stream.write(offset.to_bytes(4, byteorder='little', signed=False))
            offset += len(strip)
        return stream.getvalue() + b''.join(strips)
