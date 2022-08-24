
from collections import defaultdict, deque
import os
from nutcracker.earwax.older import open_game_resource, read_config
from nutcracker.earwax.windex_v4 import OPCODES_v4, descumm_v4, dump_script_file, o4_actorOps, o4_mus_wd, o4_owner_wd, o4_room_wd, parse_verb_meta_v4, script_map
from nutcracker.sputm.script.opcodes_v5 import BYTE, WORD, get_params, get_result_pos, o5_getObjectOwner, o5_jumpRelative, o5_multiply, o5_print, o5_resourceRoutines, o5_startMusic, realize_v5, xop
from nutcracker.sputm.script.parser import ByteValue, RefOffset
from nutcracker.sputm.windex_v5 import ConditionalJump, UnconditionalJump, o5_mult_wd, o5_print_wd, o5_resource_wd, print_asts, print_locals, ops, value, l_vars
from nutcracker.utils.funcutils import flatten


def o3_resource_wd(op):
    if op.opcode == 0x4C:
        return 'wait-for-sentence'
    return o5_resource_wd(op)


def o3_room_wd(op):
    orig = tuple(op.args)
    if op.opcode in {0x33}:
        op.args = (op.args[-1], *op.args[:-1])
    try:
        return o4_room_wd(op)
    finally:
        op.args = orig

def o3_mult_wd(op):
    if op.opcode in {0x3B, 0xBB}:
        actor = op.args[1]
        return f'wait-for-actor {value(actor)}'
    return o5_mult_wd(op)


def o3_print_wd(op):
    return o5_print_wd(op, version=3)

def o3_owner_wd(op):
    if op.opcode in {0x30, 0xB0}:
        return f'set-box {value(op.args[0])} to {value(op.args[1])}'
    return o4_owner_wd(op)


def o3_mus_wd(op):
    if op.opcode in {0x02, 0x82}:
        return f'{value(op.args[0])} = music {value(op.args[1])}'
    return o4_mus_wd(op)


ops[0x02] = o3_mus_wd
ops[0x0C] = o3_resource_wd
ops[0x10] = o3_owner_wd
ops[0x13] = o3_room_wd
ops[0x1B] = o3_mult_wd
ops[0x14] = o3_print_wd


def o3_roomOps(opcode, stream):
    if opcode in {0x33, 0x73, 0xB3, 0xF3}:  # o5_roomOps
        yield from get_params(opcode, stream, 2 * WORD)
        sub = ByteValue(stream)
        yield sub
    else:
        yield from o4_actorOps(opcode, stream)


def o3_waitForSentence(opcode, stream):
    if opcode in {0x4C}:
        return
    yield from o5_resourceRoutines(opcode, stream)


def o3_waitForActor(opcode, stream):
    if opcode in {0x3B, 0xBB}:
        # TODO: Indy3 special case
        return
    yield from o5_multiply(opcode, stream)

def o3_print(opcode, stream):
    yield from o5_print(opcode, stream, version=3)

def o3_jumpRelative(opcode, stream):
    yield from o5_jumpRelative(opcode, stream, version=3)

def o3_getObjectOwner(opcode, stream):
    yield from o5_getObjectOwner(opcode, stream, version=3)


def o3_startMusic(opcode, stream):
    if opcode in {
        0x02,
        0x82,  # o5_startMusic
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
        return
    yield from o5_startMusic(opcode, stream)


OPCODES_v3 = realize_v5({
    **OPCODES_v4,
    0x02: xop(o3_startMusic),
    0x0C: xop(o3_waitForSentence),
    0x10: xop(o3_getObjectOwner),
    0x13: xop(o3_roomOps),
    0x14: xop(o3_print),
    0x18: xop(o3_jumpRelative),
    0x1B: xop(o3_waitForActor),
})



def decompile_script(elem):
    pref, script_data = script_map[elem.tag](elem.data)
    obj_id = None
    indent = '\t'
    if elem.tag == 'OC':
        pref = list(parse_verb_meta_v4(pref))
        obj_id = elem.attribs.get('gid') or 123
    respath_comment = f'; {elem.tag} {elem.attribs["path"]}'
    titles = {
        'LS': 'script',
        'SC': 'script',
        'EN': 'enter',
        'EX': 'exit',
    }
    if elem.tag == 'OC':
        yield ' '.join([f'object', f'{obj_id}', '{', respath_comment])
        obj_name, script_data = script_data.split(b'\0', maxsplit=1)
        obj_name_str = obj_name.decode('ascii', errors='ignore')
        yield ' '.join([f'\tname is', f'"{obj_name_str}"'])
    else:
        scr_id = int.from_bytes(pref, byteorder='little', signed=False) if pref else None
        gid = elem.attribs['gid']
        assert scr_id is None or scr_id == gid
        gid_str = '' if gid is None else f' {gid}'
        yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])

    print('============', elem)
    bytecode = descumm_v4(script_data, OPCODES_v3)
    # print_bytecode(bytecode)

    refs = [off.abs for stat in bytecode.values() for off in stat.args if isinstance(off, RefOffset)]
    curref = f'_[{0 + 8:08d}]'
    sts = deque()
    asts = defaultdict(deque)
    if elem.tag == 'OC':
        entries = {(off - len(obj_name) + 1): idx[0] for idx, off in pref}
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
            yield f'\tverb {entries[coff]} {{'
            indent = 2 * '\t'
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            curref = f'_[{coff:08d}]'
        if off in refs:
            curref = f'[{coff:08d}]'
        res = ops.get(stat.opcode & 0x1F, str)(stat) or stat
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
        _, rnam, _ = read_config(filename)
        root = open_game_resource(filename)
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
