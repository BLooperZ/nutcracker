import io
import os
import struct
from collections import defaultdict
from nutcracker.earwax.older_room import read_room

from nutcracker.utils.fileio import read_file
from nutcracker.utils.funcutils import flatten
from nutcracker.kernel.index import create_element

from .preset import earwax


UINT16LE = struct.Struct('<H')
UINT32LE = struct.Struct('<I')


def read_dir(stream):
    num = ord(stream.read(1))
    rnums = list(stream.read(num))
    offs = [UINT16LE.unpack(stream.read(UINT16LE.size))[0] for _ in range(num)]
    return enumerate(zip(rnums, offs))

def read_block(stream):
    return stream.read(UINT16LE.unpack(stream.read(UINT16LE.size))[0] - UINT16LE.size)


def write_block(data):
    return UINT16LE.pack(len(data) + UINT16LE.size) + data


def dump_resources(
    root, basename,
):
    os.makedirs(basename, exist_ok=True)
    with open(os.path.join(basename, 'rpdump.xml'), 'w') as f:
        for disk in root:
            earwax.render(disk, stream=f)
            save_tree_data_only(earwax, disk, basedir=basename)


def save_tree_data_only(cfg, element, basedir='.'):
    if not element:
        return
    path = os.path.join(basedir, element.attribs['path'])
    if element.children:
        os.makedirs(path, exist_ok=True)
        for c in element.children:
            save_tree_data_only(cfg, c, basedir=basedir)
    else:
        with open(path, 'wb') as f:
            # f.write(cfg.mktag(element.tag, element.data))
            f.write(element.data)


def mkblock(data):
    return UINT16LE.pack(len(data) + UINT16LE.size) + data


def open_game_resource(filename: str, chiper_key=0x00):

    index = read_file(filename, key=chiper_key)

    basename = os.path.basename(filename)
    print(basename)

    if basename != '00.LFL':
        raise ValueError(basename)

    # print(index)

    with io.BytesIO(index) as stream:
        magic = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
        if magic != 0x100:
            raise ValueError(f'bad magic: {magic}')

        num_objects = UINT16LE.unpack(stream.read(UINT16LE.size))[0]
        objects = [UINT32LE.unpack(stream.read(UINT32LE.size))[0] for _ in range(num_objects)]

        rooms = dict(read_dir(stream))
        costumes = dict(read_dir(stream))
        scripts = dict(read_dir(stream))
        sounds = dict(read_dir(stream))

        print(rooms)
        print(costumes)
        print(scripts)
        print(sounds)

        ind = defaultdict(list)
        for cost, (rm, off) in costumes.items():
            ind[rm].append((off, cost, 'CO'))
        for scr, (rm, off) in scripts.items():
            ind[rm].append((off, scr, 'SC'))
        for sou, (rm, off) in sounds.items():
            ind[rm].append((off, sou, 'SO'))

        for rm_id, reses in ind.items():
            print(rm_id, reses)

    room_pattern = '{room:02d}.LFL'
    for room_id, rm_info in rooms.items():
        if not 0 < room_id < 99:
            continue
        fname = room_pattern.format(room=room_id)

        fullname = os.path.join(os.path.dirname(filename), fname)
        if not os.path.exists(fullname):
            print(f'warning: {fname} does not exist, {rm_info}')
            continue
        room_data = read_file(fullname, key=chiper_key)

        print(fname, rm_info)
        room = create_element(
            0,
            earwax.untag(earwax.mktag('LF', room_data)),
            gid=room_id,
            path=f'LFv3_{room_id:04d}'
        )
        with io.BytesIO(room_data) as stream:
            rm_block = read_block(stream)
            rm_elem = create_element(
                0,
                earwax.untag(earwax.mktag('RO', mkblock(rm_block))),
                path=os.path.join(room.attribs['path'], f'ROv3'),
            )
            room.children.append(rm_elem)

            rm_elem = read_room(rm_elem)

            while stream.tell() < len(room_data):
                offset = stream.tell()
                idx = next(((off, bid, tag) for off, bid, tag in ind[room_id] if off == offset), None)
                block = read_block(stream)

                if not idx:
                    idx = (offset, None, 'UN')
                # print(offset, idx, block[:16], ind[room_id])
                assert offset == idx[0], (offset, idx[0])
                room.children.append(
                    create_element(
                        offset,
                        earwax.untag(earwax.mktag(idx[2], mkblock(block))),
                        path=os.path.join(room.attribs['path'], f'{idx[2]}v3_{idx[1]:04d}' if idx[1] else f'UN_{offset:04x}'),
                        **({'gid':idx[1]} if idx[1] else {}),
                    ),
                )

        yield room


if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:
        root = open_game_resource(filename, chiper_key=int(args.chiper_key, 16))
        dump_resources(root, os.path.basename(os.path.dirname(filename)))
