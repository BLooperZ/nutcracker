#!/usr/bin/env python3

import io
import os
from typing import Iterable, Optional
from string import printable

from nutcracker.utils.fileio import read_file
from nutcracker.sputm.types import Element
from nutcracker.sputm.build import rebuild_resources
from nutcracker.sputm.script.bytecode import (
    descumm,
    get_strings,
    update_strings,
    script_map,
    to_bytes,
)
from nutcracker.sputm.script.opcodes import (
    OPCODES_he80,
    OPCODES_v6,
    OPCODES_v8,
    OpTable,
)


def get_all_scripts(root: Iterable[Element], opcodes: OpTable):
    for elem in root:
        if elem.tag == 'OBNA':
            msg = b''.join(escape_message(elem.data))
            if msg != b'':
                yield msg
        elif elem.tag in {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}:
            if elem.tag in script_map:
                # print('==================', elem.attribs['path'])
                _, script_data = script_map[elem.tag](elem.data)
                bytecode = descumm(script_data, opcodes)
                for msg in get_strings(bytecode):
                    yield msg.msg
            else:
                yield from get_all_scripts(elem.children, opcodes)


def update_element_strings(root, strings, opcodes):
    offset = 0
    for elem in root:
        elem.attribs['offset'] = offset
        if elem.tag == 'OBNA' and elem.data != b'\x00':
            elem.data = next(strings) + b'\x00'
        elif elem.tag in {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}:
            if elem.tag in script_map:
                serial, script_data = script_map[elem.tag](elem.data)
                bc = descumm(script_data, opcodes)
                updated = update_strings(bc, strings)
                attribs = elem.attribs
                elem.data = serial + to_bytes(updated)
                elem.attribs = attribs
            else:
                elem.children = list(update_element_strings(elem, strings, opcodes))
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
            elif c not in (printable.encode() + bytes(range(ord('\xE0'), ord('\xFA')))):
                c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c == b'\\':
                c = b'\\\\'
            yield c


def encode_seq(seq: bytes):
    try:
        return bytes([int(b'0x' + seq[:2], 16)]) + seq[2:]
    except Exception as e:
        print(e)
        return seq


def unescape_message(msg: bytes):
    prefix, *rest = msg.split(b'\\x')
    return (prefix + b''.join(encode_seq(seq) for seq in rest)).replace(b'\\\\', b'\\')


def print_to_msg(line: str, encoding: str = 'windows-1255') -> bytes:
    return (
        unescape_message(line.replace('\r', '').replace('\n', '').encode(encoding))
        .replace(b'\\r', b'\r')
        .replace(b'\\/t', b'\t')
        .replace(b'\\x80', b'\x80')
        .replace(b'\\xd9', b'\xd9')
        .replace(b'\\x7f', b'\x7f')
    )


def msg_to_print(msg: bytes, encoding: str = 'windows-1255') -> str:
    assert b'\\x80' not in msg
    assert b'\\xd9' not in msg
    assert b'\\r' not in msg
    assert b'\\/t' not in msg
    escaped = b''.join(escape_message(msg, escape=b'\xff', var_size=2))
    assert b'\n' not in escaped
    line = (
        escaped.replace(b'\r', b'\\r')
        .replace(b'\t', b'\\/t')
        .replace(b'\x80', b'\\x80')
        .replace(b'\xd9', b'\\xd9')
        .replace(b'\x7f', b'\\x7f')
        .decode(encoding)
    )
    assert (unescaped := print_to_msg(line, encoding)) == msg, (unescaped, escaped, msg)
    return line


if __name__ == '__main__':
    import argparse
    import pprint

    from .preset import sputm
    from .resource import detect_resource
    from .index2 import read_game_resources

    parser = argparse.ArgumentParser(description='read smush file')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--extract', '-e', action='store_true')
    group.add_argument('--inject', '-i', action='store_true')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument(
        '--textfile', '-t', help='save strings to file', default='strings.txt'
    )
    args = parser.parse_args()

    game = detect_resource(args.filename)
    index_file, *disks = game.resources

    index = read_file(index_file, key=game.chiper_key)

    s = sputm.generate_schema(index)
    pprint.pprint(s)

    index_root = sputm(schema=s).map_chunks(index)
    index_root = list(index_root)

    _, idgens = game.read_index(index_root)

    root = read_game_resources(game, idgens, disks, max_depth=5)

    script_ops = OPCODES_v6

    if args.extract:
        with open(args.textfile, 'w') as f:
            for msg in get_all_scripts(root, script_ops):
                print(msg_to_print(msg), file=f)

    elif args.inject:
        with open(args.textfile, 'r') as f:
            fixed_lines = (print_to_msg(line) for line in f)
            updated_resource = list(
                update_element_strings(root, fixed_lines, script_ops)
            )

        basename = os.path.basename(args.filename)
        rebuild_resources(game, basename, disks, index_root, updated_resource)
