import io
from functools import partial

from nutcracker.utils.funcutils import flatten
from .script.opcodes import makeop, ByteValue, WordValue, RefOffset, CString
from .script.bytecode import to_bytes, get_scripts, script_map, print_bytecode, refresh_offsets

PARAM_1 = 0x80
PARAM_2 = 0x40
PARAM_3 = 0x20

class Statement_v5:
    def __init__(self, name, op, opcode, stream):
        self.name = name
        self.opcode = opcode
        self.offset = stream.tell() - 1
        self.args = tuple(op(opcode, stream))

    def __repr__(self):
        return ' '.join([f'0x{self.opcode:02x}', self.name, '{', *(str(x) for x in self.args), '}'])

    def to_bytes(self):
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])

class Variable:
    def __init__(self, num):
        self.num = int.from_bytes(num, byteorder='little', signed=True)
    def __repr__(self):
        return f'VAR_{self.num}'
    def to_bytes(self):
        return self.num.to_bytes(2, byteorder='little', signed=True)

def get_var(stream):
    return Variable(WordValue(stream).op)

def get_var_or_byte(opcode, mask, stream):
    if opcode & mask:
        return get_var(stream)
    return ByteValue(stream)

def get_var_or_word(opcode, mask, stream):
    if opcode & mask:
        return get_var(stream)
    return WordValue(stream)

def get_result_pos(opcode, stream):
    var = get_var(stream)
    if var.num & 0x2000:
        return var, get_var(stream)
    return (var,)

def get_word_varargs(opcode, stream):
    while True:
        sub = ByteValue(stream)
        yield sub
        if sub.op == b'\xff':
            break
        yield get_var_or_word(opcode, PARAM_1, stream)

def noparams(opcode, stream):
    raise NotImplementedError()
    return ()

def nop(name, op=noparams):
    return partial(Statement_v5, name, op)

def xop(func):
    return nop(func.__name__, func)

def o5_putActor(opcode, stream):
    actor = get_var_or_byte(opcode, PARAM_1, stream)
    x = get_var_or_word(opcode, PARAM_2, stream)
    y = get_var_or_word(opcode, PARAM_3, stream)
    return actor, x, y

def o5_startMusic(opcode, stream):
    if opcode in {
            0x02, 0x82,  # o5_startMusic
            0x62, 0xe2,  # o5_stopScript
    }:
        return (get_var_or_byte(opcode, PARAM_1, stream),)
    if opcode in {0x22, 0xa2}:  # o5_getAnimCounter
        pos = get_result_pos(opcode, stream)
        act = get_var_or_byte(opcode, PARAM_1, stream)
        return pos, act
    if opcode in {0x42, 0xc2}:  # o5_chainScript
        script = get_var_or_byte(opcode, PARAM_1, stream)
        return script, *get_word_varargs(opcode, stream)

def o5_getActorRoom(opcode, stream):
    pos = get_result_pos(opcode, stream)
    if opcode in {
            0x03, 0x83,  # o5_getActorRoom
            0x63, 0xe3,  # o5_getActorFacing
    }:
        act = get_var_or_byte(opcode, PARAM_1, stream)
        return pos, act
    if opcode in {
            0x23, 0xa3,  # o5_getActorY
            0x43, 0xc3,  # o5_getActorX
    }:
        act = get_var_or_word(opcode, PARAM_1, stream)
        return pos, act

def o5_isGreaterEqual(opcode, stream):
    if opcode in {
            0x04, 0x84,  # o5_isGreaterEqual
            0x44, 0xc4,  # o5_isLess
    }:
        a = get_var(stream)
        b = get_var_or_word(opcode, PARAM_1, stream)
        offset = RefOffset(stream)
        return a, b, offset
    if opcode in {
            0x24, 0x64, 0xa4, 0xe4  # o5_loadRoomWithEgo
    }:
        obj = get_var_or_word(opcode, PARAM_1, stream)
        room = get_var_or_byte(opcode, PARAM_2, stream)
        x = WordValue(stream)
        y = WordValue(stream)
        return obj, room, x, y

def o5_isNotEqual(opcode, stream):
    if opcode in {
            0x08, 0x88,  # o5_isNotEqual
            0x48, 0xc8,  # o5_isEqual
    }:
        a = get_var(stream)
        b = get_var_or_word(opcode, PARAM_1, stream)
        offset = RefOffset(stream)
        return a, b, offset
    if opcode in {
            0x28,  # o5_equalZero
            0xa8,  # o5_notEqualZero
    }:
        a = get_var(stream)
        offset = RefOffset(stream)
        return a, offset
    if opcode in {
            0x68, 0xe8  # o5_isScriptRunning
    }:
        pos = get_result_pos(opcode, stream)
        b = get_var_or_byte(opcode, PARAM_1, stream)
        return pos, b

def o5_stopObjectCode(opcode, stream):
    if opcode in {
            0x00, 0xa0,  # o5_stopObjectCode
            0x20,  # o5_stopMusic
            0x80,  # o5_breakHere
            0xc0,  # o5_endCutscene
    }:
        return ()
    if opcode in {0x40}:  # o5_cutscene
        return get_word_varargs(opcode, stream)
    if opcode in {0x60, 0xe0}: # o5_freezeScripts
        return get_var_or_byte(opcode, PARAM_1, stream)

def o5_drawObject(opcode, stream):
    if opcode in {
            0x05, 0x45, 0x85, 0xc5,  # o5_drawObject
    }:
        obj = get_var_or_word(opcode, PARAM_1, stream)
        sub = ByteValue(stream)
        masked = sub.op & 0x1f
        if masked == 1:
            xpos = get_var_or_word(opcode, PARAM_1, stream)
            ypos = get_var_or_word(opcode, PARAM_2, stream)
            return obj, sub, xpos, ypos
        elif masked == 2:
            state = get_var_or_word(opcode, PARAM_1, stream)
            return obj, sub, state
        elif masked == 0x1f:
            return obj, sub
        else:
            raise NotImplememntedError(sub)
    if opcode in {
            0x25, 0x65, 0xa5, 0xe5  # o5_pickupObject
    }:
        obj = get_var_or_word(opcode, PARAM_1, stream)
        room = get_var_or_byte(opcode, PARAM_2, stream)
        return obj, room

def o5_move(opcode, stream):
    if opcode in {
            0x1a, 0x9a,  # o5_move
            0x3a, 0xba,  # o5_subtract
            0x5a, 0xda,  # o5_add
    }:
        yield get_result_pos(opcode, stream)
        yield get_var_or_word(opcode, PARAM_1, stream)
    if opcode in {
            0x7a, 0xfa,  # o5_verbOps
    }:
        verb = get_var_or_byte(opcode, PARAM_1, stream)
        raise NotImplementedError()

def o5_actorOps(opcode, stream):
    if opcode in {
            0x13, 0x53, 0x93, 0xd3,  # o5_actorOps
    }:
        act = get_var_or_byte(opcode, PARAM_1, stream)
        yield act
        while True:
            sub = ByteValue(stream)
            yield sub
            if sub.op == b'\xff':
                break
            masked = ord(sub.op) & 0x1f
            if masked in {0, 1, 3, 4, 6, 12, 14, 16, 19, 22, 23}:
                yield get_var_or_byte(opcode, PARAM_1, stream)
            elif masked in {2, 5, 11, 17}:
                yield get_var_or_byte(opcode, PARAM_1, stream)
                yield get_var_or_byte(opcode, PARAM_2, stream)
            elif masked in {7}:
                yield get_var_or_byte(opcode, PARAM_1, stream)
                yield get_var_or_byte(opcode, PARAM_2, stream)
                yield get_var_or_byte(opcode, PARAM_3, stream)
            elif masked in {8, 10, 13, 18, 20, 21}:
                continue
            elif masked in {9}:
                yield get_var_or_word(opcode, PARAM_1, stream)
            else:
                raise NotImplementedError(sub.op)
    if opcode in {
            0x33, 0x7d, 0xb3, 0xf3  # o5_roomOps
    }:
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x1f
        if masked in {1, 2, 3}:
            yield get_var_or_word(opcode, PARAM_1, stream)
            yield get_var_or_word(opcode, PARAM_2, stream)
        elif masked in {4}:
            yield get_var_or_word(opcode, PARAM_1, stream)
            yield get_var_or_word(opcode, PARAM_2, stream)
            yield get_var_or_word(opcode, PARAM_3, stream)
            yield ByteValue(stream)
            yield get_var_or_byte(opcode, PARAM_3, stream)
        elif masked in {5, 6}:
            pass
        elif masked in {7}:
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
            yield ByteValue(stream)
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
            yield ByteValue(stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
        elif masked in {8}:
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
            yield get_var_or_byte(opcode, PARAM_3, stream)
        elif masked in {9, 16}:
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
        elif masked in {10}:
            yield get_var_or_word(opcode, PARAM_1, stream)
        elif masked in {11, 12}:
            yield get_var_or_word(opcode, PARAM_1, stream)
            yield get_var_or_word(opcode, PARAM_2, stream)
            yield get_var_or_word(opcode, PARAM_3, stream)
            yield ByteValue(stream)
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
        elif masked in {13, 14}:
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield CString(stream)
        elif masked in {15}:
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield ByteValue(stream)
            yield get_var_or_byte(opcode, PARAM_1, stream)
            yield get_var_or_byte(opcode, PARAM_2, stream)
            yield ByteValue(stream)
            yield get_var_or_byte(opcode, PARAM_1, stream)
        else:
            raise NotImplementedError(sub.op)

def o5_jumpRelative(opcode, stream):
    if opcode in {
            0x18,  # o5_jumpRelative
    }:
        off = RefOffset(stream)
        return (off,)
    if opcode in {
            0x38, 0xb8,  # o5_isLessEqual
            0x78, 0xf8,  # o5_isGreater
    }:
        a = get_var(stream)
        b = get_var_or_word(opcode, PARAM_1, stream)
        offset = RefOffset(stream)
        return a, b, offset
    if opcode in {
            0x58,  # o5_beginOverride
            0x98,  # o5_systemOps
    }:
        sub = ByteValue(stream)
        return (sub,)
    if opcode in {
            0xd8,  # o5_printEgo
    }:
        msg = CString(stream)
        return (msg,)

OPCODES_v5 = {
    0x00: xop(o5_stopObjectCode),
    0x01: xop(o5_putActor),
    0x02: xop(o5_startMusic),
    0x03: xop(o5_getActorRoom),
    0x04: xop(o5_isGreaterEqual),
    0x05: xop(o5_drawObject),
    0x06: nop('o5_getActorElevation'),
    0x07: nop('o5_setState'),
    0x08: xop(o5_isNotEqual),
    0x09: nop('o5_faceActor'),
    0x0a: nop('o5_startScript'),
    0x0b: nop('o5_getVerbEntrypoint'),
    0x0c: nop('o5_resourceRoutines'),
    0x0d: nop('o5_walkActorToActor'),
    0x0e: nop('o5_putActorAtObject'),
    0x0f: nop('o5_getObjectState'),
    0x10: nop('o5_getObjectOwner'),
    0x11: nop('o5_animateActor'),
    0x12: nop('o5_panCameraTo'),
    0x13: xop(o5_actorOps),
    0x14: nop('o5_print'),
    0x15: nop('o5_actorFromPos'),
    0x16: nop('o5_getRandomNr'),
    0x17: nop('o5_and'),
    0x18: xop(o5_jumpRelative),
    0x19: nop('o5_doSentence'),
    0x1a: xop(o5_move),
    0x1b: nop('o5_multiply'),
    0x1c: nop('o5_startSound'),
    0x1d: nop('o5_ifClassOfIs'),
    0x1e: nop('o5_walkActorTo'),
    0x1f: nop('o5_isActorInBox'),
}

def descumm_v5(data: bytes, opcodes):
    with io.BytesIO(data) as stream:
        bytecode = {}
        while True:
            next_byte = stream.read(1)
            if not next_byte:
                break
            opcode = ord(next_byte)
            try:
                op = opcodes[opcode & 0x1f](opcode, stream)
                bytecode[op.offset] = op
                print(f'0x{op.offset:04x}', op)

            except Exception as e:
                print(f'{type(e)}: {str(e)}')
                print(f'0x{stream.tell():04x}', f'0x{opcode:02x}')
                raise e

        for _off, stat in bytecode.items():
            for arg in stat.args:
                if isinstance(arg, RefOffset):
                    assert arg.abs in bytecode, hex(arg.abs)

        assert to_bytes(bytecode) == data
        assert to_bytes(refresh_offsets(bytecode)) == data, (to_bytes(refresh_offsets(bytecode)), data)
        return bytecode

if __name__ == '__main__':
    import argparse
    import os
    import glob

    from .preset import sputm
    from nutcracker.utils.fileio import read_file

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:

        resource = read_file(filename, key=int(args.chiper_key, 16))

        for elem in get_scripts(sputm.map_chunks(resource)):
            _, script_data = script_map[elem.tag](elem.data)
            bytecode = descumm_v5(script_data, OPCODES_v5)
            print_bytecode(bytecode)
