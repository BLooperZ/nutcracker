
from collections import deque
import os
from nutcracker.earwax.older import open_game_resource, read_config
from nutcracker.earwax.windex_v4 import OPCODES_v4, dump_script_file, o4_actorOps, o4_pickupObject, o4_roomOps_wd, o4_saveLoadGame, parse_verb_meta_v4, script_map
from nutcracker.sputm.script.bytecode import BytecodeParseError, descumm_iter, get_argtype
from nutcracker.sputm.script.opcodes_v5 import BYTE, IMBYTE, PARAMS, RESULT, SUBMASK, WORD, flatop, mop, o5_jumpRelative, o5_multiply, o5_print, o5_resourceRoutines, realize_v5
from nutcracker.sputm.script.parser import RefOffset
from nutcracker.sputm.script.shared import BytecodeError, ScriptError, realize_refs
from nutcracker.sputm.windex_v5 import ConditionalJump, UnconditionalJump, fstat, print_asts, print_locals, ops, semantic_key, l_vars
from nutcracker.utils.funcutils import flatten


def o3_startMusic_wd(op):
    return fstat('{0} = music {1:music}', *op.args)


def o3_waitForSentence_wd(op):
    return fstat('wait-for-sentence', *op.args)


def o3_setBoxFlags_wd(op):
    return fstat('set-box {0} to {1:box-status}', *op.args)


def o3_roomOps_wd(op):
    orig = tuple(op.args)
    if op.opcode in {0x33}:
        *words, sub = op.args
        assert sub.args == (), sub
        sub.args = words
        op.args = (sub,)
    try:
        return o4_roomOps_wd(op, version=3)
    finally:
        sub.args = ()
        op.args = orig


def o3_waitForActor_wd(op):
    return fstat('wait-for-actor {0:object}', *op.args)


ops['o3_startMusic'] = o3_startMusic_wd
ops['o3_waitForSentence'] = o3_waitForSentence_wd
ops['o3_setBoxFlags'] = o3_setBoxFlags_wd
ops['o3_roomOps'] = o3_roomOps_wd
ops['o3_waitForActor'] = o3_waitForActor_wd


def o3_startMusic(opcode, stream):
    return flatop(
        ('o3_startMusic', {0x02, 0x82}, RESULT, PARAMS(BYTE)),
        fallback=o4_saveLoadGame,
    )(opcode, stream)


def o3_waitForSentence(opcode, stream):
    return flatop(
        ('o3_waitForSentence', {0x4C}),
        fallback=o5_resourceRoutines,
    )(opcode, stream)


def o3_getObjectOwner(opcode, stream):
    return flatop(
        ('o3_setBoxFlags', {0x30, 0xB0}, PARAMS(BYTE), IMBYTE),
        fallback=o4_pickupObject,
    )(opcode, stream)


def o3_roomOps(opcode, stream):
    return flatop(
        ('o3_roomOps', {0x33, 0x73, 0xB3, 0xF3}, PARAMS(2 * WORD), SUBMASK(0x1F, {
            0x01: mop('SO_ROOM_SCROLL'),
            0x02: mop('SO_ROOM_COLOR'),
            0x03: mop('SO_ROOM_SCREEN'),
            0x04: mop('SO_ROOM_PALETTE'),
            0x05: mop('SO_ROOM_SHAKE_ON'),
            0x06: mop('SO_ROOM_SHAKE_OFF'),
        })),
        fallback=o4_actorOps,
    )(opcode, stream)


def o3_print(opcode, stream):
    return o5_print(opcode, stream, version=3)


def o3_jumpRelative(opcode, stream):
    return o5_jumpRelative(opcode, stream, version=3)


def o3_waitForActor(opcode, stream):
    return flatop(
        ('o3_waitForActor', {0x3B, 0xBB}),
        fallback=o5_multiply,
    )(opcode, stream)


OPCODES_v3 = realize_v5({
    **OPCODES_v4,
    0x02: o3_startMusic,
    0x0C: o3_waitForSentence,
    0x10: o3_getObjectOwner,
    0x13: o3_roomOps,
    0x14: o3_print,
    0x18: o3_jumpRelative,
    0x1B: o3_waitForActor,
})


obj_names = {}


def make_block_context(elem, gid):
    respath_comment = f'; {elem.tag} {elem.attribs["path"]}'
    titles = {
        'LS': 'script',
        'SC': 'script',
        'EN': 'enter',
        'EX': 'exit',
        'OC': 'object',
    }
    gid_str = '' if gid is None else f' {semantic_key(gid, titles[elem.tag])}'
    yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])
    if elem.tag == 'OC':
        yield ' '.join(['\tname is', f'"{obj_names[gid]}"'])


def get_elem_info(elem):
    pref, script_data = script_map[elem.tag](elem.data)
    gid = elem.attribs['gid']
    entries = {}
    if elem.tag == 'OC':
        pref = list(parse_verb_meta_v4(pref))
        obj_name, script_data = script_data.split(b'\0', maxsplit=1)
        obj_names[gid] = obj_name.decode('ascii', errors='ignore')
        entries = {(off - len(obj_name) + 1): idx[0] for idx, off in pref}
    else:
        scr_id = int.from_bytes(pref, byteorder='little', signed=False) if pref else None
        assert scr_id is None or scr_id == gid
    return script_data, gid, entries


def decompile_script(elem):
    script_data, gid, entries = get_elem_info(elem)
    yield from make_block_context(elem, gid)
    indent = '\t'

    print('============', elem)
    bytecode = descumm_iter(script_data, OPCODES_v3, base_offset=8)

    hrefs = set()
    srefs = {0}
    asts = deque()
    res = None
    while True:
        try:
            off, stat = next(bytecode)
        except StopIteration:
            break
        except BytecodeParseError as exc:
            raise BytecodeError(
                exc,
                elem.attribs['path'],
                dict(realize_refs(srefs, hrefs, asts)),
            )
        hrefs.update(roff.abs for roff in get_argtype(stat.args, RefOffset))
        coff = off + 8
        if elem.tag == 'OC' and coff in entries:
            if coff > min(entries.keys()):
                yield from print_locals(indent)
            l_vars.clear()
            yield from print_asts(
                indent,
                dict(realize_refs(srefs, hrefs, asts)),
            )
            srefs = {off}
            hrefs = {ref for ref in hrefs if ref >= off}
            asts = deque()
            if coff > min(entries.keys()):
                yield '\t}'
                l_vars.clear()
            yield ''  # new line
            yield f'\tverb {semantic_key(entries[coff], sem="verb")} {{'
            indent = 2 * '\t'
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            srefs.add(off)
        try:
            res = ops.get(stat.name, str)(stat) or stat
        except Exception as exc:
            raise ScriptError(
                exc,
                elem.attribs['path'],
                dict(realize_refs(srefs, hrefs, asts)),
                stat,
                None,
            ) from exc
        asts.append((off, res))
    yield from print_locals(indent)
    l_vars.clear()
    yield from print_asts(
        indent,
        dict(realize_refs(srefs, hrefs, asts)),
    )
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
