import io
import itertools
from typing import Sequence


from .base import wrap_uint16le, unwrap_uint16le


def encode_lined_rle(bmap: Sequence[Sequence[int]]) -> bytes:
    with io.BytesIO() as stream:
        for line in bmap:
            if set(line) == {0}:
                stream.write(b'\00\00')
                continue

            grouped = [list(group) for _, group in itertools.groupby(line)]
            eg = list(encode_rle_groups(grouped))
            # print('ENCODED', eg)
            stream.write(
                wrap_uint16le(
                    b''.join(bytes([ll, *(() if ll & 1 else g)]) for ll, g in eg)
                )
            )
        return stream.getvalue()


def decode_rle_group(line, width):
    out = [0 for _ in range(width)]
    currx = 0
    with io.BytesIO(line) as stream:
        while stream.tell() < len(line) and currx < width:
            code = ord(stream.read(1))
            if code & 1:  # skip count
                currx += code >> 1
            else:
                count = (code >> 2) + 1
                out[currx : currx + count] = (
                    stream.read(1) * count if code & 2 else stream.read(count)
                )
                currx += count
    return out


def decode_rle_group_gen(line, width):
    with io.BytesIO(line) as stream:
        while stream.tell() < len(line):
            code = ord(stream.read(1))
            if code & 1:  # skip count
                yield (code, [0] * (code >> 1))
            else:
                count = (code >> 2) + 1
                yield (
                    code,
                    list(stream.read(1) * count if code & 2 else stream.read(count)),
                )


def to_byte(num):
    return bytes([num])


def encode_rle_groups(groups, buf=()):

    buf = list(buf)
    groups = iter(groups)
    for group in groups:

        if set(group) == {0}:
            if buf:
                # if len(set(buf)) == 1:
                #     yield (4 * (len(buf) - 1) + 2, buf[:1])
                # else:
                yield (4 * (len(buf) - 1), list(buf))
                buf = []

            if len(group) > 127:
                yield (2 * 127 + 1, group[:1])
                group = group[127:]
                assert not buf
                if group:
                    yield (2 * 1 + 1, group[:1])
                    group = group[1:]
                if group:
                    yield from encode_rle_groups([group, *groups])

            elif group:
                yield (2 * len(group) + 1, group[:1])
        else:

            raw = 1 + len(buf) + len(group)
            encoded = 1 + len(buf) + 2
            if raw < encoded or (raw == encoded and buf):
                buf += group

                if len(buf) > 64:
                    yield (4 * (64 - 1), buf[:64])
                    buf = buf[64:]
                    if len(set(buf)) == 1:
                        yield from encode_rle_groups([buf, *groups])
                        buf = []
                    else:
                        yield from encode_rle_groups(groups, buf=buf)

            else:
                if buf:
                    yield (4 * (len(buf) - 1), list(buf))
                    buf = []

                if len(group) > 64:
                    yield (4 * (64 - 1) + 2, group[:1])
                    group = group[64:]
                    assert not buf
                    if len(group) == 1:
                        yield (2, group)
                    else:
                        yield from encode_rle_groups([group, *groups])
                else:
                    yield (4 * (len(group) - 1) + 2, group[:1])
    if buf:
        yield (4 * (len(buf) - 1), list(buf))


def decode_lined_rle(data, width, height, verify=True):
    with io.BytesIO(data) as stream:
        lines = [unwrap_uint16le(stream) for _ in range(height)]
    output = [decode_rle_group(line, width) for line in lines]
    output2 = [list(decode_rle_group_gen(line, width)) for line in lines]

    for ll, o in zip(lines, output2):
        g = [
            list(group)
            for c, group in itertools.groupby(b''.join(bytes(oo) for _, oo in o))
        ]
        e = [t for t in encode_rle_groups(g)]
        o = [(c, gl[:1]) if c & (1 | 2) else (c, gl) for c, gl in o]
        if e != o:
            print('================')
            print('ORIG', list(ll))
            print('REGROUPED', g)
            print('OGROUPS', o)
            print('ENCODED', e)
    if verify:
        encoded = encode_lined_rle(output)

        with io.BytesIO(encoded) as stream:
            elines = [unwrap_uint16le(stream) for _ in range(height)]
        ex = False
        for idx, (ll, e) in enumerate(zip(lines, elines)):
            if not ll == e:
                print(idx)
                print('ORIGiNA', ll)
                print('ENCODED', e)
                ex = True
        if ex:
            exit(1)

        assert encoded == data, (encoded, data)
    return output
