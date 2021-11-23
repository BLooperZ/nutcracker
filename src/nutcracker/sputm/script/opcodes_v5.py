from functools import partial
from typing import IO, Optional, Sequence, Type

from nutcracker.sputm.script.parser import ScriptArg

from .opcodes import ByteValue, CString, RefOffset, WordValue

PARAM_1 = 0x80
PARAM_2 = 0x40
PARAM_3 = 0x20
MASKS = (PARAM_1, PARAM_2, PARAM_3)

BYTE = (ByteValue,)
WORD = (WordValue,)


class Statement_v5:
    def __init__(self, name, op, opcode, stream):
        self.name = name
        self.opcode = opcode
        self.offset = stream.tell() - 1
        self.args = tuple(op(opcode, stream))

    def __repr__(self):
        return ' '.join(
            [f'0x{self.opcode:02x}', self.name, '{', *(str(x) for x in self.args), '}']
        )

    def to_bytes(self):
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])


def named(arg):
    # from SCUMM reference, appendix F
    defs = {
        0: 'complex-temp',
        1: 'selected-actor',
        2: 'camera-x',
        3: 'message-going',
        4: 'selected-room',
        5: 'override-hit',
        6: 'machine-speed',
        7: 'me',
        8: 'number-of-actors',
        9: 'current-lights',
        10: 'current-disk-side',
        11: 'jiffy1',
        12: 'jiffy2',
        13: 'jiffy3',
        14: 'music-flag',
        15: 'actor-range-min',
        16: 'actor-range-max',
        17: 'camera-min',
        18: 'camera-max',
        19: 'min-jiffies',
        20: 'cursor-x',
        21: 'cursor-y',
        22: 'real-selected',
        23: 'last-sound',
        24: 'override-key',
        25: 'actor-talking',
        26: 'snap-scroll',
        27: 'camera-script',
        28: 'enter-room1-script',
        29: 'enter-room2-script',
        30: 'exit-room1-script',
        31: 'exit-room2-script',
        32: 'build-sentence-script',
        33: 'sentence-script',
        34: 'update-inven-script',
        35: 'cut-scene1-script',
        36: 'cut-scene2-script',
        37: 'text-speed',
        38: 'entered-door',
        39: 'sputm-debug',
        40: 'K-of-heap',
        41: 'sputm-version',
        42: 'restart-key',
        43: 'pause-key',
        44: 'screen-x',
        45: 'screen-y',
        46: 'frame-jiffies',
        47: 'total-jiffies',
        48: 'sound-mode',
        49: 'graphics-mode',
        50: 'save-load-key',
        51: 'hard-disk',
        52: 'cursor-state',
        53: 'userput-state',
        54: 'text-offset',
    }
    return defs.get(arg.num, arg)

def value(arg):
    if isinstance(arg, Variable):
        return named(arg)
    return f"#{int.from_bytes(arg.op, byteorder='little', signed=False)}"


class Variable:
    def __init__(self, num, more: Optional['Variable'] = None):
        self.num = num
        self.more = more

    def __repr__(self):
        more = f'[{value(self.more)}]' if self.more else ''
        if self.num & 0x4000:
            return f'L.{self.num - 0x4000}{more}'
        if self.num & 0x8000:
            return f'B.{self.num - 0x8000}{more}'
        else:
            return f'V.{self.num}{more}'

    def to_bytes(self):
        if isinstance(self.more, Variable):
            return (self.num | 0x2000).to_bytes(2, byteorder='little', signed=False) + (
                self.more.num | 0x2000
            ).to_bytes(2, byteorder='little', signed=False)
        if isinstance(self.more, WordValue):
            return (self.num | 0x2000).to_bytes(
                2, byteorder='little', signed=False
            ) + self.more.to_bytes()
        return self.num.to_bytes(2, byteorder='little', signed=False)


def get_var(stream):
    var = Variable(
        int.from_bytes(WordValue(stream).op, byteorder='little', signed=False)
    )
    if var.num & 0x2000:
        word = WordValue(stream)
        more = int.from_bytes(word.op, byteorder='little', signed=False)
        if more & 0x2000:
            return Variable(var.num - 0x2000, Variable(more - 0x2000))
        else:
            assert more < 0x2000, (var, more)
            return Variable(var.num - 0x2000, word)
    return var


def get_params(
    opcode: int,
    stream: IO[bytes],
    args: Sequence[Type[ScriptArg]],
    masks: Sequence[int] = MASKS,
):
    # NOTE: need to be lazy for do-sentence (o5_doSentence)
    assert len(args) <= len(masks)
    for mask, ctype in zip(masks, args):
        param = get_var(stream) if opcode & mask else ctype(stream)
        assert isinstance(param, Variable if opcode & mask else ctype)
        yield param


def get_result_pos(opcode, stream):
    return get_var(stream)


def get_word_varargs(opcode, stream):
    while True:
        sub = ByteValue(stream)
        yield sub
        if sub.op[0] == 0xFF:
            break
        yield from get_params(sub.op[0], stream, WORD)


def noparams(name, opcode, stream):
    raise NotImplementedError(name)
    return ()


def nop(name, op=None):
    if not op:
        op = partial(noparams, name)
    return partial(Statement_v5, name, op)


def xop(func):
    return nop(func.__name__, func)


def decode_parse_string(stream):
    while True:
        sub = ByteValue(stream)
        yield sub
        if ord(sub.op) == 0xFF:
            break
        masked = ord(sub.op) & 0x0F
        if masked in {0, 3, 8}:
            yield from get_params(sub.op[0], stream, 2 * WORD)
        elif masked in {1}:
            yield from get_params(sub.op[0], stream, BYTE)
        elif masked in {2}:
            yield from get_params(sub.op[0], stream, WORD)
        elif masked in {4, 6, 7}:
            continue
        if masked in {15}:
            yield CString(stream)
            break


def o5_putActor(opcode, stream):
    actor, x, y = get_params(opcode, stream, BYTE + 2 * WORD)
    return actor, x, y


def o5_startMusic(opcode, stream):
    if opcode in {
        0x02,
        0x82,  # o5_startMusic
        0x62,
        0xE2,  # o5_stopScript
    }:
        yield from get_params(opcode, stream, BYTE)
    if opcode in {0x22, 0xA2}:  # o5_getAnimCounter
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    if opcode in {0x42, 0xC2}:  # o5_chainScript
        yield from get_params(opcode, stream, BYTE)
        yield from get_word_varargs(opcode, stream)


def o5_getActorRoom(opcode, stream):
    pos = get_result_pos(opcode, stream)
    if opcode in {
        0x03,
        0x83,  # o5_getActorRoom
        0x63,
        0xE3,  # o5_getActorFacing
    }:
        (act,) = get_params(opcode, stream, BYTE)
        return pos, act
    if opcode in {
        0x23,
        0xA3,  # o5_getActorY
        0x43,
        0xC3,  # o5_getActorX
    }:
        (act,) = get_params(opcode, stream, WORD)
        return pos, act


def o5_isGreaterEqual(opcode, stream):
    if opcode in {
        0x04,
        0x84,  # o5_isGreaterEqual
        0x44,
        0xC4,  # o5_isLess
    }:
        a = get_var(stream)
        (b,) = get_params(opcode, stream, WORD)
        offset = RefOffset(stream)
        return a, b, offset
    if opcode in {0x24, 0x64, 0xA4, 0xE4}:  # o5_loadRoomWithEgo
        obj, room = get_params(opcode, stream, WORD + BYTE)
        x, y = WordValue(stream), WordValue(stream)
        return obj, room, x, y


def o5_isNotEqual(opcode, stream):
    if opcode in {
        0x08,
        0x88,  # o5_isNotEqual
        0x48,
        0xC8,  # o5_isEqual
    }:
        a = get_var(stream)
        (b,) = get_params(opcode, stream, WORD)
        offset = RefOffset(stream)
        return a, b, offset
    elif opcode in {
        0x28,  # o5_equalZero
        0xA8,  # o5_notEqualZero
    }:
        a = get_var(stream)
        offset = RefOffset(stream)
        return a, offset
    elif opcode in {0x68, 0xE8}:  # o5_isScriptRunning
        pos = get_result_pos(opcode, stream)
        (b,) = get_params(opcode, stream, BYTE)
        return pos, b
    else:
        raise NotImplementedError()


def o5_stopObjectCode(opcode, stream):
    if opcode in {
        0x00,
        0xA0,  # o5_stopObjectCode
        0x20,  # o5_stopMusic
        0x80,  # o5_breakHere
        0xC0,  # o5_endCutscene
    }:
        return
    elif opcode in {0x40}:  # o5_cutscene
        yield from get_word_varargs(opcode, stream)
    elif opcode in {0x60, 0xE0}:  # o5_freezeScripts
        yield from get_params(opcode, stream, BYTE)


def o5_drawObject(opcode, stream):
    if opcode in {
        0x05,
        0x45,
        0x85,
        0xC5,
    }:  # o5_drawObject
        (obj,) = get_params(opcode, stream, WORD)
        sub = ByteValue(stream)
        masked = ord(sub.op) & 0x1F
        if masked == 1:
            xpos, ypos = get_params(sub.op[0], stream, 2 * WORD)
            return obj, sub, xpos, ypos
        elif masked == 2:
            (state,) = get_params(sub.op[0], stream, WORD)
            return obj, sub, state
        elif masked == 0x1F:
            return obj, sub
        else:
            raise NotImplementedError(sub, masked)
    if opcode in {
        0x25,
        0x65,
        0xA5,
        0xE5,
    }:  # o5_pickupObject
        obj, room = get_params(opcode, stream, WORD + BYTE)
        return obj, room


def o5_move(opcode, stream):
    if opcode in {
        0x1A,
        0x9A,  # o5_move
        0x3A,
        0xBA,  # o5_subtract
        0x5A,
        0xDA,  # o5_add
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, WORD)
    elif opcode in {
        0x7A,
        0xFA,  # o5_verbOps
    }:
        (verb,) = get_params(opcode, stream, BYTE)
        yield verb
        while True:
            sub = ByteValue(stream)
            yield sub
            if ord(sub.op) == 0xFF:
                break
            masked = ord(sub.op) & 0x1F
            if masked in {1, 20}:
                yield from get_params(sub.op[0], stream, WORD)
            elif masked in {2}:
                yield CString(stream)
            elif masked in {3, 4, 16, 18, 23}:
                yield from get_params(sub.op[0], stream, BYTE)
            elif masked in {5}:
                yield from get_params(sub.op[0], stream, 2 * WORD)
            elif masked in {6, 7, 8, 9, 17, 19}:
                continue
            elif masked in {22}:
                yield from get_params(sub.op[0], stream, WORD + BYTE)
            else:
                raise NotImplementedError(sub.op, masked)
    else:
        raise NotImplementedError()


def o5_actorOps(opcode, stream):
    if opcode in {
        0x13,
        0x53,
        0x93,
        0xD3,  # o5_actorOps
    }:
        (act,) = get_params(opcode, stream, BYTE)
        yield act
        while True:
            sub = ByteValue(stream)
            yield sub
            if sub.op[0] == 0xFF:
                break
            masked = ord(sub.op) & 0x1F
            if masked in {0, 1, 3, 4, 6, 12, 14, 16, 19, 22, 23}:
                yield from get_params(sub.op[0], stream, BYTE)
            elif masked in {2, 5, 11, 17}:
                yield from get_params(sub.op[0], stream, 2 * BYTE)
            elif masked in {7}:
                yield from get_params(sub.op[0], stream, 3 * BYTE)
            elif masked in {8, 10, 18, 20, 21}:
                continue
            elif masked in {13}:
                yield CString(stream)
            elif masked in {9}:
                yield from get_params(sub.op[0], stream, WORD)
            else:
                raise NotImplementedError(sub.op)
    elif opcode in {0x33, 0x73, 0xB3, 0xF3}:  # o5_roomOps
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x1F
        if masked in {1, 2, 3}:
            yield from get_params(sub.op[0], stream, 2 * WORD)
        elif masked in {4}:
            yield from get_params(sub.op[0], stream, 3 * WORD)
            sub2 = ByteValue(stream)
            yield sub2
            yield from get_params(sub2.op[0], stream, BYTE)
        elif masked in {5, 6}:
            pass
        elif masked in {7}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
            sub2 = ByteValue(stream)
            yield sub2
            yield from get_params(sub2.op[0], stream, 2 * BYTE)
            sub3 = ByteValue(stream)
            yield sub3
            yield from get_params(sub3.op[0], stream, BYTE)
        elif masked in {8}:
            yield from get_params(sub.op[0], stream, 3 * BYTE)
        elif masked in {9, 16}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
        elif masked in {10}:
            yield from get_params(sub.op[0], stream, WORD)
        elif masked in {11, 12}:
            yield from get_params(sub.op[0], stream, 3 * WORD)
            sub2 = ByteValue(stream)
            yield sub2
            yield from get_params(sub2.op[0], stream, 2 * BYTE)
        elif masked in {13, 14}:
            yield from get_params(sub.op[0], stream, BYTE)
            yield CString(stream)
        elif masked in {15}:
            yield from get_params(sub.op[0], stream, BYTE)
            sub2 = ByteValue(stream)
            yield sub2
            yield from get_params(sub2.op[0], stream, 2 * BYTE)
            sub3 = ByteValue(stream)
            yield sub3
            yield from get_params(sub3.op[0], stream, BYTE)
        else:
            raise NotImplementedError(sub.op[0] & 0x1F)


def o5_jumpRelative(opcode, stream):
    if opcode in {
        0x18,  # o5_jumpRelative
    }:
        off = RefOffset(stream)
        return (off,)
    if opcode in {
        0x38,
        0xB8,  # o5_isLessEqual
        0x78,
        0xF8,  # o5_isGreater
    }:
        a = get_var(stream)
        (b,) = get_params(opcode, stream, WORD)
        offset = RefOffset(stream)
        return a, b, offset
    if opcode in {
        0x58,  # o5_beginOverride
        0x98,  # o5_systemOps
    }:
        sub = ByteValue(stream)
        return (sub,)
    if opcode in {
        0xD8,  # o5_printEgo
    }:
        # raise NotImplementedError('o5_printEgo')
        return tuple(decode_parse_string(stream))


def o5_resourceRoutines(opcode, stream):
    if opcode in {
        0x0C,  # o5_resourceRoutines
        0x8C,  # o5_resourceRoutines
    }:
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x3F
        if masked in {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            18,
            19,
            32,
            33,
        }:
            yield from get_params(sub.op[0], stream, BYTE)
        elif masked in {17}:
            return
        elif masked in {20}:
            yield from get_params(sub.op[0], stream, BYTE + WORD)
        elif masked in {35, 37}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
        elif masked in {36}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
            yield ByteValue(stream)
    elif opcode in {
        0x2C,  # o5_cursorCommand
    }:
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x1F
        if masked in {1, 2, 3, 4, 5, 6, 7, 8}:
            return
        elif masked in {10}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
        elif masked in {11}:
            yield from get_params(sub.op[0], stream, 3 * BYTE)
        elif masked in {12, 13}:
            yield from get_params(sub.op[0], stream, BYTE)
        elif masked in {14}:
            yield from get_word_varargs(sub.op[0], stream)
    elif opcode in {
        0x4C,  # o5_soundKludge
    }:
        yield from get_word_varargs(opcode, stream)
    elif opcode in {
        0x6C,  # o5_getActorWidth
        0xEC,  # o5_getActorWidth
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    elif opcode in {
        0xAC,  # o5_expression
    }:
        yield get_result_pos(opcode, stream)
        while True:
            sub = ByteValue(stream)
            yield sub
            if sub.op[0] == 0xFF:
                break
            masked = ord(sub.op) & 0x1F
            if masked == 1:
                yield from get_params(sub.op[0], stream, WORD)
            if masked == 6:
                nest = ByteValue(stream)
                yield OPCODES_v5[nest.op[0] & 0x1F](nest.op[0], stream)
    elif opcode in {
        0xCC,  # o5_pseudoRoom
    }:
        yield ByteValue(stream)
        while True:
            val = ByteValue(stream)
            yield val
            if val.op[0] == 0:
                break
    else:
        raise NotImplementedError(opcode)


def o5_walkActorToActor(opcode, stream):
    if opcode in {
        0x2D,  # o5_putActorInRoom
        0x6D,  # o5_putActorInRoom
        0xAD,  # o5_putActorInRoom
        0xED,  # o5_putActorInRoom
    }:
        yield from get_params(opcode, stream, 2 * BYTE)
    elif opcode in {
        0x0D,  # o5_walkActorToActor
        0x4D,  # o5_walkActorToActor
        0x8D,  # o5_walkActorToActor
        0xCD,  # o5_walkActorToActor
    }:
        yield from get_params(opcode, stream, 2 * BYTE)
        yield ByteValue(stream)
    else:
        raise NotImplementedError(opcode)


def o5_panCameraTo(opcode, stream):
    if opcode in {
        0x52,  # o5_actorFollowCamera
        0xD2,  # o5_actorFollowCamera
        0x72,  # o5_loadRoom
        0xF2,  # o5_loadRoom
    }:
        yield from get_params(opcode, stream, BYTE)
    elif opcode in {
        0x12,  # o5_panCameraTo
        0x92,  # o5_panCameraTo
        0x32,  # o5_setCameraAt
        0xB2,  # o5_setCameraAt
    }:
        yield from get_params(opcode, stream, WORD)
    else:
        raise NotImplementedError(opcode)


def o5_ifClassOfIs(opcode, stream):
    if opcode in {
        0x1D,  # o5_ifClassOfIs
        0x9D,  # o5_ifClassOfIs
    }:
        (obj,) = get_params(opcode, stream, WORD)
        yield obj
        yield from get_word_varargs(opcode, stream)
        yield RefOffset(stream)
    elif opcode in {
        0x5D,  # o5_setClass
        0xDD,  # o5_setClass
    }:
        (obj,) = get_params(opcode, stream, WORD)
        yield obj
        yield from get_word_varargs(opcode, stream)
    elif opcode in {
        0x3D,  # o5_findInventory
        0x7D,  # o5_findInventory
        0xBD,  # o5_findInventory
        0xFD,  # o5_findInventory
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, 2 * BYTE)
    else:
        raise NotImplementedError(opcode)


def o5_and(opcode, stream):
    if opcode in {
        0x17,  # o5_and
        0x97,  # o5_and
        0x57,  # o5_or
        0xD7,  # o5_or
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, WORD)
    elif opcode in {
        0x37,  # o5_startObject
        0x77,  # o5_startObject
        0xB7,  # o5_startObject
        0xF7,  # o5_startObject
    }:
        yield from get_params(opcode, stream, WORD + BYTE)
        yield from get_word_varargs(opcode, stream)
    else:
        raise NotImplementedError(opcode)


def o5_getActorElevation(opcode, stream):
    if opcode in {
        0x06,  # o5_getActorElevation
        0x86,  # o5_getActorElevation
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    elif opcode in {
        0x46,  # o5_increment
        0xC6,  # o5_decrement
    }:
        yield get_result_pos(opcode, stream)
    elif opcode in {
        0x26,  # o5_setVarRange
        0xA6,  # o5_setVarRange
    }:
        yield get_result_pos(opcode, stream)
        num = ByteValue(stream)
        yield num
        for i in range(num.op[0]):
            yield WordValue(stream) if opcode & PARAM_1 else ByteValue(stream)
    elif opcode in {
        0x66,  # o5_getClosestObjActor
        0xE6,  # o5_getClosestObjActor
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, WORD)
    else:
        raise NotImplementedError(opcode)


def o5_isActorInBox(opcode, stream):
    if opcode in {
        0x3F,  # o5_drawBox
        0x7F,  # o5_drawBox
        0xBF,  # o5_drawBox
        0xFF,  # o5_drawBox
    }:
        yield from get_params(opcode, stream, 2 * WORD)
        sub = ByteValue(stream)
        yield sub
        yield from get_params(sub.op[0], stream, 2 * WORD + BYTE)
    else:
        raise NotImplementedError(opcode)


def o5_getObjectState(opcode, stream):
    if opcode in {
        0x2F,  # o5_ifNotState
        0x6F,  # o5_ifNotState
        0xAF,  # o5_ifNotState
        0xEF,  # o5_ifNotState
    }:
        raise NotImplementedError('o5_ifNotState')
    elif opcode in {
        0x0F,  # o5_getObjectState
        0x8F,  # o5_getObjectState
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, WORD)
    else:
        raise NotImplementedError(opcode)


def o5_putActorAtObject(opcode, stream):
    if opcode in {
        0x0E,  # o5_putActorAtObject
        0x4E,  # o5_putActorAtObject
        0x8E,  # o5_putActorAtObject
        0xCE,  # o5_putActorAtObject
    }:
        yield from get_params(opcode, stream, BYTE + WORD)
    elif opcode in {
        0xAE,  # o5_wait
    }:
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x1F
        if masked in {1}:
            yield from get_params(sub.op[0], stream, BYTE)
        elif masked in {2, 3, 4}:
            return
        else:
            raise NotImplementedError(sub.op[0])
    elif opcode in {
        0x2E,  # o5_delay
    }:
        yield ByteValue(stream)
        yield ByteValue(stream)
        yield ByteValue(stream)
    elif opcode in {
        0x6E,  # o5_stopObjectScript
        0xEE,  # o5_stopObjectScript
    }:
        yield from get_params(opcode, stream, WORD)
    else:
        raise NotImplementedError(opcode, 'o5_putActorAtObject')


def o5_multiply(opcode, stream):
    if opcode in {
        0x1B,  # o5_multiply
        0x9B,  # o5_multiply
        0x5B,  # o5_divide
        0xDB,  # o5_divide
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, WORD)
    elif opcode in {
        0x3B,  # o5_getActorScale
        0xBB,  # o5_getActorScale
        0x7B,  # o5_getActorWalkBox
        0xFB,  # o5_getActorWalkBox
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    else:
        raise NotImplementedError(opcode, 'o5_multiply')


def o5_walkActorTo(opcode, stream):
    if opcode in {
        0x1E,  # o5_walkActorTo
        0x3E,  # o5_walkActorTo
        0x5E,  # o5_walkActorTo
        0x7E,  # o5_walkActorTo
        0x9E,  # o5_walkActorTo
        0xBE,  # o5_walkActorTo
        0xDE,  # o5_walkActorTo
        0xFE,  # o5_walkActorTo
    }:
        yield from get_params(opcode, stream, BYTE + 2 * WORD)
    else:
        raise NotImplementedError(opcode, 'o5_walkActorTo')


def o5_startScript(opcode, stream):
    if opcode in {
        0x0A,  # o5_startScript
        0x2A,  # o5_startScript
        0x4A,  # o5_startScript
        0x6A,  # o5_startScript
        0x8A,  # o5_startScript
        0xAA,  # o5_startScript
        0xCA,  # o5_startScript
        0xEA,  # o5_startScript
    }:
        yield from get_params(opcode, stream, BYTE)
        yield from get_word_varargs(opcode, stream)
    else:
        raise NotImplementedError(opcode, 'o5_startScript')


def o5_getObjectOwner(opcode, stream):
    if opcode in {
        0x10,  # o5_getObjectOwner
        0x90,  # o5_getObjectOwner
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, WORD)
    elif opcode in {
        0x30,  # o5_matrixOps
        0xB0,  # o5_matrixOps
    }:
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x1F
        if masked in {1, 2, 3}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
    elif opcode in {
        0x70,  # o5_lights
        0xF0,  # o5_lights
    }:
        yield from get_params(opcode, stream, BYTE)
        yield ByteValue(stream)
        yield ByteValue(stream)
    else:
        raise NotImplementedError(opcode, 'o5_getObjectOwner')


def o5_startSound(opcode, stream):
    if opcode in {
        0x1C,  # o5_startSound
        0x9C,  # o5_startSound
        0x3C,  # o5_stopSound
        0xBC,  # o5_stopSound
    }:
        yield from get_params(opcode, stream, BYTE)
    elif opcode in {
        0x7C,  # o5_isSoundRunning
        0xFC,  # o5_isSoundRunning
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    else:
        raise NotImplementedError(opcode, 'o5_startSound')


def o5_setState(opcode, stream):
    if opcode in {
        0x07,  # o5_setState
        0x47,  # o5_setState
        0x87,  # o5_setState
        0xC7,  # o5_setState
    }:
        yield from get_params(opcode, stream, WORD + BYTE)
    elif opcode in {
        0x27,  # o5_stringOps
    }:
        sub = ByteValue(stream)
        yield sub
        masked = ord(sub.op) & 0x1F
        if masked in {1}:
            yield from get_params(sub.op[0], stream, BYTE)
            yield CString(stream)
        if masked in {2, 5}:
            yield from get_params(sub.op[0], stream, 2 * BYTE)
        if masked in {3}:
            yield from get_params(sub.op[0], stream, 3 * BYTE)
        if masked in {4}:
            yield get_result_pos(sub.op[0], stream)
            yield from get_params(sub.op[0], stream, 2 * BYTE)
    elif opcode in {
        0x67,  # o5_getStringWidth
        0xE7,  # o5_getStringWidth
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    elif opcode in {
        0xA7,  # o5_dummy
    }:
        return
    else:
        raise NotImplementedError(opcode, 'o5_setState')


def o5_faceActor(opcode, stream):
    if opcode in {
        0x09,  # o5_faceActor
        0x49,  # o5_faceActor
        0x89,  # o5_faceActor
        0xC9,  # o5_faceActor
    }:
        yield from get_params(opcode, stream, BYTE + WORD)
    elif opcode in {
        0x29,  # o5_setOwnerOf
        0x69,  # o5_setOwnerOf
        0xA9,  # o5_setOwnerOf
        0xE9,  # o5_setOwnerOf
    }:
        yield from get_params(opcode, stream, WORD + BYTE)
    else:
        raise NotImplementedError(opcode, 'o5_faceActor')


def o5_print(opcode, stream):
    if opcode in {
        0x14,  # o5_print
        0x94,  # o5_print
    }:
        yield from get_params(opcode, stream, BYTE)
        yield from decode_parse_string(stream)
        # raise NotImplementedError('o5_print')
    elif opcode in {
        0x54,  # o5_setObjectName
        0xD4,  # o5_setObjectName
    }:
        yield from get_params(opcode, stream, WORD)
        yield CString(stream)
    elif opcode in {
        0x34,  # o5_getDist
        0x74,  # o5_getDist
        0xB4,  # o5_getDist
        0xF4,  # o5_getDist
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, 2 * WORD)
    else:
        raise NotImplementedError(opcode, 'o5_print')


def o5_getRandomNr(opcode, stream):
    if opcode in {
        0x16,  # o5_getRandomNr
        0x96,  # o5_getRandomNr
        0x56,  # o5_getActorMoving
        0xD6,  # o5_getActorMoving
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    elif opcode in {
        0x36,  # o5_walkActorToObject
        0x76,  # o5_walkActorToObject
        0xB6,  # o5_walkActorToObject
        0xF6,  # o5_walkActorToObject
    }:
        yield from get_params(opcode, stream, BYTE + WORD)
    else:
        raise NotImplementedError(opcode, 'o5_getRandomNr')


def o5_animateActor(opcode, stream):
    if opcode in {
        0x11,  # o5_animateActor
        0x51,  # o5_animateActor
        0x91,  # o5_animateActor
        0xD1,  # o5_animateActor
    }:
        yield from get_params(opcode, stream, 2 * BYTE)

    elif opcode in {
        0x31,  # o5_getInventoryCount
        0xB1,  # o5_getInventoryCount
        0x71,  # o5_getActorCostume
        0xF1,  # o5_getActorCostume
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, BYTE)
    else:
        raise NotImplementedError(opcode, 'o5_animateActor')


def o5_doSentence(opcode, stream):
    if opcode in {
        0x19,  # o5_doSentence
        0x39,  # o5_doSentence
        0x59,  # o5_doSentence
        0x79,  # o5_doSentence
        0x99,  # o5_doSentence
        0xB9,  # o5_doSentence
        0xD9,  # o5_doSentence
        0xF9,  # o5_doSentence
    }:
        params = get_params(opcode, stream, BYTE + 2 * WORD)
        var = next(params)
        yield var
        if isinstance(var, ByteValue) and var.op[0] == 254:
            return
        yield from params
    else:
        raise NotImplementedError(opcode, 'o5_doSentence')


def o5_getVerbEntrypoint(opcode, stream):
    if opcode in {
        0x0B,  # o5_getVerbEntrypoint
        0x4B,  # o5_getVerbEntrypoint
        0x8B,  # o5_getVerbEntrypoint
        0xCB,  # o5_getVerbEntrypoint
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, 2 * WORD)
    elif opcode in {
        0x2B,  # o5_delayVariable
    }:
        yield get_var(stream)
    elif opcode in {
        0x6B,  # o5_debug
        0xEB,  # o5_debug
    }:
        yield from get_params(opcode, stream, WORD)
    elif opcode in {
        0xAB,  # o5_saveRestoreVerbs
    }:
        sub = ByteValue(stream)
        yield sub
        yield from get_params(sub.op[0], stream, 3 * BYTE)
    else:
        raise NotImplementedError(opcode, 'o5_getVerbEntrypoint')


def o5_actorFromPos(opcode, stream):
    if opcode in {
        0x35,  # o5_findObject
        0x75,  # o5_findObject
        0xB5,  # o5_findObject
        0xF5,  # o5_findObject
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, 2 * BYTE)
    elif opcode in {
        0x15,  # o5_actorFromPos
        0x55,  # o5_actorFromPos
        0x95,  # o5_actorFromPos
        0xD5,  # o5_actorFromPos
    }:
        yield get_result_pos(opcode, stream)
        yield from get_params(opcode, stream, 2 * WORD)
    else:
        raise NotImplementedError(opcode, 'o5_actorFromPos')


def realize_v5(mapping):
    # emulate: op = opcodes[opcode & 0x1F](opcode, stream)
    return dict((0x20 * i + key, val) for i in range(8) for key, val in mapping.items())


OPCODES_v5 = realize_v5({
    0x00: xop(o5_stopObjectCode),
    0x01: xop(o5_putActor),
    0x02: xop(o5_startMusic),
    0x03: xop(o5_getActorRoom),
    0x04: xop(o5_isGreaterEqual),
    0x05: xop(o5_drawObject),
    0x06: xop(o5_getActorElevation),
    0x07: xop(o5_setState),
    0x08: xop(o5_isNotEqual),
    0x09: xop(o5_faceActor),
    0x0A: xop(o5_startScript),
    0x0B: xop(o5_getVerbEntrypoint),
    0x0C: xop(o5_resourceRoutines),
    0x0D: xop(o5_walkActorToActor),
    0x0E: xop(o5_putActorAtObject),
    0x0F: xop(o5_getObjectState),
    0x10: xop(o5_getObjectOwner),
    0x11: xop(o5_animateActor),
    0x12: xop(o5_panCameraTo),
    0x13: xop(o5_actorOps),
    0x14: xop(o5_print),
    0x15: xop(o5_actorFromPos),
    0x16: xop(o5_getRandomNr),
    0x17: xop(o5_and),
    0x18: xop(o5_jumpRelative),
    0x19: xop(o5_doSentence),
    0x1A: xop(o5_move),
    0x1B: xop(o5_multiply),
    0x1C: xop(o5_startSound),
    0x1D: xop(o5_ifClassOfIs),
    0x1E: xop(o5_walkActorTo),
    0x1F: xop(o5_isActorInBox),
})


if __name__ == '__main__':
    import argparse
    import glob

    from nutcracker.utils.fileio import read_file
    from nutcracker.utils.funcutils import flatten

    from ..preset import sputm
    from .bytecode import descumm, get_scripts, script_map

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = sorted(set(flatten(glob.iglob(r) for r in args.files)))
    for filename in files:
        print('===============', filename)

        resource = read_file(filename, key=int(args.chiper_key, 16))

        for elem in get_scripts(sputm.map_chunks(resource)):
            print('===============', elem)
            _, script_data = script_map[elem.tag](elem.data)
            bytecode = descumm(script_data, OPCODES_v5)
            # print_bytecode(bytecode)
            # for off, stat in bytecode.items():
            #     print(f'{off:08d}', stat)
