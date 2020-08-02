#!/usr/bin/env python3
import io
import operator
from collections import deque
from functools import partial
from itertools import takewhile

from nutcracker.utils.funcutils import grouper, flatten

class CString:
    def __init__(self, stream):
        self.msg = readcstr(stream)
    def __repr__(self):
        return f'MSG {self.msg!r}'
    def to_bytes(self):
        msg = self.msg if self.msg is not None else b''
        return msg + b'\0'

class SubOp:
    def __init__(self, stream):
        self.op = stream.read(1)
    def __repr__(self):
        return f'OP hex=0x{ord(self.op):02x} dec={ord(self.op)}'
    def to_bytes(self):
        return self.op

class ByteValue:
    def __init__(self, stream):
        self.op = stream.read(1)
    def __repr__(self):
        return f'BYTE hex=0x{ord(self.op):02x} dec={ord(self.op)}'
    def to_bytes(self):
        return self.op

class WordValue:
    def __init__(self, stream):
        self.op = stream.read(2)
    def __repr__(self):
        val = int.from_bytes(self.op, byteorder='little', signed=True)
        return f'WORD hex=0x{val:04x} dec={val}'
    def to_bytes(self):
        return self.op

class DWordValue:
    def __init__(self, stream):
        self.op = stream.read(4)
    def __repr__(self):
        val = int.from_bytes(self.op, byteorder='little', signed=True)
        return f'DWORD hex=0x{val:04x} dec={val}'
    def to_bytes(self):
        return self.op

class RefOffset:
    def __init__(self, stream):
        rel = int.from_bytes(stream.read(2), byteorder='little', signed=True)
        self.endpos = stream.tell()
        self.abs = rel + self.endpos

    @property
    def rel(self):
        return self.abs - self.endpos

    def __repr__(self):
        return f'REF rel=0x{self.rel:04x} abs=0x{(self.abs):04x}'

    def to_bytes(self):
        return self.rel.to_bytes(2, byteorder='little', signed=True)

def readcstr(stream):
    bound_read = iter(partial(stream.read, 1), b'')
    res = b''.join(takewhile(partial(operator.ne, b'\00'), bound_read))
    return res if res else None

def simple_op(stream):
	return ()

def extended_b_op(stream):
	return (ByteValue(stream),)

def extended_w_op(stream):
	return (WordValue(stream),)

def extended_dw_op(stream):
	return (DWordValue(stream),)

def extended_bw_op(stream):
	return (ByteValue(stream), WordValue(stream))

def jump_cmd(stream):
	return (RefOffset(stream),)

def msg_cmd(stream):
    cmd = SubOp(stream)
    if ord(cmd.op) in {75, 194}:
        return (cmd, CString(stream))
    return (cmd,)

def array_ops(stream):
    cmd = SubOp(stream)
    arr = WordValue(stream)
    if ord(cmd.op) in {127}:
        return (cmd, arr, WordValue(stream))
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd, arr)

def wait_ops(stream):
    cmd = SubOp(stream)
    if ord(cmd.op) in {168, 226, 232}:
        return (cmd, RefOffset(stream))
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd,)

def write_file(stream):
    cmd = SubOp(stream)
    if ord(cmd.op) in {8}:
        return (cmd, ByteValue(stream))
    return (cmd,)

def msg_op(stream):
    return (CString(stream),)

def makeop(name, op=simple_op):
    return partial(Statement, name, op)

class Statement:
    def __init__(self, name, op, opcode, stream):
        self.name = name
        self.opcode = opcode
        self.offset = stream.tell() - 1
        self.args = op(stream)

    def __repr__(self):
        return ' '.join([f'0x{self.opcode:02x}', self.name, '{', *(str(x) for x in self.args), '}'])

    def to_bytes(self):
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])

OPCODES_v6 = {
    0x00: makeop('push-byte', extended_b_op),
    0x01: makeop('push-word', extended_w_op),
    0x03: makeop('push-word-var', extended_w_op),
    0x07: makeop('word-array-read', extended_w_op),
    0x10: makeop('gt'),
    0x0b: makeop('read-indexed-word-array', extended_w_op),
    0x0c: makeop('dup'),
    0x0d: makeop('not'),
    0x0e: makeop('eq'),
    0x0f: makeop('neq'),
    0x10: makeop('gt'),
    0x11: makeop('lt'),
    0x12: makeop('le'),
    0x13: makeop('ge'),
    0x14: makeop('add'),
    0x15: makeop('sub'),
    0x16: makeop('mul'),
    0x17: makeop('div'),
    0x18: makeop('logical-and'),
    0x19: makeop('logical-or'),
    0x1a: makeop('pop'),
    0x43: makeop('write-word-var', extended_w_op),
    0x47: makeop('word-array-write', extended_w_op),
    0x4b: makeop('word-array-indexed-write', extended_w_op),
    0x4f: makeop('inc-word-var', extended_w_op),
    0x50: makeop('reset-cutscene'),
    0x53: makeop('word-array-inc', extended_w_op),
    0x57: makeop('dec-word-var', extended_w_op),
    0x5c: makeop('jump-if', jump_cmd),
    0x5d: makeop('jump-if-not', jump_cmd),
    0x65: makeop('stop-object-code'),
    0x66: makeop('stop-object-code'),
    0x6e: makeop('set-class'),
    0x6f: makeop('get-state'),
    0x6b: makeop('cursor-command', extended_b_op),
    0x6c: makeop('break-here'),
    0x6d: makeop('if-class-of-is'),
    0x73: makeop('jump', jump_cmd),
    0x75: makeop('stop-sound'),
    0x7a: makeop('set-camera-at'),
    0x7b: makeop('load-room'),
    0x7c: makeop('stop-script'),
    0x7e: makeop('walk-actor-to'),
    0x7f: makeop('put-actor-xy'),
    0x80: makeop('put-actor-obj'),
    0x82: makeop('animate-actor'),
    0x87: makeop('get-random-number'),
    0x88: makeop('get-random-number-range'),
    0x8b: makeop('is-script-running'),
    0x8d: makeop('get-object-x'),
    0x8e: makeop('get-object-y'),
    0x8f: makeop('get-object-old-dir'),
    0x91: makeop('get-actor-costume'),
    0x95: makeop('begin-override'),
    0x96: makeop('end-override'),
    0x98: makeop('is-sound-running'),
    0x9f: makeop('get-actor-from-xy'),
    0xa0: makeop('find-object'),
    0xa3: makeop('get-verb-entrypoint'),
    0xa6: makeop('draw-box'),
    0xa7: makeop('pop'),
    0xa9: makeop('wait', wait_ops),
    0xad: makeop('is-any-of'),
    0xb0: makeop('delay'),
    0xb1: makeop('delay-seconds'),
    0xb4: makeop('print-line', msg_cmd),
    0xb5: makeop('print-text', msg_cmd),
    0xb6: makeop('print-debug', msg_cmd),
    0xb7: makeop('print-system', msg_cmd),
    0xb8: makeop('print-actor', msg_cmd),
    0xb9: makeop('print-ego', msg_cmd),
    0xbf: makeop('start-script-quick2'),
    0xc4: makeop('abs'),
    0xca: makeop('delay-frame'),
    0xcb: makeop('pick-one-of'),
    0xcc: makeop('pick-one-of-default'),
    0xcd: makeop('stamp-object'),
    0xd0: makeop('get-datetime'),
    0xd1: makeop('stop-talking'),
    0xd2: makeop('animate-var'),
    0xd4: makeop('shuffle', extended_w_op),
    0xd6: makeop('bitwise-and'),
    0xd7: makeop('bitwise-or'),
    0xd8: makeop('is-room-script-running'),
}

OPCODES_he60 = {
    **OPCODES_v6,
    0xbd: makeop('stop-object-code'),
    0xd9: makeop('close-file'), 
    0xe2: makeop('localize-array-to-script'),
    0xe9: makeop('seek-file-pos'),
}

OPCODES_he70 = {
    **OPCODES_he60,
    0x74: makeop('sound-ops', extended_b_op),
    0x8c: makeop('get-actor-room'),
    0x9b: makeop('load-resource', extended_b_op),
    0xee: makeop('strlen'),
    0xf2: makeop('is-resource-loaded', extended_b_op),
}

OPCODES_he71 = {
    **OPCODES_he70,
    0xc9: makeop('kernel-set'),
    0xed: makeop('get-string-width'),
    0xef: makeop('append-string'),
    0xf5: makeop('get-strlen-for-width'),
    0xf6: makeop('get-char-index-in-str'),
    0xfb: makeop('polygon-ops', extended_b_op),
    0xfc: makeop('polygon-hit'),
}

OPCODES_he72 = {
    **OPCODES_he71,
    0x02: makeop('push-dword-var', extended_dw_op),
    0x04: makeop('get-script-string', msg_op),
    0x1b: makeop('is-any-of-72'),
    0x54: makeop('get-object-image-x'),
    0x55: makeop('get-object-image-y'),
    0x56: makeop('capture-wiz-image'),
    0x58: makeop('get-timer', extended_b_op),
    0x59: makeop('set-timer', extended_b_op),
    0x5a: makeop('get-sound-position'),
    0x5e: makeop('start-script', extended_b_op),
    0x60: makeop('start-object', extended_b_op),
    0x61: makeop('draw-object', extended_b_op),
    0x63: makeop('get-array-dim-size', extended_bw_op),
    0x9c: makeop('room-ops', extended_b_op),
    0x9d: makeop('actor-ops', extended_b_op),
    0xa4: makeop('array-ops', array_ops),
    0xae: makeop('system-ops', extended_b_op),
    0xba: makeop('talk-actor', msg_op),
    0xbb: makeop('talk-ego', msg_op),
    0xbc: makeop('dim-array', extended_bw_op),
    0xc0: makeop('dim2dim-array', extended_bw_op),
    0xce: makeop('draw-wiz-image'),
    0xcf: makeop('debug-input'),
    0xd5: makeop('jump-to-script', extended_b_op),
    0xda: makeop('open-file'),
    0xdb: makeop('read-file', extended_b_op),
    0xdc: makeop('write-file', write_file),
    0xdd: makeop('find-all-objects'),
    0xde: makeop('delete-file'),
    0xdf: makeop('rename'),
    0xea: makeop('redim-array', extended_bw_op),
    0xf3: makeop('read-ini', extended_b_op),
    0xf4: makeop('write-ini', extended_b_op),
    0xf8: makeop('get-resource-size', extended_b_op),
    0xf9: makeop('create-directory'),
    0xfa: makeop('set-system-message', extended_b_op),
}

OPCODES_he80 = {
    **OPCODES_he72,
    0x45: makeop('create-sound', extended_b_op),
    0x48: makeop('string-to-int'),
    0x49: makeop('get-sound-var'),
    0x4a: makeop('word-array-indexed-write', extended_w_op),
    0x4d: makeop('read-config-file', extended_b_op),
    0x70: makeop('set-state'),
    0xe3: makeop('pick-random-var', extended_w_op),
}

def descumm(data: bytes, opcodes):
    with io.BytesIO(data) as stream:
        bytecode = {}
        while True:
            next_byte = stream.read(1)
            if not next_byte:
                break
            opcode = ord(next_byte)
            try:
                op = opcodes[opcode](opcode, stream)
                bytecode[op.offset] = op
                # print(f'0x{op.offset:04x}', op)

            except Exception as e:
                print(f'{type(e)}: {str(e)}')
                print(f'0x{stream.tell():04x}', f'0x{opcode:02x}')
                raise e

        for off, stat in bytecode.items():
            for arg in stat.args:
                if isinstance(arg, RefOffset):
                    assert arg.abs in bytecode, hex(arg.abs)

        assert to_bytes(bytecode) == data
        assert to_bytes(refresh_offsets(bytecode)) == data, (to_bytes(refresh_offsets(bytecode)), data)
        return bytecode

def print_bytecode(bytecode):
    for off, stat in bytecode.items():
        print(f'0x{off:04x}', stat)

def get_strings(bytecode):
    for off, stat in bytecode.items():
        for arg in stat.args:
            if isinstance(arg, CString):
                yield arg

def update_strings(bytecode, strings):
    for orig, upd in zip(get_strings(bytecode), strings):
        orig.msg = upd
    return refresh_offsets(bytecode)

def refresh_offsets(bytecode):
    updated = {}
    off = 0
    for stat in bytecode.values():
        for arg in stat.args:
            if isinstance(arg, RefOffset):
                arg.endpos += off - stat.offset
        stat.offset = off
        off += len(stat.to_bytes())
    for stat in bytecode.values():
        for arg in stat.args:
            if isinstance(arg, RefOffset):
                arg.abs = bytecode[arg.abs].offset
        updated[stat.offset] = stat
    return updated

def to_bytes(bytecode):
    with io.BytesIO() as stream:
        for off, stat in bytecode.items():
            assert off == stream.tell()
            stream.write(stat.to_bytes())
        return stream.getvalue()

def parse_script(elem):
    script = elem.data
    if elem.tag in {
        'LSCR',
        # 'SCRP',
        # 'ENCD',
        # 'EXCD'
    }:
        # print(filename)
        if elem.tag in {'LSCR'}:
            serial = elem.data[0]
            # print(f'Script #{serial}')
            script = elem.data[1:]

        bytecode = descumm(script, OPCODES_he80)
        # print_bytecode(bytecode)

        for msg in get_strings(bytecode):
            assert b'\n' not in msg.msg
            assert b'\\x80' not in msg.msg
            assert b'\\xd9' not in msg.msg
            print(
                msg.msg
                    .replace(b'\r', b'\\r')
                    .replace(b'\x80', b'\\x80')
                    .replace(b'\xd9', b'\\xd9')
                    .replace(b'\x7f', b'\\x7f')
                    .decode()
            )

if __name__ == '__main__':
    import argparse
    import os
    import glob

    from .preset import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    args = parser.parse_args()


    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:

        with open(filename, 'rb') as res:
            resource = res.read()

        elem = next(sputm.map_chunks(resource))
        parse_script(elem)
