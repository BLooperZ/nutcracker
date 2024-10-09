from collections.abc import Callable, Iterable, Mapping
from enum import IntEnum
from functools import partial
from typing import IO, TypeVar

from nutcracker.sputm.script.opcodes_v5 import SomeOp

from .parser import (
    ByteValue,
    CString,
    DWordValue,
    RefOffset,
    ScriptArg,
    Statement,
    WordValue,
)

OpTable = Mapping[int, Callable[[int, IO[bytes]], Statement | SomeOp]]

T = TypeVar('T')
R = TypeVar('R')


def realize(src: Mapping[T, R | None]) -> dict[T, R]:
    return {key: value for key, value in src.items() if value is not None}


def simple_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return ()


def extended_b_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream),)

class SubOpsV6(IntEnum):
    SO_AT = 65
    SO_COLOR = 66
    SO_CLIPPED = 67
    SO_CENTER = 69

    SO_LEFT = 71
    SO_OVERHEAD = 72

    SO_MUMBLE = 74
    SO_TEXTSTRING = 75
    SO_COSTUME = 76
    SO_STEP_DIST = 77
    SO_SOUND = 78
    SO_WALK_ANIMATION = 79
    SO_TALK_ANIMATION = 80
    SO_STAND_ANIMATION = 81
    SO_ANIMATION = 82
    SO_DEFAULT = 83
    SO_ELEVATION = 84
    SO_ANIMATION_DEFAULT = 85
    SO_PALETTE = 86
    SO_TALK_COLOR = 87
    SO_ACTOR_NAME = 88
    SO_INIT_ANIMATION = 89

    SO_ACTOR_WIDTH = 91
    SO_SCALE = 92
    SO_NEVER_ZCLIP = 93
    SO_ALWAYS_ZCLIP = 94
    SO_IGNORE_BOXES = 95
    SO_FOLLOW_BOXES = 96
    SO_ANIMATION_SPEED = 97
    SO_SHADOW = 98
    SO_TEXT_OFFSET = 99

    SO_LOAD_SCRIPT = 100
    SO_LOAD_SOUND = 101
    SO_LOAD_COSTUME = 102
    SO_LOAD_ROOM = 103
    SO_NUKE_SCRIPT = 104
    SO_NUKE_SOUND = 105
    SO_NUKE_COSTUME = 106
    SO_NUKE_ROOM = 107
    SO_LOCK_SCRIPT = 108
    SO_LOCK_SOUND = 109
    SO_LOCK_COSTUME = 110
    SO_LOCK_ROOM = 111
    SO_UNLOCK_SCRIPT = 112
    SO_UNLOCK_SOUND = 113
    SO_UNLOCK_COSTUME = 114
    SO_UNLOCK_ROOM = 115
    SO_CLEAR_HEAP = 116
    SO_LOAD_CHARSET = 117
    SO_NUKE_CHARSET = 118
    SO_LOAD_OBJECT = 119

    SO_VERB_IMAGE = 124
    SO_VERB_NAME = 125
    SO_VERB_COLOR = 126
    SO_VERB_HICOLOR = 127
    SO_VERB_AT = 128
    SO_VERB_ON = 129
    SO_VERB_OFF = 130
    SO_VERB_DELETE = 131
    SO_VERB_NEW = 132
    SO_VERB_DIMCOLOR = 133
    SO_VERB_DIM = 134
    SO_VERB_KEY = 135
    SO_VERB_CENTER = 136
    SO_VERB_NAME_STR = 137

    SO_VERB_IMAGE_IN_ROOM = 139
    SO_VERB_BAKCOLOR = 140
    SO_SAVE_VERBS = 141
    SO_RESTORE_VERBS = 142
    SO_DELETE_VERBS = 143
    SO_CURSOR_ON = 144
    SO_CURSOR_OFF = 145
    SO_USERPUT_ON = 146
    SO_USERPUT_OFF = 147
    SO_CURSOR_SOFT_ON = 148
    SO_CURSOR_SOFT_OFF = 149
    SO_USERPUT_SOFT_ON = 150
    SO_USERPUT_SOFT_OFF = 151

    SO_CURSOR_IMAGE = 153
    SO_CURSOR_HOTSPOT = 154

    SO_CHARSET_SET = 156
    SO_CHARSET_COLOR = 157
    SO_RESTART = 158
    SO_PAUSE = 159
    SO_QUIT = 160

    SO_WAIT_FOR_ACTOR = 168
    SO_WAIT_FOR_MESSAGE = 169
    SO_WAIT_FOR_CAMERA = 170
    SO_WAIT_FOR_SENTENCE = 171
    SO_ROOM_SCROLL = 172
    SO_ROOM_SCREEN = 174
    SO_ROOM_PALETTE = 175
    SO_ROOM_SHAKE_ON = 176
    SO_ROOM_SHAKE_OFF = 177
    SO_ROOM_INTENSITY = 179
    SO_ROOM_SAVEGAME = 180
    SO_ROOM_FADE = 181
    SO_RGB_ROOM_INTENSITY = 182
    SO_ROOM_SHADOW = 183
    SO_SAVE_STRING = 184
    SO_LOAD_STRING = 185
    SO_ROOM_TRANSFORM = 186
    SO_CYCLE_SPEED = 187

    SO_VERB_INIT = 196
    SO_ACTOR_INIT = 197
    SO_ACTOR_VARIABLE = 198
    SO_INT_ARRAY = 199
    SO_BIT_ARRAY = 200
    SO_NIBBLE_ARRAY = 201
    SO_BYTE_ARRAY = 202
    SO_STRING_ARRAY = 203
    SO_UNDIM_ARRAY = 204
    SO_ASSIGN_STRING = 205

    SO_ASSIGN_INT_LIST = 208

    SO_ASSIGN_2DIM_LIST = 212
    SO_ROOM_NEW_PALETTE = 213
    SO_CURSOR_TRANSPARENT = 214
    SO_ACTOR_IGNORE_TURNS_ON = 215
    SO_ACTOR_IGNORE_TURNS_OFF = 216
    SO_NEW = 217

    SO_ALWAYS_ZCLIP_FT_DEMO = 225
    SO_WAIT_FOR_ANIMATION = 226
    SO_ACTOR_DEPTH = 227
    SO_ACTOR_WALK_SCRIPT = 228
    SO_ACTOR_STOP = 229

    SO_ACTOR_FACE = 230
    SO_ACTOR_TURN = 231
    SO_WAIT_FOR_TURN = 232
    SO_ACTOR_WALK_PAUSE = 233
    SO_ACTOR_WALK_RESUME = 234
    SO_ACTOR_TALK_SCRIPT = 235

    SO_BASEOP = 254
    SO_END = 255


class SubOpsV8(IntEnum):
    SO_INT_ARRAY = 10  # SO_ARRAY_SCUMMVAR
    SO_STRING_ARRAY = 11  # SO_ARRAY_STRING
    SO_UNDIM_ARRAY = 12  # SO_ARRAY_UNDIM

    SO_ASSIGN_STRING = 20
    SO_ASSIGN_INT_LIST = 21  # SO_ASSIGN_SCUMMVAR_LIST
    SO_ASSIGN_2DIM_LIST = 22

    SO_WAIT_FOR_ACTOR = 30
    SO_WAIT_FOR_MESSAGE = 31
    SO_WAIT_FOR_CAMERA = 32
    SO_WAIT_FOR_SENTENCE = 33
    SO_WAIT_FOR_ANIMATION = 34
    SO_WAIT_FOR_TURN = 35

    SO_RESTART = 40  # SO_SYSTEM_RESTART
    SO_QUIT = 41  # SO_SYSTEM_QUIT

    SO_CAMERA_PAUSE = 50
    SO_CAMERA_RESUME = 51

    SO_HEAP_LOAD_CHARSET = 60
    SO_HEAP_LOAD_COSTUME = 61
    SO_HEAP_LOAD_OBJECT = 62
    SO_HEAP_LOAD_ROOM = 63
    SO_HEAP_LOAD_SCRIPT = 64
    SO_HEAP_LOAD_SOUND = 65
    SO_HEAP_LOCK_COSTUME = 66
    SO_HEAP_LOCK_ROOM = 67
    SO_HEAP_LOCK_SCRIPT = 68
    SO_HEAP_LOCK_SOUND = 69
    SO_HEAP_UNLOCK_COSTUME = 70
    SO_HEAP_UNLOCK_ROOM = 71
    SO_HEAP_UNLOCK_SCRIPT = 72
    SO_HEAP_UNLOCK_SOUND = 73
    SO_HEAP_NUKE_COSTUME = 74
    SO_HEAP_NUKE_ROOM = 75
    SO_HEAP_NUKE_SCRIPT = 76
    SO_HEAP_NUKE_SOUND = 77

    SO_ROOM_PALETTE = 82

    SO_ROOM_FADE = 87
    SO_ROOM_RGB_INTENSITY = 88
    SO_ROOM_TRANSFORM = 89

    SO_ROOM_NEW_PALETTE = 92
    SO_ROOM_SAVE_GAME = 93
    SO_ROOM_LOAD_GAME = 94
    SO_ROOM_SATURATION = 95

    SO_COSTUME = 100
    SO_STEP_DIST = 101

    SO_ANIMATION_DEFAULT = 103  # SO_ACTOR_ANIMATION_DEFAULT
    SO_INIT_ANIMATION = 104  # SO_ACTOR_ANIMATION_INIT
    SO_TALK_ANIMATION = 105  # SO_ACTOR_ANIMATION_TALK
    SO_WALK_ANIMATION = 106  # SO_ACTOR_ANIMATION_WALK
    SO_STAND_ANIMATION = 107  # SO_ACTOR_ANIMATION_STAND
    SO_ANIMATION_SPEED = 108  # SO_ACTOR_ANIMATION_SPEED
    SO_DEFAULT = 109  # SO_ACTOR_DEFAULT
    SO_ELEVATION = 110  # SO_ACTOR_ELEVATION
    SO_PALETTE = 111  # SO_ACTOR_PALETTE
    SO_TALK_COLOR = 112  # SO_ACTOR_TALK_COLOR
    SO_ACTOR_NAME = 113
    SO_ACTOR_WIDTH = 114
    SO_SCALE = 115  # SO_ACTOR_SCALE
    SO_NEVER_ZCLIP = 116  # SO_ACTOR_NEVER_ZCLIP
    SO_ALWAYS_ZCLIP = 117  # SO_ACTOR_ALWAYS_ZCLIP
    SO_IGNORE_BOXES = 118  # SO_ACTOR_IGNORE_BOXES
    SO_FOLLOW_BOXES = 119  # SO_ACTOR_FOLLOW_BOXES
    SO_SHADOW = 120  # SO_ACTOR_SPECIAL_DRAW
    SO_TEXT_OFFSET = 121  # SO_ACTOR_TEXT_OFFSET
    SO_ACTOR_INIT = 122
    SO_ACTOR_VARIABLE = 123
    SO_ACTOR_IGNORE_TURNS_ON = 124
    SO_ACTOR_IGNORE_TURNS_OFF = 125
    SO_NEW = 126  # SO_ACTOR_NEW
    SO_ACTOR_DEPTH = 127
    SO_ACTOR_STOP = 128
    SO_ACTOR_FACE = 129
    SO_ACTOR_TURN = 130
    SO_ACTOR_WALK_SCRIPT = 131
    SO_ACTOR_TALK_SCRIPT = 132
    SO_ACTOR_WALK_PAUSE = 133
    SO_ACTOR_WALK_RESUME = 134
    SO_ACTOR_VOLUME = 135
    SO_ACTOR_FREQUENCY = 136
    SO_ACTOR_PAN = 137

    SO_VERB_INIT = 150
    SO_VERB_NEW = 151
    SO_VERB_DELETE = 152
    SO_VERB_NAME = 153
    SO_VERB_AT = 154
    SO_VERB_ON = 155
    SO_VERB_OFF = 156
    SO_VERB_COLOR = 157
    SO_VERB_HICOLOR = 158

    SO_VERB_DIMCOLOR = 160
    SO_VERB_DIM = 161
    SO_VERB_KEY = 162
    SO_VERB_IMAGE = 163
    SO_VERB_NAME_STR = 164
    SO_VERB_CENTER = 165
    SO_VERB_CHARSET = 166
    SO_VERB_LINE_SPACING = 167

    SO_SAVE_VERBS = 180  # SO_VERBS_SAVE
    SO_RESTORE_VERBS = 181  # SO_VERBS_RESTORE
    SO_DELETE_VERBS = 182  # SO_VERBS_DELETE

    SO_BASEOP = 200  # SO_PRINT_BASEOP
    SO_END = 201  # SO_PRINT_END
    SO_AT = 202  # SO_PRINT_AT
    SO_COLOR = 203  # SO_PRINT_COLOR
    SO_CENTER = 204  # SO_PRINT_CENTER
    SO_PRINT_CHARSET = 205
    SO_LEFT = 206  # SO_PRINT_LEFT
    SO_OVERHEAD = 207  # SO_PRINT_OVERHEAD
    SO_MUMBLE = 208  # SO_PRINT_MUMBLE
    SO_PRINT_STRING = 209
    SO_PRINT_WRAP = 210

    SO_CURSOR_ON = 220
    SO_CURSOR_OFF = 221
    SO_CURSOR_SOFT_ON = 222
    SO_CURSOR_SOFT_OFF = 223
    SO_USERPUT_ON = 224
    SO_USERPUT_OFF = 225
    SO_USERPUT_SOFT_ON = 226
    SO_USERPUT_SOFT_OFF = 227
    SO_CURSOR_IMAGE = 228
    SO_CURSOR_HOTSPOT = 229
    SO_CURSOR_TRANSPARENT = 230
    SO_CHARSET_SET = 231
    SO_CHARSET_COLOR = 232
    SO_CURSOR_PUT = 233


def IMBYTE(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream),)

def IMWORD(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (WordValue(stream),)

def IMDWORD(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (DWordValue(stream),)

def extended_w_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (WordValue(stream),)


def extended_ww_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (WordValue(stream), WordValue(stream))


def extended_dw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (DWordValue(stream),)


def extended_ddw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (DWordValue(stream), DWordValue(stream))


def extended_bw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream), WordValue(stream))


def extended_bdw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream), DWordValue(stream))

def OFFSET(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (RefOffset(stream),)

def DOFFSET(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (RefOffset(stream, word_size=4),)

def MSG_OP(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream),)


def msg_cmd(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {75, 194}:
        return (cmd, CString(stream))
    return (cmd,)


def msg_cmd_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {209}:
        return (cmd, CString(stream, var_size=4))
    return (cmd,)


def msg_cmd_he100(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {35, 79}:
        return (cmd, CString(stream))
    return (cmd,)


def actor_ops_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {0x71}:
        return (cmd, CString(stream, var_size=4))
    return (cmd,)


def actor_ops_v6(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {0x58}:
        return (cmd, CString(stream))
    return (cmd,)


def verb_ops_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {0x99, 0xA4}:
        return (cmd, CString(stream, var_size=4))
    return (cmd,)


def verb_ops_v6(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {0x7D}:
        return (cmd, CString(stream))
    return (cmd,)


def array_ops(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    arr = WordValue(stream)
    if ord(cmd.op) in {127}:
        return (cmd, arr, WordValue(stream))
    if ord(cmd.op) in {138}:
        return (cmd, arr, WordValue(stream), WordValue(stream))
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd, arr)


def room_ops_he60(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {221}:
        return (cmd, CString(stream))
    return (cmd,)


def actor_ops_he60(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {225}:
        return (cmd, CString(stream))
    return (cmd,)


def array_ops_v6(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    arr = WordValue(stream)
    if ord(cmd.op) in {205}:
        return (cmd, arr, CString(stream))
    return (cmd, arr)


def array_ops_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    arr = DWordValue(stream)
    if ord(cmd.op) in {0x14}:
        return (cmd, arr, CString(stream, var_size=4))
    return (cmd, arr)


def array_ops_he100(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    arr = WordValue(stream)
    # if ord(cmd.op) in {35}:
    #     return (cmd, arr, CString(stream))
    if ord(cmd.op) in {131}:
        return (cmd, arr, WordValue(stream))
    if ord(cmd.op) in {132}:
        return (cmd, arr, WordValue(stream), WordValue(stream))
    return (cmd, arr)


def wait_ops(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {168, 226, 232}:
        return (cmd, RefOffset(stream))
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd,)


def wait_ops_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {30, 34, 35}:
        return (cmd, RefOffset(stream, word_size=4))
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd,)


def wait_ops_he100(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {128}:
        return (cmd, RefOffset(stream))
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd,)


def file_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {8}:
        return (cmd, ByteValue(stream))
    return (cmd,)


def file_op_he100(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {5}:
        return (cmd, ByteValue(stream))
    return (cmd,)


def msg_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream),)


def sys_msg(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream), CString(stream))


def dmsg_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream), CString(stream))


def ini_op_v71(stream: IO[bytes]) -> Iterable[ScriptArg]:
    # HACK: The arguments for o70_writeINI are different depending on
    # what type of value it is.  If it's a number type (1), then only
    # the option string follows (as the value is stored in the stack).
    # But both the option and value string follows if it's a string type (2).
    #
    # So what I've done to temporary seek the bytecode stream back and read
    # the type (as a WORD) and seek back when we are done.
    #
    # Very hacky solution, but it works for the most part.
    stream.seek(-3, 1)  # seek -3 from current position
    type = ord(stream.read(1))
    stream.seek(2, 1)  # seek back to where it was.
    if type == 1:
        return (CString(stream),)
    elif type == 2:
        return (CString(stream), CString(stream))
    else:
        raise ValueError(type)


def msg_op_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream, var_size=4),)


def makeop(
    name: str,
    *ops: Iterable[Callable[[IO[bytes]], Iterable[ScriptArg]]],
) -> Callable[[int, IO[bytes]], Statement]:
    return partial(Statement.parse, name, ops)

def SUBOP_R(mapping: Mapping[int, Callable[[IO[bytes]], Iterable[ScriptArg]]]) -> Callable[[IO[bytes]], Iterable[ScriptArg]]:
    def subop(stream: IO[bytes]) -> Iterable[ScriptArg]:
        cmd = ByteValue(stream)
        return (mapping[ord(cmd.op)](ord(cmd.op), stream),)
    return subop

def SUBOP(subs, mapping=None):
    if mapping is None:
        mapping = {}
    def subop(stream: IO[bytes]) -> Iterable[ScriptArg]:
        cmd = ByteValue(stream)
        op = ord(cmd.op)
        name = subs(op).name
        factory = makeop(name, *mapping.get(op, ()))
        return (factory(op, stream),)
    return subop


OPCODES_v6: OpTable = realize({
    0x00: makeop('o6_pushByte', IMBYTE),
    0x01: makeop('o6_pushWord', IMWORD),
    0x02: makeop('o6_pushByteVar', IMBYTE),
    0x03: makeop('o6_pushWordVar', IMWORD),
    # TODO: 0x06: makeop('o6_byteArrayRead'),
    0x07: makeop('o6_wordArrayRead', IMWORD),
    0x0A: makeop('o6_byteArrayIndexedRead', IMBYTE),
    0x0B: makeop('o6_wordArrayIndexedRead', IMWORD),
    0x0C: makeop('o6_dup'),
    0x0D: makeop('o6_not'),
    0x0E: makeop('o6_eq'),
    0x0F: makeop('o6_neq'),
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
    0x1A: makeop('o6_pop'),
    # TODO: 0x42: makeop('o6_writeByteVar'),
    0x43: makeop('o6_writeWordVar', IMWORD),
    # TODO: 0x46: makeop('o6_byteArrayWrite'),
    0x47: makeop('o6_wordArrayWrite', IMWORD),
    # TODO: 0x4a: makeop('o6_byteArrayIndexedWrite'),
    0x4B: makeop('o6_wordArrayIndexedWrite', IMWORD),
    # TODO: 0x4e: makeop('o6_byteVarInc'),
    0x4F: makeop('o6_wordVarInc', IMWORD),
    # TODO: 0x52: makeop('o6_byteArrayInc'),
    0x53: makeop('o6_wordArrayInc', IMWORD),
    # TODO: 0x56: makeop('o6_byteVarDec'),
    0x57: makeop('o6_wordVarDec', IMWORD),
    # TODO: 0x5a: makeop('o6_byteArrayDec'),
    0x5B: makeop('o6_wordArrayDec', IMWORD),
    0x5C: makeop('o6_if', OFFSET),  # jump if
    0x5D: makeop('o6_ifNot', OFFSET),  # jump if not
    0x5E: makeop('o6_startScript'),
    0x5F: makeop('o6_startScriptQuick'),
    0x60: makeop('o6_startObject'),
    0x61: makeop('o6_drawObject'),
    0x62: makeop('o6_drawObjectAt'),
    0x63: makeop('o6_drawBlastObject'),
    0x64: makeop('o6_setBlastObjectWindow'),
    0x65: makeop('o6_stopObjectCodeObject'),  # o6_stopObjectCode
    0x66: makeop('o6_stopObjectCodeScript'),  # o6_stopObjectCode
    0x67: makeop('o6_endCutscene'),
    0x68: makeop('o6_cutscene'),
    # TODO: 0x69: makeop('o6_stopMusic'),
    0x6A: makeop('o6_freezeUnfreeze'),
    0x6B: makeop('o6_cursorCommand', SUBOP(SubOpsV6)),
    0x6C: makeop('o6_breakHere'),
    0x6D: makeop('o6_ifClassOfIs'),
    0x6E: makeop('o6_setClass'),
    0x6F: makeop('o6_getState'),
    0x70: makeop('o6_setState'),
    0x71: makeop('o6_setOwner'),
    0x72: makeop('o6_getOwner'),
    0x73: makeop('o6_jump', OFFSET),
    0x74: makeop('o6_startSound'),
    0x75: makeop('o6_stopSound'),
    # TODO: 0x76: makeop('o6_startMusic'),
    0x77: makeop('o6_stopObjectScript'),
    0x78: makeop('o6_panCameraTo'),
    0x79: makeop('o6_actorFollowCamera'),
    0x7A: makeop('o6_setCameraAt'),
    0x7B: makeop('o6_loadRoom'),
    0x7C: makeop('o6_stopScript'),
    0x7D: makeop('o6_walkActorToObj'),
    0x7E: makeop('o6_walkActorTo'),
    0x7F: makeop('o6_putActorAtXY'),
    0x80: makeop('o6_putActorAtObject'),
    0x81: makeop('o6_faceActor'),
    0x82: makeop('o6_animateActor'),
    0x83: makeop('o6_doSentence'),
    0x84: makeop('o6_pickupObject'),
    0x85: makeop('o6_loadRoomWithEgo'),
    0x87: makeop('o6_getRandomNumber'),
    0x88: makeop('o6_getRandomNumberRange'),
    0x8A: makeop('o6_getActorMoving'),
    0x8B: makeop('o6_isScriptRunning'),
    0x8C: makeop('o6_getActorRoom'),
    0x8D: makeop('o6_getObjectX'),
    0x8E: makeop('o6_getObjectY'),
    0x8F: makeop('o6_getObjectOldDir'),
    0x90: makeop('o6_getActorWalkBox'),
    0x91: makeop('o6_getActorCostume'),
    0x92: makeop('o6_findInventory'),
    0x93: makeop('o6_getInventoryCount'),
    0x94: makeop('o6_getVerbFromXY'),
    0x95: makeop('o6_beginOverride'),
    0x96: makeop('o6_endOverride'),
    0x97: makeop('o6_setObjectName', MSG_OP),
    0x98: makeop('o6_isSoundRunning'),
    0x99: makeop('o6_setBoxFlags'),
    0x9A: makeop('o6_createBoxMatrix'),
    0x9B: makeop('o6_resourceRoutines', SUBOP(SubOpsV6)),
    0x9C: makeop('o6_roomOps', SUBOP(SubOpsV6)),
    0x9D: makeop('o6_actorOps', SUBOP(SubOpsV6, {
        SubOpsV6.SO_ACTOR_NAME: (MSG_OP,),
    })),
    0x9E: makeop('o6_verbOps', SUBOP(SubOpsV6, {
        SubOpsV6.SO_VERB_NAME: (MSG_OP,),
    })),
    0x9F: makeop('o6_getActorFromXY'),
    0xA0: makeop('o6_findObject'),
    0xA1: makeop('o6_pseudoRoom'),
    0xA2: makeop('o6_getActorElevation'),
    0xA3: makeop('o6_getVerbEntrypoint'),
    0xA4: makeop('o6_arrayOps', SUBOP(SubOpsV6, {
        SubOpsV6.SO_ASSIGN_STRING: (IMWORD, MSG_OP),
        SubOpsV6.SO_ASSIGN_INT_LIST: (IMWORD,),
        SubOpsV6.SO_ASSIGN_2DIM_LIST: (IMWORD,),
    })),
    0xA5: makeop('o6_saveRestoreVerbs', SUBOP(SubOpsV6)),
    0xA6: makeop('o6_drawBox'),
    0xA7: makeop('o6_pop'),
    0xA8: makeop('o6_getActorWidth'),
    0xA9: makeop('o6_wait', wait_ops),
    0xAA: makeop('o6_getActorScaleX'),
    0xAB: makeop('o6_getActorAnimCounter'),
    0xAC: makeop('o6_soundKludge'),
    0xAD: makeop('o6_isAnyOf'),
    0xAE: makeop('o6_systemOps', extended_b_op),
    0xAF: makeop('o6_isActorInBox'),
    0xB0: makeop('o6_delay'),
    0xB1: makeop('o6_delaySeconds'),
    0xB2: makeop('o6_delayMinutes'),
    0xB3: makeop('o6_stopSentence'),
    0xB4: makeop('o6_printLine', msg_cmd),
    0xB5: makeop('o6_printText', msg_cmd),
    0xB6: makeop('o6_printDebug', msg_cmd),
    0xB7: makeop('o6_printSystem', msg_cmd),
    0xB8: makeop('o6_printActor', msg_cmd),
    0xB9: makeop('o6_printEgo', msg_cmd),
    0xBA: makeop('o6_talkActor', msg_op),
    0xBB: makeop('o6_talkEgo', msg_op),
    0xBC: makeop('o6_dimArray', extended_bw_op),
    0xBD: makeop('o6_dummy'),
    0xBE: makeop('o6_startObjectQuick'),
    0xBF: makeop('o6_startScriptQuick2'),
    0xC0: makeop('o6_dim2dimArray', extended_bw_op),
    0xC4: makeop('o6_abs'),
    0xC5: makeop('o6_distObjectObject'),
    # TODO: 0xc6: makeop('o6_distObjectPt'),
    0xC7: makeop('o6_distPtPt'),
    0xC8: makeop('o6_kernelGetFunctions'),
    0xC9: makeop('o6_kernelSetFunctions'),
    0xCA: makeop('o6_delayFrames'),
    0xCB: makeop('o6_pickOneOf'),
    0xCC: makeop('o6_pickOneOfDefault'),
    0xCD: makeop('o6_stampObject'),
    0xD0: makeop('o6_getDateTime'),
    0xD1: makeop('o6_stopTalking'),
    0xD2: makeop('o6_getAnimateVariable'),
    0xD4: makeop('o6_shuffle', extended_w_op),
    0xD5: makeop('o6_jumpToScript'),
    0xD6: makeop('o6_band'),  # bitwise and
    0xD7: makeop('o6_bor'),  # bitwise or
    0xD8: makeop('o6_isRoomScriptRunning'),
    0xDD: makeop('o6_findAllObjects'),
    0xE1: makeop('o6_getPixel'),
    0xE3: makeop('o6_pickVarRandom', extended_w_op),
    0xE4: makeop('o6_setBoxSet', extended_b_op),
    0xEC: makeop('o6_getActorLayer'),
    0xED: makeop('o6_getObjectNewDir'),
})

OPCODES_he60 = realize(
    {
        **OPCODES_v6,
        0x63: None,
        0x64: None,
        0x70: makeop('o60_setState'),
        0x9A: None,
        0x9C: makeop('o60_roomOps', room_ops_he60),
        0x9D: makeop('o60_actorOps', actor_ops_he60),
        0xAC: None,
        0xBD: makeop('o6_stopObjectCodeReturn'),
        0xC8: makeop('o60_kernelGetFunctions'),
        0xC9: makeop('o60_kernelSetFunctions'),
        0xD9: makeop('o60_closeFile'),
        0xDA: makeop('o60_openFile', msg_op),
        0xDB: makeop('o60_readFile'),
        0xDC: makeop('o60_writeFile'),
        0xDE: makeop('o60_deleteFile', msg_op),
        0xDF: makeop('o60_rename', dmsg_op),
        0xE0: makeop('o60_soundOps', extended_b_op),
        0xE2: makeop('o60_localizeArrayToScript'),
        0xE9: makeop('o60_seekFilePos'),
        0xEA: makeop('o60_redimArray', extended_bw_op),
        0xEB: makeop('o60_readFilePos'),
        0xEC: None,
        0xED: None,
    },
)

OPCODES_he70: OpTable = realize(
    {
        **OPCODES_he60,
        0x74: makeop('o70_soundOps', extended_b_op),
        0x84: makeop('o70_pickupObject'),
        0x8C: makeop('o70_getActorRoom'),
        0x9B: makeop('o70_resourceRoutines', extended_b_op),
        0xAE: makeop('o70_systemOps', extended_b_op),
        0xEE: makeop('o70_getStringLen'),
        0xF2: makeop('o70_isResourceLoaded', extended_b_op),
        0xF3: makeop('o70_readINI', msg_op),
        0xF4: makeop('o70_writeINI', ini_op_v71),
        0xF9: makeop('o70_createDirectory', msg_op),
        0xFA: makeop('o70_setSystemMessage', sys_msg),
    },
)

OPCODES_he71: OpTable = realize(
    {
        **OPCODES_he70,
        0xC9: makeop('o71_kernelSetFunctions'),
        0xEC: makeop('o71_copyString'),
        0xED: makeop('o71_getStringWidth'),
        0xEF: makeop('o71_appendString'),
        0xF0: makeop('o71_concatString'),
        0xF1: makeop('o71_compareString'),
        0xF5: makeop('o71_getStringLenForWidth'),
        0xF6: makeop('o71_getCharIndexInString'),
        0xF7: makeop('o71_findBox'),
        0xFB: makeop('o71_polygonOps', extended_b_op),
        0xFC: makeop('o71_polygonHit'),
    },
)

OPCODES_he72: OpTable = realize(
    {
        **OPCODES_he71,
        0x02: makeop('o72_pushDWord', extended_dw_op),
        0x04: makeop('o72_getScriptString', msg_op),
        0x0A: None,
        0x1B: makeop('o72_isAnyOf'),
        0x42: None,
        0x46: None,
        0x4A: None,
        0x4E: None,
        0x50: makeop('o72_resetCutscene'),
        0x51: makeop('o72_getHeap', extended_b_op),
        0x52: makeop('o72_findObjectWithClassOf'),
        0x54: makeop('o72_getObjectImageX'),
        0x55: makeop('o72_getObjectImageY'),
        0x56: makeop('o72_captureWizImage'),
        0x58: makeop('o72_getTimer', extended_b_op),
        0x59: makeop('o72_setTimer', extended_b_op),
        0x5A: makeop('o72_getSoundPosition'),
        0x5E: makeop('o72_startScript', extended_b_op),
        0x60: makeop('o72_startObject', extended_b_op),
        0x61: makeop('o72_drawObject', extended_b_op),
        0x62: makeop('o72_printWizImage'),
        0x63: makeop('o72_getArrayDimSize', extended_bw_op),
        0x64: makeop('o72_getNumFreeArrays'),
        0x97: None,
        0x9C: makeop('o72_roomOps', extended_b_op),
        0x9D: makeop('o72_actorOps', extended_b_op),
        0x9E: makeop('o72_verbOps', extended_b_op),
        # TODO: 0xa0: makeop('o72_findObject'),
        0xA4: makeop('o72_arrayOps', array_ops),
        0xAE: makeop('o72_systemOps', extended_b_op),
        0xBA: makeop('o72_talkActor', msg_op),
        0xBB: makeop('o72_talkEgo', msg_op),
        0xBC: makeop('o72_dimArray', extended_bw_op),
        0xC0: makeop('o72_dim2dimArray', extended_bw_op),
        0xC1: makeop('o72_traceStatus'),
        0xC8: makeop('o72_kernelGetFunctions'),
        0xCE: makeop('o72_drawWizImage'),
        0xCF: makeop('o72_debugInput'),
        0xD5: makeop('o72_jumpToScript', extended_b_op),
        0xDA: makeop('o72_openFile'),
        0xDB: makeop('o72_readFile', file_op),
        0xDC: makeop('o72_writeFile', file_op),
        0xDD: makeop('o72_findAllObjects'),
        0xDE: makeop('o72_deleteFile'),
        0xDF: makeop('o72_rename'),
        0xE1: makeop('o72_getPixel', extended_b_op),
        # TODO: 0xe3: makeop('o72_pickVarRandom'),
        0xEA: makeop('o72_redimArray', extended_bw_op),
        0xF3: makeop('o72_readINI', extended_b_op),
        0xF4: makeop('o72_writeINI', extended_b_op),
        0xF8: makeop('o72_getResourceSize'),
        0xF9: makeop('o72_createDirectory'),
        0xFA: makeop('o72_setSystemMessage', extended_b_op),
    },
)

OPCODES_he73: OpTable = realize(
    {
        **OPCODES_he72,
        0xF8: makeop('o73_getResourceSize', extended_b_op),
    },
)

OPCODES_he80: OpTable = realize(
    {
        **OPCODES_he73,
        0x45: makeop('o80_createSound', extended_b_op),
        0x46: makeop('o80_getFileSize'),
        0x48: makeop('o80_stringToInt'),
        0x49: makeop('o80_getSoundVar'),
        0x4A: makeop('o80_localizeArrayToRoom'),
        # TODO: 0x4C: makeop('o80_sourceDebug'),
        0x4D: makeop('o80_readConfigFile', extended_b_op),
        0x4E: makeop('o80_writeConfigFile', extended_b_op),
        0x69: None,
        0x6B: makeop('o80_cursorCommand', extended_b_op),
        0x70: makeop('o80_setState'),
        0x76: None,
        0x94: None,
        0x9E: None,
        0xA5: None,
        0xAC: makeop('o80_drawWizPolygon'),
        0xE0: makeop('o80_drawLine', extended_b_op),
        0xE3: makeop('o80_pickVarRandom', extended_w_op),
    },
)

OPCODES_he90: OpTable = realize(
    {
        **OPCODES_he80,
        0x0A: makeop('o90_dup_n', extended_w_op),
        0x1C: makeop('o90_wizImageOps', extended_b_op),
        0x1D: makeop('o90_min'),
        0x1E: makeop('o90_max'),
        0x1F: makeop('o90_sin'),
        0x20: makeop('o90_cos'),
        0x21: makeop('o90_sqrt'),
        0x22: makeop('o90_atan2'),
        0x23: makeop('o90_getSegmentAngle'),
        0x24: makeop('o90_getDistanceBetweenPoints', extended_b_op),
        0x25: makeop('o90_getSpriteInfo', extended_b_op),
        0x26: makeop('o90_setSpriteInfo', extended_b_op),
        0x27: makeop('o90_getSpriteGroupInfo', extended_b_op),
        0x28: makeop('o90_setSpriteGroupInfo', extended_b_op),
        0x29: makeop('o90_getWizData', extended_b_op),
        0x2A: makeop('o90_getActorData'),
        0x2B: makeop('o90_startScriptUnk', extended_b_op),
        0x2C: makeop('o90_jumpToScriptUnk', extended_b_op),
        0x2D: makeop('o90_videoOps', extended_b_op),
        0x2E: makeop('o90_getVideoData', extended_b_op),
        0x2F: makeop('o90_floodFill', extended_b_op),
        0x30: makeop('o90_mod'),
        0x31: makeop('o90_shl'),
        0x32: makeop('o90_shr'),
        0x33: makeop('o90_xor'),
        0x34: makeop('o90_findAllObjectsWithClassOf'),
        0x35: makeop('o90_getPolygonOverlap'),
        0x36: makeop('o90_cond'),
        0x37: makeop('o90_dim2dim2Array', extended_bw_op),
        0x38: makeop('o90_redim2dimArray', extended_bw_op),
        0x39: makeop('o90_getLinesIntersectionPoint', extended_ww_op),
        0x3A: makeop('o90_sortArray', extended_bw_op),
        0x44: makeop('o90_getObjectData', extended_b_op),
        0x69: makeop('o90_disabled_windowOps', extended_b_op),
        0x94: makeop('o90_getPaletteData', extended_b_op),
        0x9E: makeop('o90_paletteOps', extended_b_op),
        0xA5: makeop('o90_fontEnum', extended_b_op),
        # TODO: 0xab: makeop('o90_getActorAnimProgress'),
        # TODO: 0xc8: makeop('o90_kernelGetFunctions'),
        # TODO: 0xc9: makeop('o90_kernelSetFunctions'),,
    }
)

OPCODES_he100: OpTable = realize(
    {
        0x00: makeop('o100_actorOps', extended_b_op),
        0x01: makeop('o6_add'),
        0x02: makeop('o6_faceActor'),
        0x03: makeop('o90_sortArray', extended_bw_op),
        0x04: makeop('o100_arrayOps', array_ops_he100),
        0x05: makeop('o6_band'),
        0x06: makeop('o6_bor'),
        0x07: makeop('o6_breakHere'),
        0x08: makeop('o6_delayFrames'),
        0x09: makeop('o90_shl'),
        0x0A: makeop('o90_shr'),
        0x0B: makeop('o90_xor'),
        0x0C: makeop('o6_setCameraAt'),
        0x0D: makeop('o6_actorFollowCamera'),
        0x0E: makeop('o6_loadRoom'),
        # TODO: 0x0f: makeop('o6_panCameraTo'),
        # TODO: 0x10: makeop('o72_captureWizImage'),
        0x11: makeop('o100_jumpToScript', extended_b_op),
        0x12: makeop('o6_setClass'),
        0x13: makeop('o60_closeFile'),
        # TODO: 0x14: makeop('o6_loadRoomWithEgo'),
        0x16: makeop('o72_createDirectory'),
        0x17: makeop('o100_createSound', extended_b_op),
        # TODO: 0x18: makeop('o6_cutscene'),
        0x19: makeop('o6_pop'),
        0x1A: makeop('o72_traceStatus'),
        0x1B: makeop('o6_wordVarDec', extended_w_op),
        0x1C: makeop('o6_wordArrayDec', extended_w_op),
        0x1D: makeop('o72_deleteFile'),
        0x1E: makeop('o100_dim2dimArray', extended_bw_op),
        0x1F: makeop('o100_dimArray', extended_bw_op),
        0x20: makeop('o6_div'),
        0x21: makeop('o6_animateActor'),
        # TODO: 0x22: makeop('o6_doSentence'),
        0x23: makeop('o6_drawBox'),
        # TODO: 0x24: makeop('o72_drawWizImage'),
        # TODO: 0x25: makeop('o80_drawWizPolygon'),
        0x26: makeop('o100_drawLine', extended_b_op),
        0x27: makeop('o100_drawObject', extended_b_op),
        0x28: makeop('o6_dup'),
        0x29: makeop('o90_dup_n', extended_w_op),
        # TODO: 0x2a: makeop('o6_endCutscene'),
        0x2B: makeop('o6_stopObjectCodeObject'),  # o6_stopObjectCode
        0x2C: makeop('o6_stopObjectCodeScript'),  # o6_stopObjectCode
        0x2D: makeop('o6_eq'),
        # TODO: 0x2e: makeop('o100_floodFill'),
        # TODO: 0x2f: makeop('o6_freezeUnfreeze'),
        0x30: makeop('o6_ge'),
        0x31: makeop('o6_getDateTime'),
        0x32: makeop('o100_setSpriteGroupInfo', extended_b_op),
        0x33: makeop('o6_gt'),
        0x34: makeop('o100_resourceRoutines', extended_b_op),
        0x35: makeop('o6_if', OFFSET),
        0x36: makeop('o6_ifNot', OFFSET),
        0x37: makeop('o100_wizImageOps', extended_b_op),
        0x38: makeop('o72_isAnyOf'),
        0x39: makeop('o6_wordVarInc', extended_w_op),
        0x3A: makeop('o6_wordArrayInc', extended_w_op),
        0x3B: makeop('o6_jump', OFFSET),
        0x3C: makeop('o90_kernelSetFunctions'),
        0x3D: makeop('o6_land'),
        0x3E: makeop('o6_le'),
        0x3F: makeop('o60_localizeArrayToScript'),
        0x40: makeop('o6_wordArrayRead', extended_w_op),
        0x41: makeop('o6_wordArrayIndexedRead', extended_w_op),
        0x42: makeop('o6_lor'),
        0x43: makeop('o6_lt'),
        0x44: makeop('o90_mod'),
        0x45: makeop('o6_mul'),
        0x46: makeop('o6_neq'),
        0x47: makeop('o100_dim2dim2Array', extended_bw_op),
        0x49: makeop('o100_redim2dimArray', extended_bw_op),
        0x4A: makeop('o6_not'),
        0x4C: makeop('o6_beginOverride'),
        0x4D: makeop('o6_endOverride'),
        0x4E: makeop('o72_resetCutscene'),
        0x4F: makeop('o6_setOwner'),
        0x50: makeop('o100_paletteOps', extended_b_op),
        0x51: makeop('o70_pickupObject'),
        0x52: makeop('o100_polygonOps', extended_b_op),  # o71_polygonOps
        0x53: makeop('o6_pop'),
        0x54: makeop('o100_printDebug', msg_cmd_he100),  # o6_printDebug
        0x55: makeop('o72_printWizImage'),
        0x56: makeop('o100_printLine', msg_cmd_he100),  # o6_printLine
        0x57: makeop('o100_printSystem', msg_cmd_he100),  # o6_printSystem
        0x58: makeop('o100_printText', msg_cmd_he100),  # o6_printText
        # TODO: 0x59: makeop('o100_jumpToScriptUnk'),
        0x5A: makeop('o100_startScriptUnk', extended_b_op),
        # TODO: 0x5b: makeop('o6_pseudoRoom'),
        0x5C: makeop('o6_pushByte', extended_b_op),
        0x5D: makeop('o72_pushDWord', extended_dw_op),
        0x5E: makeop('o72_getScriptString', msg_op),
        0x5F: makeop('o6_pushWord', extended_w_op),
        0x60: makeop('o6_pushWordVar', extended_w_op),
        0x61: makeop('o6_putActorAtObject'),
        0x62: makeop('o6_putActorAtXY'),
        0x64: makeop('o100_redimArray', extended_bw_op),
        0x65: makeop('o72_rename'),
        0x66: makeop('o6_stopObjectCodeReturn'),  # o6_stopObjectCode
        # TODO: 0x67: makeop('o80_localizeArrayToRoom'),
        0x68: makeop('o100_roomOps', extended_b_op),
        0x69: makeop('o100_printActor', msg_cmd_he100),  # o6_printActor
        0x6A: makeop('o100_printEgo', msg_cmd_he100),  # o6_printEgo
        0x6B: makeop('o72_talkActor', msg_op),
        0x6C: makeop('o72_talkEgo', msg_op),
        0x6E: makeop('o60_seekFilePos'),
        0x6F: makeop('o6_setBoxFlags'),
        # TODO: 0x71: makeop('o6_setBoxSet'),
        0x72: makeop('o100_setSystemMessage', extended_b_op),
        0x73: makeop('o6_shuffle', extended_w_op),
        0x74: makeop('o6_delay'),
        # TODO: 0x75: makeop('o6_delayMinutes'),
        0x76: makeop('o6_delaySeconds'),
        0x77: makeop('o100_soundOps', extended_b_op),
        0x78: makeop('o80_sourceDebug', extended_ddw_op),
        0x79: makeop('o100_setSpriteInfo', extended_b_op),
        0x7A: makeop('o6_stampObject'),
        0x7B: makeop('o72_startObject', extended_b_op),
        0x7C: makeop('o100_startScript', extended_b_op),
        # TODO: 0x7d: makeop('o6_startScriptQuick'),
        0x7E: makeop('o80_setState'),
        0x7F: makeop('o6_stopObjectScript'),
        0x80: makeop('o6_stopScript'),
        0x81: makeop('o6_stopSentence'),
        0x82: makeop('o6_stopSound'),
        0x83: makeop('o6_stopTalking'),
        0x84: makeop('o6_writeWordVar', extended_w_op),
        0x85: makeop('o6_wordArrayWrite', extended_w_op),
        0x86: makeop('o6_wordArrayIndexedWrite', extended_w_op),
        0x87: makeop('o6_sub'),
        0x88: makeop('o100_systemOps', extended_b_op),
        0x8A: makeop('o72_setTimer', extended_b_op),
        0x8B: makeop('o100_cursorCommand', extended_b_op),
        0x8C: makeop('o100_videoOps', extended_b_op),
        0x8D: makeop('o100_wait', wait_ops_he100),
        # TODO: 0x8e: makeop('o6_walkActorToObj'),
        0x8F: makeop('o6_walkActorTo'),
        0x89: makeop('o100_disabled_windowOps', extended_b_op),
        0x90: makeop('o100_writeFile', file_op_he100),
        0x91: makeop('o72_writeINI', extended_b_op),
        0x92: makeop('o80_writeConfigFile', extended_b_op),
        0x93: makeop('o6_abs'),
        # TODO: 0x94: makeop('o6_getActorWalkBox'),
        0x95: makeop('o6_getActorCostume'),
        0x96: makeop('o6_getActorElevation'),
        0x97: makeop('o6_getObjectOldDir'),
        0x98: makeop('o6_getActorMoving'),
        0x99: makeop('o90_getActorData'),
        0x9A: makeop('o6_getActorRoom'),
        0x9B: makeop('o6_getActorScaleX'),
        0x9C: makeop('o6_getAnimateVariable'),
        # TODO: 0x9d: makeop('o6_getActorWidth'),
        0x9E: makeop('o6_getObjectX'),
        0x9F: makeop('o6_getObjectY'),
        0xA0: makeop('o90_atan2'),
        0xA1: makeop('o90_getSegmentAngle'),
        # TODO: 0xa2: makeop('o90_getActorAnimProgress'),
        0xA3: makeop('o90_getDistanceBetweenPoints', extended_b_op),
        0xA4: makeop('o6_ifClassOfIs'),
        0xA6: makeop('o90_cond'),
        0xA7: makeop('o90_cos'),
        0xA8: makeop('o100_debugInput', extended_b_op),
        0xA9: makeop('o80_getFileSize'),
        0xAA: makeop('o6_getActorFromXY'),
        0xAB: makeop('o72_findAllObjects'),
        0xAC: makeop('o90_findAllObjectsWithClassOf'),
        # TODO: 0xad: makeop('o71_findBox'),
        # TODO: 0xae: makeop('o6_findInventory'),
        0xAF: makeop('o72_findObject'),
        # TODO: 0xb0: makeop('o72_findObjectWithClassOf'),
        0xB1: makeop('o71_polygonHit'),
        # TODO: 0xb2: makeop('o90_getLinesIntersectionPoint'),
        0xB3: makeop('o90_fontEnum', extended_b_op),
        0xB4: makeop('o72_getNumFreeArrays'),
        0xB5: makeop('o72_getArrayDimSize', extended_bw_op),
        0xB6: makeop('o100_isResourceLoaded', extended_b_op),
        0xB7: makeop('o100_getResourceSize', extended_b_op),
        0xB8: makeop('o100_getSpriteGroupInfo', extended_b_op),
        0xB9: makeop('o100_getHeap', extended_b_op),
        0xBA: makeop('o100_getWizData', extended_b_op),
        # TODO: 0xbb: makeop('o6_isActorInBox'),
        0xBC: makeop('o6_isAnyOf'),
        # TODO: 0xbd: makeop('o6_getInventoryCount'),
        0xBE: makeop('o90_kernelGetFunctions'),
        0xBF: makeop('o90_max'),
        0xC0: makeop('o90_min'),
        0xC1: makeop('o72_getObjectImageX'),
        0xC2: makeop('o72_getObjectImageY'),
        0xC3: makeop('o6_isRoomScriptRunning'),
        # TODO: 0xc4: makeop('o90_getObjectData'),
        0xC5: makeop('o72_openFile'),
        0xC6: makeop('o90_getPolygonOverlap'),
        0xC7: makeop('o6_getOwner'),
        0xC8: makeop('o100_getPaletteData', extended_b_op),
        0xC9: makeop('o6_pickOneOf'),
        0xCA: makeop('o6_pickOneOfDefault'),
        0xCB: makeop('o80_pickVarRandom', extended_w_op),
        # TODO: 0xcc: makeop('o72_getPixel'),
        # TODO: 0xcd: makeop('o6_distObjectObject'),
        # TODO: 0xce: makeop('o6_distObjectPt'),
        # TODO: 0xcf: makeop('o6_distPtPt'),
        0xD0: makeop('o6_getRandomNumber'),
        0xD1: makeop('o6_getRandomNumberRange'),
        0xD3: makeop('o100_readFile', file_op_he100),
        0xD4: makeop('o72_readINI', extended_b_op),
        0xD5: makeop('o80_readConfigFile', extended_b_op),
        0xD6: makeop('o6_isScriptRunning'),
        0xD7: makeop('o90_sin'),
        0xD8: makeop('o72_getSoundPosition'),
        0xD9: makeop('o6_isSoundRunning'),
        # TODO: 0xda: makeop('o80_getSoundVar'),
        0xDB: makeop('o100_getSpriteInfo', extended_b_op),
        0xDC: makeop('o90_sqrt'),
        0xDD: makeop('o6_startObjectQuick'),
        0xDE: makeop('o6_startScriptQuick2'),
        0xDF: makeop('o6_getState'),
        0xE0: makeop('o71_compareString'),
        0xE1: makeop('o71_copyString'),
        0xE2: makeop('o71_appendString'),
        # TODO: 0xe3: makeop('o71_concatString'),
        0xE4: makeop('o70_getStringLen'),
        0xE5: makeop('o71_getStringLenForWidth'),
        0xE6: makeop('o80_stringToInt'),
        0xE7: makeop('o71_getCharIndexInString'),
        0xE8: makeop('o71_getStringWidth'),
        0xE9: makeop('o60_readFilePos'),
        0xEA: makeop('o72_getTimer', extended_b_op),
        0xEB: makeop('o6_getVerbEntrypoint'),
        0xEC: makeop('o100_getVideoData', extended_b_op),
    }
)

OPCODES_he101: OpTable = realize(
    {
        **OPCODES_he100,
        0xA8: makeop('o72_debugInput'),
    }
)

OPCODES_v8: OpTable = realize({
    0x01: makeop('o6_pushWord', IMDWORD),
    0x02: makeop('o6_pushWordVar', IMDWORD),
    0x03: makeop('o6_wordArrayRead', IMDWORD),
    0x04: makeop('o6_wordArrayIndexedRead', IMDWORD),
    0x05: makeop('o6_dup'),
    0x06: makeop('o6_pop'),
    0x07: makeop('o6_not'),
    0x08: makeop('o6_eq'),
    0x09: makeop('o6_neq'),
    0x0A: makeop('o6_gt'),
    0x0B: makeop('o6_lt'),
    0x0C: makeop('o6_le'),
    0x0D: makeop('o6_ge'),
    0x0E: makeop('o6_add'),
    0x0F: makeop('o6_sub'),
    0x10: makeop('o6_mul'),
    0x11: makeop('o6_div'),
    0x12: makeop('o6_land'),
    0x13: makeop('o6_lor'),
    0x14: makeop('o6_band'),
    0x15: makeop('o6_bor'),
    0x16: makeop('o8_mod'),
    0x64: makeop('o6_if'),
    0x65: makeop('o6_ifNot', DOFFSET),
    0x66: makeop('o6_jump', DOFFSET),
    0x67: makeop('o6_breakHere'),
    0x68: makeop('o6_delayFrames'),
    0x69: makeop('o8_wait', SUBOP(SubOpsV8, {
        SubOpsV8.SO_WAIT_FOR_ACTOR: (DOFFSET,),
        SubOpsV8.SO_WAIT_FOR_ANIMATION: (DOFFSET,),
        SubOpsV8.SO_WAIT_FOR_TURN: (DOFFSET,),
    })),
    0x6A: makeop('o6_delay'),
    0x6B: makeop('o6_delaySeconds'),
    0x6C: makeop('o6_delayMinutes'),
    0x6D: makeop('o6_writeWordVar', IMDWORD),
    0x6E: makeop('o6_wordVarInc', IMDWORD),
    0x6F: makeop('o6_wordVarDec', IMDWORD),
    0x70: makeop('o8_dimArray', extended_bdw_op),
    0x71: makeop('o6_wordArrayWrite', IMDWORD),
    0x72: makeop('o6_wordArrayInc', IMDWORD),
    0x73: makeop('o6_wordArrayDec', IMDWORD),
    0x74: makeop('o8_dim2dimArray', extended_bdw_op),
    0x75: makeop('o6_wordArrayIndexedWrite', IMDWORD),
    0x76: makeop('o8_arrayOps', array_ops_v8),
    0x79: makeop('o6_startScript'),
    0x7A: makeop('o6_startScriptQuick'),
    0x7B: makeop('o6_stopObjectCodeScript'),  # o6_stopObjectCode
    0x7C: makeop('o6_stopScript'),
    0x7D: makeop('o6_jumpToScript'),
    0x7E: makeop('o6_dummy'),
    0x7F: makeop('o6_startObject'),
    0x80: makeop('o6_stopObjectScript'),
    0x81: makeop('o6_cutscene'),
    0x82: makeop('o6_endCutscene'),
    0x83: makeop('o6_freezeUnfreeze'),
    0x84: makeop('o6_beginOverride'),
    0x85: makeop('o6_endOverride'),
    0x86: makeop('o6_stopSentence'),
    0x87: makeop('o8_debug'),
    0x89: makeop('o6_setClass'),
    0x8A: makeop('o6_setState'),
    0x8B: makeop('o6_setOwner'),
    0x8C: makeop('o6_panCameraTo'),
    0x8D: makeop('o6_actorFollowCamera'),
    0x8E: makeop('o6_setCameraAt'),
    0x8F: makeop('o8_printActor', msg_cmd_v8),  # o6_printActor
    0x90: makeop('o8_printEgo', msg_cmd_v8),  # o6_printEgo
    0x91: makeop('o8_talkActor', msg_op_v8),  # o6_talkActor
    0x92: makeop('o8_talkEgo', msg_op_v8),  # o6_talkEgo
    0x93: makeop('o8_printLine', msg_cmd_v8),  # o6_printLine
    0x94: makeop('o8_printText', msg_cmd_v8),  # o6_printText
    0x95: makeop('o8_printDebug', msg_cmd_v8),  # o6_printDebug
    0x96: makeop('o8_printSystem', msg_cmd_v8),  # o6_printSystem
    0x97: makeop('o8_blastText', msg_cmd_v8),
    0x98: makeop('o8_drawObject'),
    0x9C: makeop('o8_cursorCommand', extended_b_op),
    0x9D: makeop('o6_loadRoom'),
    0x9E: makeop('o6_loadRoomWithEgo'),
    0x9F: makeop('o6_walkActorToObj'),
    0xA0: makeop('o6_walkActorTo'),
    0xA1: makeop('o6_putActorAtXY'),
    0xA2: makeop('o6_putActorAtObject'),
    0xA3: makeop('o6_faceActor'),
    0xA4: makeop('o6_animateActor'),
    0xA5: makeop('o8_doSentence'),  # o6_doSentence
    0xA6: makeop('o6_pickupObject'),
    0xA7: makeop('o6_setBoxFlags'),
    0xA8: makeop('o6_createBoxMatrix'),
    0xAA: makeop('o8_resourceRoutines', extended_b_op),
    0xAB: makeop('o8_roomOps', extended_b_op),
    0xAC: makeop('o8_actorOps', actor_ops_v8),
    0xAD: makeop('o8_cameraOps', extended_b_op),
    0xAE: makeop('o8_verbOps', verb_ops_v8),
    0xAF: makeop('o6_startSound'),
    0xB0: makeop('o6_startMusic'),
    0xB1: makeop('o6_stopSound'),
    0xB2: makeop('o6_soundKludge'),
    0xB3: makeop('o8_systemOps', extended_b_op),
    0xB4: makeop('o6_saveRestoreVerbs', extended_b_op),
    0xB5: makeop('o6_setObjectName', msg_op_v8),
    0xB6: makeop('o6_getDateTime'),
    0xB7: makeop('o6_drawBox'),
    0xB9: makeop('o8_startVideo', msg_op_v8),
    0xBA: makeop('o8_kernelSetFunctions'),
    0xC8: makeop('o6_startScriptQuick2'),
    0xC9: makeop('o6_startObjectQuick'),
    0xCA: makeop('o6_pickOneOf'),
    0xCB: makeop('o6_pickOneOfDefault'),
    0xCD: makeop('o6_isAnyOf'),
    0xCE: makeop('o6_getRandomNumber'),
    0xCF: makeop('o6_getRandomNumberRange'),
    0xD0: makeop('o6_ifClassOfIs'),
    0xD1: makeop('o6_getState'),
    0xD2: makeop('o6_getOwner'),
    0xD3: makeop('o6_isScriptRunning'),
    0xD5: makeop('o6_isSoundRunning'),
    0xD6: makeop('o6_abs'),
    0xD8: makeop('o8_kernelGetFunctions'),
    0xD9: makeop('o6_isActorInBox'),
    0xDA: makeop('o6_getVerbEntrypoint'),
    0xDB: makeop('o6_getActorFromXY'),
    0xDC: makeop('o6_findObject'),
    0xDD: makeop('o6_getVerbFromXY'),
    0xDF: makeop('o6_findInventory'),
    0xE0: makeop('o6_getInventoryCount'),
    0xE1: makeop('o6_getAnimateVariable'),
    0xE2: makeop('o6_getActorRoom'),
    0xE3: makeop('o6_getActorWalkBox'),
    0xE4: makeop('o6_getActorMoving'),
    0xE5: makeop('o6_getActorCostume'),
    0xE6: makeop('o6_getActorScaleX'),
    0xE7: makeop('o6_getActorLayer'),
    0xE8: makeop('o6_getActorElevation'),
    0xE9: makeop('o6_getActorWidth'),
    0xEA: makeop('o6_getObjectNewDir'),
    0xEB: makeop('o6_getObjectX'),
    0xEC: makeop('o6_getObjectY'),
    0xED: makeop('o8_getActorChore'),
    0xEE: makeop('o6_distObjectObject'),
    0xEF: makeop('o6_distPtPt'),
    0xF0: makeop('o8_getObjectImageX'),
    0xF1: makeop('o8_getObjectImageY'),
    0xF2: makeop('o8_getObjectImageWidth'),
    0xF3: makeop('o8_getObjectImageHeight'),
    0xF6: makeop('o8_getStringWidth', msg_op_v8),
    0xF7: makeop('o8_getActorZPlane'),
})


def fstack(pattern, *args, **kwargs):
    def inner(op, stack):
        return pattern.format(*(f(op, stack) for f in args), **kwargs)
    return inner

def npop(stack, num):
    return [stack.pop() for _ in range(num)]
