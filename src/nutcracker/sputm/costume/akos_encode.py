#!/usr/bin/env python3
import io
import os
import pathlib
import struct
from typing import Iterable, Iterator, NamedTuple, Tuple

import numpy as np
from PIL import Image

from nutcracker.codex import bomp, rle, smap, bpp_cost
from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.utils.fileio import write_file
from nutcracker.utils.funcutils import flatten

from nutcracker.sputm.room.pproom import get_rooms, read_room_settings
from nutcracker.sputm.tree import open_game_resource

from ..preset import sputm

class AkosHeader(NamedTuple):
    version: int
    flags: int
    num_anims: int
    num_cels: int
    codec: int
    num_layers: int


def akos_header_from_bytes(data: bytes) -> AkosHeader:
    with io.BytesIO(data) as stream:
        return AkosHeader(
            version=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            flags=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            num_anims=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            num_cels=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            codec=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
            num_layers=int.from_bytes(stream.read(2), signed=False, byteorder='little'),
        )


def akof_from_bytes(data: bytes) -> Iterator[Tuple[int, int]]:
    with io.BytesIO(data) as stream:
        while True:
            entry = stream.read(6)
            if not entry:
                break
            cd_off = int.from_bytes(entry[0:4], signed=False, byteorder='little')
            ci_off = int.from_bytes(entry[4:6], signed=False, byteorder='little')
            # print(cd_off, ci_off)
            yield cd_off, ci_off


def decode1(width, height, pal, data, verify=True):
    with io.BytesIO(data) as stream:
        res = convert_to_pil_image(
            bpp_cost.decode1(width, height, len(pal.data), stream, strict=False),
            size=(width, height)
        )

    if verify:
        d_data = bpp_cost.encode1(np.asarray(res), len(pal.data))
        with io.BytesIO(d_data) as stream:
            res2 = convert_to_pil_image(
                bpp_cost.decode1(width, height, len(pal.data), stream, strict=False),
                size=(width, height)
            )
        assert np.array_equal(np.asarray(res), np.asarray(res2))
        assert d_data == data, (len(d_data), len(data))

    return res


def decode5(width, height, pal, data):
    out = bomp.decode_image(data, width, height, fill_value=b'\xff')
    return convert_to_pil_image(out, size=(width, height))


def decode32(width, height, pal, data):
    out = rle.decode_lined_rle(data, width, height, verify=False)
    return convert_to_pil_image(out, size=(width, height))


def decode16(width, height, pal, data):
    with io.BytesIO(data) as stream:
        bpp = stream.read(1)[0]
        out = smap.decode_run_majmin(stream, width * height, bpp)
        return convert_to_pil_image(out, size=(width, height))

def decode_frame(akhd, ci, cd, palette):

    width = int.from_bytes(ci[0:2], signed=False, byteorder='little')
    height = int.from_bytes(ci[2:4], signed=False, byteorder='little')
    xoff = int.from_bytes(ci[4:6], signed=False, byteorder='little')
    yoff = int.from_bytes(ci[6:8], signed=False, byteorder='little')

    # print(akhd, width, height)
    return (xoff, yoff), {
        1: decode1,
        5: decode5,
        16: decode16,
        32: decode32,
    }[akhd.codec](width, height, palette, cd)


def construct_palette(akpl_data, rgbs_data):
    palette = bytearray(0x300)
    for idx, color in enumerate(akpl_data):
        palette[3*idx:3*(idx+1)] = rgbs_data[3*color:3*(color+1)]
    return palette


def read_akos_resource(akos, room_palette):
    # akos = check_tag('AKOS', next(sputm.map_chunks(resource)))
    # akos = sputm.find('AKOS', sputm.map_chunks(resource))
    # if not akos:
    #     return
    # akos = iter(akos)
    akhd = akos_header_from_bytes(sputm.find('AKHD', akos).data)

    # colors
    akpl = sputm.find('AKPL', akos)
    rgbs = sputm.find('RGBS', akos)

    print('CODEC', akhd.codec)

    if rgbs is None or akhd.codec in {5, 16}:
        palette = room_palette
    elif akpl is None:
        palette = rgbs.data
    else:
        palette = construct_palette(akpl.data, rgbs.data)

    # scripts?
    aksq = sputm.find('AKSQ', akos)
    # akch = sputm.find('AKCH', akos)

    # image
    akof = list(akof_from_bytes(sputm.find('AKOF', akos).data))
    akci = sputm.find('AKCI', akos)
    akcd = sputm.find('AKCD', akos)

    # aklc = sputm.find('AKLC', akos)
    # akst = sputm.find('AKST', akos)
    # akct = sputm.find('AKCT', akos)
    # if aklc:
    #     print(aklc, aklc.data)
    # if akst:
    #     size = len(akst.data) // 8
    #     print(akst, [
    #         (
    #             int.from_bytes(
    #                 akst.data[8 * i : 8 * i + 4],
    #                 signed=False,
    #                 byteorder='little',
    #             ),
    #             int.from_bytes(
    #                 akst.data[8 * i + 4 : 8 * (i + 1)],
    #                 signed=False,
    #                 byteorder='little',
    #             ),
    #         )
    #         for i in range(size)
    #     ])
    # if akct:
    #     print(akct, akct.data)

    # print(akof, akci, akcd)

    ends = akof[1:] + [(len(akcd.data), len(akci.data))]
    print(akof)
    for (cd_start, ci_start), (cd_end, ci_end) in zip(akof, ends):
        ci = akci.data[ci_start : ci_start + 8]
        # print(len(ci))
        # if not akhd.codec in {32}:
        #     continue
        cd = akcd.data[cd_start:cd_end]
        locs, decoded = decode_frame(akhd, ci, cd, akpl)
        decoded.putpalette(palette)
        yield akhd.codec, akpl, locs, decoded

    return akhd, akpl, rgbs, aksq


def create_akof(offsets: Iterable[tuple[int, int]]):
    return b''.join(struct.Struct('<IH').pack(*offs) for offs in offsets)

if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    args = parser.parse_args()

    files = sorted(set(flatten(glob.iglob(r) for r in args.files)))
    print(files)
    for filename in files:

        print(filename)

        gameres = open_game_resource(filename)
        basename = gameres.basename

        root = gameres.read_resources(
            # schema=narrow_schema(
            #     SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'PALS'}
            # )
        )

        os.makedirs(f'AKOS_out/{basename}', exist_ok=True)

        for t in root:

            for lflf in get_rooms(t):
                # print(lflf, lflf.attribs["path"])
                _, palette, _, _ = read_room_settings(lflf)

                for akos in sputm.findall('AKOS', lflf):
                    if akos.attribs['gid'] not in {59, 60, 61, 564}:
                        continue

                    print(akos, akos.attribs["path"])

                    offset = 0
                    ci_offset = 0
                    offsets = []
                    cdata = bytearray()

                    for idx, (codec, akpl, (xoff, yoff), im) in enumerate(
                        read_akos_resource(akos, palette),
                    ):
                        offsets.append((offset, ci_offset))
                        imname = f'{os.path.basename(lflf.attribs["path"])}_{os.path.basename(akos.attribs["path"])}_aframe_{idx}.png'
                        fullpath = pathlib.Path('AKOS_out', basename, imname)
                        if fullpath.exists():
                            im = Image.open(fullpath)

                        if codec == 1:
                            cdata += bpp_cost.encode1(np.asarray(im), len(akpl.data))
                        else:
                            raise ValueError(codec)

                        offset = len(cdata)
                        ci_offset += 4

                    os.makedirs(os.path.dirname(f'{basename}/{akos.attribs["path"]}'), exist_ok=True)
                    write_file(
                        f'{basename}/{akos.attribs["path"]}',
                        sputm.mktag(
                            akos.tag,
                            sputm.write_chunks(
                                sputm.mktag(e.tag, create_akof(offsets)) if e.tag == 'AKOF'
                                else sputm.mktag(e.tag, cdata) if e.tag == 'AKCD'
                                else sputm.mktag(e.tag, e.data)
                                for e in akos
                            )
                        ),
                    )
