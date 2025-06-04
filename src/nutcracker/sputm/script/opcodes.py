from collections.abc import Callable, Iterable, Mapping
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


class ReverseLookup:
    @classmethod
    def lookup(cls, value: int) -> str:
        reverse_map = {}
        for base in reversed(cls.__mro__):
            reverse_map.update({v: k for k, v in base.__dict__.items()})
        return reverse_map[value]


class SubOpsV6(ReverseLookup):
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
    SO_INT = 199  # SO_INT_ARRAY
    SO_BIT = 200  # SO_BIT_ARRAY
    SO_NIBBLE = 201  # SO_NIBBLE_ARRAY
    SO_BYTE = 202  # SO_BYTE_ARRAY
    SO_STRING = 203  # SO_STRING_ARRAY
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


class SubOpsV8(ReverseLookup):
    SO_INT = 10  # SO_ARRAY_SCUMMVAR
    SO_STRING = 11  # SO_ARRAY_STRING
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
    SO_RGB_ROOM_INTENSITY = 88  # SO_ROOM_RGB_INTENSITY
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
    SO_VERB_IMAGE_IN_ROOM = 163  # SO_VERB_IMAGE
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
    SO_TEXTSTRING = 209  # SO_PRINT_STRING
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


def realize(src: Mapping[T, R | None]) -> dict[T, R]:
    return {key: value for key, value in src.items() if value is not None}


def IMBYTE(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream),)


def IMWORD(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (WordValue(stream),)


def IMDWORD(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (DWordValue(stream),)


def OFFSET(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (RefOffset(stream),)


def DOFFSET(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (RefOffset(stream, word_size=4),)


def MSG_OP(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream),)


def MSG_OP_V8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream, var_size=4),)


def makeop(
    name: str,
    *ops: Callable[[IO[bytes]], Iterable[ScriptArg]],
) -> Callable[[int, IO[bytes]], Statement]:
    return partial(Statement.parse, name, ops)


def SUBOP(
    subs: type[ReverseLookup],
    mapping: Mapping[int, Iterable[Callable[[IO[bytes]], Iterable[ScriptArg]]]] | None = None
) -> Callable[[IO[bytes]], Iterable[ScriptArg]]:
    if mapping is None:
        mapping = {}
    def subop(stream: IO[bytes]) -> Iterable[ScriptArg]:
        cmd = ByteValue(stream)
        op = ord(cmd.op)
        name = subs.lookup(op)
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
    0x42: makeop('o6_writeByteVar', IMBYTE),
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
    0x9D: makeop('actorOps', SUBOP(SubOpsV6, {
        SubOpsV6.SO_ACTOR_NAME: (MSG_OP,),
    })),
    0x9E: makeop('verbOps', SUBOP(SubOpsV6, {
        SubOpsV6.SO_VERB_NAME: (MSG_OP,),
    })),
    0x9F: makeop('o6_getActorFromXY'),
    0xA0: makeop('o6_findObject'),
    0xA1: makeop('o6_pseudoRoom'),
    0xA2: makeop('o6_getActorElevation'),
    0xA3: makeop('o6_getVerbEntrypoint'),
    0xA4: makeop('arrayOps', SUBOP(SubOpsV6, {
        SubOpsV6.SO_ASSIGN_STRING: (IMWORD, MSG_OP),
        SubOpsV6.SO_ASSIGN_INT_LIST: (IMWORD,),
        SubOpsV6.SO_ASSIGN_2DIM_LIST: (IMWORD,),
    })),
    0xA5: makeop('o6_saveRestoreVerbs', SUBOP(SubOpsV6)),
    0xA6: makeop('o6_drawBox'),
    0xA7: makeop('o6_pop'),
    0xA8: makeop('o6_getActorWidth'),
    0xA9: makeop('o6_wait', SUBOP(SubOpsV6, {
        SubOpsV6.SO_WAIT_FOR_ACTOR: (OFFSET,),
        SubOpsV6.SO_WAIT_FOR_ANIMATION: (OFFSET,),
        SubOpsV6.SO_WAIT_FOR_TURN: (OFFSET,),
    })),
    0xAA: makeop('o6_getActorScaleX'),
    0xAB: makeop('o6_getActorAnimCounter'),
    0xAC: makeop('o6_soundKludge'),
    0xAD: makeop('o6_isAnyOf'),
    0xAE: makeop('o6_systemOps', SUBOP(SubOpsV6)),
    0xAF: makeop('o6_isActorInBox'),
    0xB0: makeop('o6_delay'),
    0xB1: makeop('o6_delaySeconds'),
    0xB2: makeop('o6_delayMinutes'),
    0xB3: makeop('o6_stopSentence'),
    0xB4: makeop('o6_printLine', SUBOP(SubOpsV6, {
        SubOpsV6.SO_TEXTSTRING: (MSG_OP,),
    })),
    0xB5: makeop('o6_printText', SUBOP(SubOpsV6, {
        SubOpsV6.SO_TEXTSTRING: (MSG_OP,),
    })),
    0xB6: makeop('o6_printDebug', SUBOP(SubOpsV6, {
        SubOpsV6.SO_TEXTSTRING: (MSG_OP,),
    })),
    0xB7: makeop('o6_printSystem', SUBOP(SubOpsV6, {
        SubOpsV6.SO_TEXTSTRING: (MSG_OP,),
    })),
    0xB8: makeop('o6_printActor', SUBOP(SubOpsV6, {
        SubOpsV6.SO_TEXTSTRING: (MSG_OP,),
    })),
    0xB9: makeop('o6_printEgo', SUBOP(SubOpsV6, {
        SubOpsV6.SO_TEXTSTRING: (MSG_OP,),
    })),
    0xBA: makeop('o6_talkActor', MSG_OP),
    0xBB: makeop('o6_talkEgo', MSG_OP),
    0xBC: makeop('dimArray', SUBOP(SubOpsV6, {
        SubOpsV6.SO_INT: (IMWORD,),
        SubOpsV6.SO_BIT: (IMWORD,),
        SubOpsV6.SO_NIBBLE: (IMWORD,),
        SubOpsV6.SO_BYTE: (IMWORD,),
        SubOpsV6.SO_STRING: (IMWORD,),
        SubOpsV6.SO_UNDIM_ARRAY: (IMWORD,),
    })),
    0xBD: makeop('o6_stopObjectCodeReturn'),
    0xBE: makeop('o6_startObjectQuick'),
    0xBF: makeop('o6_startScriptQuick2'),
    0xC0: makeop('dim2dimArray', SUBOP(SubOpsV6, {
        SubOpsV6.SO_INT: (IMWORD,),
        SubOpsV6.SO_BIT: (IMWORD,),
        SubOpsV6.SO_NIBBLE: (IMWORD,),
        SubOpsV6.SO_BYTE: (IMWORD,),
        SubOpsV6.SO_STRING: (IMWORD,),
    })),
    0xC4: makeop('o6_abs'),
    0xC5: makeop('o6_distObjectObject'),
    # TODO: 0xc6: makeop('o6_distObjectPt'),
    0xC7: makeop('o6_distPtPt'),
    0xC8: makeop('kernelGetFunctions'),
    0xC9: makeop('kernelSetFunctions'),
    0xCA: makeop('o6_delayFrames'),
    0xCB: makeop('o6_pickOneOf'),
    0xCC: makeop('o6_pickOneOfDefault'),
    0xCD: makeop('o6_stampObject'),
    0xD0: makeop('o6_getDateTime'),
    0xD1: makeop('o6_stopTalking'),
    0xD2: makeop('o6_getAnimateVariable'),
    0xD4: makeop('o6_shuffle', IMWORD),
    0xD5: makeop('o6_jumpToScript'),
    0xD6: makeop('o6_band'),  # bitwise and
    0xD7: makeop('o6_bor'),  # bitwise or
    0xD8: makeop('o6_isRoomScriptRunning'),
    0xDD: makeop('o6_findAllObjects'),
    0xE1: makeop('o6_getPixel'),
    0xE3: makeop('o6_pickVarRandom', IMWORD),
    0xE4: makeop('o6_setBoxSet', IMBYTE),
    0xEC: makeop('o6_getActorLayer'),
    0xED: makeop('o6_getObjectNewDir'),
})


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
    0x70: makeop('dimArray', SUBOP(SubOpsV8, {
        SubOpsV8.SO_INT: (IMDWORD,),
        SubOpsV8.SO_STRING: (IMDWORD,),
        SubOpsV8.SO_UNDIM_ARRAY: (IMDWORD,),
    })),
    0x71: makeop('o6_wordArrayWrite', IMDWORD),
    0x72: makeop('o6_wordArrayInc', IMDWORD),
    0x73: makeop('o6_wordArrayDec', IMDWORD),
    0x74: makeop('dim2dimArray', SUBOP(SubOpsV8, {
        SubOpsV8.SO_INT: (IMDWORD,),
        SubOpsV8.SO_STRING: (IMDWORD,),
    })),
    0x75: makeop('o6_wordArrayIndexedWrite', IMDWORD),
    0x76: makeop('arrayOps', SUBOP(SubOpsV8, {
        SubOpsV8.SO_ASSIGN_STRING: (IMDWORD, MSG_OP_V8),
        SubOpsV8.SO_ASSIGN_INT_LIST: (IMDWORD,),
        SubOpsV8.SO_ASSIGN_2DIM_LIST: (IMDWORD,),
    })),
    0x79: makeop('o6_startScript'),
    0x7A: makeop('o6_startScriptQuick'),
    0x7B: makeop('o6_stopObjectCodeScript'),  # o6_stopObjectCode
    0x7C: makeop('o6_stopScript'),
    0x7D: makeop('o6_jumpToScript'),
    0x7E: makeop('o6_stopObjectCodeReturn'),
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
    0x8F: makeop('o6_printActor', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x90: makeop('o6_printEgo', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x91: makeop('o6_talkActor', MSG_OP_V8),
    0x92: makeop('o6_talkEgo', MSG_OP_V8),
    0x93: makeop('o6_printLine', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x94: makeop('o6_printText', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x95: makeop('o6_printDebug', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x96: makeop('o6_printSystem', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x97: makeop('o8_blastText', SUBOP(SubOpsV8, {
        SubOpsV8.SO_TEXTSTRING: (MSG_OP_V8,),
    })),
    0x98: makeop('o8_drawObject'),
    0x9C: makeop('o8_cursorCommand', SUBOP(SubOpsV8)),
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
    0xAA: makeop('o8_resourceRoutines', SUBOP(SubOpsV8)),
    0xAB: makeop('o8_roomOps', SUBOP(SubOpsV8)),
    0xAC: makeop('o8_actorOps', SUBOP(SubOpsV8, {
        SubOpsV8.SO_ACTOR_NAME: (MSG_OP_V8,),
    })),
    0xAD: makeop('o8_cameraOps', SUBOP(SubOpsV8)),
    0xAE: makeop('verbOps', SUBOP(SubOpsV8, {
        SubOpsV8.SO_VERB_NAME: (MSG_OP_V8,),
    })),
    0xAF: makeop('o6_startSound'),
    0xB0: makeop('o6_startMusic'),
    0xB1: makeop('o6_stopSound'),
    0xB2: makeop('o6_soundKludge'),
    0xB3: makeop('o8_systemOps', SUBOP(SubOpsV8)),
    0xB4: makeop('o6_saveRestoreVerbs', SUBOP(SubOpsV8)),
    0xB5: makeop('o6_setObjectName', MSG_OP_V8),
    0xB6: makeop('o6_getDateTime'),
    0xB7: makeop('o6_drawBox'),
    0xB9: makeop('o8_startVideo', MSG_OP_V8),
    0xBA: makeop('kernelSetFunctions'),
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
    0xD8: makeop('kernelGetFunctions'),
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
    0xF6: makeop('o8_getStringWidth', MSG_OP_V8),
    0xF7: makeop('o8_getActorZPlane'),
})
