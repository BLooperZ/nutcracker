import io
import struct
from typing import Iterator, Tuple

from nutcracker.chiper import xor
from nutcracker.sputm.index import compare_pid_off
from nutcracker.utils.funcutils import flatten

UINT16LE = struct.Struct('<H')


def read_room_names(data: bytes) -> Iterator[Tuple[int, str]]:
    with io.BytesIO(data) as stream:
        while True:
            (num,) = stream.read(1)
            if not num:
                break
            name = xor.read(stream, 9, key=0xFF).rstrip(b'\00').decode()
            yield num, name


def read_dir(data: bytes) -> Iterator[Tuple[int, int]]:
    with io.BytesIO(data) as stream:
        num = int.from_bytes(stream.read(2), byteorder='little', signed=False)
        for _ in range(num):
            (room_num,) = stream.read(1)
            offset = int.from_bytes(stream.read(4), byteorder='little', signed=False)
            yield room_num, offset


def read_offs(data: bytes) -> Iterator[Tuple[int, int]]:
    with io.BytesIO(data) as stream:
        (num,) = stream.read(1)
        for _ in range(num):
            (room_num,) = stream.read(1)
            offset = int.from_bytes(stream.read(4), byteorder='little', signed=False)
            yield room_num, offset


def read_index(root):
    rnam = {}
    droo = {}
    for t in root:
        if t.tag == 'RN':
            rnam = dict(read_room_names(t.data))
            pprint(rnam)
        if t.tag == '0R':
            droo = dict(enumerate(read_dir(t.data)))
            pprint(droo)
        if t.tag == '0S':
            dscr = dict(enumerate(read_dir(t.data)))
            pprint(dscr)
        if t.tag == '0N':
            dsou = dict(enumerate(read_dir(t.data)))
            pprint(dsou)
        if t.tag == '0C':
            dcos = dict(enumerate(read_dir(t.data)))
            pprint(dcos)
        if t.tag == '0O':
            print('OBJ DIR not yet supported')
    return rnam, droo, {}


if __name__ == '__main__':
    import argparse
    import glob
    import os
    from pprint import pprint

    from nutcracker.utils.fileio import read_file

    from .preset import earwax

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:

        index = read_file(filename, key=int(args.chiper_key, 16))

        basename = os.path.basename(filename)
        room_pattern = '{room:02d}.LFL' if basename == '00.LFL' else '{room:03d}.LFL'
        disk_pattetn = 'DISK{disk:02d}.LEC'
        basedir = os.path.dirname(filename)

        root = earwax.map_chunks(index)
        rnam, droo, idgens = read_index(root)
        disks = sorted(set(disk for room_id, (disk, _) in droo.items()))

        for disk_id in disks:
            if disk_id == 0:
                continue

            def update_element_path(parent, chunk, offset):

                if chunk.tag == 'FO':

                    offs = dict(read_offs(chunk.data))
                    droo = {k: (disk_id, v) for k, v in offs.items()}
                    idgens['LF'] = compare_pid_off(droo, 6)

                get_gid = idgens.get(chunk.tag)
                if not parent:
                    gid = disk_id
                else:
                    gid = get_gid and get_gid(
                        parent and parent.attribs['gid'], chunk.data, offset
                    )

                base = chunk.tag + (
                    f'_{gid:04d}'
                    if gid is not None
                    else ''
                    if not get_gid
                    else f'_o_{offset:04X}'
                )

                dirname = parent.attribs['path'] if parent else ''
                path = os.path.join(dirname, base)

                res = {'path': path, 'gid': gid}
                return res

            disk_file = os.path.join(basedir, disk_pattetn.format(disk=disk_id))
            res = read_file(disk_file, key=0x69)
            schema = earwax.generate_schema(res)
            root = list(
                earwax(schema=schema).map_chunks(res, extra=update_element_path)
            )
            for t in root:
                earwax.render(t)

            for t in earwax.find('LE', root):
                if t.tag == 'LF':
                    room_id = UINT16LE.unpack(t.data[:2])[0]
                    assert t.attribs['gid'] == room_id
                    schema = earwax.generate_schema(t.data[2:])
                    schema['SA'] = set()
                    r = list(earwax(schema=schema).map_chunks(t.data[2:]))
                    for a in r:
                        earwax.render(a)

        for room_id, (disk, offset) in droo.items():
            if room_id in {0, 99}:
                continue
            if (disk, offset) == (0, 0):
                room_file = os.path.join(basedir, room_pattern.format(room=room_id))
                if os.path.exists(room_file):
                    res = read_file(room_file, key=int(args.chiper_key, 16))

                    print(room_file)
                    schema = earwax.generate_schema(res)

                    pprint(schema)
                    # exit(1)

                    root = list(earwax(schema=schema).map_chunks(res))
                    for t in root:
                        earwax.render(t)

                    # exit(1)
