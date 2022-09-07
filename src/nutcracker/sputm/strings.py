#!/usr/bin/env python3

import io
from string import printable
from typing import Callable, Iterable, Iterator, Mapping, Optional, Tuple

from nutcracker.sputm.script.bytecode import (
    descumm,
    get_strings,
    global_script,
    local_script,
    local_script_v7,
    local_script_v8,
    to_bytes,
    update_strings,
    verb_script,
)
from nutcracker.sputm.script.opcodes import (
    OPCODES_he60,
    OPCODES_he70,
    OPCODES_he71,
    OPCODES_he72,
    OPCODES_he73,
    OPCODES_he80,
    OPCODES_he90,
    OPCODES_he100,
    OPCODES_v6,
    OPCODES_v8,
    OpTable,
)
from nutcracker.sputm.script.opcodes_v5 import OPCODES_v5

from .preset import sputm
from .resource import Game
from .types import Element


def get_all_scripts(
    root: Iterable[Element],
    opcodes: OpTable,
    script_map: Mapping[str, Callable[[bytes], Tuple[bytes, bytes]]],
) -> Iterator[bytes]:
    for elem in root:
        if elem.tag in {'OBNA', 'TEXT'}:
            msg, rest = elem.data.split(b'\x00', maxsplit=1)
            assert rest == b''
            if msg != b'':
                yield msg
        elif elem.tag in {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', 'TLKE', *script_map}:
            if elem.tag in script_map:
                # print('==================', elem.attribs['path'])
                _, script_data = script_map[elem.tag](elem.data)
                bytecode = descumm(script_data, opcodes)
                for msg in get_strings(bytecode):
                    yield msg.msg
            else:
                yield from get_all_scripts(elem.children, opcodes, script_map)


def parse_verb_meta(meta):
    with io.BytesIO(meta) as stream:
        while True:
            key = stream.read(1)
            if key in {b'\0'}:  # , b'\xFF'}:
                break
            entry = int.from_bytes(
                stream.read(2), byteorder='little', signed=False
            )
            yield key, entry - len(meta)
        assert stream.read() == b''


def compose_verb_meta(entries):
    meta = bytearray()
    ln = 3 * len(entries) + 1
    for key, entry in entries:
        meta += key + (entry + ln).to_bytes(2, byteorder='little', signed=False)
    meta += b'\0'
    return bytes(meta)


def update_element_strings(
    root: Iterable[Element],
    strings: Iterator[bytes],
    opcodes: OpTable,
    script_map: Mapping[str, Callable[[bytes], Tuple[bytes, bytes]]],
) -> Iterator[Element]:
    offset = 0
    strings = iter(strings)
    for elem in root:
        elem.attribs['offset'] = offset
        if elem.tag in {'OBNA', 'TEXT'} and elem.data != b'\x00':
            elem.data = next(strings) + b'\x00'
        elif elem.tag in {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', 'TLKE', *script_map}:
            if elem.tag in script_map:
                serial, script_data = script_map[elem.tag](elem.data)
                bc = descumm(script_data, opcodes)
                updated = update_strings(bc, strings)
                if elem.tag == 'VERB':
                    pref = list(parse_verb_meta(serial))
                    comp = compose_verb_meta(pref)
                    assert comp == serial, (comp, serial, pref)
                    entries = [(idx, bc[off - 8].offset + 8) for idx, off in pref]
                    serial = compose_verb_meta(entries)
                attribs = elem.attribs
                elem.data = serial + to_bytes(updated)
                elem.attribs = attribs
            else:
                elem.children = list(
                    update_element_strings(elem, strings, opcodes, script_map)
                )
                elem.data = sputm.write_chunks(
                    sputm.mktag(e.tag, e.data) for e in elem.children
                )
        offset += len(elem.data) + 8
        elem.attribs['size'] = len(elem.data)
        yield elem


def escape_message(
    msg: bytes, escape: Optional[bytes] = None, var_size: int = 2
) -> bytes:
    with io.BytesIO(msg) as stream:
        while True:
            c = stream.read(1)
            if c in {b'', b'\0'}:
                break
            assert c is not None
            if c == escape:
                t = stream.read(1)
                c += t
                if ord(t) not in {1, 2, 3, 8}:
                    c += stream.read(var_size)
                c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c not in (printable.encode() + bytes(range(ord('\xE0'), ord('\xFA') + 1))):
                c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c == b'\\':
                c = b'\\\\'
            yield c


def encode_seq(seq: bytes) -> bytes:
    try:
        return bytes([int(b'0x' + seq[:2], 16)]) + seq[2:]
    except Exception as e:
        print(e)
        return seq


def unescape_message(msg: bytes) -> bytes:
    prefix, *rest = msg.split(b'\\x')
    return (prefix + b''.join(encode_seq(seq) for seq in rest)).replace(b'\\\\', b'\\')


def print_to_msg(line: str, encoding: str = 'windows-1255') -> bytes:
    return (
        unescape_message(
            line
            .replace('\r', '')
            .replace('\n', '').encode(encoding)
        )
        .replace(b'\\x0D', b'\r')
        .replace(b'\\x09', b'\t')
        .replace(b'\\x80', b'\x80')
        .replace(b'\\xd9', b'\xd9')
        .replace(b'\\x7f', b'\x7f')
    )


def msg_to_print(msg: bytes, encoding: str = 'windows-1255', var_size=2) -> str:
    assert b'\\x80' not in msg
    assert b'\\xd9' not in msg
    assert b'\\x0D' not in msg
    assert b'\\x09' not in msg
    escaped = b''.join(escape_message(msg, escape=b'\xff', var_size=var_size))
    assert b'\n' not in escaped
    line = (
        escaped
        .replace(b'\r', b'\\x0D')
        .replace(b'\t', b'\\x09')
        .replace(b'\x80', b'\\x80')
        .replace(b'\xd9', b'\\xd9')
        .replace(b'\x7f', b'\\x7f')
        .decode(encoding)
    )
    assert (unescaped := print_to_msg(line, encoding)) == msg, (unescaped, escaped, msg)
    return line


def get_optable(game: Game) -> OpTable:
    if game.version >= 8:
        return OPCODES_v8
    if game.version >= 7:
        return OPCODES_v6  # ???
    if game.he_version >= 100:
        return OPCODES_he100
    if game.he_version >= 90:
        return OPCODES_he90
    if game.he_version >= 80:
        return OPCODES_he80
    if game.he_version >= 73:
        return OPCODES_he73
    if game.he_version >= 72:
        return OPCODES_he72
    if game.he_version >= 71:
        return OPCODES_he71
    if game.he_version >= 70:
        return OPCODES_he70
    if game.he_version >= 60:
        return OPCODES_he60
    if game.version >= 6:
        return OPCODES_v6
    if game.version >= 5:
        return OPCODES_v5
    raise NotImplementedError('SCUMM < 5 is not implemented')


def get_script_map(game: Game) -> Mapping[str, Callable[[bytes], Tuple[bytes, bytes]]]:
    script_map = {
        'SCRP': global_script,
        'LSCR': local_script,
        'LSC2': local_script_v8,
        'VERB': verb_script,
        'ENCD': global_script,
        'EXCD': global_script,
    }
    if game.version >= 8:
        script_map['LSCR'] = local_script_v8
    elif game.version >= 7:
        script_map['LSCR'] = local_script_v7
    return script_map
