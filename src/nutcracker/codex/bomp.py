import io
import itertools
from typing import Optional, Sequence

import numpy as np

from nutcracker.codex import base
from nutcracker.kernel.buffer import BufferLike, UnexpectedBufferSize


def iter_decode(src: BufferLike):
    with io.BytesIO(src) as stream:
        while stream.tell() < len(src):
            code = stream.read(1)[0]
            run_len = (code // 2) + 1
            run_line = (
                stream.read(1)  # * run_len
                if code & 1
                else stream.read(run_len)
            )
            yield code, list(run_line)


def decode_line(
    src: BufferLike,
    decoded_size: Optional[int] = None,
    fill_value: Optional[bytes] = None,
) -> bytes:
    buffer = bytearray()
    with io.BytesIO(src) as stream:
        while stream.tell() < len(src):

            if decoded_size and len(buffer) >= decoded_size:
                rest = stream.read()
                assert rest in {
                    b'', b'\x00',
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                }, rest
                break

            code = stream.read(1)[0]
            run_len = (code // 2) + 1
            run_line = (
                stream.read(1) * run_len if code & 1 else stream.read(run_len)
            )
            buffer += run_line

    if decoded_size and len(buffer) != decoded_size:
        if len(buffer) < decoded_size and fill_value is not None:
            buffer += fill_value * (decoded_size - len(buffer))
        else:
            raise UnexpectedBufferSize(decoded_size, len(buffer), buffer)

    return bytes(buffer)


def decode_image(
    data: BufferLike,
    width: int,
    height: int,
    fill_value: Optional[bytes] = None,
) -> Sequence[Sequence[int]]:
    with io.BytesIO(data) as stream:
        lines = [base.unwrap_uint16le(stream) for _ in range(height)]
        rest = stream.read()
        # \xff appears in DIG at AKOS_0102, same also missing bytes on last line which have to be filled
        assert rest in {b'', b'\0', b'\xff'}, rest

    buffer = [list(decode_line(line, width, fill_value)) for line in lines]
    return np.array(buffer, dtype=np.uint8)


BUFFER_LIMIT = 128

def compressed_group(buf):
    return (2 * (len(buf) - 1) + 1, buf[:1])

def raw_group(buf):
    return (2 * (len(buf) - 1), list(buf))

def encode_groups(groups, buf=(), limit=4, carry=True, end_limit=1, seps=False):
    buf = list(buf)
    # print('GROUPS', [tuple(g) for g in groups])
    groups = iter(groups)
    for group in groups:

        if len(set(buf)) == 1 and len(buf) > 1:
            yield compressed_group(buf)
            buf = []

        if seps and buf == [0]:
            yield compressed_group(buf)
            if len(group) <= limit:
                yield raw_group(group)
            else:
                yield raw_group(group[:1])
                yield compressed_group(group[1:])
            buf = []
            continue


        if len(group) < limit or len(buf) + limit > BUFFER_LIMIT:
            if seps and set(group) == {0}:
                if buf:
                    yield raw_group(buf)
                buf = group
                continue

            buf += group

            if len(buf) > BUFFER_LIMIT:
                yield raw_group(buf[:BUFFER_LIMIT])
                buf = buf[BUFFER_LIMIT:]

            continue

        if buf:
            if carry:
                buf += group[:1]
                group = group[1:]
            yield raw_group(buf)
            buf = []

        if len(group) > BUFFER_LIMIT:
            yield compressed_group(group[:BUFFER_LIMIT])
            group = group[BUFFER_LIMIT:]
            assert not buf
            yield from encode_groups([group, *groups], buf=(), limit=limit, carry=carry, end_limit=end_limit, seps=seps)
        else:
            # print('AAA 1', (2 * (len(group) - 1) + 1, group[:1]))
            if len(group) > 1 or set(group) == {0}:
                # print('AAA 1', (2 * (len(group) - 1) + 1, group[:1]))
                yield compressed_group(group)
            else:
                # print('AAA 2', (2 * (len(group) - 1), list(group)))
                yield raw_group(group)
    if buf:
        if len(set(buf)) == 1 and len(buf) > end_limit:
            yield compressed_group(buf)
        else:
            yield raw_group(buf)


def encode_image(bmap, limit=4, carry=True, end_limit=1, seps=False):
    buffer = bytearray()
    for line in bmap:
        grouped = [list(group) for c, group in itertools.groupby(line)]
        eg = list(encode_groups(grouped, buf=(), limit=limit, carry=carry, end_limit=end_limit, seps=seps))
        # print('ENCODED', eg)
        linedata = b''.join(bytes([ll, *g]) for ll, g in eg)
        buffer += base.wrap_uint16le(linedata)
    # if len(buffer) % 2:
    #     buffer += b'\x00'
    return bytes(buffer)
