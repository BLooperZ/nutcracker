from functools import partial
from typing import Callable, Dict, IO, Iterable, Mapping, Optional, TypeVar

from .parser import (
    ByteValue,
    CString,
    DWordValue,
    RefOffset,
    WordValue,
    Statement,
    ScriptArg,
)

OpTable = Mapping[int, Callable[[int, IO[bytes]], Statement]]

T = TypeVar('T')
R = TypeVar('R')


def realize(src: Mapping[T, Optional[R]]) -> Dict[T, R]:
    return {key: value for key, value in src.items() if value is not None}


def simple_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return ()


def extended_b_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream),)


def extended_w_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (WordValue(stream),)


def extended_dw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (DWordValue(stream),)


def extended_bw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream), WordValue(stream))


def extended_bdw_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (ByteValue(stream), DWordValue(stream))


def jump_cmd(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (RefOffset(stream),)


def djump_cmd(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (RefOffset(stream, word_size=4),)


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
    # if ord(cmd.op) in {194}:
    #     return (cmd, arr, CString(stream))
    return (cmd, arr)


def room_ops_he60(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {221}:
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


def write_file(stream: IO[bytes]) -> Iterable[ScriptArg]:
    cmd = ByteValue(stream)
    if ord(cmd.op) in {8}:
        return (cmd, ByteValue(stream))
    return (cmd,)


def msg_op(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream),)


def msg_op_v8(stream: IO[bytes]) -> Iterable[ScriptArg]:
    return (CString(stream, var_size=4),)


def makeop(
    name: str, op: Callable[[IO[bytes]], Iterable[ScriptArg]] = simple_op
) -> Callable[[int, IO[bytes]], Statement]:
    return partial(Statement, name, op)


OPCODES_v6: OpTable = realize({
    0x00: makeop('o6_pushByte', extended_b_op),
    0x01: makeop('o6_pushWord', extended_w_op),
    # TODO: 0x02: makeop('o6_pushByteVar'),
    0x03: makeop('o6_pushWordVar', extended_w_op),
    # TODO: 0x06: makeop('o6_byteArrayRead'),
    0x07: makeop('o6_wordArrayRead', extended_w_op),
    0x0A: makeop('o6_byteArrayIndexedRead', extended_b_op),
    0x0B: makeop('o6_wordArrayIndexedRead', extended_w_op),
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
    0x43: makeop('o6_writeWordVar', extended_w_op),
    # TODO: 0x46: makeop('o6_byteArrayWrite'),
    0x47: makeop('o6_wordArrayWrite', extended_w_op),
    # TODO: 0x4a: makeop('o6_byteArrayIndexedWrite'),
    0x4B: makeop('o6_wordArrayIndexedWrite', extended_w_op),
    # TODO: 0x4e: makeop('o6_byteVarInc'),
    0x4F: makeop('o6_wordVarInc', extended_w_op),
    # TODO: 0x52: makeop('o6_byteArrayInc'),
    0x53: makeop('o6_wordArrayInc', extended_w_op),
    # TODO: 0x56: makeop('o6_byteVarDec'),
    0x57: makeop('o6_wordVarDec', extended_w_op),
    # TODO: 0x5a: makeop('o6_byteArrayDec'),
    0x5B: makeop('o6_wordArrayDec', extended_w_op),
    0x5C: makeop('o6_if', jump_cmd),  # jump if
    0x5D: makeop('o6_ifNot', jump_cmd),  # jump if not
    0x5E: makeop('o6_startScript'),
    0x5F: makeop('o6_startScriptQuick'),
    0x60: makeop('o6_startObject'),
    0x61: makeop('o6_drawObject'),
    0x62: makeop('o6_drawObjectAt'),
    0x63: makeop('o6_drawBlastObject'),
    # TODO: 0x64: makeop('o6_setBlastObjectWindow'),
    0x65: makeop('o6_stopObjectCode'),
    0x66: makeop('o6_stopObjectCode'),
    0x67: makeop('o6_endCutscene'),
    0x68: makeop('o6_cutscene'),
    # TODO: 0x69: makeop('o6_stopMusic'),
    0x6A: makeop('o6_freezeUnfreeze'),
    0x6B: makeop('o6_cursorCommand', extended_b_op),
    0x6C: makeop('o6_breakHere'),
    0x6D: makeop('o6_ifClassOfIs'),
    0x6E: makeop('o6_setClass'),
    0x6F: makeop('o6_getState'),
    0x70: makeop('o6_setState'),
    0x71: makeop('o6_setOwner'),
    0x72: makeop('o6_getOwner'),
    0x73: makeop('o6_jump', jump_cmd),
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
    0x97: makeop('o6_setObjectName', msg_op),
    0x98: makeop('o6_isSoundRunning'),
    0x99: makeop('o6_setBoxFlags'),
    0x9A: makeop('o6_createBoxMatrix'),
    0x9B: makeop('o6_resourceRoutines', extended_b_op),
    0x9C: makeop('o6_roomOps', extended_b_op),
    0x9D: makeop('o6_actorOps', actor_ops_v6),
    0x9E: makeop('o6_verbOps', verb_ops_v6),
    0x9F: makeop('o6_getActorFromXY'),
    0xA0: makeop('o6_findObject'),
    # TODO: 0xa1: makeop('o6_pseudoRoom'),
    0xA2: makeop('o6_getActorElevation'),
    0xA3: makeop('o6_getVerbEntrypoint'),
    0xA4: makeop('o6_arrayOps', array_ops_v6),
    # TODO: 0xa5: makeop('o6_saveRestoreVerbs'),
    0xA6: makeop('o6_drawBox'),
    0xA7: makeop('o6_pop'),
    0xA8: makeop('o6_getActorWidth'),
    0xA9: makeop('o6_wait', wait_ops),
    0xAA: makeop('o6_getActorScaleX'),
    # TODO: 0xab: makeop('o6_getActorAnimCounter'),
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
    # TODO: 0xbe: makeop('o6_startObjectQuick'),
    0xBF: makeop('o6_startScriptQuick2'),
    0xC0: makeop('o6_dim2dimArray', extended_bw_op),
    0xC4: makeop('o6_abs'),
    0xC5: makeop('o6_distObjectObject'),
    # TODO: 0xc6: makeop('o6_distObjectPt'),
    0xc7: makeop('o6_distPtPt'),
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
    # TODO: 0xdd: makeop('o6_findAllObjects'),
    # TODO: 0xe1: makeop('o6_getPixel'),
    # TODO: 0xe3: makeop('o6_pickVarRandom'),
    # TODO: 0xe4: makeop('o6_setBoxSet'),
    0xEC: makeop('o6_getActorLayer'),
    # TODO: 0xed: makeop('o6_getObjectNewDir'),
})

OPCODES_he60 = realize({
    **OPCODES_v6,
    0x63: None,
    0x64: None,
    0x70: makeop('o60_setState'),
    0x9A: None,
    0x9C: makeop('o60_roomOps', room_ops_he60),
    0x9D: makeop('o60_actorOps', extended_b_op),
    0xAC: None,
    0xBD: makeop('o6_stopObjectCode'),
    0xC8: makeop('o60_kernelGetFunctions'),
    0xC9: makeop('o60_kernelSetFunctions'),
    0xD9: makeop('o60_closeFile'),
    # TODO: 0xda: makeop('o60_openFile'),
    # TODO: 0xdb: makeop('o60_readFile'),
    # TODO: 0xdc: makeop('o60_writeFile'),
    # TODO: 0xde: makeop('o60_deleteFile'),
    # TODO: 0xdf: makeop('o60_rename'),
    # TODO: 0xe0: makeop('o60_soundOps'),
    0xE2: makeop('o60_localizeArrayToScript'),
    0xE9: makeop('o60_seekFilePos'),
    # TODO: 0xea: makeop('o60_redimArray'),
    # TODO: 0xeb: makeop('o60_readFilePos'),
    0xEC: None,
    0xED: None,
})

OPCODES_he70: OpTable = realize({
    **OPCODES_he60,
    0x74: makeop('o70_soundOps', extended_b_op),
    0x84: makeop('o70_pickupObject'),
    0x8C: makeop('o70_getActorRoom'),
    0x9B: makeop('o70_resourceRoutines', extended_b_op),
    # TODO: 0xae: makeop('o70_systemOps'),
    0xEE: makeop('o70_getStringLen'),
    0xF2: makeop('o70_isResourceLoaded', extended_b_op),
    # TODO: 0xf3: makeop('o70_readINI'),
    # TODO: 0xf4: makeop('o70_writeINI'),
    # TODO: 0xf9: makeop('o70_createDirectory'),
    # TODO: 0xfa: makeop('o70_setSystemMessage'),
})

OPCODES_he71: OpTable = realize({
    **OPCODES_he70,
    0xC9: makeop('o71_kernelSetFunctions'),
    # TODO: 0xec: makeop('o71_copyString'),
    0xED: makeop('o71_getStringWidth'),
    0xEF: makeop('o71_appendString'),
    # TODO: 0xf0: makeop('o71_concatString'),
    # TODO: 0xf1: makeop('o71_compareString'),
    0xF5: makeop('o71_getStringLenForWidth'),
    0xF6: makeop('o71_getCharIndexInString'),
    # TODO: 0xf7: makeop('o71_findBox'),
    0xFB: makeop('o71_polygonOps', extended_b_op),
    0xFC: makeop('o71_polygonHit'),
})

OPCODES_he72: OpTable = realize({
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
    # TODO: 0x52: makeop('o72_findObjectWithClassOf'),
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
    # TODO: 0x64: makeop('o72_getNumFreeArrays'),
    0x97: None,
    0x9C: makeop('o72_roomOps', extended_b_op),
    0x9D: makeop('o72_actorOps', extended_b_op),
    # TODO: 0x9e: makeop('o72_verbOps'),
    # TODO: 0xa0: makeop('o72_findObject'),
    0xA4: makeop('o72_arrayOps', array_ops),
    0xAE: makeop('o72_systemOps', extended_b_op),
    0xBA: makeop('o72_talkActor', msg_op),
    0xBB: makeop('o72_talkEgo', msg_op),
    0xBC: makeop('o72_dimArray', extended_bw_op),
    0xC0: makeop('o72_dim2dimArray', extended_bw_op),
    # TODO: 0xc1: makeop('o72_traceStatus'),
    0xC8: makeop('o72_kernelGetFunctions'),
    0xCE: makeop('o72_drawWizImage'),
    0xCF: makeop('o72_debugInput'),
    0xD5: makeop('o72_jumpToScript', extended_b_op),
    0xDA: makeop('o72_openFile'),
    0xDB: makeop('o72_readFile', extended_b_op),
    0xDC: makeop('o72_writeFile', write_file),
    0xDD: makeop('o72_findAllObjects'),
    0xDE: makeop('o72_deleteFile'),
    0xDF: makeop('o72_rename'),
    # TODO: 0xe1: makeop('o72_getPixel'),
    # TODO: 0xe3: makeop('o72_pickVarRandom'),
    0xEA: makeop('o72_redimArray', extended_bw_op),
    0xF3: makeop('o72_readINI', extended_b_op),
    0xF4: makeop('o72_writeINI', extended_b_op),
    0xF8: makeop('o72_getResourceSize', extended_b_op),
    0xF9: makeop('o72_createDirectory'),
    0xFA: makeop('o72_setSystemMessage', extended_b_op),
})

OPCODES_he80: OpTable = realize({
    **OPCODES_he72,
    0x45: makeop('o80_createSound', extended_b_op),
    # TODO: 0x46: makeop('o80_getFileSize'),
    0x48: makeop('o80_stringToInt'),
    0x49: makeop('o80_getSoundVar'),
    0x4A: makeop('o80_localizeArrayToRoom'),
    # TODO: 0x4c: makeop('o80_sourceDebug'),
    0x4D: makeop('o80_readConfigFile', extended_b_op),
    # TODO: 0x4e: makeop('o80_writeConfigFile'),
    0x69: None,
    # TODO: 0x6b: makeop('o80_cursorCommand'),
    0x70: makeop('o80_setState'),
    0x76: None,
    0x94: None,
    0x9E: None,
    0xA5: None,
    0xAC: makeop('o80_drawWizPolygon'),
    # TODO: 0xe0: makeop('o80_drawLine'),
    0xE3: makeop('o80_pickVarRandom', extended_w_op),
})

OPCODES_v8: OpTable = realize({
    0x01: makeop('o6_pushWord', extended_dw_op),
    0x02: makeop('o6_pushWordVar', extended_dw_op),
    0x03: makeop('o6_wordArrayRead', extended_dw_op),
    0x04: makeop('o6_wordArrayIndexedRead', extended_dw_op),
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
    0x65: makeop('o6_ifNot', djump_cmd),
    0x66: makeop('o6_jump', djump_cmd),
    0x67: makeop('o6_breakHere'),
    0x68: makeop('o6_delayFrames'),
    0x69: makeop('o8_wait', wait_ops_v8),
    0x6A: makeop('o6_delay'),
    0x6B: makeop('o6_delaySeconds'),
    0x6C: makeop('o6_delayMinutes'),
    0x6D: makeop('o6_writeWordVar', extended_dw_op),
    0x6E: makeop('o6_wordVarInc', extended_dw_op),
    0x6F: makeop('o6_wordVarDec', extended_dw_op),
    0x70: makeop('o8_dimArray', extended_bdw_op),
    0x71: makeop('o6_wordArrayWrite', extended_dw_op),
    0x72: makeop('o6_wordArrayInc', extended_dw_op),
    0x73: makeop('o6_wordArrayDec', extended_dw_op),
    0x74: makeop('o8_dim2dimArray', extended_bdw_op),
    0x75: makeop('o6_wordArrayIndexedWrite', extended_dw_op),
    0x76: makeop('o8_arrayOps', array_ops_v8),
    0x79: makeop('o6_startScript'),
    0x7A: makeop('o6_startScriptQuick'),
    0x7B: makeop('o6_stopObjectCode'),
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
    0x8F: makeop('o6_printActor', msg_cmd_v8),
    0x90: makeop('o6_printEgo', msg_cmd_v8),
    0x91: makeop('o6_talkActor', msg_op_v8),
    0x92: makeop('o6_talkEgo', msg_op_v8),
    0x93: makeop('o6_printLine', msg_cmd_v8),
    0x94: makeop('o6_printText', msg_cmd_v8),
    0x95: makeop('o6_printDebug', msg_cmd_v8),
    0x96: makeop('o6_printSystem', msg_cmd_v8),
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
    0xA5: makeop('o6_doSentence'),
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
