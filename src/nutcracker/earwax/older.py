import struct
import os
from pprint import pprint

from nutcracker.earwax.resource import dump_resources, read_dir, read_inner_uint16le, read_room_names
from nutcracker.sputm.index import compare_pid_off, read_uint8le
from nutcracker.utils.funcutils import flatten
from nutcracker.utils.fileio import read_file

from .preset import earwax

UINT16LE = struct.Struct('<H')

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
        'SO': compare_pid_off(dsou),
        'SC': compare_pid_off(dscr),
        'CO': compare_pid_off(dcos),
        'OC': read_inner_uint16le,
        'OI': read_inner_uint16le,
        'LS': read_uint8le,
    }

def read_config(filename, chiper_key=0x00):
    index = read_file(filename, key=chiper_key)

    basename = os.path.basename(filename)
    print(basename)

    if basename != '00.LFL':
        raise ValueError(basename)

    root = earwax.map_chunks(index)
    rnam, idgens = read_index(root)
    return index, rnam, idgens

def open_game_resource(filename: str, chiper_key=0x00):
    index, rnam, idgens = read_config(filename, chiper_key=chiper_key)

    droo = idgens['LF']

    room_pattern = '{room:02d}.LFL'

    print(droo)

    for room_id in droo:
        if not 0 < room_id < 99:
            continue
        fname = room_pattern.format(room=room_id)
        fullname = os.path.join(os.path.dirname(filename), fname)
        if not os.path.exists(fullname):
            print(f'warning: {fname} does not exist')
            continue
        room_data = earwax.mktag('LF', read_file(fullname, key=chiper_key))

        def update_element_path(parent, chunk, offset):
            idgens['LF'] = lambda *_: room_id

            get_gid = idgens.get(chunk.tag)
            gid = get_gid and get_gid(
                room_id, chunk.data, offset
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

        room = list(earwax(schema=schema).map_chunks(room_data, extra=update_element_path))
        # pprint((fname, room))
        yield from room


if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:
        root = list(open_game_resource(filename))
        for t in root:
            earwax.render(t)
        dump_resources(root, os.path.basename(os.path.dirname(filename)))
