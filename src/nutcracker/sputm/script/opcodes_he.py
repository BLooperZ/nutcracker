from collections.abc import Iterable
from typing import IO

from nutcracker.sputm.script.opcodes import (
    IMBYTE,
    IMDWORD,
    IMWORD,
    MSG_OP,
    OFFSET,
    SUBOP,
    OPCODES_v6,
    OpTable,
    ReverseLookup,
    SubOpsV6,
    makeop,
    realize,
)
from nutcracker.sputm.script.parser import CString, ScriptArg


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
    typ = ord(stream.read(1))
    stream.seek(2, 1)  # seek back to where it was.
    if typ == 1:
        return (CString(stream),)
    if typ == 2:
        return (CString(stream), CString(stream))
    raise ValueError(type)


class SubOpsHE60(SubOpsV6):
    SO_ACTOR_DEFAULT_CLIPPED = 30
    SO_BACKGROUND_ON = 218
    SO_BACKGROUND_OFF = 219
    SO_ROOM_COPY_PALETTE = 220
    SO_ROOM_SAVEGAME_BY_NAME = 221
    SO_SOUND_START_VOLUME = 222
    SO_SOUND_VOLUME_RAMP = 223
    SO_SOUND_FREQUENCY = 224
    SO_TALKIE = 225
    SO_OBJECT_ORDER = 234
    SO_ROOM_PALETTE_IN_ROOM = 236
    SO_COLOR_LIST = 249


class SubOpsHE70(SubOpsHE60):
    SO_SOFT = 9
    SO_IMAGE_LOADED = 18
    SO_VARIABLE = 23
    SO_SOUND_VOLUME = 25
    SO_NOW = 56
    SO_PRELOAD_SCRIPT = 120
    SO_PRELOAD_SOUND = 121
    SO_PRELOAD_COSTUME = 122
    SO_PRELOAD_ROOM = 123
    SO_UNLOCK_IMAGE = 159
    SO_ADD = 164
    SO_NUKE_IMAGE = 192
    SO_LOAD_IMAGE = 201
    SO_LOCK_IMAGE = 202
    SO_PRELOAD_IMAGE = 203
    SO_ROOM_LOADED = 226
    SO_COSTUME_LOADED = 227
    SO_SOUND_LOADED = 228
    SO_SCRIPT_LOADED = 229
    SO_SOUND_CHANNEL = 230
    SO_AT = 231
    SO_SOUND_START = 232
    SO_LOCK_FLOBJECT = 233
    SO_UNLOCK_FLOBJECT = 235
    SO_PRELOAD_FLUSH = 239
    SO_PAUSE_MESSAGE = 240
    SO_PAUSE_TITLE = 241
    SO_PAUSE_OPTION = 242
    SO_TITLE_BAR = 243
    SO_QUIT_QUIT = 244
    SO_SOUND_LOOPING = 245
    SO_START_SYSTEM = 250
    SO_START_SYSTEM_STRING = 251
    SO_RESTART_STRING = 252
    SO_RESTART_ARRAY = 253


class SubOpsHE71(SubOpsHE70):
    SO_SET_POLYGON = 246
    SO_DELETE_POLYGON = 247
    SO_SET_POLYGON_LOCAL = 248


class SubOpsHE72(SubOpsHE71):
    SO_NONE = 1
    SO_BIT = 2  # SO_INT1
    SO_NIBBLE = 3  # SO_INT4
    SO_BYTE = 4  # SO_INT8
    SO_INT = 5  # SO_INT16
    SO_DWORD = 6  # SO_INT32
    SO_STRING = 7
    SO_ARRAY = 8
    SO_MSECONDS = 10
    SO_HEAP_FREE = 11
    SO_HEAP_LARGEST_FREE = 12
    SO_SOUND_SIZE = 13
    SO_ROOM_SIZE = 14
    SO_IMAGE_SIZE = 15
    SO_COSTUME_SIZE = 16
    SO_SCRIPT_SIZE = 17
    SO_CONDITION = 21
    SO_FLUSH_OBJECT_DRAW_QUE = 22
    SO_TALK_CONDITION = 24
    SO_UPDATE_SCREEN = 26
    SO_PRIORITY = 43
    SO_AT_IMAGE = 62
    SO_IMAGE = 63
    SO_ACTOR_DEFAULT_CLIPPED = 64
    SO_ERASE = 68
    SO_COMPLEX_ARRAY_ASSIGNMENT = 126
    SO_COMPLEX_ARRAY_COPY_OPERATION = 127
    SO_RANGE_ARRAY_ASSIGNMENT = 128
    SO_COMPLEX_ARRAY_MATH_OPERATION = 138
    SO_FORMATTED_STRING = 194
    SO_REC = 195
    SO_BAK = 199
    SO_BAKREC = 200
    SO_UNDIM_ARRAY = 204


class SubOpsHE80(SubOpsHE72):
    SO_CURSOR_IMAGE = 19
    SO_CURSOR_COLOR_IMAGE = 20
    SO_SOUND_ADD = 27
    SO_ACTOR = 55
    SO_BUTTON = 60


class SubOpsHE90(SubOpsHE80):
    SO_COORD_2D = 28
    SO_COORD_3D = 29
    SO_XPOS = 30
    SO_YPOS = 31
    SO_WIDTH = 32
    SO_HEIGHT = 33
    SO_STEP_DIST_X = 34
    SO_STEP_DIST_Y = 35
    SO_COUNT = 36
    SO_GROUP = 37
    SO_DRAW_XPOS = 38
    SO_DRAW_YPOS = 39
    SO_PROPERTY = 42
    SO_PRIORITY = 43
    SO_MOVE = 44
    SO_FIND = 45
    SO_GENERAL_CLIP_STATE = 46
    SO_GENERAL_CLIP_RECT = 47
    SO_DRAW = 48
    SO_LOAD = 49
    SO_SAVE = 50
    SO_CAPTURE = 51
    SO_STATE = 52
    SO_ANGLE = 53
    SO_SET_FLAGS = 54
    SO_INIT = 57
    SO_SCRIPT = 58
    SO_SHOW = 59
    SO_AT_IMAGE = 62
    SO_IMAGE = 63
    SO_AT = 65
    SO_ERASE = 68
    SO_TO = 70
    SO_STEP_DIST = 77
    SO_ANIMATION = 82
    SO_PALETTE = 86
    SO_SCALE = 92
    SO_ANIMATION_SPEED = 97
    SO_SHADOW = 98
    SO_UPDATE = 124
    SO_CLASS = 125
    SO_SORT = 129
    SO_HISTOGRAM = 130
    SO_POLY_TO_POLY = 131  # SO_POLY_POLYGON
    SO_CHANNEL = 132
    SO_RENDER_RECTANGLE = 133
    SO_RENDER_LINE = 134
    SO_RENDER_PIXEL = 135
    SO_RENDER_FLOOD_FILL = 136
    SO_RENDER_INTO_IMAGE = 137
    SO_NEW_GENERAL_PROPERTY = 139
    SO_MASK = 140
    SO_FONT_START = 141
    SO_FONT_CREATE = 142
    SO_FONT_RENDER = 143
    SO_CLOSE = 165
    SO_RENDER_ELLIPSE = 189
    SO_FONT_END = 196
    SO_ACTOR_VARIABLE = 198


class SubOpsHE100:
    class Common(ReverseLookup):
        SO_INIT = 0
        SO_ACTOR = 1
        SO_ANGLE = 2
        SO_ANIMATION = 3
        SO_ANIMATION_SPEED = 4
        SO_ARRAY = 5
        SO_AT = 6
        SO_AT_IMAGE = 7
        SO_BACKGROUND_OFF = 8
        SO_BACKGROUND_ON = 9
        SO_CAPTURE = 11
        SO_CENTER = 12
        SO_CHANNEL = 13
        SO_CHARSET = 14
        SO_CHARSET_COLOR = 15
        SO_CLASS = 16
        # SO_CLEAR_FLAGS = 17
        SO_CLIPPED = 18
        SO_CLOSE = 19
        SO_COLOR = 20
        SO_COLOR_LIST = 21
        SO_CONDITION = 22
        SO_COORD_2D = 23
        SO_COORD_3D = 24
        SO_COSTUME = 25
        SO_COUNT = 26
        SO_DEFAULT = 27
        SO_DELETE_POLYGON = 28
        SO_DRAW = 29
        SO_DRAW_XPOS = 30
        SO_DRAW_YPOS = 31
        SO_ERASE = 32
        SO_FIND = 33
        SO_FLOBJECT = 34
        SO_FORMATTED_STRING = 35
        SO_GENERAL_CLIP_RECT = 36
        SO_GENERAL_CLIP_STATE = 37
        SO_GROUP = 38
        SO_HEIGHT = 39
        SO_IMAGE = 40
        SO_BIT = 41  # SO_INT1
        SO_INT = 42  # SO_INT16
        SO_DWORD = 43  # SO_INT32
        SO_NIBBLE = 44  # SO_INT4
        SO_BYTE = 45  # SO_INT8
        SO_LEFT = 46
        SO_LOAD = 47
        SO_MASK = 48
        SO_MOVE = 49
        SO_MSECONDS = 50
        SO_MUMBLE = 51
        SO_NAME = 52
        SO_NEW = 53
        SO_NEW_GENERAL_PROPERTY = 54
        SO_NOW = 55
        SO_OVERHEAD = 56
        SO_PALETTE = 57
        SO_POLY_TO_POLY = 58
        SO_PRIORITY = 59
        SO_PROPERTY = 60
        SO_RESTART = 61
        SO_ROOM = 62
        SO_ROOM_PALETTE = 63
        SO_SAVE = 64
        SO_SCALE = 65
        SO_SCRIPT = 66
        SO_SET_FLAGS = 67
        SO_SET_POLYGON = 68
        SO_SET_POLYGON_LOCAL = 69
        SO_SHADOW = 70
        # SO_SHOW = 71
        SO_SOUND = 72
        SO_STATE = 73
        SO_STEP_DIST = 74
        SO_STEP_DIST_X = 75
        SO_STEP_DIST_Y = 76
        SO_STRING = 77
        SO_TALKIE = 78
        SO_TEXTSTRING = 79
        SO_TITLE_BAR = 80
        SO_TO = 81
        SO_UPDATE = 82
        SO_VARIABLE = 83
        SO_WIDTH = 84
        SO_XPOS = 85
        SO_YPOS = 86
        SO_ALWAYS_ZCLIP = 87
        SO_IMAGE_ZCLIP = 88
        SO_NEVER_ZCLIP = 89
        SO_NONE = 90
        SO_BASEOP = 91
        SO_END = 92

    class Actor(Common):
        SO_ACTOR_DEFAULT_CLIPPED = 128
        SO_ACTOR_INIT = 129
        SO_ACTOR_SOUNDS = 130
        SO_ACTOR_WIDTH = 131
        SO_ANIMATION_DEFAULT = 132
        SO_ELEVATION = 133
        SO_FOLLOW_BOXES = 134
        SO_IGNORE_BOXES = 135
        SO_ACTOR_IGNORE_TURNS_OFF = 136  # SO_IGNORE_TURNS_OFF
        SO_ACTOR_IGNORE_TURNS_ON = 137  # SO_IGNORE_TURNS_ON
        SO_INIT_ANIMATION = 138
        SO_STAND_ANIMATION = 139
        SO_TALK_ANIMATION = 140
        SO_TALK_COLOR = 141
        SO_TALK_CONDITION = 142
        SO_TEXT_OFFSET = 143
        SO_WALK_ANIMATION = 144

    class Array(Common):
        SO_ASSIGN_2DIM_LIST = 128
        SO_ASSIGN_INT_LIST = 129
        SO_COMPLEX_ARRAY_ASSIGNMENT = 130
        SO_COMPLEX_ARRAY_COPY_OPERATION = 131
        SO_COMPLEX_ARRAY_MATH_OPERATION = 132
        SO_RANGE_ARRAY_ASSIGNMENT = 133
        SO_SORT = 134
        SO_UNDIM_ARRAY = 135

    class Heap(Common):
        SO_CLEAR_HEAP = 128
        SO_PRELOAD_FLUSH = 129
        SO_HEAP_FREE = 130
        SO_HEAP_LARGEST_FREE = 131
        SO_LOCK = 132
        SO_NUKE = 133
        SO_OFF_HEAP = 134
        SO_ON_HEAP = 135
        SO_PRELOAD = 136
        SO_UNLOCK = 137

    class Image(Common):
        SO_FONT_CREATE = 128
        SO_FONT_END = 129
        SO_FONT_RENDER = 130
        SO_FONT_START = 131
        SO_HISTOGRAM = 132
        SO_RENDER_ELLIPSE = 133
        SO_RENDER_FLOOD_FILL = 134
        SO_RENDER_INTO_IMAGE = 135
        SO_RENDER_LINE = 136
        SO_RENDER_PIXEL = 137
        SO_RENDER_RECTANGLE = 138

    class Cursor(Common):
        SO_CURSOR_IMAGE = 128
        SO_CURSOR_COLOR_IMAGE = 129
        SO_CURSOR_COLOR_PAL_IMAGE = 130
        SO_CURSOR_HOTSPOT = 132
        SO_CURSOR_ON = 134
        SO_CURSOR_OFF = 135
        SO_CURSOR_SOFT_ON = 136
        SO_CURSOR_SOFT_OFF = 137
        SO_USERPUT_ON = 139
        SO_USERPUT_OFF = 140
        SO_USERPUT_SOFT_ON = 141
        SO_USERPUT_SOFT_OFF = 142

    class Room(Common):
        SO_OBJECT_ORDER = 129
        SO_ROOM_COPY_PALETTE = 130
        SO_ROOM_FADE = 131
        SO_ROOM_INTENSITY = 132
        SO_ROOM_INTENSITY_RGB = 133
        SO_ROOM_NEW_PALETTE = 134
        SO_ROOM_PALETTE_IN_ROOM = 135
        SO_ROOM_SAVEGAME = 136
        SO_ROOM_SAVEGAME_BY_NAME = 137
        SO_ROOM_SCREEN = 138
        SO_ROOM_SCROLL = 139
        SO_ROOM_SHAKE_OFF = 140
        SO_ROOM_SHAKE_ON = 141
        SO_ROOM_TRANSFORM = 142

    class Script(Common):
        SO_BAK = 128
        SO_BAKREC = 129
        SO_REC = 130

    class System(Common):
        SO_FLUSH_OBJECT_DRAW_QUE = 128  # SO_FLUSH_OBJECT_DRAW_QUEUE
        SO_PAUSE_TITLE = 131
        SO_QUIT = 132
        SO_QUIT_QUIT = 133
        SO_RESTART_STRING = 134
        SO_START_SYSTEM_STRING = 135
        SO_UPDATE_SCREEN = 136

    class Sound(Common):
        SO_SOUND_ADD = 128
        SO_SOUND_CHANNEL = 129
        SO_SOUND_FREQUENCY = 130
        SO_SOUND_LOOPING = 131
        SO_SOUND_MODIFY = 132
        SO_SOUND_PAN = 133
        SO_SOUND_START = 134
        SO_SOFT = 135  # SO_SOUND_SOFT
        SO_SOUND_VOLUME = 136

    class Wait(Common):
        SO_WAIT_FOR_ACTOR = 128
        SO_WAIT_FOR_CAMERA = 129
        SO_WAIT_FOR_MESSAGE = 130
        SO_WAIT_FOR_SENTENCE = 131


OPCODES_he60 = realize(
    {
        **OPCODES_v6,
        0x63: None,
        0x64: None,
        0x70: makeop('o60_setState'),
        0x9A: None,
        0x9C: makeop('o6_roomOps', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_ROOM_SAVEGAME_BY_NAME: (MSG_OP,),
        })),
        0x9D: makeop('actorOps', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TALKIE: (MSG_OP,),
        })),
        0xAC: None,
        0xB4: makeop('o6_printLine', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TEXTSTRING: (MSG_OP,),
        })),
        0xB5: makeop('o6_printText', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TEXTSTRING: (MSG_OP,),
        })),
        0xB6: makeop('o6_printDebug', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TEXTSTRING: (MSG_OP,),
        })),
        0xB7: makeop('o6_printSystem', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TEXTSTRING: (MSG_OP,),
        })),
        0xB8: makeop('o6_printActor', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TEXTSTRING: (MSG_OP,),
        })),
        0xB9: makeop('o6_printEgo', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_TEXTSTRING: (MSG_OP,),
        })),
        0xD9: makeop('o60_closeFile'),
        0xDA: makeop('o60_openFile', MSG_OP),
        0xDB: makeop('o60_readFile'),
        0xDC: makeop('o60_writeFile'),
        0xDE: makeop('o60_deleteFile', MSG_OP),
        0xDF: makeop('o60_rename', MSG_OP, MSG_OP),
        0xE0: makeop('o60_soundOps', SUBOP(SubOpsHE60)),
        0xE2: makeop('o60_localizeArrayToScript'),
        0xE9: makeop('o60_seekFilePos'),
        0xEA: makeop('o60_redimArray', SUBOP(SubOpsHE60, {
            SubOpsHE60.SO_INT: (IMWORD,),
            SubOpsHE60.SO_BYTE: (IMWORD,),
        })),
        0xEB: makeop('o60_readFilePos'),
        0xEC: None,
        0xED: None,
    },
)

OPCODES_he70: OpTable = realize(
    {
        **OPCODES_he60,
        0x74: makeop('o70_soundOps', SUBOP(SubOpsHE70)),
        0x84: makeop('o70_pickupObject'),
        0x8C: makeop('o70_getActorRoom'),
        0x9B: makeop('o70_resourceRoutines', SUBOP(SubOpsHE70)),
        0xAE: makeop('o70_systemOps', SUBOP(SubOpsHE70, {
            SubOpsHE70.SO_RESTART_STRING: (MSG_OP,),
        })),
        0xEE: makeop('o70_getStringLen'),
        0xF2: makeop('o70_isResourceLoaded', SUBOP(SubOpsHE70)),
        0xF3: makeop('o70_readINI', MSG_OP),
        0xF4: makeop('o70_writeINI', ini_op_v71),
        0xF9: makeop('o70_createDirectory', MSG_OP),
        0xFA: makeop('o70_setSystemMessage', SUBOP(SubOpsHE70, {
            SubOpsHE70.SO_PAUSE_MESSAGE: (MSG_OP,),
            SubOpsHE70.SO_PAUSE_TITLE: (MSG_OP,),
            SubOpsHE70.SO_PAUSE_OPTION: (MSG_OP,),
            SubOpsHE70.SO_TITLE_BAR: (MSG_OP,),
        })),
    },
)

OPCODES_he71: OpTable = realize(
    {
        **OPCODES_he70,
        0xEC: makeop('o71_copyString'),
        0xED: makeop('o71_getStringWidth'),
        0xEF: makeop('o71_appendString'),
        0xF0: makeop('o71_concatString'),
        0xF1: makeop('o71_compareString'),
        0xF5: makeop('o71_getStringLenForWidth'),
        0xF6: makeop('o71_getCharIndexInString'),
        0xF7: makeop('o71_findBox'),
        0xFB: makeop('o71_polygonOps', SUBOP(SubOpsHE71)),
        0xFC: makeop('o71_polygonHit'),
    },
)

OPCODES_he72: OpTable = realize(
    {
        **OPCODES_he71,
        0x02: makeop('o72_pushDWord', IMDWORD),
        0x04: makeop('o72_getScriptString', MSG_OP),
        0x0A: None,
        0x1B: makeop('o6_isAnyOf'),
        0x42: None,
        0x46: None,
        0x4A: None,
        0x4E: None,
        0x50: makeop('o72_resetCutscene'),
        0x51: makeop('o72_getHeap', SUBOP(SubOpsHE72)),
        0x52: makeop('o72_findObjectWithClassOf'),
        0x54: makeop('o72_getObjectImageX'),
        0x55: makeop('o72_getObjectImageY'),
        0x56: makeop('o72_captureWizImage'),
        0x58: makeop('o72_getTimer', SUBOP(SubOpsHE72)),
        0x59: makeop('o72_setTimer', SUBOP(SubOpsHE72)),
        0x5A: makeop('o72_getSoundPosition'),
        0x5E: makeop('o72_startScript', SUBOP(SubOpsHE72)),
        0x60: makeop('o72_startObject', SUBOP(SubOpsHE72)),
        0x61: makeop('o72_drawObject', SUBOP(SubOpsHE72)),
        0x62: makeop('o72_printWizImage'),
        0x63: makeop('o72_getArrayDimSize', IMBYTE, IMWORD),
        0x64: makeop('o72_getNumFreeArrays'),
        0x97: None,
        0x9C: makeop('o6_roomOps', SUBOP(SubOpsHE72)),
        0x9D: makeop('actorOps', SUBOP(SubOpsHE72)),
        0x9E: makeop('verbOps', SUBOP(SubOpsHE72)),
        # TODO: 0xa0: makeop('o72_findObject'),
        0xA4: makeop('o72_arrayOps', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_STRING: (IMWORD,),
            SubOpsHE72.SO_COMPLEX_ARRAY_ASSIGNMENT: (IMWORD,),
            SubOpsHE72.SO_COMPLEX_ARRAY_COPY_OPERATION: (IMWORD, IMWORD),
            SubOpsHE72.SO_RANGE_ARRAY_ASSIGNMENT: (IMWORD,),
            SubOpsHE72.SO_COMPLEX_ARRAY_MATH_OPERATION: (IMWORD, IMWORD, IMWORD),
            SubOpsHE72.SO_FORMATTED_STRING: (IMWORD,),
            SubOpsHE72.SO_ASSIGN_INT_LIST: (IMWORD,),
            SubOpsHE72.SO_ASSIGN_2DIM_LIST: (IMWORD,),
        })),
        0xAE: makeop('o72_systemOps', SUBOP(SubOpsHE72)),
        0xB4: makeop('o6_printLine', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE72.SO_FORMATTED_STRING: (MSG_OP,),
        })),
        0xB5: makeop('o6_printText', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE72.SO_FORMATTED_STRING: (MSG_OP,),
        })),
        0xB6: makeop('o6_printDebug', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE72.SO_FORMATTED_STRING: (MSG_OP,),
        })),
        0xB7: makeop('o6_printSystem', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE72.SO_FORMATTED_STRING: (MSG_OP,),
        })),
        0xB8: makeop('o6_printActor', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE72.SO_FORMATTED_STRING: (MSG_OP,),
        })),
        0xB9: makeop('o6_printEgo', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE72.SO_FORMATTED_STRING: (MSG_OP,),
        })),
        0xBA: makeop('o72_talkActor', MSG_OP),
        0xBB: makeop('o72_talkEgo', MSG_OP),
        0xBC: makeop('o72_dimArray', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_BIT: (IMWORD,),
            SubOpsHE72.SO_NIBBLE: (IMWORD,),
            SubOpsHE72.SO_BYTE: (IMWORD,),
            SubOpsHE72.SO_INT: (IMWORD,),
            SubOpsHE72.SO_DWORD: (IMWORD,),
            SubOpsHE72.SO_STRING: (IMWORD,),
            SubOpsHE72.SO_UNDIM_ARRAY: (IMWORD,),
        })),
        0xC0: makeop('o72_dim2dimArray', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_BIT: (IMWORD,),
            SubOpsHE72.SO_NIBBLE: (IMWORD,),
            SubOpsHE72.SO_BYTE: (IMWORD,),
            SubOpsHE72.SO_INT: (IMWORD,),
            SubOpsHE72.SO_DWORD: (IMWORD,),
            SubOpsHE72.SO_STRING: (IMWORD,),
        })),
        0xC1: makeop('o72_traceStatus'),
        0xCE: makeop('o72_drawWizImage'),
        0xCF: makeop('o72_debugInput'),
        0xD5: makeop('o72_jumpToScript', SUBOP(SubOpsHE72)),
        0xDA: makeop('o72_openFile'),
        0xDB: makeop('o72_readFile', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_ARRAY: (IMBYTE,),
        })),
        0xDC: makeop('o72_writeFile', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_ARRAY: (IMBYTE,),
        })),
        0xDD: makeop('o72_findAllObjects'),
        0xDE: makeop('o72_deleteFile'),
        0xDF: makeop('o72_rename'),
        0xE1: makeop('o72_getPixel', SUBOP(SubOpsHE72)),
        # TODO: 0xe3: makeop('o72_pickVarRandom'),
        0xEA: makeop('o72_redimArray', SUBOP(SubOpsHE72, {
            SubOpsHE72.SO_BYTE: (IMWORD,),
            SubOpsHE72.SO_INT: (IMWORD,),
            SubOpsHE72.SO_DWORD: (IMWORD,),
        })),
        0xF3: makeop('o72_readINI', SUBOP(SubOpsHE72)),
        0xF4: makeop('o72_writeINI', SUBOP(SubOpsHE72)),
        0xF8: makeop('o72_getResourceSize'),
        0xF9: makeop('o72_createDirectory'),
        0xFA: makeop('o72_setSystemMessage', SUBOP(SubOpsHE72)),
    },
)

OPCODES_he73: OpTable = realize(
    {
        **OPCODES_he72,
        0xF8: makeop('o73_getResourceSize', SUBOP(SubOpsHE72)),
    },
)

OPCODES_he80: OpTable = realize(
    {
        **OPCODES_he73,
        0x45: makeop('o80_createSound', SUBOP(SubOpsHE80)),
        0x46: makeop('o80_getFileSize'),
        0x48: makeop('o80_stringToInt'),
        0x49: makeop('o80_getSoundVar'),
        0x4A: makeop('o80_localizeArrayToRoom'),
        0x4C: makeop('o80_sourceDebug', IMDWORD, IMDWORD),
        0x4D: makeop('o80_readConfigFile', SUBOP(SubOpsHE80)),
        0x4E: makeop('o80_writeConfigFile', SUBOP(SubOpsHE80)),
        0x69: None,
        0x6B: makeop('o80_cursorCommand', SUBOP(SubOpsHE80)),
        0x70: makeop('o80_setState'),
        0x76: None,
        0x94: None,
        0x9E: None,
        0xA5: None,
        0xAC: makeop('o80_drawWizPolygon'),
        0xE0: makeop('o80_drawLine', SUBOP(SubOpsHE80)),
        0xE3: makeop('o80_pickVarRandom', IMWORD),
    },
)

OPCODES_he90: OpTable = realize(
    {
        **OPCODES_he80,
        0x0A: makeop('o90_dup_n', IMWORD),
        0x1C: makeop('o90_wizImageOps', SUBOP(SubOpsHE90)),
        0x1D: makeop('o90_min'),
        0x1E: makeop('o90_max'),
        0x1F: makeop('o90_sin'),
        0x20: makeop('o90_cos'),
        0x21: makeop('o90_sqrt'),
        0x22: makeop('o90_atan2'),
        0x23: makeop('o90_getSegmentAngle'),
        0x24: makeop('o90_getDistanceBetweenPoints', SUBOP(SubOpsHE90)),
        0x25: makeop('o90_getSpriteInfo', SUBOP(SubOpsHE90)),
        0x26: makeop('o90_setSpriteInfo', SUBOP(SubOpsHE90)),
        0x27: makeop('o90_getSpriteGroupInfo', SUBOP(SubOpsHE90)),
        0x28: makeop('o90_setSpriteGroupInfo', SUBOP(SubOpsHE90)),
        0x29: makeop('o90_getWizData', SUBOP(SubOpsHE90)),
        0x2A: makeop('o90_getActorData'),
        0x2B: makeop('o90_priorityStartScript', SUBOP(SubOpsHE90)),
        0x2C: makeop('o90_priorityChainScript', SUBOP(SubOpsHE90)),
        0x2D: makeop('videoOps', SUBOP(SubOpsHE90)),
        0x2E: makeop('getVideoData', SUBOP(SubOpsHE90)),
        0x2F: makeop('o90_floodFill', SUBOP(SubOpsHE90)),
        0x30: makeop('o90_mod'),
        0x31: makeop('o90_shl'),
        0x32: makeop('o90_shr'),
        0x33: makeop('o90_xor'),
        0x34: makeop('o90_findAllObjectsWithClassOf'),
        0x35: makeop('o90_getPolygonOverlap'),
        0x36: makeop('o90_cond'),
        0x37: makeop('o90_dim2dim2Array', SUBOP(SubOpsHE90, {
            SubOpsHE90.SO_BIT: (IMWORD,),
            SubOpsHE90.SO_NIBBLE: (IMWORD,),
            SubOpsHE90.SO_BYTE: (IMWORD,),
            SubOpsHE90.SO_INT: (IMWORD,),
            SubOpsHE90.SO_DWORD: (IMWORD,),
            SubOpsHE90.SO_STRING: (IMWORD,),
        })),
        0x38: makeop('o90_redim2dimArray', SUBOP(SubOpsHE90, {
            SubOpsHE90.SO_BIT: (IMWORD,),
            SubOpsHE90.SO_NIBBLE: (IMWORD,),
            SubOpsHE90.SO_BYTE: (IMWORD,),
            SubOpsHE90.SO_INT: (IMWORD,),
            SubOpsHE90.SO_DWORD: (IMWORD,),
            SubOpsHE90.SO_STRING: (IMWORD,),
        })),
        0x39: makeop('o90_getLinesIntersectionPoint', IMWORD, IMWORD),
        0x3A: makeop('o90_sortArray', SUBOP(SubOpsHE90, {
            SubOpsHE90.SO_SORT: (IMWORD,),
        })),
        0x44: makeop('o90_getObjectData', SUBOP(SubOpsHE90)),
        0x69: makeop('o90_disabled_windowOps', SUBOP(SubOpsHE90)),
        0x94: makeop('o90_getPaletteData', SUBOP(SubOpsHE90)),
        0x9D: makeop('actorOps', SUBOP(SubOpsHE90)),
        0x9E: makeop('o90_paletteOps', SUBOP(SubOpsHE90)),
        0xA5: makeop('o90_fontEnum', SUBOP(SubOpsHE90)),
        # TODO: 0xab: makeop('o90_getActorAnimProgress'),
    }
)

OPCODES_he100: OpTable = realize(
    {
        0x00: makeop('actorOps', SUBOP(SubOpsHE100.Actor)),
        0x01: makeop('o6_add'),
        0x02: makeop('o6_faceActor'),
        0x03: makeop('o90_sortArray', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_SORT: (IMWORD,),
        })),
        0x04: makeop('o72_arrayOps', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_ASSIGN_2DIM_LIST: (IMWORD,),
            SubOpsHE100.Array.SO_ASSIGN_INT_LIST: (IMWORD,),
            SubOpsHE100.Array.SO_COMPLEX_ARRAY_ASSIGNMENT: (IMWORD,),
            SubOpsHE100.Array.SO_COMPLEX_ARRAY_COPY_OPERATION: (IMWORD, IMWORD),
            SubOpsHE100.Array.SO_COMPLEX_ARRAY_MATH_OPERATION: (IMWORD, IMWORD, IMWORD),
            SubOpsHE100.Array.SO_RANGE_ARRAY_ASSIGNMENT: (IMWORD,),
            SubOpsHE100.Array.SO_STRING: (IMWORD,),
            SubOpsHE100.Array.SO_FORMATTED_STRING: (IMWORD,),
        })),
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
        0x0F: makeop('o6_panCameraTo'),
        # TODO: 0x10: makeop('o72_captureWizImage'),
        0x11: makeop('o72_jumpToScript', SUBOP(SubOpsHE100.Script)),
        0x12: makeop('o6_setClass'),
        0x13: makeop('o60_closeFile'),
        # TODO: 0x14: makeop('o6_loadRoomWithEgo'),
        0x16: makeop('o72_createDirectory'),
        0x17: makeop('o80_createSound', SUBOP(SubOpsHE100.Sound)),
        # TODO: 0x18: makeop('o6_cutscene'),
        0x19: makeop('o6_pop'),
        0x1A: makeop('o72_traceStatus'),
        0x1B: makeop('o6_wordVarDec', IMWORD),
        0x1C: makeop('o6_wordArrayDec', IMWORD),
        0x1D: makeop('o72_deleteFile'),
        0x1E: makeop('o72_dim2dimArray', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_BIT: (IMWORD,),
            SubOpsHE100.Array.SO_NIBBLE: (IMWORD,),
            SubOpsHE100.Array.SO_BYTE: (IMWORD,),
            SubOpsHE100.Array.SO_INT: (IMWORD,),
            SubOpsHE100.Array.SO_DWORD: (IMWORD,),
            SubOpsHE100.Array.SO_STRING: (IMWORD,),
            SubOpsHE100.Array.SO_UNDIM_ARRAY: (IMWORD,),
        })),
        0x1F: makeop('o72_dimArray', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_BIT: (IMWORD,),
            SubOpsHE100.Array.SO_NIBBLE: (IMWORD,),
            SubOpsHE100.Array.SO_BYTE: (IMWORD,),
            SubOpsHE100.Array.SO_INT: (IMWORD,),
            SubOpsHE100.Array.SO_DWORD: (IMWORD,),
            SubOpsHE100.Array.SO_STRING: (IMWORD,),
            SubOpsHE100.Array.SO_UNDIM_ARRAY: (IMWORD,),
        })),
        0x20: makeop('o6_div'),
        0x21: makeop('o6_animateActor'),
        # TODO: 0x22: makeop('o6_doSentence'),
        0x23: makeop('o6_drawBox'),
        # TODO: 0x24: makeop('o72_drawWizImage'),
        # TODO: 0x25: makeop('o80_drawWizPolygon'),
        0x26: makeop('o80_drawLine', SUBOP(SubOpsHE100.Common)),
        0x27: makeop('o72_drawObject', SUBOP(SubOpsHE100.Common)),
        0x28: makeop('o6_dup'),
        0x29: makeop('o90_dup_n', IMWORD),
        # TODO: 0x2a: makeop('o6_endCutscene'),
        0x2B: makeop('o6_stopObjectCodeObject'),  # o6_stopObjectCode
        0x2C: makeop('o6_stopObjectCodeScript'),  # o6_stopObjectCode
        0x2D: makeop('o6_eq'),
        # TODO: 0x2e: makeop('o100_floodFill'),
        # TODO: 0x2f: makeop('o6_freezeUnfreeze'),
        0x30: makeop('o6_ge'),
        0x31: makeop('o6_getDateTime'),
        0x32: makeop('o90_setSpriteGroupInfo', SUBOP(SubOpsHE100.Common)),
        0x33: makeop('o6_gt'),
        0x34: makeop('o100_resourceRoutines', SUBOP(SubOpsHE100.Heap)),
        0x35: makeop('o6_if', OFFSET),
        0x36: makeop('o6_ifNot', OFFSET),
        0x37: makeop('o90_wizImageOps', SUBOP(SubOpsHE100.Image)),
        0x38: makeop('o6_isAnyOf'),
        0x39: makeop('o6_wordVarInc', IMWORD),
        0x3A: makeop('o6_wordArrayInc', IMWORD),
        0x3B: makeop('o6_jump', OFFSET),
        0x3C: makeop('kernelSetFunctions'),
        0x3D: makeop('o6_land'),
        0x3E: makeop('o6_le'),
        0x3F: makeop('o60_localizeArrayToScript'),
        0x40: makeop('o6_wordArrayRead', IMWORD),
        0x41: makeop('o6_wordArrayIndexedRead', IMWORD),
        0x42: makeop('o6_lor'),
        0x43: makeop('o6_lt'),
        0x44: makeop('o90_mod'),
        0x45: makeop('o6_mul'),
        0x46: makeop('o6_neq'),
        0x47: makeop('o90_dim2dim2Array', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_BIT: (IMWORD,),
            SubOpsHE100.Array.SO_NIBBLE: (IMWORD,),
            SubOpsHE100.Array.SO_BYTE: (IMWORD,),
            SubOpsHE100.Array.SO_INT: (IMWORD,),
            SubOpsHE100.Array.SO_DWORD: (IMWORD,),
            SubOpsHE100.Array.SO_STRING: (IMWORD,),
            SubOpsHE100.Array.SO_UNDIM_ARRAY: (IMWORD,),
        })),
        0x49: makeop('o90_redim2dimArray', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_BYTE: (IMWORD,),
            SubOpsHE100.Array.SO_INT: (IMWORD,),
            SubOpsHE100.Array.SO_DWORD: (IMWORD,),
        })),
        0x4A: makeop('o6_not'),
        0x4C: makeop('o6_beginOverride'),
        0x4D: makeop('o6_endOverride'),
        0x4E: makeop('o72_resetCutscene'),
        0x4F: makeop('o6_setOwner'),
        0x50: makeop('o90_paletteOps', SUBOP(SubOpsHE100.Common)),
        0x51: makeop('o70_pickupObject'),
        0x52: makeop('o71_polygonOps', SUBOP(SubOpsHE100.Common)),
        0x53: makeop('o6_pop'),
        0x54: makeop('o6_printDebug', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE100.Common.SO_FORMATTED_STRING: (MSG_OP,),
        })),  # o6_printDebug
        0x55: makeop('o72_printWizImage'),
        0x56: makeop('o6_printLine', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE100.Common.SO_FORMATTED_STRING: (MSG_OP,),
        })),  # o6_printLine
        0x57: makeop('o6_printSystem', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE100.Common.SO_FORMATTED_STRING: (MSG_OP,),
        })),  # o6_printSystem
        0x58: makeop('o6_printText', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE100.Common.SO_FORMATTED_STRING: (MSG_OP,),
        })),  # o6_printText
        0x59: makeop('o90_priorityChainScript', SUBOP(SubOpsHE100.Script)),
        0x5A: makeop('o90_priorityStartScript', SUBOP(SubOpsHE100.Script)),
        # TODO: 0x5b: makeop('o6_pseudoRoom'),
        0x5C: makeop('o6_pushByte', IMBYTE),
        0x5D: makeop('o72_pushDWord', IMDWORD),
        0x5E: makeop('o72_getScriptString', MSG_OP),
        0x5F: makeop('o6_pushWord', IMWORD),
        0x60: makeop('o6_pushWordVar', IMWORD),
        0x61: makeop('o6_putActorAtObject'),
        0x62: makeop('o6_putActorAtXY'),
        0x64: makeop('o72_redimArray', SUBOP(SubOpsHE100.Array, {
            SubOpsHE100.Array.SO_BYTE: (IMWORD,),
            SubOpsHE100.Array.SO_INT: (IMWORD,),
            SubOpsHE100.Array.SO_DWORD: (IMWORD,),
        })),
        0x65: makeop('o72_rename'),
        0x66: makeop('o6_stopObjectCodeReturn'),  # o6_stopObjectCode
        0x67: makeop('o80_localizeArrayToRoom'),
        0x68: makeop('o6_roomOps', SUBOP(SubOpsHE100.Room)),
        0x69: makeop('o6_printActor', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE100.Common.SO_FORMATTED_STRING: (MSG_OP,),
        })),  # o6_printActor
        0x6A: makeop('o6_printEgo', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_TEXTSTRING: (MSG_OP,),
            SubOpsHE100.Common.SO_FORMATTED_STRING: (MSG_OP,),
        })),  # o6_printEgo
        0x6B: makeop('o72_talkActor', MSG_OP),
        0x6C: makeop('o72_talkEgo', MSG_OP),
        0x6E: makeop('o60_seekFilePos'),
        0x6F: makeop('o6_setBoxFlags'),
        # TODO: 0x71: makeop('o6_setBoxSet'),
        0x72: makeop('o72_setSystemMessage', SUBOP(SubOpsHE100.System)),
        0x73: makeop('o6_shuffle', IMWORD),
        0x74: makeop('o6_delay'),
        # TODO: 0x75: makeop('o6_delayMinutes'),
        0x76: makeop('o6_delaySeconds'),
        0x77: makeop('o70_soundOps', SUBOP(SubOpsHE100.Sound)),
        0x78: makeop('o80_sourceDebug', IMDWORD, IMDWORD),
        0x79: makeop('o90_setSpriteInfo', SUBOP(SubOpsHE100.Common)),
        0x7A: makeop('o6_stampObject'),
        0x7B: makeop('o72_startObject', SUBOP(SubOpsHE100.Script)),
        0x7C: makeop('o72_startScript', SUBOP(SubOpsHE100.Script)),
        # TODO: 0x7d: makeop('o6_startScriptQuick'),
        0x7E: makeop('o80_setState'),
        0x7F: makeop('o6_stopObjectScript'),
        0x80: makeop('o6_stopScript'),
        0x81: makeop('o6_stopSentence'),
        0x82: makeop('o6_stopSound'),
        0x83: makeop('o6_stopTalking'),
        0x84: makeop('o6_writeWordVar', IMWORD),
        0x85: makeop('o6_wordArrayWrite', IMWORD),
        0x86: makeop('o6_wordArrayIndexedWrite', IMWORD),
        0x87: makeop('o6_sub'),
        0x88: makeop('o72_systemOps', SUBOP(SubOpsHE100.System)),
        0x8A: makeop('o72_setTimer', SUBOP(SubOpsHE100.Common)),
        0x8B: makeop('o80_cursorCommand', SUBOP(SubOpsHE100.Cursor)),
        0x8C: makeop('videoOps', SUBOP(SubOpsHE100.Common)),
        0x8D: makeop('o6_wait', SUBOP(SubOpsHE100.Wait, {
            SubOpsHE100.Wait.SO_WAIT_FOR_ACTOR: (OFFSET,),
        })),
        # TODO: 0x8e: makeop('o6_walkActorToObj'),
        0x8F: makeop('o6_walkActorTo'),
        0x89: makeop('o90_disabled_windowOps', SUBOP(SubOpsHE100.Common)),
        0x90: makeop('o72_writeFile', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_ARRAY: (IMBYTE,),
        })),
        0x91: makeop('o72_writeINI', SUBOP(SubOpsHE100.Common)),
        0x92: makeop('o80_writeConfigFile', SUBOP(SubOpsHE100.Common)),
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
        0xA3: makeop('o90_getDistanceBetweenPoints', SUBOP(SubOpsHE100.Common)),
        0xA4: makeop('o6_ifClassOfIs'),
        0xA6: makeop('o90_cond'),
        0xA7: makeop('o90_cos'),
        0xA8: makeop('o100_debugInput', SUBOP(SubOpsHE100.Common)),
        0xA9: makeop('o80_getFileSize'),
        0xAA: makeop('o6_getActorFromXY'),
        0xAB: makeop('o72_findAllObjects'),
        0xAC: makeop('o90_findAllObjectsWithClassOf'),
        # TODO: 0xad: makeop('o71_findBox'),
        # TODO: 0xae: makeop('o6_findInventory'),
        0xAF: makeop('o72_findObject'),
        0xB0: makeop('o72_findObjectWithClassOf'),
        0xB1: makeop('o71_polygonHit'),
        0xB2: makeop('o90_getLinesIntersectionPoint', IMWORD, IMWORD),
        0xB3: makeop('o90_fontEnum', SUBOP(SubOpsHE100.Common)),
        0xB4: makeop('o72_getNumFreeArrays'),
        0xB5: makeop('o72_getArrayDimSize', IMBYTE, IMWORD),
        0xB6: makeop('o100_isResourceLoaded', SUBOP(SubOpsHE100.Common)),
        0xB7: makeop('o100_getResourceSize', SUBOP(SubOpsHE100.Common)),
        0xB8: makeop('o90_getSpriteGroupInfo', SUBOP(SubOpsHE100.Common)),
        0xB9: makeop('o72_getHeap', SUBOP(SubOpsHE100.Heap)),
        0xBA: makeop('o90_getWizData', SUBOP(SubOpsHE100.Image)),
        # TODO: 0xbb: makeop('o6_isActorInBox'),
        0xBC: makeop('o6_isAnyOf'),
        # TODO: 0xbd: makeop('o6_getInventoryCount'),
        0xBE: makeop('kernelGetFunctions'),
        0xBF: makeop('o90_max'),
        0xC0: makeop('o90_min'),
        0xC1: makeop('o72_getObjectImageX'),
        0xC2: makeop('o72_getObjectImageY'),
        0xC3: makeop('o6_isRoomScriptRunning'),
        # TODO: 0xc4: makeop('o90_getObjectData'),
        0xC5: makeop('o72_openFile'),
        0xC6: makeop('o90_getPolygonOverlap'),
        0xC7: makeop('o6_getOwner'),
        0xC8: makeop('o90_getPaletteData', SUBOP(SubOpsHE100.Common)),
        0xC9: makeop('o6_pickOneOf'),
        0xCA: makeop('o6_pickOneOfDefault'),
        0xCB: makeop('o80_pickVarRandom', IMWORD),
        0xCC: makeop('o72_getPixel', SUBOP(SubOpsHE100.Common)),
        # TODO: 0xcd: makeop('o6_distObjectObject'),
        # TODO: 0xce: makeop('o6_distObjectPt'),
        # TODO: 0xcf: makeop('o6_distPtPt'),
        0xD0: makeop('o6_getRandomNumber'),
        0xD1: makeop('o6_getRandomNumberRange'),
        0xD3: makeop('o72_readFile', SUBOP(SubOpsHE100.Common, {
            SubOpsHE100.Common.SO_ARRAY: (IMBYTE,),
        })),
        0xD4: makeop('o72_readINI', SUBOP(SubOpsHE100.Common)),
        0xD5: makeop('o80_readConfigFile', SUBOP(SubOpsHE100.Common)),
        0xD6: makeop('o6_isScriptRunning'),
        0xD7: makeop('o90_sin'),
        0xD8: makeop('o72_getSoundPosition'),
        0xD9: makeop('o6_isSoundRunning'),
        0xDA: makeop('o80_getSoundVar'),
        0xDB: makeop('o90_getSpriteInfo', SUBOP(SubOpsHE100.Common)),
        0xDC: makeop('o90_sqrt'),
        0xDD: makeop('o6_startObjectQuick'),
        0xDE: makeop('o6_startScriptQuick2'),
        0xDF: makeop('o6_getState'),
        0xE0: makeop('o71_compareString'),
        0xE1: makeop('o71_copyString'),
        0xE2: makeop('o71_appendString'),
        0xE3: makeop('o71_concatString'),
        0xE4: makeop('o70_getStringLen'),
        0xE5: makeop('o71_getStringLenForWidth'),
        0xE6: makeop('o80_stringToInt'),
        0xE7: makeop('o71_getCharIndexInString'),
        0xE8: makeop('o71_getStringWidth'),
        0xE9: makeop('o60_readFilePos'),
        0xEA: makeop('o72_getTimer', SUBOP(SubOpsHE100.Common)),
        0xEB: makeop('o6_getVerbEntrypoint'),
        0xEC: makeop('getVideoData', SUBOP(SubOpsHE100.Common)),
    }
)

OPCODES_he101: OpTable = realize(
    {
        **OPCODES_he100,
        0xA8: makeop('o72_debugInput'),
    }
)
