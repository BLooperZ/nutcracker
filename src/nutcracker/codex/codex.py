#!/usr/bin/env python3
import io
import struct
import itertools

from .codex37_np import decode37 as e_decode37, fake_encode37
from .codex47_np import decode47 as e_decode47, fake_encode47

# from codex37_old import decode37

# DECODE


def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]


def unidecoder(width, height, f):
    BG = 39

    out = [BG for _ in range(width * height)]
    dst = 0
    src = 0
    for _ in range(height):
        dstPtrNext = dst + width
        srcPtrNext = src + 2 + read_le_uint16(f[src:])
        src += 2
        lens = width
        while lens > 0:
            offs = read_le_uint16(f[src:])
            src += 2
            dst += offs
            lens -= offs
            w = read_le_uint16(f[src:]) + 1
            src += 2
            lens -= w
            if lens < 0:
                w += lens
            out[dst : dst + w] = f[src : src + w]
            dst += w
            src += w
        assert dst == dstPtrNext
        dst = dstPtrNext
        src = srcPtrNext
    if src != len(f):
        print('DIFF', f[src:])
    return to_matrix(width, height, out)


def encode1(bmap):
    def encode_groups(groups, buf=()):
        BG = 39

        buf = list(buf)
        groups = iter(groups)
        for group in groups:
            if set(group) == {BG}:
                group = [0] * len(group)
            raw = 1 + len(buf) + len(group)
            encoded = 1 + len(buf) + 2
            if raw < encoded or (raw == encoded and buf):
                buf += group

                if len(buf) > 128:
                    yield (2 * (128 - 1), buf[:128])
                    buf = buf[128:]
                    if len(set(buf)) == 1:
                        yield from encode_groups([buf, *groups])
                        buf = []
                    else:
                        yield from encode_groups(groups, buf=buf)

            else:
                if buf:
                    yield (2 * (len(buf) - 1), list(buf))
                    buf = []

                if len(group) > 128:
                    yield (2 * (128 - 1) + 1, group[:1])
                    group = group[128:]
                    assert not buf
                    yield from encode_groups([group, *groups])
                else:
                    yield (2 * (len(group) - 1) + 1, group[:1])
        if buf:
            yield (2 * (len(buf) - 1), list(buf))

    with io.BytesIO() as stream:
        for line in bmap:
            grouped = [list(group) for c, group in itertools.groupby(line)]
            eg = list(encode_groups(grouped))
            # print('ENCODED', eg)
            linedata = b''.join(bytes([l, *g]) for l, g in eg)
            sized = (
                len(linedata).to_bytes(2, byteorder='little', signed=False) + linedata
            )
            stream.write(sized)
        return stream.getvalue()


def decode1(width, height, f):
    BG = 39
    out = [BG for _ in range(width * height)]

    with io.BytesIO(f) as stream:
        lines = [stream.read(read_le_uint16(stream.read(2))) for _ in range(height)]
        tail = stream.read()
        assert tail in {b'', b'\00'}, tail

    with io.BytesIO() as outstream:
        for line in lines:
            with io.BytesIO(line) as stream:
                # log = []
                while stream.tell() < len(line):
                    code = ord(stream.read(1))
                    run_len = (code // 2) + 1
                    run_line = (
                        stream.read(1) * run_len if code & 1 else stream.read(run_len)
                    )
                    outstream.write(run_line)
                #     log.append((code, run_line[:1] if code & 1 else run_line))
                # print('I', [(code, list(run_line)) for code, run_line in log])
        buffer = outstream.getvalue()

    out = [x if x else bg for bg, x in zip(out, buffer)]
    mat = to_matrix(width, height, out)
    # assert encode1(mat) == f or encode1(mat) + b'\00' == f, (encode1(mat), f)
    return mat


def decode47(width, height, f):
    return e_decode47(f, width, height)


def decode37(width, height, f):
    return e_decode37(f, width, height)


def unidecoder_factory(width, height):
    return unidecoder


decoders = {
    1: decode1,
    21: unidecoder,
    44: unidecoder,
    47: decode47,
    37: decode37,
}


def get_decoder(codec):
    if codec in decoders:
        return decoders[codec]
    return NotImplemented


def to_matrix(w, h, data):
    return [data[i * w : (i + 1) * w] for i in range(h)]


# ENCODE


def codec44(width, height, out):
    BG = 39

    f = b''
    for line in out:
        le = b''
        done = 0
        while done < width:
            i = 0
            while done + i < width and line[done + i] == BG:
                i += 1
            off = i
            while done + i < width and line[done + i] != BG:
                i += 1
            lst = line[done + off : done + i]
            le += struct.pack('<H', off)
            r = 1 if (done + i < width) else 0
            if len(lst) > 0:
                le += struct.pack('<H', len(lst) - r)
                for it in lst:
                    le += struct.pack('<B', it)
            else:
                le += struct.pack('<H', 0)
            done += i
        f += struct.pack('<H', len(le) + 1) + le + struct.pack('<B', 0)
    f += struct.pack('<H', width + 5) + b'\x00\x00' + struct.pack('<H', width)
    f += b'\x00' * (width + 1)
    if len(f) % 2 != 0:
        f += b'\x00'
    return f


def codec21(width, height, out):
    BG = 39

    f = b''
    for line in out + [[BG for _ in range(width)]]:
        le = b''
        done = 0
        while done <= width:
            i = 0
            while done + i < width and line[done + i] == BG:
                i += 1
            off = i
            r = i + 1
            if done + r > width:
                le += struct.pack('<H', r)
                break
            while done + i < width and line[done + i] != BG:
                i += 1
            lst = line[done + off : done + i]
            le += struct.pack('<H', off)
            if len(lst) > 0:
                le += struct.pack('<H', len(lst) - 1)
                for it in lst:
                    le += struct.pack('<B', it)
            done += i
        f += struct.pack('<H', len(le)) + le
    if len(f) % 2 != 0:
        f += b'\x00'
    return f


encoders = {
    21: codec21,
    44: codec44,
    37: fake_encode37,
    47: fake_encode47,
}


def get_encoder(codec):
    if codec in encoders:
        return encoders[codec]
    print(codec)
    return NotImplemented
