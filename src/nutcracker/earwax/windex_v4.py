
from collections import deque
import io
import os
from typing import IO, Callable, Iterable, Iterator, Tuple
from nutcracker.earwax.resource import open_game_resource, read_config
from nutcracker.kernel.element import Element
from nutcracker.sputm.script.bytecode import BytecodeParseError, descumm_iter, get_argtype, local_script, verb_script
from nutcracker.sputm.script.opcodes_v5 import BYTE, OFFSET, PARAMS, SUBMASK, WORD, RESULT, OPCODES_v5, flatop, mop, o5_actorOps, o5_getObjectOwner, o5_isActorInBox, o5_setState, o5_startMusic, o5_startSound, realize_v5
from nutcracker.sputm.script.parser import RefOffset
from nutcracker.sputm.script.shared import BytecodeError, ScriptError, realize_refs
from nutcracker.sputm.windex_v5 import ConditionalJump, UnconditionalJump, builder, fstat, o5_actorOps_wd, o5_roomOps_wd, print_asts, print_locals, ops, semantic_key, l_vars
from nutcracker.utils.funcutils import flatten

def global_script(data: bytes) -> Tuple[bytes, bytes]:
    return b'', data


VERB_HEADER_SIZE = 13

def verb_script_v4(data):
    header = data[:VERB_HEADER_SIZE]
    print(data)
    print(header)
    # exit(1)
    pref, data = verb_script(data[VERB_HEADER_SIZE:])
    return header + pref, data

def parse_verb_meta_v4(meta):
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
    'SC': global_script,
    'OC': verb_script_v4,
    'LS': local_script,
    'EN': global_script,
    'EX': global_script,
}


def o4_saveLoadGame_wd(op):
    return fstat('$ game saveload {0} {1}', *op.args)


def o4_drawObject_wd(op):
    return fstat('draw-object {0:object} at {1},{2}', *op.args)


def o4_saveLoadVars_wd(op):
    return builder({'SAVE-VARS': 'save-variables', 'LOAD-VARS': 'load-variables'})(op.args)


def o4_ifState_wd(op):
    return ConditionalJump(
        fstat('state-of {0:object} is {1:state}', *op.args[:2]),
        op.args[2]
    )


def o4_pickupObject_wd(op):
    return fstat('pick-up-object {0:object}', *op.args)


def o4_roomOps_wd(op, version=4):
    return o5_roomOps_wd(op, version=version)


def o4_actorOps_wd(op):
    return o5_actorOps_wd(op, version=4)


def o4_oldRoomEffect_wd(op):
    return builder({'SO_ROOM_FADE' : 'fades {0:fade}'})(op.args)


ops['o4_saveLoadGame'] = o4_saveLoadGame_wd
ops['o4_drawObject'] = o4_drawObject_wd
ops['o4_saveLoadVars'] = o4_saveLoadVars_wd
ops['o4_ifState'] = o4_ifState_wd
ops['o4_pickupObject'] = o4_pickupObject_wd
ops['o5_actorOps'] = o4_actorOps_wd
ops['o5_roomOps'] = o4_roomOps_wd
ops['o4_oldRoomEffect'] = o4_oldRoomEffect_wd


def o4_saveLoadGame(opcode, stream):
    return flatop(
        ('o4_saveLoadGame', {0x22, 0xA2}, RESULT, PARAMS(BYTE)),
        fallback=o5_startMusic,
    )(opcode, stream)


def o4_drawObject(opcode, stream):
    return mop('o4_drawObject', PARAMS(3 * WORD))(opcode, stream)


def o4_saveLoadVars(opcode, stream):
    return flatop(
        ('o4_saveLoadVars', {0xA7}, SUBMASK(0x1F, {
                0x01: mop('SAVE-VARS'),
                0x02: mop('LOAD-VARS'),
            }
        )),
        fallback=o5_setState,
    )(opcode, stream)


def o4_ifState(opcode, stream):
    return mop('o4_ifState', PARAMS(WORD + BYTE), OFFSET)(opcode, stream)


def o4_pickupObject(opcode, stream):
    return flatop(
        ('o4_pickupObject', {0x50, 0xD0}, PARAMS(WORD)),
        fallback=o5_getObjectOwner,
    )(opcode, stream)


def o4_actorOps(opcode, stream):
    return o5_actorOps(opcode, stream, version=4)


def o4_oldRoomEffect(opcode, stream):
    return flatop(
        ('o4_oldRoomEffect', {0x5C, 0xDC}, SUBMASK(0x1F, {
            0x03: mop('SO_ROOM_FADE', PARAMS(WORD)),
        })),
        fallback=o5_startSound,
    )(opcode, stream)


def o4_isActorInBox(opcode, stream):
    return flatop(
        ('o5_isActorInBox', {0x1F, 0x5F, 0x9F, 0xDF}, PARAMS(2 * BYTE), OFFSET),
        fallback=o5_isActorInBox,
    )(opcode, stream)


OPCODES_v4 = realize_v5({
    **OPCODES_v5,
    0x02: o4_saveLoadGame,
    0x05: o4_drawObject,
    0x07: o4_saveLoadVars,
    0x0F: o4_ifState,
    0x10: o4_pickupObject,
    0x13: o4_actorOps,
    0x1C: o4_oldRoomEffect,
    0x1F: o4_isActorInBox,
})


def get_global_scripts(root: Iterable[Element]) -> Iterator[Element]:
    for elem in root:
        if elem.tag in {'LE', 'LF', 'OC', *script_map}:
            if elem.tag in {*script_map}:
                yield elem
            else:
                yield from get_global_scripts(elem.children)


def get_room_scripts(root: Iterable[Element]) -> Iterator[Element]:
    for elem in root:
        if elem.tag in {'LE', 'LF', 'RO', 'OC', *script_map}:
            if elem.tag == 'SC':
                assert 'RO' not in elem.attribs['path'], elem
                continue
            elif elem.tag in {*script_map, 'OC'}:
                yield elem
            elif elem.tag != 'RO' or not elem.attribs.get('gid'):
                yield from get_room_scripts(elem.children)


def dump_script_file(
    room_no: str,
    room: Iterable[Element],
    decompile: Callable[[Element], Iterator[str]],
    outfile: IO[str],
):
    for elem in get_global_scripts(room):
        for line in decompile(elem):
            print(line, file=outfile)
        print('', file=outfile)  # end with new line
    print(f'room {room_no}', '{', file=outfile)
    for elem in get_room_scripts(room):
        print('', file=outfile)  # end with new line
        for line in decompile(elem):
            print(line if line.endswith(']:') or not line else f'\t{line}', file=outfile)
    print('}', file=outfile)
    print('', file=outfile)  # end with new line


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
    bytecode = descumm_iter(script_data, OPCODES_v4, base_offset=8)

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

    from .preset import earwax

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:
        rnam, _ = read_config(filename)
        root = open_game_resource(filename)
        print(rnam)

        script_dir = os.path.join('scripts', os.path.basename(os.path.dirname(filename)))
        os.makedirs(script_dir, exist_ok=True)

        for disk in root:
            for room in earwax.findall('LF', disk):
                room_no = rnam.get(room.attribs['gid'], f"room_{room.attribs['gid']}")
                print(
                    '==========================',
                    room.attribs['path'],
                    room_no,
                )
                fname = f"{script_dir}/{room.attribs['gid']:04d}_{room_no}.scu"

                with open(fname, 'w') as f:
                    dump_script_file(room_no, room, decompile_script, f)
