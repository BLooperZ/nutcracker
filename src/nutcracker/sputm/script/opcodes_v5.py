import itertools
from typing import IO, Optional, Sequence, Type

from nutcracker.sputm.script.parser import ScriptArg

from .opcodes import ByteValue, CString, RefOffset, WordValue

PARAM_1 = 0x80
PARAM_2 = 0x40
PARAM_3 = 0x20
MASKS = (PARAM_1, PARAM_2, PARAM_3)

BYTE = (ByteValue,)
WORD = (WordValue,)


class SomeOp:
    def __init__(self, name, opcode, offset, args) -> None:
        self.name = name
        self.opcode = opcode
        self.offset = offset
        self.args = args

    @classmethod
    def parse(cls, name, ops, opcode, stream):
        return cls(
            name,
            opcode,
            stream.tell() -1,
            tuple(
                itertools.chain.from_iterable(
                    op(opcode, stream)
                    for op in ops
                ),
            ),
        )

    def to_bytes(self) -> bytes:
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])

    def __repr__(self) -> str:
        return ' '.join(
            ['OP', f'0x{self.opcode:02x}', self.name, '{', *(str(x) for x in self.args), '}']
        )


def mop(name, *ops, terminate=False):
    def inner(opcode, stream):
        res = SomeOp.parse(name, ops, opcode, stream)
        res.terminate = terminate
        return res
    return inner


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
    # return f"#{int.from_bytes(arg.op, byteorder='little', signed=False)}"
    return f"{int.from_bytes(arg.op, byteorder='little', signed=False)}"


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
            # assert more < 0x2000, (var, more)
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


def RESULT(opcode, stream):
    yield get_var(stream)


class VarArgs:
    def __init__(self, args):
        self.args = tuple(args)

    def __repr__(self):
        return f'({", ".join(str(x) for x in self.args)})'

    def to_bytes(self):
        return b''.join(x.to_bytes() for x in self.args)


def WORD_VARARGS(opcode, stream):
    yield VarArgs(SUBMASK_VARARGS(0x1F, {
        0x01: mop('ARG', PARAMS(WORD)),
    })(opcode, stream))


def SUBMASK_VARARGS(mask, mapping, term=0xFF):
    def inner(opcode, stream):
        while True:
            sub = ByteValue(stream)
            if ord(sub.op) == term:
                yield sub
                break
            op = ord(sub.op)
            args = mapping[op & mask](op, stream)
            yield args
            if args.terminate:
                break
    return inner


def SUBMASK(mask, mapping):
    def inner(opcode, stream):
        sub = ByteValue(stream)
        yield mapping[ord(sub.op) & mask](ord(sub.op), stream)
    return inner


def PARAMS(*args):
    def inner(opcode, stream):
        for idx, arg in enumerate(args):
            if idx != 0:
                sub = ByteValue(stream)
                yield sub
                opcode = ord(sub.op)
            yield from get_params(opcode, stream, arg)
    return inner


def MSG_OP(opcode, stream):
    yield CString(stream)


def STRING_SUBARGS(version=5):
    return SUBMASK_VARARGS(0x1F, {
        0x00: mop('SO_AT', PARAMS(2 * WORD)),
        0x01: mop('SO_COLOR', PARAMS(BYTE)),
        0x02: mop('SO_CLIPPED', PARAMS(WORD)),
        0x03: mop('SO_ERASE', PARAMS(2 * WORD)),
        0x04: mop('SO_CENTER'),
        0x05: mop('??UNKONWN5??'),
        0x06: mop('HEIGHT', PARAMS(WORD)) if version == 3 else mop('SO_LEFT'),
        0x07: mop('SO_OVERHEAD'),
        0x08: mop('SO_SAY_VOICE', PARAMS(2 * WORD)),
        0x0F: mop('SO_TEXTSTRING', MSG_OP, terminate=True),
    })


def VAR(opcode, stream):
    yield get_var(stream)

def OFFSET(opcode, stream):
    yield RefOffset(stream)

def IMWORD(opcode, stream):
    yield WordValue(stream)

def IMBYTE(opcode, stream):
    yield ByteValue(stream)


def OPERATION(opcode, stream):
    nest = ByteValue(stream)
    yield OPCODES_v5[nest.op[0] & 0x1F](nest.op[0], stream)


def BYTE_VARARGS(opcode, stream):
    while True:
        val = ByteValue(stream)
        yield val
        if ord(val.op) == 0:
            break


def VAR_RANGE(opcode, stream):
    num = ByteValue(stream)
    yield num
    for _ in range(num.op[0]):
        yield WordValue(stream) if opcode & PARAM_1 else ByteValue(stream)


def do_sentence_params(opcode, stream):
    params = get_params(opcode, stream, BYTE + 2 * WORD)
    var = next(params)
    yield var
    if isinstance(var, ByteValue) and ord(var.op) == 0xFE:
        return
    yield from params


def flatop(*args, fallback=None):
    mapping = {}
    for name, opcodes, *params in args:
        func = mop(name, *params)
        for op in opcodes:
            mapping[op] = func

    def inner(opcode, stream):
        return mapping.get(opcode, fallback)(opcode, stream)

    return inner


def o5_stopObjectCode(opcode, stream):
    return flatop(
        ('o5_stopObjectCode', {0x00}),
        ('o5_stopMusic', {0x20}),
        ('o5_cutscene', {0x40}, WORD_VARARGS),
        ('o5_freezeScripts', {0x60, 0xE0}, PARAMS(BYTE)),
        ('o5_breakHere', {0x80}),
        ('o5_stopObjectCode', {0xA0}),
        ('o5_endCutscene', {0xC0}),
    )(opcode, stream)


def o5_putActor(opcode, stream):
    return mop('o5_putActor', PARAMS(BYTE + 2 * WORD))(opcode, stream)


def o5_startMusic(opcode, stream):
    return flatop(
        ('o5_startMusic', {0x02, 0x82}, PARAMS(BYTE)),
        ('o5_getAnimCounter', {0x22, 0xA2}, RESULT, PARAMS(BYTE)),
        ('o5_chainScript', {0x42, 0xC2}, PARAMS(BYTE), WORD_VARARGS),
        ('o5_stopScript', {0x62, 0xE2}, PARAMS(BYTE)),
    )(opcode, stream)


def o5_getActorRoom(opcode, stream):
    return flatop(
        ('o5_getActorRoom', {0x03, 0x83}, RESULT, PARAMS(BYTE)),
        ('o5_getActorY', {0x23, 0xA3}, RESULT, PARAMS(WORD)),
        ('o5_getActorX', {0x43, 0xC3}, RESULT, PARAMS(WORD)),
        ('o5_getActorFacing', {0x63, 0xE3}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_isGreaterEqual(opcode, stream):
    return flatop(
        ('o5_isGreaterEqual', {0x04, 0x84}, VAR, PARAMS(WORD), OFFSET),
        ('o5_isLess', {0x44, 0xC4}, VAR, PARAMS(WORD), OFFSET),
        ('o5_loadRoomWithEgo', {0x24, 0x64, 0xA4, 0xE4}, PARAMS(WORD + BYTE), IMWORD, IMWORD),
    )(opcode, stream)


def o5_drawObject(opcode, stream):
    return flatop(
        ('o5_drawObject', {0x05, 0x45, 0x85, 0xC5}, PARAMS(WORD), SUBMASK_VARARGS(0x1F, {
            0x01: mop('AT', PARAMS(2 * WORD), terminate=True),
            0x02: mop('STATE', PARAMS(WORD), terminate=True),
        })),
        ('o5_pickupObject', {0x25, 0x65, 0xA5, 0xE5}, PARAMS(WORD + BYTE)),
    )(opcode, stream)


def o5_getActorElevation(opcode, stream):
    return flatop(
        ('o5_getActorElevation', {0x06, 0x86}, RESULT, PARAMS(BYTE)),
        ('o5_setVarRange', {0x26, 0xA6}, RESULT, VAR_RANGE),
        ('o5_increment', {0x46}, RESULT),
        ('o5_decrement', {0xC6}, RESULT),
        ('o5_getClosestObjActor', {0x66, 0xE6}, RESULT, PARAMS(WORD)),
    )(opcode, stream)


def o5_setState(opcode, stream):
    return flatop(
        ('o5_setState', {0x07, 0x47, 0x87, 0xC7}, PARAMS(WORD + BYTE)),
        ('o5_stringOps', {0x27}, SUBMASK(0x1F, {
            0x01: mop('ASSIGN-STRING', PARAMS(BYTE), MSG_OP),
            0x02: mop('ASSIGN-STRING-VAR', PARAMS(2 * BYTE)),
            0x03: mop('ASSIGN-INDEX', PARAMS(3 * BYTE)),
            0x04: mop('ASSIGN-VAR', RESULT, PARAMS(2 * BYTE)),
            0x05: mop('STRING-INDEX', PARAMS(2 * BYTE)),
        })),
        ('o5_dummy', {0xA7}),
        ('o5_getStringWidth', {0x67, 0xE7}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_isNotEqual(opcode, stream):
    return flatop(
        ('o5_isNotEqual', {0x08, 0x88}, VAR, PARAMS(WORD), OFFSET),
        ('o5_equalZero', {0x28}, VAR, OFFSET),
        ('o5_notEqualZero', {0xA8}, VAR, OFFSET),
        ('o5_isEqual', {0x48, 0xC8}, VAR, PARAMS(WORD), OFFSET),
        ('o5_isScriptRunning', {0x68, 0xE8}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_faceActor(opcode, stream):
    return flatop(
        ('o5_faceActor', {0x09, 0x49, 0x89, 0xC9}, PARAMS(BYTE + WORD)),
        ('o5_setOwnerOf', {0x29, 0x69, 0xA9, 0xE9}, PARAMS(WORD + BYTE)),
    )(opcode, stream)


def o5_startScript(opcode, stream):
    return mop('o5_startScript', PARAMS(BYTE), WORD_VARARGS)(opcode, stream)


def o5_getVerbEntrypoint(opcode, stream):
    return flatop(
        ('o5_getVerbEntrypoint', {0x0B, 0x4B, 0x8B, 0xCB}, RESULT, PARAMS(2 * WORD)),
        ('o5_delayVariable', {0x2B}, VAR),
        ('o5_debug', {0x6B}, PARAMS(WORD)),
        ('o5_saveRestoreVerbs', {0xAB}, SUBMASK(0x1F, {
            0x01: mop('SO_SAVE_VERBS', PARAMS(3 * BYTE)),
            0x02: mop('SO_RESTORE_VERBS', PARAMS(3 * BYTE)),
            # TODO: 0x03: mop('SO_DELETE_VERBS', PARAMS(3 * BYTE)),
        })),
    )(opcode, stream)


def o5_resourceRoutines(opcode, stream):
    return flatop(
        ('o5_resourceRoutines', {0x0C, 0x8C}, SUBMASK(0x3F, {
            0x01: mop('SO_LOAD_SCRIPT', PARAMS(BYTE)),
            0x02: mop('SO_LOAD_SOUND', PARAMS(BYTE)),
            0x03: mop('SO_LOAD_COSTUME', PARAMS(BYTE)),
            0x04: mop('SO_LOAD_ROOM', PARAMS(BYTE)),
            0x05: mop('SO_NUKE_SCRIPT', PARAMS(BYTE)),
            0x06: mop('SO_NUKE_SOUND', PARAMS(BYTE)),
            0x07: mop('SO_NUKE_COSTUME', PARAMS(BYTE)),
            0x08: mop('SO_NUKE_ROOM', PARAMS(BYTE)),
            0x09: mop('SO_LOCK_SCRIPT', PARAMS(BYTE)),
            0x0A: mop('SO_LOCK_SOUND', PARAMS(BYTE)),
            0x0B: mop('SO_LOCK_COSTUME', PARAMS(BYTE)),
            0x0C: mop('SO_LOCK_ROOM', PARAMS(BYTE)),
            0x0D: mop('SO_UNLOCK_SCRIPT', PARAMS(BYTE)),
            0x0E: mop('SO_UNLOCK_SOUND', PARAMS(BYTE)),
            0x0F: mop('SO_UNLOCK_COSTUME', PARAMS(BYTE)),
            0x10: mop('SO_UNLOCK_ROOM', PARAMS(BYTE)),
            0x11: mop('SO_CLEAR_HEAP'),
            0x12: mop('SO_LOAD_CHARSET', PARAMS(BYTE)),
            0x13: mop('SO_NUKE_CHARSET', PARAMS(BYTE)),
            0x14: mop('SO_LOAD_OBJECT', PARAMS(BYTE + WORD)),
            0x20: mop('??UNKNOWN20??', PARAMS(BYTE)),
            0x21: mop('??UNKNOWN21??', PARAMS(BYTE)),
            0x23: mop('??UNKNOWN23??', PARAMS(2 * BYTE)),
            0x24: mop('??UNKNOWN24??', PARAMS(2 * BYTE), IMBYTE),
            0x25: mop('??UNKNOWN25??', PARAMS(2 * BYTE)),
        })),
        ('o5_cursorCommand', {0x2C}, SUBMASK(0x1F, {
            0x01: mop('SO_CURSOR_ON'),
            0x02: mop('SO_CURSOR_OFF'),
            0x03: mop('SO_USERPUT_ON'),
            0x04: mop('SO_USERPUT_OFF'),
            0x05: mop('SO_CURSOR_SOFT_ON'),
            0x06: mop('SO_CURSOR_SOFT_OFF'),
            0x07: mop('SO_USERPUT_SOFT_ON'),
            0x08: mop('SO_USERPUT_SOFT_OFF'),
            0x0A: mop('SO_CURSOR_IMAGE', PARAMS(2 * BYTE)),
            0x0B: mop('SO_CURSOR_HOTSPOT', PARAMS(3 * BYTE)),
            0x0C: mop('SO_CURSOR_SET', PARAMS(BYTE)),
            0x0D: mop('SO_CHARSET_SET', PARAMS(BYTE)),
            0x0E: mop('CHARSET-COLOR', WORD_VARARGS)
        })),
        ('o5_expression', {0xAC}, RESULT, SUBMASK_VARARGS(0x1F, {
            0x01: mop('ARG', PARAMS(WORD)),
            0x02: mop('ADD'),
            0x03: mop('SUBSTRACT'),
            0x04: mop('MULTIPLY'),
            0x05: mop('DIVIDE'),
            0x06: mop('OPERATION', OPERATION)
        })),
        ('o5_soundKludge', {0x4C}, WORD_VARARGS),
        ('o5_pseudoRoom', {0xCC}, IMBYTE, BYTE_VARARGS),
        ('o5_getActorWidth', {0x6C, 0xEC}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_walkActorToActor(opcode, stream):
    return flatop(
        ('o5_walkActorToActor', {0x0D, 0x4D, 0x8D, 0xCD}, PARAMS(2 * BYTE), IMBYTE),
        ('o5_putActorInRoom', {0x2D, 0x6D, 0xAD, 0xED}, PARAMS(2 * BYTE)),
    )(opcode, stream)


def o5_putActorAtObject(opcode, stream):
    return flatop(
        ('o5_putActorAtObject', {0x0E, 0x4E, 0x8E, 0xCE}, PARAMS(BYTE + WORD)),
        ('o5_delay', {0x2E}, IMBYTE, IMBYTE, IMBYTE),
        ('o5_wait', {0xAE}, SUBMASK(0x1F, {
            0x01: mop('SO_WAIT_FOR_ACTOR', PARAMS(BYTE)),
            0x02: mop('SO_WAIT_FOR_MESSAGE'),
            0x03: mop('SO_WAIT_FOR_CAMERA'),
            0x04: mop('SO_WAIT_FOR_SENTENCE'),
        })),
        ('o5_stopObjectScript', {0x6E, 0xEE}, PARAMS(WORD)),
    )(opcode, stream)


def o5_getObjectState(opcode, stream):
    return flatop(
        ('o5_getObjectState', {0x0F, 0x8F}, RESULT, PARAMS(WORD)),
    )(opcode, stream)


def o5_getObjectOwner(opcode, stream, version=5):
    return flatop(
        ('o5_getObjectOwner', {0x10, 0x90}, RESULT, PARAMS(WORD)),
        ('o5_matrixOps', {0x30, 0xB0}, SUBMASK(0x1F, {
            0x01: mop('SET-BOX-STATUS', PARAMS(2 * BYTE)),
            0x02: mop('SET-BOX-??', PARAMS(2 * BYTE)),
            0x03: mop('SET-BOX-???', PARAMS(2 * BYTE)),
            0x04: mop('SET-BOX-PATH'),
        })),
        ('o5_lights', {0x70, 0xF0}, PARAMS(BYTE), IMBYTE, IMBYTE),
    )(opcode, stream)


def o5_animateActor(opcode, stream):
    return flatop(
        ('o5_animateActor', {0x11, 0x51, 0x91, 0xD1}, PARAMS(2 * BYTE)),
        ('o5_getActorCostume', {0x71, 0xF1}, RESULT, PARAMS(BYTE)),
        ('o5_getInventoryCount', {0x31, 0xB1}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_panCameraTo(opcode, stream):
    return flatop(
        ('o5_panCameraTo', {0x12, 0x92}, PARAMS(WORD)),
        ('o5_setCameraAt', {0x32, 0xB2}, PARAMS(WORD)),
        ('o5_actorFollowCamera', {0x52, 0xD2}, PARAMS(BYTE)),
        ('o5_loadRoom', {0x72, 0xF2}, PARAMS(BYTE)),
    )(opcode, stream)


actor_convert = [
    1, 0, 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20,
]


def o5_actorOps(opcode, stream, version=5):
    # support for version <5 by
    # op = (op & 0xE0) | actor_convert[(op & 0x1F) - 1]
    # also note special case when subop is 0x11: PARAMS(BYTE)
    actor_ops = {
        0x00: mop('???DUMMY???', PARAMS(BYTE)),
        0x01: mop('SO_COSTUME', PARAMS(BYTE)),
        0x02: mop('SO_STEP_DIST', PARAMS(2 * BYTE)),
        0x03: mop('SO_SOUND', PARAMS(BYTE)),
        0x04: mop('SO_WALK_ANIMATION', PARAMS(BYTE)),
        0x05: mop('SO_TALK_ANIMATION', PARAMS(2 * BYTE)),
        0x06: mop('SO_STAND_ANIMATION', PARAMS(BYTE)),
        0x07: mop('SO_ANIMATION', PARAMS(3 * BYTE)),
        0x08: mop('SO_DEFAULT'),
        0x09: mop('SO_ELEVATION', PARAMS(WORD)),
        0x0A: mop('SO_ANIMATION_DEFAULT'),
        0x0B: mop('SO_PALETTE', PARAMS(2 * BYTE)),
        0x0C: mop('SO_TALK_COLOR', PARAMS(BYTE)),
        0x0D: mop('SO_ACTOR_NAME', MSG_OP),
        0x0E: mop('SO_INIT_ANIMATION', PARAMS(BYTE)),
        0x10: mop('SO_ACTOR_WIDTH', PARAMS(BYTE)),
        0x11: mop('SO_ACTOR_SCALE', PARAMS(BYTE)) if version == 4 else mop('SO_ACTOR_SCALE', PARAMS(2 * BYTE)),
        0x12: mop('SO_NEVER_ZCLIP'),
        0x13: mop('SO_ALWAYS_ZCLIP', PARAMS(BYTE)),
        0x14: mop('SO_IGNORE_BOXES'),
        0x15: mop('SO_FOLLOW_BOXES'),
        0x16: mop('SO_ANIMATION_SPEED', PARAMS(BYTE)),
        0x17: mop('SO_SHADOW', PARAMS(BYTE)),
    }
    if version < 5:
        actor_ops = {
            op: actor_ops[actor_convert[op - 1]]
            for op in range(1, 21)
            if actor_convert[op - 1] in actor_ops
        }

    return flatop(
        ('o5_actorOps', {0x13, 0x53, 0x93, 0xD3}, PARAMS(BYTE), SUBMASK_VARARGS(0x1F, actor_ops)),
        ('o5_roomOps', {0x33, 0x73, 0xB3, 0xF3}, SUBMASK(0x1F, {
            0x01: mop('SO_ROOM_SCROLL', PARAMS(2 * WORD)),
            0x02: mop('SO_ROOM_COLOR', PARAMS(2 * WORD)),
            0x03: mop('SO_ROOM_SCREEN', PARAMS(2 * WORD)),
            0x04: mop('SO_ROOM_PALETTE', PARAMS(2 * WORD) if version == 4 else PARAMS(3 * WORD, BYTE)),
            0x05: mop('SO_ROOM_SHAKE_ON'),
            0x06: mop('SO_ROOM_SHAKE_OFF'),
            0x07: mop('SO_ROOM_SCALE', PARAMS(2 * BYTE, 2 * BYTE, BYTE)),
            0x08: mop('SO_ROOM_INTENSITY', PARAMS(3 * BYTE)),
            0x09: mop('SO_ROOM_SAVEGAME', PARAMS(2 * BYTE)),
            0x0A: mop('SO_ROOM_FADE', PARAMS(WORD)),
            0x0B: mop('SO_RGB_ROOM_INTENSITY', PARAMS(3 * WORD, 2 * BYTE)),
            0x0C: mop('SO_ROOM_SHADOW', PARAMS(3 * WORD, 2 * BYTE)),
            0x0D: mop('SO_SAVE_STRING', PARAMS(BYTE), MSG_OP),
            0x0E: mop('SO_LOAD_STRING', PARAMS(BYTE), MSG_OP),
            0x0F: mop('SO_ROOM_TRANSFORM', PARAMS(BYTE, 2 * BYTE, BYTE)),
            0x10: mop('SO_CYCLE_SPEED', PARAMS(2 * BYTE)),
        })),
    )(opcode, stream)


def o5_print(opcode, stream, version=5):
    return flatop(
        ('o5_print', {0x14, 0x94}, PARAMS(BYTE), STRING_SUBARGS(version=version)),
        ('o5_setObjectName', {0x54, 0xD4}, PARAMS(WORD), MSG_OP),
        ('o5_getDist', {0x34, 0x74, 0xB4, 0xF4}, RESULT, PARAMS(2 * WORD)),
    )(opcode, stream)


def o5_actorFromPos(opcode, stream):
    return flatop(
        ('o5_actorFromPos', {0x15, 0x55, 0x95, 0xD5}, RESULT, PARAMS(2 * WORD)),
        ('o5_findObject', {0x35, 0x75, 0xB5, 0xF5}, RESULT, PARAMS(2 * BYTE)),
    )(opcode, stream)


def o5_getRandomNr(opcode, stream):
    return flatop(
        ('o5_getRandomNr', {0x16, 0x96}, RESULT, PARAMS(BYTE)),
        ('o5_getActorMoving', {0x56, 0xD6}, RESULT, PARAMS(BYTE)),
        ('o5_walkActorToObject', {0x36, 0x76, 0xB6, 0xF6}, PARAMS(BYTE + WORD)),
    )(opcode, stream)


def o5_and(opcode, stream):
    return flatop(
        ('o5_and', {0x17, 0x97}, RESULT, PARAMS(WORD)),
        ('o5_or', {0x57, 0xD7}, RESULT, PARAMS(WORD)),
        ('o5_startObject', {0x37, 0x77, 0xB7, 0xF7}, PARAMS(WORD + BYTE), WORD_VARARGS),
    )(opcode, stream)


def o5_jumpRelative(opcode, stream, version=5):
    return flatop(
        ('o5_jumpRelative', {0x18}, OFFSET),
        ('o5_beginOverride', {0x58}, SUBMASK(0xFF, {
            0x00: mop('OFF'),
            0x01: mop('ON'),
        })),
        ('o5_systemOps', {0x98}, SUBMASK(0xFF, {
            0x01: mop('SO_RESTART'),
            0x02: mop('SO_PAUSE'),
            0x03: mop('SO_QUIT'),
        })),
        ('o5_printEgo', {0xD8}, STRING_SUBARGS(version=version)),
        ('o5_isLessEqual', {0x38, 0xB8}, VAR, PARAMS(WORD), OFFSET),
        ('o5_isGreater', {0x78, 0xF8}, VAR, PARAMS(WORD), OFFSET),
    )(opcode, stream)


def o5_doSentence(opcode, stream):
    return mop('o5_doSentence', do_sentence_params)(opcode, stream)


def o5_move(opcode, stream):
    return flatop(
        ('o5_move', {0x1A, 0x9A}, RESULT, PARAMS(WORD)),
        ('o5_subtract', {0x3A, 0xBA}, RESULT, PARAMS(WORD)),
        ('o5_add', {0x5A, 0xDA}, RESULT, PARAMS(WORD)),
        ('o5_verbOps', {0x7A, 0xFA}, PARAMS(BYTE), SUBMASK_VARARGS(0x1F, {
            0x01: mop('SO_VERB_IMAGE', PARAMS(WORD)),
            0x02: mop('SO_VERB_NAME', MSG_OP),
            0x03: mop('SO_VERB_COLOR', PARAMS(BYTE)),
            0x04: mop('SO_VERB_HICOLOR', PARAMS(BYTE)),
            0x05: mop('SO_VERB_AT', PARAMS(2 * WORD)),
            0x06: mop('SO_VERB_ON'),
            0x07: mop('SO_VERB_OFF'),
            0x08: mop('SO_VERB_DELETE'),
            0x09: mop('SO_VERB_NEW'),
            0x10: mop('SO_VERB_DIMCOLOR', PARAMS(BYTE)),
            0x11: mop('SO_VERB_DIM'),
            0x12: mop('SO_VERB_KEY', PARAMS(BYTE)),
            0x13: mop('SO_VERB_CENTER'),
            0x14: mop('SO_VERB_NAME_STR', PARAMS(WORD)),
            0x16: mop('IMAGE-ROOM', PARAMS(WORD + BYTE)),
            0x17: mop('BAKCOLOR', PARAMS(BYTE)),
        })),
    )(opcode, stream)


def o5_multiply(opcode, stream):
    return flatop(
        ('o5_multiply', {0x1B, 0x9B}, RESULT, PARAMS(WORD)),
        ('o5_getActorScale', {0x3B, 0xBB}, RESULT, PARAMS(BYTE)),
        ('o5_divide', {0x5B, 0xDB}, RESULT, PARAMS(WORD)),
        ('o5_getActorWalkBox', {0x7B, 0xFB}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_startSound(opcode, stream):
    return flatop(
        ('o5_startSound', {0x1C, 0x9C}, PARAMS(BYTE)),
        ('o5_stopSound', {0x3C, 0xBC}, PARAMS(BYTE)),
        ('o5_isSoundRunning', {0x7C, 0xFC}, RESULT, PARAMS(BYTE)),
    )(opcode, stream)


def o5_ifClassOfIs(opcode, stream):
    return flatop(
        ('o5_ifClassOfIs', {0x1D, 0x9D}, PARAMS(WORD), WORD_VARARGS, OFFSET),
        ('o5_findInventory', {0x3D, 0x7D, 0xBD, 0xFD}, RESULT, PARAMS(2 * BYTE)),
        ('o5_setClass', {0x5D, 0xDD}, PARAMS(WORD), WORD_VARARGS),
    )(opcode, stream)


def o5_walkActorTo(opcode, stream):
    return mop('o5_walkActorTo', PARAMS(BYTE + 2 * WORD))(opcode, stream)


def o5_isActorInBox(opcode, stream):
    return flatop(
        ('o5_drawBox', {0x3F, 0x7F, 0xBF, 0xFF}, PARAMS(2 * WORD, 2 * WORD + BYTE)),
    )(opcode, stream)


def realize_v5(mapping):
    # emulate: op = opcodes[opcode & 0x1F](opcode, stream)
    return dict((0x20 * i + key, val) for i in range(8) for key, val in mapping.items())


OPCODES_v5 = realize_v5({
    0x00: o5_stopObjectCode,
    0x01: o5_putActor,
    0x02: o5_startMusic,
    0x03: o5_getActorRoom,
    0x04: o5_isGreaterEqual,
    0x05: o5_drawObject,
    0x06: o5_getActorElevation,
    0x07: o5_setState,
    0x08: o5_isNotEqual,
    0x09: o5_faceActor,
    0x0A: o5_startScript,
    0x0B: o5_getVerbEntrypoint,
    0x0C: o5_resourceRoutines,
    0x0D: o5_walkActorToActor,
    0x0E: o5_putActorAtObject,
    0x0F: o5_getObjectState,
    0x10: o5_getObjectOwner,
    0x11: o5_animateActor,
    0x12: o5_panCameraTo,
    0x13: o5_actorOps,
    0x14: o5_print,
    0x15: o5_actorFromPos,
    0x16: o5_getRandomNr,
    0x17: o5_and,
    0x18: o5_jumpRelative,
    0x19: o5_doSentence,
    0x1A: o5_move,
    0x1B: o5_multiply,
    0x1C: o5_startSound,
    0x1D: o5_ifClassOfIs,
    0x1E: o5_walkActorTo,
    0x1F: o5_isActorInBox,
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
