import io
import itertools
import struct

from .base import unwrap_uint16le

UINT16LE = struct.Struct('<H')


def read_le_uint16(f):
    return UINT16LE.unpack(f[:2])[0]


def to_matrix(w, h, data):
    return [data[i * w : (i + 1) * w] for i in range(h)]


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
            linedata = b''.join(bytes([ll, *g]) for ll, g in eg)
            sized = (
                len(linedata).to_bytes(2, byteorder='little', signed=False) + linedata
            )
            stream.write(sized)
        return stream.getvalue()


def decode1(width, height, f):
    BG = 39
    out = [BG for _ in range(width * height)]

    with io.BytesIO(f) as stream:
        lines = [unwrap_uint16le(stream) for _ in range(height)]
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
