#!/usr/bin/env python3
import io
import os
import struct
import itertools

from nutcracker.sputm.room.pproom import get_rooms, read_room_settings

from nutcracker.sputm.tree import open_game_resource

UINT32LE = struct.Struct('<I')
UINT16LE = struct.Struct('<H')
SINT16LE = struct.Struct('<h')


from nutcracker.codex import bpp_cost
from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.utils.funcutils import flatten

from ..preset import sputm

def read_cost_resource(cost, room_palette, version):
    with io.BytesIO(cost.data) as stream:
        size = 1
        if version == 6:
            size = UINT32LE.unpack(stream.read(UINT32LE.size))[0]
            header = stream.read(2)
            assert header == b'CO'
        num_anim = stream.read(1)[0] + (1 if size > 0 else 0)
        assert num_anim > 0
        flags = stream.read(1)[0]
        num_colors = 32 if flags % 2 else 16
        palette = list(itertools.chain.from_iterable([room_palette[3*x:3*x+3] for x in stream.read(num_colors)]))
        anim_cmds_offset = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
        limbs_offsets = [UINT16LE.unpack(stream.read(UINT16LE.size))[0] for _ in range(16)]
        anim_offsets = [UINT16LE.unpack(stream.read(UINT16LE.size))[0] for _ in range(num_anim)]
        print(anim_offsets)

        parsed_offs = set()

        glimb_mask = 0

        for off in anim_offsets:
            if off == 0:
                continue
            if off in parsed_offs:
                continue
            assert stream.tell() == off, (stream.tell(), off)
            parsed_offs |= {off}
            limb_mask = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
            # print('LIMB MASK', f'{limb_mask:016b}')
            glimb_mask |= limb_mask
            num_limbs = sum(int(x) for x in f'{limb_mask:016b}')
            for limb in range(num_limbs):
                # print('LIMB', limb)
                start = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
                # print('START', start)
                if start != 0xFFFF:
                    next_byte = stream.read(1)[0]
                    no_loop = next_byte & 0x80
                    end_offset = next_byte & 0x7F
                    # print('START', start, 'NOLOOP', no_loop, 'END', end_offset)

        # print('GLIMB MASK', f'{glimb_mask:016b}')
        assert glimb_mask != 0, glimb_mask
        assert stream.tell() == anim_cmds_offset, (stream.tell(), anim_cmds_offset)
        cmds = stream.read(limbs_offsets[0] - stream.tell())

        cpic_offs = []

        diff_limbs = sorted(set(limbs_offsets))
        if len(diff_limbs) > 1:
            for limb_idx, off in enumerate(diff_limbs[:-1]):
                assert stream.tell() == off, (stream.tell(), off)
                num_pics = (diff_limbs[limb_idx + 1] - off) // 2
                pic_offs = [UINT16LE.unpack(stream.read(UINT16LE.size))[0] for _ in range(num_pics)]
                cpic_offs += pic_offs
        else:
            assert stream.tell() == diff_limbs[0], (stream.tell(), diff_limbs[0])
            cpic_offs = [UINT16LE.unpack(stream.read(UINT16LE.size))[0]]
            while stream.tell() < cpic_offs[0]:
                cpic_offs.append(UINT16LE.unpack(stream.read(UINT16LE.size))[0])

        flag_skip = None
        for off in cpic_offs:
            if off == 0:
                continue
            if stream.tell() + 1 == off:
                pad = stream.read(1)
                # assert pad == b'\0', (stream.tell(), off, pad)
            assert stream.tell() == off, (stream.tell(), off)
            width = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
            height = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
            rel_x = SINT16LE.unpack(stream.read(SINT16LE.size))[0]
            rel_y = SINT16LE.unpack(stream.read(SINT16LE.size))[0]
            move_x = SINT16LE.unpack(stream.read(SINT16LE.size))[0]
            move_y = SINT16LE.unpack(stream.read(SINT16LE.size))[0]
            redir_limb, redir_pict = 0, 0
            if flags & 0x7E == 0x60:
                redir_limb, redir_pict = stream.read(2)
            print(width, height, rel_x, rel_y, move_x, move_y, redir_limb, redir_pict)


            if flag_skip is None:
                flag_skip = redir_pict

            if flag_skip == redir_pict:
                im = convert_to_pil_image(
                    bpp_cost.decode1(width, height, num_colors, stream),
                    size=(width, height)
                )
                im.putpalette(palette)
                yield off, im


        print(stream.tell(), size, header, palette, anim_cmds_offset, limbs_offsets, anim_offsets)
        rest = stream.read()
        assert rest in {b'', b'\0'}, (stream.tell() - len(rest), rest)


        # exit(1)


if __name__ == '__main__':
    import argparse
    import glob
    import os

    from nutcracker.utils.fileio import read_file

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

        os.makedirs(f'COST_out/{basename}', exist_ok=True)

        for t in root:

            for lflf in get_rooms(t):
                print(lflf, lflf.attribs["path"])
                _, palette, _, _ = read_room_settings(lflf)

                for cost in sputm.findall('COST', lflf):
                    print(cost, cost.attribs["path"], gameres.game.version)

                    for off, im in read_cost_resource(cost, palette, gameres.game.version):
                        im.save(f'COST_out/{basename}/{os.path.basename(lflf.attribs["path"])}_{os.path.basename(cost.attribs["path"])}_{off:08X}.png')

        # for idx, im in enumerate(read_akos_resource(resource)):
        #     im.save(f'COST_out/{os.path.basename(filename)}_aframe_{idx}.png')
