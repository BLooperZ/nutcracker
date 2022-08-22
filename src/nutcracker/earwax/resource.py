import io
import os
import struct
from pprint import pprint
from typing import Iterator, Tuple

from nutcracker.chiper import xor
from nutcracker.kernel.buffer import Splicer, UnexpectedBufferSize
from nutcracker.kernel.chunk import Chunk
from nutcracker.kernel.index import create_element
from nutcracker.sputm.index import compare_pid_off
from nutcracker.sputm.tree import save_tree
from nutcracker.utils.funcutils import flatten, grouper
from nutcracker.utils.fileio import read_file

from .preset import earwax

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
            pprint(('RN', rnam))
        if t.tag == '0R':
            droo = dict(enumerate(read_dir(t.data)))
            pprint(('0R', droo))
        if t.tag == '0S':
            dscr = dict(enumerate(read_dir(t.data)))
            pprint(('0S', dscr))
        if t.tag == '0N':
            dsou = dict(enumerate(read_dir(t.data)))
            pprint(('0N', dsou))
        if t.tag == '0C':
            dcos = dict(enumerate(read_dir(t.data)))
            pprint(('0C', dcos))
        if t.tag == '0O':
            print('OBJ DIR not yet supported')
    return rnam, {
        'LF': droo,
        'SO': compare_pid_off(dsou, base=-2),
        'SC': compare_pid_off(dscr, base=-2),
        'CO': compare_pid_off(dcos, base=-2),
        'RO': compare_pid_off(dsou, base=-2),
    }


def read_config(filename, chiper_key=0x00):
    index = read_file(filename, key=chiper_key)

    root = earwax.map_chunks(index)
    rnam, idgens = read_index(root)
    return rnam, idgens


def open_game_resource(filename: str, chiper_key=0x00):
    rnam, idgens = read_config(filename)

    basename = os.path.basename(filename)
    room_pattern = '{room:02d}.LFL' if basename == '00.LFL' else '{room:03d}.LFL'
    disk_pattetn = 'DISK{disk:02d}.LEC'
    basedir = os.path.dirname(filename)

    disks = sorted(set(disk for room_id, (disk, _) in idgens['LF'].items()))

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
                if get_gid and not gid:
                    print('GID', chunk, parent, droo)

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


        def path_only(parent, chunk, offset):
            base = chunk.tag

            dirname = parent.attribs['path'] if parent else ''
            path = os.path.join(dirname, base)

            res = {'path': path}
            return res


        disk_file = os.path.join(basedir, disk_pattetn.format(disk=disk_id))
        res = read_file(disk_file, key=0x69)
        schema = earwax.generate_schema(res)
        root = list(
            earwax(schema=schema).map_chunks(res, extra=update_element_path)
        )
        # for t in root:
        #     earwax.render(t)

        for t in earwax.find('LE', root):
            # print(disk_file, t)
            if t.tag != 'LF':
                assert t.tag == 'FO', t
                continue
            room_id = UINT16LE.unpack(t.data[:2])[0]
            assert t.attribs['gid'] == room_id
            schema = {
                'LF': {'RO', 'SC', 'SO', 'CO'},
                'RO': {'SP', 'HD', 'EX', 'CC', 'OC', 'OI', 'NL', 'BM', 'SL', 'LS', 'BX', 'LC', 'PA', 'SA', 'EN'},
                'HD': set(),
                'CC': set(),
                'SP': set(),
                'BX': set(),
                'PA': set(),
                'SA': set(),
                'BM': set(),
                'OI': set(),
                'NL': set(),
                'SL': set(),
                'OC': set(),
                'EX': set(),
                'EN': set(),
                'LC': set(),
                'LS': set(),
                'SO': set(),
                'SC': set(),
                'CO': set(),
            }
            # schema = earwax.generate_schema(t.data[2:])
            # print(schema)
            # print('ROOM', room_id)
            c = 2

            room_chunk = next(earwax(schema=schema, max_depth=0).map_chunks(t.data, offset=c, parent=t, extra=path_only), None)
            assert room_chunk.tag == 'RO', room_chunk
            t.children.append(room_chunk)
            c += len(bytes(room_chunk.chunk))
            # print('ROOOM')
            # earwax.render(room_chunk)
            # print('END ROOOM')
            r = earwax(schema=dict(schema, RO=set()), max_depth=0).map_chunks(t.data, offset=c, parent=t, extra=update_element_path)
            try:
                for a in r:
                    # earwax.render(a)
                    assert t.data[c+4:c+6] == a.tag.encode(), (t.data[c+4:c+6], a.tag.encode())
                    c += len(bytes(a.chunk))
                    t.children.append(a)
                    # print(a)
            except UnexpectedBufferSize as exc:
                print(f'warning: {exc}')
            rawd = t.data[c:]
            if rawd != b'':
                t.children.append(
                    create_element(
                        c,
                        Chunk('__', rawd, Splicer(0, len(rawd))),
                        path=os.path.join(t.attribs['path'], 'REST')
                    )
                )
                # print(t.children)
                # print(len(rawd))
                # for chnk in grouper(rawd, 100):
                #     print('RAWD', bytes(x for x in chnk if x is not None))
        yield from root

def dump_resources(
    root, basename,
):
    os.makedirs(basename, exist_ok=True)
    with open(os.path.join(basename, 'rpdump.xml'), 'w') as f:
        for disk in root:
            earwax.render(disk, stream=f)
            save_tree(earwax, disk, basedir=basename)


if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:
        root = open_game_resource(filename, int(args.chiper_key, 16))
        # for t in root:
        #     earwax.render(t)
        dump_resources(root, 'monkey-ega')
