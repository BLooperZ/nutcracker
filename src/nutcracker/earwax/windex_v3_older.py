
from collections import defaultdict, deque
import io
import os
from typing import IO, Callable, Iterable, Iterator, Tuple
from nutcracker.earwax.older_sizeonly import open_game_resource
from nutcracker.earwax.windex_v3 import OPCODES_v3, ops
from nutcracker.earwax.windex_v4 import get_room_scripts, get_global_scripts, global_script
from nutcracker.kernel.element import Element
from nutcracker.sputm.script.bytecode import descumm, verb_script
from nutcracker.sputm.script.parser import RefOffset
from nutcracker.sputm.windex_v5 import ConditionalJump, UnconditionalJump, print_asts, print_locals, l_vars, semantic_key
from nutcracker.utils.funcutils import flatten

def global_script_v3(data: bytes) -> Tuple[bytes, bytes]:
    return data[:4], data[4:]

VERB_HEADER_SIZE = 17

def verb_script_v3(data):
    header = data[:VERB_HEADER_SIZE]
    print(data)
    print(header)
    # exit(1)
    pref, data = verb_script(data[VERB_HEADER_SIZE:])
    return header + pref, data

def parse_verb_meta_v3(meta):
    with io.BytesIO(meta[VERB_HEADER_SIZE:]) as stream:
        while True:
            key = stream.read(1)
            if key in {b'\0'}:  # , b'\xFF'}:
                break
            entry = int.from_bytes(
                stream.read(2), byteorder='little', signed=False
            )
            yield key, entry - len(meta)
        assert stream.read() == b''


script_map = {
    'SC': global_script_v3,
    'OC': verb_script_v3,
    'LS': global_script,
    'EN': global_script,
    'EX': global_script,
}



def dump_script_file(
    room_no: str,
    room: Iterable[Element],
    decompile: Callable[[Element], Iterator[str]],
    outfile: IO[str],
):
    for elem in get_global_scripts(room):
        print('=================', elem)
        for line in decompile(elem):
            print(line, file=outfile)
        print('', file=outfile)  # end with new line
    print(f'room {room_no}', '{', file=outfile)
    for elem in get_room_scripts(room):
        print('', file=outfile)  # end with new line
        print('=================', elem)
        for line in decompile(elem):
            print(line if line.endswith(']:') or not line else f'\t{line}', file=outfile)
    print('}', file=outfile)
    print('', file=outfile)  # end with new line


def decompile_script(elem):
    pref, script_data = script_map[elem.tag](elem.data)
    obj_id = None
    indent = '\t'
    if elem.tag == 'OC':
        pref = list(parse_verb_meta_v3(pref))
        obj_id = elem.attribs.get('gid') or 123
    respath_comment = f'; {elem.tag} {elem.attribs["path"]}'
    titles = {
        'LS': 'script',
        'SC': 'script',
        'EN': 'enter',
        'EX': 'exit',
    }
    if elem.tag == 'OC':
        yield ' '.join([f'object', semantic_key(obj_id, sem='object'), '{', respath_comment])
        obj_name, script_data = script_data.split(b'\0', maxsplit=1)
        obj_name_str = obj_name.decode('ascii', errors='ignore')
        yield ' '.join([f'\tname is', f'"{obj_name_str}"'])
    else:
        gid = elem.attribs.get('gid')
        gid_str = '' if gid is None else f' {semantic_key(gid, "script")}'
        yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])

    print('============', elem)
    bytecode = descumm(script_data, OPCODES_v3)
    # print_bytecode(bytecode)

    refs = [off.abs for stat in bytecode.values() for off in stat.args if isinstance(off, RefOffset)]
    curref = f'_[{0 + 8:08d}]'
    sts = deque()
    asts = defaultdict(deque)
    if elem.tag == 'OC':
        entries = {(off - len(obj_name) + 7): idx[0] for idx, off in pref}
    res = None
    for off, stat in bytecode.items():
        coff = off + 8
        if elem.tag == 'OC' and coff in entries:
            if coff in entries:
                if coff > min(entries.keys()):
                    yield from print_locals(indent)
                l_vars.clear()
                yield from print_asts(indent, asts)  # transform_asts(indent, asts))
                curref = f'_[{coff:08d}]'
                asts = defaultdict(deque)
            if coff > min(entries.keys()):
                yield '\t}'
                l_vars.clear()
            yield ''  # new line
            yield f'\tverb {semantic_key(entries[coff], sem="verb")} {{'
            indent = 2 * '\t'
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            curref = f'_[{coff:08d}]'
        if off in refs:
            curref = f'[{coff:08d}]'
        res = ops.get(stat.name, str)(stat) or stat
        sts.append(res)
        asts[curref].append(res)
    yield from print_locals(indent)
    l_vars.clear()
    yield from print_asts(indent, asts)  # transform_asts(indent, asts))
    if elem.tag == 'OC' and entries:
        yield '\t}'
    yield '}'


if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:
        rnam = {}
        root = open_game_resource(filename, chiper_key=int(args.chiper_key, 16))
        print(rnam)

        script_dir = os.path.join('scripts', os.path.basename(os.path.dirname(filename)))
        os.makedirs(script_dir, exist_ok=True)

        for room in root:
            room_no = rnam.get(room.attribs['gid'], f"room_{room.attribs['gid']}")
            print(
                '==========================',
                room.attribs['path'],
                room_no,
            )
            fname = f"{script_dir}/{room.attribs['gid']:04d}_{room_no}.scu"

            with open(fname, 'w') as f:
                dump_script_file(room_no, room, decompile_script, f)
