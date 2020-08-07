#!/usr/bin/env python3

import io
import glob
import itertools
import os
from typing import Iterable

from nutcracker.chiper import xor
from nutcracker.sputm.index import read_index_v5tov7, read_index_he, read_file
from nutcracker.sputm.build import write_file, make_index_from_resource
from nutcracker.sputm.scummtr import descumm, get_strings, update_strings, OPCODES_he80, OPCODES_v6, to_bytes

def global_script(data):
    return b'', data

def local_script(data):
    return bytes([data[0]]), data[1:]

def verb_script(data):
    serial = b''
    with io.BytesIO(data) as stream:
        while True:
            key = stream.read(1)
            serial += key
            if key in {b'\0', b'\xFF'}:
                break
            serial += stream.read(2)
        return serial, stream.read()

script_map = {
    'SCRP': global_script,
    'LSCR': local_script,
    'VERB': verb_script
}

if __name__ == '__main__':
    import argparse
    import pprint
    from typing import Dict

    from .preset import sputm
    from .types import Chunk, Element

    parser = argparse.ArgumentParser(description='read smush file')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--extract', '-e', action='store_true')
    group.add_argument('--inject', '-i', action='store_true')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--textfile', '-t', help='save strings to file', default='strings.txt')
    args = parser.parse_args()

    # Configuration for HE games
    index_suffix = '.HE0'
    resource_suffix = '.HE1'
    # resource_suffix = '.(a)'
    read_index = read_index_he
    chiper_key = 0x69
    max_depth = 5
    script_ops = OPCODES_he80

    # # Configuration for SCUMM v5-v6 games
    # index_suffix = '.000'
    # resource_suffix = '.001'
    # read_index = read_index_v5tov7
    # chiper_key = 0x69
    # max_depth = 4
    # script_ops = OPCODES_v6

    # # Configuration for SCUMM v7 games
    # index_suffix = '.LA0'
    # resource_suffix = '.LA1'
    # read_index = read_index_v5tov7
    # chiper_key = 0x00
    # max_depth = 3

    index = read_file(args.filename + index_suffix, key=chiper_key)

    s = sputm.generate_schema(index)

    index_root = list(sputm(schema=s).map_chunks(index))

    idgens = read_index(index_root)

    resource = read_file(args.filename + resource_suffix, key=chiper_key)

    # # commented out, use pre-calculated index instead, as calculating is time-consuming
    # s = sputm.generate_schema(resource)
    # pprint.pprint(s)
    # root = sputm.map_chunks(resource, idgen=idgens, schema=s)

    def update_element_path(parent, chunk, offset):
        get_gid = idgens.get(chunk.tag)
        gid = get_gid and get_gid(parent and parent.attribs['gid'], chunk.data, offset)

        base = chunk.tag + (f'_{gid:04d}' if gid is not None else '' if not get_gid else f'_o_{offset:04X}')

        dirname = parent.attribs['path'] if parent else ''
        path = os.path.join(dirname, base)
        res = {'path': path, 'gid': gid}

        return res

    root = sputm(max_depth=max_depth).map_chunks(resource, extra=update_element_path)

    def get_all_scripts(root, opcodes):
        for lecf in root:
            for lflf in sputm.findall('LFLF', lecf):
                for elem in lflf.children:
                    if elem.tag == 'RMDA':
                        for robj in elem.children:
                            if robj.tag == 'LSCR':
                                _, script_data = script_map[robj.tag](robj.data)
                                bytecode = descumm(script_data, opcodes)
                                for msg in get_strings(bytecode):
                                    yield msg.msg
                            elif robj.tag == 'OBCD':
                                for verb in sputm.findall('VERB', robj):
                                    _, script_data = script_map[verb.tag](verb.data)
                                    bytecode = descumm(script_data, opcodes)
                                    for msg in get_strings(bytecode):
                                        yield msg.msg
                    if elem.tag == 'SCRP':
                        # print(elem.attribs['path'])
                        _, script_data = script_map[elem.tag](elem.data)
                        bytecode = descumm(script_data, opcodes)
                        for msg in get_strings(bytecode):
                            yield msg.msg

    def update_element_strings(root, strings, opcodes):
        offset = 0
        for elem in root:
            elem.attribs['offset'] = offset
            if elem.tag in {'LECF', 'LFLF', 'RMDA', 'OBCD', *script_map}:
                if elem.tag in script_map:
                    serial, script_data = script_map[elem.tag](elem.data)
                    bc = descumm(script_data, opcodes)
                    updated = update_strings(bc, strings)
                    attribs = elem.attribs
                    elem.data = serial + to_bytes(updated)
                    elem.attribs = attribs
                else:
                    elem.children = list(update_element_strings(elem, strings, opcodes))
                    elem.data = sputm.write_chunks(sputm.mktag(e.tag, e.data) for e in elem.children)
            offset += len(elem.data) + 8
            elem.attribs['size'] = len(elem.data)
            yield elem

    if args.extract:
        with open(args.textfile, 'w') as f:
            for msg in get_all_scripts(root, script_ops):
                assert b'\n' not in msg
                assert b'\\x80' not in msg
                assert b'\\xd9' not in msg
                assert b'\\r' not in msg
                assert b'\\/t' not in msg
                line = msg \
                    .replace(b'\r', b'\\r') \
                    .replace(b'\t', b'\\/t') \
                    .replace(b'\x80', b'\\x80') \
                    .replace(b'\xd9', b'\\xd9') \
                    .replace(b'\x7f', b'\\x7f') \
                    .decode('windows-1255')
                f.write(line + '\n')

    elif args.inject:
        with open(args.textfile, 'r') as f:
            fixed_lines = (
                line.replace('\r', '').replace('\n', '').encode('windows-1255')
                    .replace(b'\\r', b'\r')
                    .replace(b'\\/t', b'\t')
                    .replace(b'\\x80', b'\x80')
                    .replace(b'\\xd9', b'\xd9')
                    .replace(b'\\x7f', b'\x7f')
                for line in f
            )
            updated_resource = list(update_element_strings(root, fixed_lines, script_ops))

        basename = os.path.basename(args.filename)
        write_file(
            f'{basename}{resource_suffix}',
            sputm.write_chunks(sputm.mktag(e.tag, e.data) for e in updated_resource),
            key=chiper_key
        )
        write_file(
            f'{basename}{index_suffix}',
            sputm.write_chunks(make_index_from_resource(updated_resource, index_root)),
            key=chiper_key
        )
