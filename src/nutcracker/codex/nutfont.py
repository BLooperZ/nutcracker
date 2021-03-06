import struct
import io
import itertools

from .base import UINT16LE, wrap_uint16le, unwrap_uint16le

BG = 39


def decode_line(line, width, bg):
    with io.BytesIO(line) as stream, io.BytesIO() as ostr:
        while ostr.tell() < width:
            off = UINT16LE.unpack(stream.read(2))[0]
            if ostr.tell() + off > width:
                break
            ostr.write(bytes([bg for _ in range(off)]))
            w = UINT16LE.unpack(stream.read(2))[0] + 1
            ostr.write(stream.read(w))
        ostr.write(bytes([bg for _ in range(width - ostr.tell())]))
        return list(ostr.getvalue())[:width]


def unidecoder(width, height, f):
    with io.BytesIO(f) as stream:
        lines = [
            decode_line(unwrap_uint16le(stream), width, BG) for _ in range(height + 1)
        ][:height]
        tail = stream.read()
        assert tail in {b'', b'\00'}, tail
        return lines


def encode_line_44(width, line, bg):
    le = b''
    done = 0
    while done < width:
        i = 0
        while done + i < width and line[done + i] == bg:
            i += 1
        off = i
        while done + i < width and line[done + i] != bg:
            i += 1
        lst = line[done + off : done + i]
        le += struct.pack('<H', off)
        lst += b'' if (done + i < width) else b'\x00'
        if len(lst) > 0:
            le += struct.pack('<H', len(lst) - 1) + bytes(lst)
        done += i

    return le


def codec44(width, height, out):
    assert height == len(out)
    buf = b''.join(
        wrap_uint16le(encode_line_44(width, line, BG))
        for line in out + [[0 for _ in range(width)]]
    )
    return buf + b'\x00' * (len(buf) % 2)


# def get_segments_21(line, bg):

#     import itertools

#     off = 0
#     lst = b''
#     for is_bg, group in itertools.groupby(line, key=lambda val: val == bg):
#         lst = bytes(group)
#         if not is_bg:
#             yield off, lst
#         off = len(lst)
#         if not is_bg:
#             lst = b''
#     yield len(lst) + 1, b''


def encode_line_21(width, line, bg):

    # print('============', width)

    le = b''
    off = 0
    lst = b''
    for is_bg, group in itertools.groupby(line, key=lambda val: val == bg):
        lst = bytes(group)
        if not is_bg:
            le += struct.pack('<H', off) + struct.pack('<H', len(lst) - 1) + lst
        off = len(lst)
        if not is_bg:
            lst = b''
    le += struct.pack('<H', len(lst) + 1)

    # le2 = b''.join(
    #     (
    #         struct.pack('<H', off)
    #         + (struct.pack('<H', len(lst) - 1) + lst if lst else b'')
    #     )
    #     for off, lst in get_segments_21(line, bg)
    # )
    # assert le == le2, (le, le2)
    assert le == encode_line_21_old(width, line, bg)
    return le


def encode_line_21_old(width, line, bg):
    le = b''
    done = 0
    while done <= width:
        i = 0
        while done + i < width and line[done + i] == bg:
            i += 1
        off = i
        r = i + 1
        if done + r > width:
            le += struct.pack('<H', r)
            break
        while done + i < width and line[done + i] != bg:
            i += 1
        lst = line[done + off : done + i]
        le += struct.pack('<H', off)
        if len(lst) > 0:
            le += struct.pack('<H', len(lst) - 1) + bytes(lst)
        done += i
    return le


def codec21(width, height, out):
    assert height == len(out)
    buf = b''.join(
        wrap_uint16le(encode_line_21(width, line, BG))
        for line in out + [[BG for _ in range(width)]]
    )
    return buf + b'\x00' * (len(buf) % 2)
