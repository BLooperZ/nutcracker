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

def room_ops_he60(stream):
    cmd = SubOp(stream)
    if ord(cmd.op) in {221}:
        return (cmd, CString(stream))
    return (cmd,)

def array_ops_v6(stream):
    cmd = SubOp(stream)
    arr = WordValue(stream)
    if ord(cmd.op) in {205}:
        return (cmd, arr, CString(stream))
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
    0x00: makeop('o6_pushByte', extended_b_op),
    0x01: makeop('o6_pushWord', extended_w_op),
    0x03: makeop('o6_pushWordVar', extended_w_op),
    0x07: makeop('o6_wordArrayRead', extended_w_op),
    0x0b: makeop('o6_wordArrayIndexedRead', extended_w_op),
    0x0c: makeop('o6_dup'),
    0x0d: makeop('o6_not'),
    0x0e: makeop('o6_eq'),
    0x0f: makeop('o6_neq'),
    0x10: makeop('o6_gt'),
    0x11: makeop('o6_lt'),
    0x12: makeop('o6_le'),
    0x13: makeop('o6_ge'),
    0x14: makeop('o6_add'),
    0x15: makeop('o6_sub'),
    0x16: makeop('o6_mul'),
    0x17: makeop('o6_div'),
    0x18: makeop('o6_land'),  # logical and
    0x19: makeop('o6_lor'),  # logical or
    0x1a: makeop('o6_pop'),
    0x43: makeop('o6_writeWordVar', extended_w_op),
    0x47: makeop('o6_wordArrayWrite', extended_w_op),
    0x4b: makeop('o6_wordArrayIndexedWrite', extended_w_op),
    0x4f: makeop('o6_wordVarInc', extended_w_op),
    0x53: makeop('o6_wordArrayInc', extended_w_op),
    0x57: makeop('o6_wordVarDec', extended_w_op),
    0x5c: makeop('o6_if', jump_cmd),  # jump if
    0x5d: makeop('o6_ifNot', jump_cmd),  # jump if not
    0x5e: makeop('o6_startScript'),
    0x5f: makeop('o6_startScriptQuick'),
    0x65: makeop('o6_stopObjectCode'),
    0x66: makeop('o6_stopObjectCode'),
    0x6b: makeop('o6_cursorCommand', extended_b_op),
    0x6e: makeop('o6_setClass'),
    0x6f: makeop('o6_getState'),
    0x6c: makeop('o6_breakHere'),
    0x6d: makeop('o6_ifClassOfIs'),
    0x73: makeop('o6_jump', jump_cmd),
    0x75: makeop('o6_stopSound'),
    0x7a: makeop('o6_setCameraAt'),
    0x7b: makeop('o6_loadRoom'),
    0x7c: makeop('o6_stopScript'),
    0x7e: makeop('o6_walkActorTo'),
    0x7f: makeop('o6_putActorAtXY'),
    0x80: makeop('o6_putActorAtObject'),
    0x82: makeop('o6_animateActor'),
    0x84: makeop('o6_pickupObject'),
    0x87: makeop('o6_getRandomNumber'),
    0x88: makeop('o6_getRandomNumberRange'),
    0x8b: makeop('o6_isScriptRunning'),
    0x8d: makeop('o6_getObjectX'),
    0x8e: makeop('o6_getObjectY'),
    0x8f: makeop('o6_getObjectOldDir'),
    0x91: makeop('o6_getActorCostume'),
    0x95: makeop('o6_beginOverride'),
    0x96: makeop('o6_endOverride'),
    0x98: makeop('o6_isSoundRunning'),
    0x9b: makeop('o6_resourceRoutines', extended_b_op),
    0x9c: makeop('o6_roomOps', extended_b_op),
    0x9d: makeop('o6_actorOps', extended_b_op),
    0x9f: makeop('o6_getActorFromXY'),
    0xa0: makeop('o6_findObject'),
    0xa3: makeop('o6_getVerbEntrypoint'),
    0xa4: makeop('o6_arrayOps', array_ops_v6),
    0xa6: makeop('o6_drawBox'),
    0xa7: makeop('o6_pop'),
    0xa9: makeop('o6_wait', wait_ops),
    0xad: makeop('o6_isAnyOf'),
    0xb0: makeop('o6_delay'),
    0xb1: makeop('o6_delaySeconds'),
    0xb4: makeop('o6_printLine', msg_cmd),
    0xb5: makeop('o6_printText', msg_cmd),
    0xb6: makeop('o6_printDebug', msg_cmd),
    0xb7: makeop('o6_printSystem', msg_cmd),
    0xb8: makeop('o6_printActor', msg_cmd),
    0xb9: makeop('o6_printEgo', msg_cmd),
    0xbc: makeop('o6_dimArray', extended_bw_op),
    0xbf: makeop('o6_startScriptQuick2'),
    0xc4: makeop('o6_abs'),
    0xc9: makeop('o6_kernelSetFunctions'),
    0xca: makeop('o6_delayFrames'),
    0xcb: makeop('o6_pickOneOf'),
    0xcc: makeop('o6_pickOneOfDefault'),
    0xcd: makeop('o6_stampObject'),
    0xd0: makeop('o6_getDateTime'),
    0xd1: makeop('o6_stopTalking'),
    0xd2: makeop('o6_getAnimateVariable'),
    0xd4: makeop('o6_shuffle', extended_w_op),
    0xd6: makeop('o6_band'),  # bitwise and
    0xd7: makeop('o6_bor'),  # bitwise or
    0xd8: makeop('o6_isRoomScriptRunning'),
}

OPCODES_he60 = {
    **OPCODES_v6,
    0x9c: makeop('o60_roomOps', room_ops_he60),
    0x9d: makeop('o60_actorOps', extended_b_op),
    0xbd: makeop('o6_stopObjectCode'),
    0xc9: makeop('o60_kernelSetFunctions'),
    0xd9: makeop('o60_closeFile'), 
    0xe2: makeop('o60_localizeArrayToScript'),
    0xe9: makeop('o60_seekFilePos'),
}

OPCODES_he70 = {
    **OPCODES_he60,
    0x74: makeop('o70_soundOps', extended_b_op),
    0x84: makeop('o70_pickupObject'),
    0x8c: makeop('o70_getActorRoom'),
    0x9b: makeop('o70_resourceRoutines', extended_b_op),
    0xee: makeop('o70_getStringLen'),
    0xf2: makeop('o70_isResourceLoaded', extended_b_op),
}

OPCODES_he71 = {
    **OPCODES_he70,
    0xc9: makeop('o71_kernelSetFunctions'),
    0xed: makeop('o71_getStringWidth'),
    0xef: makeop('o71_appendString'),
    0xf5: makeop('o71_getStringLenForWidth'),
    0xf6: makeop('o71_getCharIndexInString'),
    0xfb: makeop('o71_polygonOps', extended_b_op),
    0xfc: makeop('o71_polygonHit'),
}

OPCODES_he72 = {
    **OPCODES_he71,
    0x02: makeop('o72_pushDWord', extended_dw_op),
    0x04: makeop('o72_getScriptString', msg_op),
    0x1b: makeop('o72_isAnyOf'),
    0x50: makeop('o72_resetCutscene'),
    0x54: makeop('o72_getObjectImageX'),
    0x55: makeop('o72_getObjectImageY'),
    0x56: makeop('o72_captureWizImage'),
    0x58: makeop('o72_getTimer', extended_b_op),
    0x59: makeop('o72_setTimer', extended_b_op),
    0x5a: makeop('o72_getSoundPosition'),
    0x5e: makeop('o72_startScript', extended_b_op),
    0x60: makeop('o72_startObject', extended_b_op),
    0x61: makeop('o72_drawObject', extended_b_op),
    0x63: makeop('o72_getArrayDimSize', extended_bw_op),
    0x9c: makeop('o72_roomOps', extended_b_op),
    0x9d: makeop('o72_actorOps', extended_b_op),
    0xa4: makeop('o72_arrayOps', array_ops),
    0xae: makeop('o72_systemOps', extended_b_op),
    0xba: makeop('o72_talkActor', msg_op),
    0xbb: makeop('o72_talkEgo', msg_op),
    0xbc: makeop('o72_dimArray', extended_bw_op),
    0xc0: makeop('o72_dim2dimArray', extended_bw_op),
    0xce: makeop('o72_drawWizImage'),
    0xcf: makeop('o72_debugInput'),
    0xd5: makeop('o72_jumpToScript', extended_b_op),
    0xda: makeop('o72_openFile'),
    0xdb: makeop('o72_readFile', extended_b_op),
    0xdc: makeop('o72_writeFile', write_file),
    0xdd: makeop('o72_findAllObjects'),
    0xde: makeop('o72_deleteFile'),
    0xdf: makeop('o72_rename'),
    0xea: makeop('o72_redimArray', extended_bw_op),
    0xf3: makeop('o72_readINI', extended_b_op),
    0xf4: makeop('o72_writeINI', extended_b_op),
    0xf8: makeop('o72_getResourceSize', extended_b_op),
    0xf9: makeop('o72_createDirectory'),
    0xfa: makeop('o72_setSystemMessage', extended_b_op),
}

OPCODES_he80 = {
    **OPCODES_he72,
    0x45: makeop('o80_createSound', extended_b_op),
    0x48: makeop('o80_stringToInt'),
    0x49: makeop('o80_getSoundVar'),
    0x4a: makeop('o80_localizeArrayToRoom'),
    0x4d: makeop('o80_readConfigFile', extended_b_op),
    0x70: makeop('o80_setState'),
    0xe3: makeop('o80_pickVarRandom', extended_w_op),
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
                if arg.msg:
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

def get_scripts(root):
    for elem in root:
        if elem.tag in {'LECF', 'LFLF', 'RMDA', 'OBCD', *script_map}:
            if elem.tag in script_map:
                yield elem
            else:
                yield from get_scripts(elem.children)


if __name__ == '__main__':
    import argparse
    import os
    import glob

    from .preset import sputm
    from .index import read_file

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:

        resource = read_file(filename, key=int(args.chiper_key, 16))

        for elem in get_scripts(sputm.map_chunks(resource)):
            _, script_data = script_map[elem.tag](elem.data)
            bytecode = descumm(script_data, OPCODES_he80)
            print_bytecode(bytecode)
