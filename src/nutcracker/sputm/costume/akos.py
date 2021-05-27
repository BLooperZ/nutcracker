#!/usr/bin/env python3
import io
import os
from typing import Iterator, NamedTuple, Tuple

from nutcracker.codex import bomb, rle
from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.utils.funcutils import flatten

from ..preset import sputm

class AkosHeader(NamedTuple):
    unk_1: int
    flags: int
    unk_2: int
    num_anims: int
    unk_3: int
    codec: int


def akos_header_from_bytes(data: bytes) -> AkosHeader:
    with io.BytesIO(data) as stream:
        return AkosHeader(
            unk_1=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            flags=ord(stream.read(1)),
            unk_2=ord(stream.read(1)),
            num_anims=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            unk_3=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            codec=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
        )


def akof_from_bytes(data: bytes) -> Iterator[Tuple[int, int]]:
    with io.BytesIO(data) as stream:
        while True:
            entry = stream.read(6)
            if not entry:
                break
            cd_off = int.from_bytes(entry[0:4], signed=False, byteorder='little')
            ci_off = int.from_bytes(entry[4:6], signed=False, byteorder='little')
            print(cd_off, ci_off)
            yield cd_off, ci_off


def decode1(width, height, pal, data):
    if len(pal.data) == 32:
        shift = 3
        mask = 0x07
    elif len(pal.data) == 64:
        shift = 2
        mask = 0x03
    else:
        shift = 4
        mask = 0x0F

    _height = height
    _width = width
    _cur_x = 0
    _dest_ptr = 0

    out = [0 for _ in range(width) for _ in range(height)]

    with io.BytesIO(data) as stream:
        while True:
            reps = stream.read(1)[0]
            color = reps >> shift
            reps &= mask

            if reps == 0:
                reps = stream.read(1)[0]

            if reps == 0:
                _width -= 1
                continue

            for b in range(reps):
                out[_dest_ptr] = color
                _dest_ptr += width

                _height -= 1
                if _height == 0:
                    _height = height
                    _cur_x += 1
                    _dest_ptr = _cur_x

                    _width -= 1
                    if _width == 0:
                        return convert_to_pil_image(out, size=(width, height))


def decode5(width, height, pal, data):
    with io.BytesIO(data) as stream:
        lines = [
            stream.read(
                int.from_bytes(stream.read(2), signed=False, byteorder='little')
            )
            for _ in range(height)
        ]

    out = [bomb.decode_line(line, width) for line in lines]

    return convert_to_pil_image(out, size=(width, height))


def decode32(width, height, pal, data):
    out = rle.decode_lined_rle(data, width, height, verify=False)
    return convert_to_pil_image(out, size=(width, height))


def decode_frame(akhd, ci, cd, palette):

    width = int.from_bytes(ci[0:2], signed=False, byteorder='little')
    height = int.from_bytes(ci[2:4], signed=False, byteorder='little')

    print(akhd, width, height)

    if akhd.codec == 1:
        try:
            return decode1(width, height, palette, cd)
        except IndexError:
            # TODO: fix failure on COMI.LA2 at AKOS_0213
            return convert_to_pil_image([[0]])
    elif akhd.codec == 5:
        return decode5(width, height, palette, cd)
    elif akhd.codec == 32:
        return decode32(width, height, palette, cd)
    else:
        print(akhd.codec)
        raise NotImplementedError()


def read_akos_resource(resource):
    # akos = check_tag('AKOS', next(sputm.map_chunks(resource)))
    akos = sputm.find('AKOS', sputm.map_chunks(resource))
    if not akos:
        return
    # akos = iter(akos)
    akhd = akos_header_from_bytes(sputm.find('AKHD', akos).data)

    # colors
    akpl = sputm.find('AKPL', akos)
    print(akpl)
    rgbs = sputm.find('RGBS', akos)
    print(rgbs)
    # palette = tuple(zip(akpl, rgbs))
    # for x in akpl.data:
    #     print(x)
    # print(palette)
    # exit(1)

    # scripts?
    aksq = sputm.find('AKSQ', akos)
    # akch = sputm.find('AKCH', akos)

    # image
    akof = list(akof_from_bytes(sputm.find('AKOF', akos).data))
    akci = sputm.find('AKCI', akos)
    akcd = sputm.find('AKCD', akos)
    akct = sputm.find('AKCT', akos)

    print(akof, akci, akcd)

    ends = akof[1:] + [(len(akcd.data), len(akci.data))]
    for (cd_start, ci_start), (cd_end, ci_end) in zip(akof, ends):
        ci = akci.data[ci_start : ci_start + 8]
        # print(len(ci))
        # if not akhd.codec in {32}:
        #     continue
        cd = akcd.data[cd_start:cd_end]
        decoded = decode_frame(akhd, ci, cd, akpl)
        decoded.putpalette(rgbs.data)
        yield decoded

    return akhd, akpl, rgbs, aksq


if __name__ == '__main__':
    import argparse
    import glob
    import os

    from nutcracker.utils.fileio import read_file

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = sorted(set(flatten(glob.iglob(r) for r in args.files)))
    print(files)
    for filename in files:

        print(filename)

        resource = read_file(filename, key=int(args.chiper_key, 16))

        os.makedirs('AKOS_out', exist_ok=True)

        for idx, im in enumerate(read_akos_resource(resource)):
            im.save(f'AKOS_out/{os.path.basename(filename)}_aframe_{idx}.png')
