import io
import os
import json
import operator
import itertools
from collections import defaultdict, deque
from dataclasses import dataclass
from string import printable
from typing import Iterable, Optional, OrderedDict

from nutcracker.kernel.element import Element

from nutcracker.sputm.preset import sputm
from nutcracker.sputm.strings import RAW_ENCODING, EncodingSetting
from nutcracker.sputm.tree import narrow_schema
from nutcracker.sputm.schema import SCHEMA

from .script.bytecode import descumm, script_map
from .script.opcodes import ByteValue, RefOffset
from .script.opcodes_v5 import OPCODES_v5, Variable, value as ovalue


USE_SEMANTIC_CONTEXT = False

l_vars = {}
semlog = defaultdict(dict)


def fstat(stat, *args, **kwargs):
    return stat.format(*[PrintArg(arg) for arg in args], **kwargs)


def build_params(mapping, args):
    for subop in args:
        if isinstance(subop, ByteValue) and ord(subop.op) == 0xFF:
            break
        fmt = mapping.get(subop.name)
        if fmt is None:
            yield str(subop)
            continue
        yield fstat(fmt, *subop.args)


def builder(mapping, sep=' '):
    def inner(args):
        return sep.join(build_params(mapping, args))
    return inner


def build_varargs(args, sep=' '):
    return builder({
        'ARG': '{0}',
    }, sep=sep)(args)


def value(arg, sem=None):
    res = ovalue(arg)
    if isinstance(res, Variable) and str(res).startswith('L.'):
        l_vars[str(res)] = res
    if USE_SEMANTIC_CONTEXT and sem and not isinstance(arg, Variable):
        res = int(res)
        if not semlog[sem].get(res):
            semlog[sem][res] = f'{sem}-{res}'
        return semlog[sem][res]
    return res


class PrintArg:
    def __init__(self, arg) -> None:
        self.arg = arg
    
    def __format__(self, format_spec) -> str:
        if format_spec == 'msg':
            return msg_val(self.arg)
        if format_spec == 'cvargs':
            return build_varargs(self.arg.args, sep=',')
        if format_spec == 'csvargs':
            return build_varargs(self.arg.args, sep=', ')
        if format_spec == 'svargs':
            return build_varargs(self.arg.args, sep=' ')
        return str(value(self.arg, sem=format_spec))


def print_locals(indent):
    for var in sorted(l_vars.values(), key=operator.attrgetter('num')):
        yield f'{indent[:-1]}local variable {var}'
    if l_vars:
        yield ''  # new line


def get_element_by_path(path: str, root: Iterable[Element]) -> Optional[Element]:
    for elem in root:
        if elem.attribs['path'] == path:
            return elem
        if path.startswith(elem.attribs['path']):
            return get_element_by_path(path, elem)
    return None


def escape_message(
    msg: bytes, escape: Optional[bytes] = None, var_size: int = 2
) -> bytes:
    controls = {0x04: 'n', 0x05: 'v', 0x06: 'o', 0x07: 's'}
    with io.BytesIO(msg) as stream:
        while True:
            c = stream.read(1)
            if c in {b'', b'\0'}:
                break
            assert c is not None
            if c == escape:
                t = stream.read(1)
                if ord(t) in controls:
                    control = controls[ord(t)]
                    num = int.from_bytes(
                        stream.read(var_size), byteorder='little', signed=False
                    )
                    c = f'%{control}{num}%'.encode()
                else:
                    c += t
                    if ord(t) not in {1, 2, 3, 8}:
                        c += stream.read(var_size)
                    c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c not in (printable.encode() + bytes(range(ord('\xE0'), ord('\xFA') + 1))):
                c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c == b'\\':
                c = b'\\\\'
            yield c


def msg_to_print(msg: bytes, encoding: EncodingSetting = RAW_ENCODING) -> str:
    return b''.join(escape_message(msg, escape=b'\xff')).decode(**encoding)


def msg_val(arg):
    # "\\xFF\\x06\\x6C\\x00" -> "%o108%"
    # "\\xFF\\x06\\x6D\\x00" -> "%o109%"
    # "\\xFF\\x06\\x07\\x00" -> "%o7%"
    # "\\xFF\\x04\\xC2\\x01" -> "%n450%"
    # "\\xFF\\x05\\x6B\\x00 \\xFF\\x06\\x6C\\x00 \\xFF\\x05\\x6E\\x00 \\xFF\\x06\\x6D\\x00" -> "%v107% %o108% %v110% %o109%"
    return json.dumps(msg_to_print(arg.msg))


def adr(arg):
    return f"&[{arg.abs + 8:08d}]"


def colored(arg):
    colors = {
        # 0: 'black',
        # 1: 'blue',
        # 2: 'green',
        # 3: 'light-purple',
        # 4: 'red',
        # 5: 'purple',
        # 6: 'brown',
        # 7: 'light-grey',
        # 8: 'dark-grey',
        # 9: 'light-blue',
        # 10: 'light-green',
        # 11: 'light-cyan',
        # 12: 'light-red',
        # 13: 'light-magenta',
        # 14: 'yellow',
        # 15: 'white'
    }
    if isinstance(arg, ByteValue):
        return colors.get(arg.op[0], value(arg))
    return value(arg)


def resolve_expr(exp):
    if isinstance(exp, list):
        return f"({' '.join(resolve_expr(e) for e in exp)})"
    return str(exp)


def rpn_to_infix(exp):
    s = deque()
    for v in exp:
        if v not in '+-*/':
            s.append(v)
        else:
            op1 = s.pop()
            op2 = s.pop()
            s.append([op2, v, op1])
    return s[0]


ops = {}

def regop(mask):
    def inner(op):
        ops[mask] = op
        return op

    return inner


@dataclass
class BreakHere:
    number: int = 1

    def __str__(self) -> str:
        num_str = f' {self.number}' if self.number > 1 else ''
        return f'break-here{num_str}'


string_params = builder(
    {
        'SO_AT': 'at {0},{1}',
        'SO_COLOR': 'color {0}',
        'SO_CLIPPED': 'clipped {0}',
        'SO_CENTER': 'center',
        'HEIGHT': 'height {0}',
        'SO_LEFT': 'left',
        'SO_OVERHEAD': 'overhead',
        'SO_SAY_VOICE': 'voice {0} delay {1}',
        'SO_TEXTSTRING': '{0:msg}',
    }
)


def parse_expr(args):
    for subop in args:
        if isinstance(subop, ByteValue) and ord(subop.op) == 0xFF:
            break
        if subop.name == 'OPERATION':
            op = subop.args[0]
            yield f'({ops.get(op.name, str)(op) or str(op)})'
            continue
        fmt = {
            'ARG': '{0}',
            'ADD': '+',
            'SUBSTRACT': '-',
            'MULTIPLY': '*',
            'DIVIDE': '/',
        }.get(subop.name)
        if fmt is None:
            yield str(subop)
            continue
        yield fstat(fmt, *subop.args)


@dataclass
class ConditionalJump:
    expr: str
    ref: RefOffset

    def __str__(self) -> str:
        return f'if !({self.expr}) jump {adr(self.ref)}'

@dataclass
class UnconditionalJump:
    ref: RefOffset

    def __str__(self) -> str:
        return f'jump {adr(self.ref)}'


@regop('o5_stopObjectCode')
def o5_stopObjectCode_wd(op):
    return 'end-object' if op.opcode == 0x00 else 'end-script'


@regop('o5_cutscene')
def o5_cutscene_wd(op):
    return fstat('cut-scene {0:svargs}', *op.args)


@regop('o5_freezeScripts')
def o5_freezeScripts_wd(op):
    scr = op.args[0]
    if ord(scr.op) == 0:
        return 'unfreeze-scripts'
    return fstat('freeze-scripts {0:script}', *op.args)


@regop('o5_breakHere')
def o5_breakHere_wd(op):
    return BreakHere()


@regop('o5_endCutscene')
def o5_endCutscene_wd(op):
    return 'end-cut-scene'


@regop('o5_putActor')
def o5_putActor_wd(op):
    return fstat('put-actor {0:object} at {1},{2}', *op.args)


@regop('o5_startMusic')
def o5_startMusic_wd(op):
    return fstat('start-music {0:music}', *op.args)


@regop('o5_chainScript')
def o5_chainScript_wd(op):
    # TODO: how to detect background/recursive in chain script?
    return fstat(
        'chain-script {background}{recursive}{0:script} ({1:cvargs})',
        *op.args,
        background='',  # 'bak ' if op.opcode & 0x20 else ''
        recursive='',  # 'rec ' if op.opcode & 0x40 else ''
    )


@regop('o5_stopScript')
def o5_stopScript_wd(op):
    return fstat('stop-script {0:script}', *op.args)


@regop('o5_getActorRoom')
def o5_getActorRoom_wd(op):
    return fstat('{0} = actor-room {1:object}', *op.args)


@regop('o5_getActorY')
def o5_getActorY_wd(op):
    return fstat('{0} = actor-y {1:object}', *op.args)


@regop('o5_getActorX')
def o5_getActorX_wd(op):
    return fstat('{0} = actor-x {1:object}', *op.args)


@regop('o5_getActorFacing')
def o5_getActorFacing_wd(op):
    return fstat('{0} = actor-facing {1:object}', *op.args)

@regop('o5_isGreaterEqual')
def o5_isGreaterEqual_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('{0} <= {1}', *args),
        offset,
    )


@regop('o5_isLess')
def o5_isLess_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('{0} > {1}', *args),
        offset,
    )


@regop('o5_loadRoomWithEgo')
def o5_loadRoomWithEgo_wd(op):
    # TODO: don't display optional  'walk-to x,y' part when x,y are -1,-1
    # windex:   come-out #161 in-room #13 walk-to #202,#202 (actual value #202,#116)
    #           come-out #1035 in-room #76
    # SCUMM refrence: come-out-door object-name in-room room-name [walk x-coord,y-coord]
    return fstat('come-out {0:object} in-room {1:room} walk-to {2},{3}', *op.args)


@regop('o5_drawObject')
def o5_drawObject_wd(op):
    obj, *args = op.args
    params = builder({
        'AT': 'at {0},{1}',
        'STATE': 'image {0:state}',
    })
    return fstat('draw-object {0:object} {params}', obj, params=params(args))


@regop('o5_pickupObject')
def o5_pickUpObject_wd(op):
    return fstat('pick-up-object {0:object} in-room {1:room}', *op.args)


@regop('o5_getActorElevation')
def o5_getActorElevation_wd(op):
    return fstat('{0} = actor-elevation {1:object}', *op.args)


@regop('o5_setVarRange')
def o5_setVarRange_wd(op):
    target, num, *rest = op.args
    assert len(rest) == num.op[0]
    values = ' '.join(value(val) for val in rest)
    return fstat('{0} = {values}', target, values=values)


@regop('o5_increment')
def o5_increment_wd(op):
    return fstat('++{0}', *op.args)


@regop('o5_decrement')
def o5_decrement_wd(op):
    return fstat('--{0}', *op.args)


@regop('o5_setState')
def o5_setState_wd(op):
    return fstat('state-of {0:object} is {1:state}', *op.args)


@regop('o5_stringOps')
def o5_stringOps_wd(op):
    return builder({
        'ASSIGN-STRING': '*{0} = {1:msg}',
        'ASSIGN-STRING-VAR': (
            # 0x27 o5_setState { BYTE hex=0x02 dec=2 BYTE hex=0x2f dec=47 BYTE hex=0x30 dec=48 }
            # *#47 = *#48
            '*{0} = *{1}'
        ),
        'ASSIGN-INDEX': (
            # 0x27 o5_setState { BYTE hex=0x03 dec=3 BYTE hex=0x15 dec=21 BYTE hex=0x00 dec=0 VAR_9991 }
            # *#21[#0] = #7
            '*{0}[{1}] = {2}'
        ),
        'ASSIGN-VAR': (
            # 0x27 o5_setState { BYTE hex=0x44 dec=68 L.2 BYTE hex=0x1e dec=30 L.0 }
            # L.{0} = *#30[L.{0}]
            '{0} = *{1}[{2}]'
        ),
        'STRING-INDEX': '*{0}[{1}]',
    })(op.args)


@regop('o5_getStringWidth')
def o5_getStringWidth_wd(op):
    return fstat('{0} = $ string-width {1}', *op.args)


@regop('o5_isNotEqual')
def o5_isNotEqual_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('{0} is-not {1}', *args),
        offset,
    )


@regop('o5_equalZero')
def o5_equalZero_wd(op):
    var, offset = op.args
    return ConditionalJump(
        fstat('!{0}', var),
        offset,
    )


@regop('o5_notEqualZero')
def o5_notEqualZero_wd(op):
    var, offset = op.args
    return ConditionalJump(
        fstat('{0}', var),
        offset,
    )


@regop('o5_isEqual')
def o5_isEqual_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('{0} is {1}', *args),
        offset,
    )


@regop('o5_isScriptRunning')
def o5_isScriptRunning_wd(op):
    return fstat('{0} = script-running {1:script}', *op.args)


@regop('o5_faceActor')
def o5_faceActor_wd(op):
    # windex shows actor {} face-towards {}
    # SCUMM reference shows: do-animation actor-name face-towards actor-name
    # NOTE: obj value might be actually actor, as seen in: ... face-towards selected-actor
    return fstat('do-animation {0:object} face-towards {1:object}', *op.args)


@regop('o5_setOwnerOf')
def o5_setOwnerOf_wd(op):
    return fstat('owner-of {0:object} is {1:object}', *op.args)


@regop('o5_startScript')
def o5_start_script_wd(op):
    return fstat(
        'start-script {background}{recursive}{0:script} ({1:cvargs})',
        *op.args,
        background='bak ' if op.opcode & 0x20 else '',
        recursive='rec ' if op.opcode & 0x40 else ''
    )


@regop('o5_getVerbEntrypoint')
def o5_getVerbEntrypoint_wd(op):
    return fstat('{0} = valid-verb {1:object}, {2:verb}', *op.args)


@regop('o5_delayVariable')
def o5_delayVariable_wd(op):
    return fstat('sleep-for {0} jiffies', *op.args)


@regop('o5_debug')
def o5_debug_wd(op):
    return fstat('debug {0}', *op.args)


@regop('o5_saveRestoreVerbs')
def o5_saveRestoreVerbs_wd(op):
    return builder({
        'SO_SAVE_VERBS': 'save-verbs {0} to {1} set {2}',
        'SO_RESTORE_VERBS': 'restore-verbs {0} to {1} set {2}',
    })(op.args)


@regop('o5_resourceRoutines')
def o5_resourceRoutines_wd(op):
    return builder({
        'SO_LOAD_SCRIPT': 'load-script {0:script}',
        'SO_LOAD_SOUND': 'load-sound {0:sound}',
        'SO_LOAD_COSTUME': 'load-costume {0:costume}',
        'SO_LOAD_ROOM': 'load-room {0:room}',
        'SO_NUKE_SCRIPT': 'nuke-script {0:script}',
        'SO_NUKE_SOUND': 'nuke-sound {0:sound}',
        'SO_NUKE_COSTUME': 'nuke-costume {0:costume}',
        'SO_NUKE_ROOM': 'nuke-room {0:room}',
        'SO_LOCK_SCRIPT': 'lock-script {0:script}',
        'SO_LOCK_SOUND': 'lock-sound {0:sound}',
        'SO_LOCK_COSTUME': 'lock-costume {0:costume}',
        'SO_LOCK_ROOM': 'lock-room {0:room}',
        'SO_UNLOCK_SCRIPT': 'unlock-script {0:script}',
        'SO_UNLOCK_SOUND': 'unlock-sound {0:sound}',
        'SO_UNLOCK_COSTUME': 'unlock-costume {0:costume}',
        'SO_UNLOCK_ROOM': 'unlock-room {0:room}',
        'SO_CLEAR_HEAP': 'clear-heap',
        'SO_LOAD_CHARSET': 'load-charset {0:charset}',
        'SO_LOAD_OBJECT': 'load-object {1:object} in-room {0:room}',
    })(op.args)


@regop('o5_cursorCommand')
def o5_cursorCommand_wd(op):
    return builder({
        'SO_CURSOR_ON': 'cursor on',
        'SO_CURSOR_OFF': 'cursor off',
        'SO_USERPUT_ON': 'userput on',
        'SO_USERPUT_OFF': 'userput off',
        'SO_CURSOR_SOFT_ON': 'cursor soft-on',
        'SO_CURSOR_SOFT_OFF': 'cursor soft-off',
        'SO_USERPUT_SOFT_ON': 'userput soft-on',
        'SO_USERPUT_SOFT_OFF': 'userput soft-off',
        'SO_CURSOR_IMAGE': 'cursor {0:cursor} image {1:state}',
        'SO_CURSOR_HOTSPOT': 'cursor {0:cursor} hotspot {1},{2}',
        'SO_CURSOR_SET': 'cursor {0:cursor}',
        'SO_CHARSET_SET': 'charset {0:charset}',
        'CHARSET-COLOR': (
            # windex just says '???'
            'charset color {0:csvargs}'
        ),
    })(op.args)


@regop('o5_expression')
def o5_expression(op):
    var, *args = op.args
    rpn = list(parse_expr(args))
    infix = rpn_to_infix(rpn)
    return fstat('{0} = {expr}', var, expr=resolve_expr(infix))


@regop('o5_soundKludge')
def o5_soundKludge_wd(op):
    return fstat('sound-kludge {0:svargs}', *op.args)


@regop('o5_pseudoRoom')
def o5_pseudoRoom_wd(op):
    room, *rooms, term = op.args
    assert ord(term.op) == 0
    rooms = ' '.join(value(val, sem="room") for val in rooms)
    return fstat('pseudo-room {0:room} is {rooms}', room, rooms=rooms)


@regop('o5_getActorWidth')
def o5_getActorWidth_wd(op):
    return fstat('{0} = actor-width {1:object}', *op.args)


@regop('o5_walkActorToActor')
def o5_walkActorToActor_wd(op):
    # windex: walk #2 to-actor #1 with-in 40
    # SCUMM reference: walk actor-name to actor-name within number
    return fstat(
        'walk {0:object} to-actor {1:object} within {2}',
        *op.args,
    )


@regop('o5_putActorInRoom')
def o5_putActorInRoom_wd(op):
    return fstat('put-actor {0:object} in-room {1:room}', *op.args)


@regop('o5_putActorAtObject')
def o5_putActorAtObject_wd(op):
    return fstat('put-actor {0:object} at-object {1:object}', *op.args)


@regop('o5_delay')
def o5_delay_wd(op):
    delay = int.from_bytes(
        op.args[2].op + op.args[1].op + op.args[0].op,
        byteorder='big',
        signed=False,
    )
    return fstat('sleep-for {delay} jiffies', delay=delay)


@regop('o5_wait')
def o5_wait_wd(op):
    return builder({
        'SO_WAIT_FOR_ACTOR': 'wait-for-actor {0:object}',
        'SO_WAIT_FOR_MESSAGE': 'wait-for-message',
        'SO_WAIT_FOR_CAMERA': 'wait-for-camera',
        'SO_WAIT_FOR_SENTENCE': 'wait-for-sentence',
    })(op.args)


@regop('o5_getObjectState')
def o5_getObjectState_wd(op):
    return fstat('{0} = state-of {1:object}', *op.args)


@regop('o5_getObjectOwner')
def o5_getObjectOwner_wd(op):
    return fstat('{0} = owner-of {1:object}', *op.args)


@regop('o5_matrixOps')
def o5_matrixOps_wd(op):
    return builder({
        'SET-BOX-STATUS': 'set-box {0} to {1:box-status}',
        'SET-BOX-PATH': 'set-box-path',
    })(op.args)


@regop('o5_lights')
def o5_lights_wd(op):
    # WINDEX shows: lights...
    # TODO: SCUMM reference shows: lights are light-status
    # or: lights beam-size is width [,height]
    return fstat('lights {0} {1} {2}', *op.args)


@regop('o5_animateActor')
def o5_animateActor_wd(op):
    return fstat('do-animation {0:object} {1:chore}', *op.args)


@regop('o5_getActorCostume')
def o5_getActorCostume_wd(op):
    return fstat('{0} = actor-costume {1:object}', *op.args)


@regop('o5_getInventoryCount')
def o5_getInventoryCount_wd(op):
    return fstat('{0} = inventory-size {1:object}', *op.args)


@regop('o5_panCameraTo')
def o5_panCameraTo_wd(op):
    return fstat('camera-pan-to {0}', *op.args)


@regop('o5_setCameraAt')
def o5_setCameraAt_wd(op):
    return fstat('camera-at {0}', *op.args)


@regop('o5_actorFollowCamera')
def o5_actorFollowCamera_wd(op):
    return fstat('camera-follow {0:object}', *op.args)


@regop('o5_loadRoom')
def o5_loadRoom_wd(op):
    return fstat('current-room {0:room}', *op.args)


@regop('o5_actorOps')
def o5_actorOps_wd(op, version=5):
    # [00000008] actor #12 costume #208 BYTE hex=0x15 dec=21 BYTE hex=0x13 dec=19 BYTE hex=0x02 dec=2 BYTE hex=0x02 dec=2 default BYTE hex=0x02 dec=2
    # actor #12 costume #208 follow-boxes always-zclip #2 step-dist #8,#2
    actor, *args = op.args
    params = builder({
        'SO_COSTUME': 'costume {0:costume}',
        'SO_STEP_DIST': 'step-dist {0},{1}',
        'SO_SOUND': 'sound {0:sound}',
        'SO_WALK_ANIMATION': 'walk-animation {0:chore}',
        'SO_TALK_ANIMATION': 'talk-animation {0:chore},{1:chore}',
        'SO_STAND_ANIMATION': 'stand-animation {0:chore}',
        'SO_ANIMATION': (
            # SO_ANIMATION  # text-offset, stop, turn, face????
            'text-offset {0},{1}'
        ),
        'SO_DEFAULT': 'default',
        'SO_ELEVATION': 'elevation {0}',
        'SO_ANIMATION_DEFAULT': 'animation default',
        'SO_PALETTE': (
            # yield f'color {0:color} is {1:color}'
            'palette {0:color} in-slot {1:color}'
        ),
        'SO_TALK_COLOR': 'talk-color {0:color}',
        'SO_ACTOR_NAME': 'name {0:msg}',
        'SO_INIT_ANIMATION': 'init-animation {0:chore}',
        'SO_ACTOR_WIDTH': 'width {0}',
        'SO_ACTOR_SCALE': 'scale {0}' if version == 4 else 'scale {0} {1}',
        'SO_NEVER_ZCLIP': 'never-zclip',
        'SO_ALWAYS_ZCLIP': 'always-zclip {0}',
        'SO_IGNORE_BOXES': 'ignore-boxes',
        'SO_FOLLOW_BOXES': 'follow-boxes',
        'SO_ANIMATION_SPEED': 'animation-speed {0}',
        'SO_SHADOW': 'special-draw {0:effect}',
    })

    return fstat('actor {0:object} {params}', actor, params=params(args))


@regop('o5_roomOps')
def o5_roomOps_wd(op, version=5):
    return builder({
        'SO_ROOM_SCROLL': 'room-scroll {0} to {1}',
        'SO_ROOM_COLOR': 'room-color {0} in-slot {1}',
        'SO_ROOM_SCREEN': 'set-screen {0} to {1}',
        'SO_ROOM_PALETTE': 'palette {0} in-slot {1}' if version < 5 else 'palette {0} {1} {2} in-slot {4}',
        'SO_ROOM_SHAKE_ON': 'shake on {0} {1}' if version == 3 else 'shake on',
        'SO_ROOM_SHAKE_OFF': 'shake off {0} {1}' if version == 3 else 'shake off',
        'SO_ROOM_INTENSITY': (
            # windex displays empty string here for some reason
            'palette intensity {0} in-slot {1} to {2}'
        ),
        'SO_ROOM_SAVEGAME': (
            # windex output: saveload-game #1 in-slot #26
            # according to SCUMM reference, original scripts might have save-game / load-game according to first arg (1 for save 2 for load)
            'saveload-game {0} in-slot {1}'
        ),
        'SO_ROOM_FADE': (
            # TODO: map fades value to name
            'fades {0:fade}'
        ),
        'SO_RGB_ROOM_INTENSITY': (
            # windex displays empty string here for some reason
            # not found in SCUMM refrence, string is made up
            'palette intensity [rgb] {0} {1} {2} in-slot {4} to {5}'
        ),
        'SO_ROOM_SHADOW': (
            # windex displays empty string here for some reason
            # not found in SCUMM refrence, string is made up
            'room-shadow [rgb] {0} {1} {2} in-slot {4} to {5}'
        ),
        'SO_SAVE_STRING': 'save-string {0} {1:msg}',
        'SO_LOAD_STRING': 'load-string {0} {1:msg}',
        'SO_ROOM_TRANSFORM': (
            # windex displays empty string here for some reason
            'palette transform {0} {2} to {3} within {5}'
        ),
        'SO_CYCLE_SPEED': (
            # unverified
            'palette cycle-speed {0} is {1}'
        ),
    })(op.args)


@regop('o5_print')
def o5_print_wd(op):
    # 0x14 o5_print { BYTE hex=0xfd dec=253 BYTE hex=0x0f dec=15 MSG b'\xff\n\x02#\xff\n\xad\x04\xff\n\x08\x00\xff\n\x00\x00' }
    # -> print-debug "....."

    # 0x14 o5_print { BYTE hex=0xff dec=255 BYTE hex=0x00 dec=0 WORD hex=0x00a0 dec=160 WORD hex=0x0008 dec=8 BYTE hex=0x04 dec=4 BYTE hex=0x07 dec=7 BYTE hex=0xff dec=255 }
    # -> print-line at #160,#8 center overhead

    actor, *args = op.args
    return fstat(
        {
            0xFC: 'print-system {params}',
            0xFD: 'print-debug {params}',
            0xFE: 'print-text {params}',
            0xFF: 'print-line {params}',
        }.get(
            ord(actor.op) if isinstance(actor, ByteValue) else None,
            'say-line {0:object} {params}'
        ),
        actor,
        params=string_params(args)
    )


@regop('o5_setObjectName')
def o5_setObjectName_wd(op):
    return fstat('new-name-of {0:object} is {1:msg}', *op.args)

@regop('o5_getDist')
def o5_getDist_wd(op):
    return fstat('{0} = proximity {1:object},{2:object}', *op.args)


@regop('o5_actorFromPos')
def o5_actorFromPos_wd(op):
    return fstat('{0} = find-actor {1},{2}', *op.args)


@regop('o5_findObject')
def o5_findObject_wd(op):
    return fstat('{0} = find-object {1},{2}', *op.args)


@regop('o5_getRandomNr')
def o5_getRandomNr_wd(op):
    return fstat('{0} = random {1}', *op.args)


@regop('o5_getActorMoving')
def o5_getActorMoving_wd(op):
    return fstat('{0} = actor-moving {1:object}', *op.args)


@regop('o5_walkActorToObject')
def o5_walkActorToObject_wd(op):
    return fstat('walk {0:object} to-object {1:object}', *op.args)


@regop('o5_and')
def o5_and_wd(op):
    return fstat('{0} &= {1}', *op.args)


@regop('o5_or')
def o5_or_wd(op):
    return fstat('{0} |= {1}', *op.args)


@regop('o5_startObject')
def o5_startObject_wd(op):
    return fstat('start-object {0:object} verb {1:verb} ({2:cvargs})', *op.args)


@regop('o5_jumpRelative')
def o5_jumpRelative_wd(op):
    return UnconditionalJump(op.args[0])


@regop('o5_beginOverride')
def o5_beginOverride_wd(op):
    return builder({
        'OFF': 'override off',
        'ON': 'override 1',
    })(op.args)


@regop('o5_systemOps')
def o5_systemOps_wd(op):
    return builder({
        'SO_RESTART': 'restart',
        'SO_PAUSE': 'pause',
        'SO_QUIT': 'quit',
    })(op.args)


@regop('o5_printEgo')
def o5_printEgo_wd(op):
    return fstat('say-line {params}', params=string_params(op.args))


@regop('o5_isLessEqual')
def o5_isLessEqual_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('{0} >= {1}', *args),
        offset,
    )


@regop('o5_isGreater')
def o5_isGreater_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('{0} < {1}', *args),
        offset,
    )


@regop('o5_doSentence')
def o5_doSentence_wd(op):
    verb, *args = op.args
    if isinstance(verb, ByteValue) and ord(verb.op) == 0xFE:
        return fstat('stop-sentence')
    return fstat('do-sentence {0:verb} {1:object} with {2:object}', verb, *args)


@regop('o5_move')
def o5_move_wd(op):
    return fstat('{0} = {1}', *op.args)


@regop('o5_subtract')
def o5_subtract_wd(op):
    return fstat('{0} -= {1}', *op.args)


@regop('o5_add')
def o5_add_wd(op):
    return fstat('{0} += {1}', *op.args)


@regop('o5_verbOps')
def o5_verbOps_wd(op):
    verb, *args = op.args
    params = builder({
        'SO_VERB_IMAGE': 'image {0}',
        'SO_VERB_NAME': 'name {0:msg}',
        'SO_VERB_COLOR': 'color {0:color}',
        'SO_VERB_HICOLOR': 'hicolor {0:color}',
        'SO_VERB_AT': 'at {0},{1}',
        'SO_VERB_ON': 'on',
        'SO_VERB_OFF': 'off',
        'SO_VERB_DELETE': 'delete',
        'SO_VERB_NEW': 'new',
        'SO_VERB_DIMCOLOR': 'dimcolor {0:color}',
        'SO_VERB_DIM': 'dim',
        'SO_VERB_KEY': 'key {0}',
        'SO_VERB_CENTER': 'center',
        'SO_VERB_NAME_STR': (
            # windex displays ?????????
            'name *{0}'
        ),
        'IMAGE-ROOM': 'image {0:object} in-room {1:room}',
        'BAKCOLOR': 'bakcolor {0:color}',
    })

    return fstat('verb {0:verb} {params}', verb, params=params(args))


@regop('o5_multiply')
def o5_multiply_wd(op):
    return fstat('{0} *= {1}', *op.args)


@regop('o5_getActorScale')
def o5_getActorScale_wd(op):
    return fstat('{0} = actor-scale {1:object}', *op.args)


@regop('o5_divide')
def o5_divide_wd(op):
    return fstat('{0} /= {1}', *op.args)


@regop('o5_getActorWalkBox')
def o5_getActorWalkBox_wd(op):
    return fstat('{0} = actor-box {1:object}', *op.args)


@regop('o5_startSound')
def o5_startSound_wd(op):
    return fstat('start-sound {0:sound}', *op.args)


@regop('o5_stopSound')
def o5_stopSound_wd(op):
    return fstat('stop-sound {0:sound}', *op.args)


@regop('o5_isSoundRunning')
def o5_isSoundRunning_wd(op):
    return fstat('{0} = sound-running {1:sound}', *op.args)


@regop('o5_ifClassOfIs')
def o5_ifClassOfIs_wd(op):
    *args, offset = op.args
    return ConditionalJump(
        fstat('class-of {0:object} is {1:svargs}', *args),
        offset,
    )


@regop('o5_findInventory')
def o5_findInventory_wd(op):
    return fstat('{0} = find-inventory {1},{2}', *op.args)


@regop('o5_setClass')
def o5_setClass_wd(op):
    return fstat('class-of {0:object} is {1:svargs}', *op.args)


@regop('o5_walkActorTo')
def o5_walkActorTo_wd(op):
    return fstat('walk {0:object} to {1},{2}', *op.args)


@regop('o5_drawBox')
def o5_drawBox_wd(op):
    return fstat('draw-box {0},{1} to {3},{4} color {5:color}', *op.args)


obj_names = {}


def collapse_break_here(asts):
    def is_break(stat):
        return isinstance(stat, BreakHere)

    # Collapse break-here
    for _, seq in asts.items():
        grouped = itertools.groupby(list(seq), key=is_break)
        seq.clear()
        for breaker, group in grouped:
            if not breaker:
                seq.extend(group)
            else:
                seq.append(BreakHere(len(list(group))))

    return asts


def inline_complex_temp(asts):
    # Inline complex-temp
    complex_temp = Variable(0)
    complex_value = None
    for _, seq in asts.items():
        stats = list(seq)
        seq.clear()
        for st in stats:
            if str(st).startswith(f'{value(complex_temp)} = '):
                complex_value = str(st).replace(f'{value(complex_temp)} = ', '')
            elif f'{value(complex_temp)} = ' in str(st):
                complex_value = None
                seq.append(str(st).replace(f'{value(complex_temp)} = ', ''))
            elif str(st).startswith('print-system'):
                complex_value = 'key-pressed'
                seq.append(st)
            elif f'{value(complex_temp)}' in str(st):
                assert complex_value is not None
                if isinstance(st, ConditionalJump):
                    seq.append(ConditionalJump(st.expr.replace(f'{value(complex_temp)}', complex_value), st.ref))
                else:
                    seq.append(str(st).replace(f'{value(complex_temp)}', complex_value))
            else:
                seq.append(st)
    return asts


def collapse_override(asts):
    for _, seq in asts.items():
        stats = iter(list(seq))
        seq.clear()
        for st in stats:
            if str(st) == 'override 1':
                jmp = next(stats)
                seq.append(f'override {adr(jmp.ref)}')
            elif str(st) == 'override 0':
                seq.append('override off')
            else:
                seq.append(st)
    return asts


def transform_asts(indent, asts, transform=True):

    if not transform:
        return asts

    # Collapse break-here
    asts = collapse_break_here(asts)

    # Inline complex-temp
    asts = inline_complex_temp(asts)

    asts = collapse_override(asts)

    # Flow structure blocks
    deps = OrderedDict()

    blocks = list(asts.items())
    if blocks:
        deps['_entry'] = [blocks[0][0]]
    for idx, (label, seq) in enumerate(blocks):
        deps[label] = []
        for st in seq:
            if isinstance(st, ConditionalJump):
                deps[label].append(st)
        if isinstance(st, UnconditionalJump):
            deps[label].append(st)
        elif isinstance(st, str) and st.startswith('override &'):
            deps[label].append(st)
        if str(st) not in {'end-object', 'end-script'}:
            deps[label].append(blocks[idx+1][0])
        assert len(deps[label]) <= 2, len(deps[label])

    # Find for loops:
    last_label = None
    changed = True
    while changed:
        deleted = set()
        deref = set()
        changed = False
        for idx, (label, exits) in enumerate(deps.items()):
            if label in deleted:
                continue

            if len(exits) == 1:
                ex, = exits
                if isinstance(ex, str) and ex.startswith('_') and label != '_entry':
                    asts[label].extend(asts[ex])
                    del asts[ex]
                    deps[label] = deps[ex]
                    deleted |= {ex}
                    changed = True
                    break

            # for loops
            if len(exits) == 2:
                ex, fall = exits
                if isinstance(ex, ConditionalJump):
                    if adr(ex.ref) == f'&{label}':
                        cond = asts[label][-1]
                        if isinstance(cond, ConditionalJump):
                            end = None
                            adv = str(asts[label][-2])
                            step, var = adv[:2], adv[2:]
                            if step == '++' and f'{var} > ' in cond.expr:
                                asts[label].pop()  # cond
                                asts[label].pop()  # adv
                                end = cond.expr.replace(f'{var} > ', '')
                            elif step == '--' and f'{var} < ' in cond.expr:
                                asts[label].pop()  # cond
                                asts[label].pop()  # adv
                                end = cond.expr.replace(f'{var} < ', '')
                            if end and last_label is not None and asts[last_label]:
                                assert last_label == list(deps)[idx - 1]
                                init = str(asts[last_label].pop())
                                if f'{var} = ' in init:
                                    ext, fall = exits
                                    assert ext == ex
                                    asts[last_label].append(f'for {init} to {end} {step} {{')
                                    asts[last_label].extend(f'\t{st}' for st in asts[label])
                                    asts[last_label].append('}')
                                    del asts[label]
                                    deleted |= {label}
                                    deps[last_label] = [fall]

                                    if fall.startswith('_'):
                                        asts[last_label].extend(asts[fall])
                                        deps[last_label] = deps[fall]
                                        del asts[fall]
                                        deleted |= {fall}

                                    changed = True
                                    break
                                else:
                                    asts[last_label].append(init)

            # do loops
            if 1 <= len(exits) <= 2:
                ex, *falls = exits
                if isinstance(ex, (UnconditionalJump, ConditionalJump)):
                    if adr(ex.ref) == f'&{label}':
                        ext = asts[label].pop()
                        assert ext == ex
                        if [str(st) for st in asts[label]] == ['break-here'] and isinstance(ex, ConditionalJump):
                            asts[label].clear()
                            asts[label].append(f'break-until ({ex.expr})')
                        else:
                            stats = [f'\t{st}' for st in asts[label]]
                            asts[label].clear()
                            asts[label].append('do {')
                            asts[label].extend(stats)
                            if isinstance(ex, UnconditionalJump):
                                asts[label].append('}')
                            elif isinstance(ex, ConditionalJump):
                                asts[label].append(f'}} until ({ex.expr})')
                                
                            else:
                                raise ValueError()
                        deps[label] = list(falls)
                        changed = True
                        deref |= {label}
                        break


            # if statements
            if len(exits) == 2:
                ex, fall = exits
                if isinstance(ex, ConditionalJump):
                    fexits = deps[fall]
                    if len(fexits) == 1 and fexits[0] == adr(ex.ref)[1:]:
                        if fall.startswith('_'):
                            stats = [f'\t{st}' for st in asts[fall]]
                            popped = asts[label].pop()
                            assert popped == ex, (popped, ex)
                            asts[fall].clear()
                            asts[label].append(f'if ({ex.expr}) {{')
                            asts[label].extend(stats)
                            asts[label].append('}')
                            deps[label] = fexits
                            changed = True
                            del asts[fall]
                            deleted |= {fall}
                            deref |= {fexits[0]}
                            break
                    # if len(fexits) == 2 and fexits[1] == adr(ex.ref)[1:] and isinstance(fexits[0], UnconditionalJump):
                    #     if adr(fexits[0].ref) != adr(ex.ref):  # when True it's probably case statement
                    #         if len(deps[deps[fall][1]]) == 2 and adr(deps[fall][0].ref)[1:] != deps[deps[fall][1]][1]:
                    #             continue
                    #         for lbl, nexits in deps.items():
                    #             if lbl == label:
                    #                 continue
                    #             if len(nexits) == 2:
                    #                 jmp = nexits[0]
                    #                 if isinstance(jmp, (ConditionalJump, UnconditionalJump)) and adr(jmp.ref) == adr(ex.ref):
                    #                     break
                    #         else:
                    #             if fall.startswith('_'):
                    #                 asts[fall].pop()
                    #                 stats = [f'\t{st}' for st in asts[fall]]
                    #                 estats = [f'\t{st}' for st in asts[deps[fall][1]]]
                    #                 popped = asts[label].pop()
                    #                 assert popped == ex, (popped, ex)
                    #                 asts[fall].clear()
                    #                 asts[deps[fall][1]].clear()
                    #                 asts[label].append(f'if ({ex.expr}) {{')
                    #                 asts[label].extend(stats)
                    #                 asts[label].append('} else {')
                    #                 asts[label].extend(estats)
                    #                 asts[label].append('}')
                    #                 deps[label] = [adr(fexits[0].ref)[1:]]
                    #                 changed = True
                    #                 del asts[fall]
                    #                 del asts[deps[fall][1]]
                    #                 deleted |= {fall, deps[fall][1]}
                    #                 deref |= {adr(fexits[0].ref)[1:]}
                    #                 break


            # # case statement
            # if len(exits) == 2:
            #     ex, fall = exits
            #     if isinstance(ex, UnconditionalJump) and adr(ex.ref) == f'&{fall}':
            #         conds = []
            #         cases = []
            #         var = None
            #         for dep in deps:
            #             if len(deps[dep]) >= 1 and isinstance(deps[dep][0], UnconditionalJump):
            #                 if adr(deps[dep][0].ref) == adr(ex.ref):
            #                     cases.append(dep)
            #         for dep in reversed(deps):
            #             if len(deps[dep]) == 2 and isinstance(deps[dep][1], str):
            #                 if isinstance(deps[dep][0], ConditionalJump) and deps[dep][1] in cases:
            #                     if ' is ' in deps[dep][0].expr:
            #                         varc, val = deps[dep][0].expr.split(' is ')
            #                         if var is None:
            #                             var = varc
            #                         if varc == var:
            #                             conds.insert(0, dep)
            #         if conds:
            #             label = conds[0]
            #             asts[label].pop() # conditional jump
            #             asts[label].append(f'case {var} {{')
            #             for cond in conds:
            #                 ext, *falls = deps[cond]
            #                 caseval = ext.expr.replace(f'{var} is ', 'of ')
            #                 asts[label].append(f'\t{caseval} {{')
            #                 asts[label].extend(f'\t\t{st}' for st in asts[deps[cond][1]])
            #                 asts[deps[cond][1]].clear()
            #                 del asts[deps[cond][1]]
            #                 asts[label].append('\t}')
            #                 if cond != label:
            #                     asts[cond].clear()
            #                     del asts[cond]
            #             asts[label].append('}')
            #             deps[label] = [adr(ex.ref)[1:]]
            #             # asts[label].extend(asts[adr(ex.ref)[1:]])
            #             # asts[adr(ex.ref)[1:]].clear()
            #             # del asts[adr(ex.ref)[1:]]
            #             deleted |= set(conds[1:] + cases)  # + [adr(ex.ref)[1:]])
            #             deref |= {adr(ex.ref)[1:]}
            #             changed = True
            #             break

            last_label = label

        for label in deleted:
            if label in deps:
                del deps[label]

        for label in deref:
            if label in deps:
                keys = set(deps) - deref
                skip_deref = False
                for ex in deps[label]:
                    if isinstance(ex, (ConditionalJump, UnconditionalJump)):
                        if adr(ex.ref) == f'&{label}':
                            skip_deref = True
                            break
                for lb in keys:
                    if lb in deleted:
                        continue
                    for ex in deps[lb]:
                        if isinstance(ex, (ConditionalJump, UnconditionalJump)):
                            if adr(ex.ref) == f'&{label}':
                                skip_deref = True
                                break
                    if skip_deref:
                        break

                if not skip_deref:
                    for lb in keys:
                        deps[lb] = [f'_{label}' if str(ex) == label else ex for ex in deps[lb]]
                    asts = {f'_{label}' if label == lbl else lbl: block for lbl, block in asts.items()}
                    deps = {f'_{label}' if label == lbl else lbl: block for lbl, block in deps.items()}

        # print(asts)
        # print(deps)
        # print('================')
    # for label, exits in deps.items():
    #     print('\t\t\t\t', label, '->', tuple(str(ex) for ex in exits), file=file)

    return asts


def print_asts(indent, asts):
    for label, seq in asts.items():
        if not label.startswith('_'):  # or True:
            yield f'{label}:'
        for st in seq:
            yield f'{indent}{st}'


def parse_verb_meta(meta):
    with io.BytesIO(meta) as stream:
        while True:
            key = stream.read(1)
            if key in {b'\0'}:  # , b'\xFF'}:
                break
            entry = int.from_bytes(
                stream.read(2), byteorder='little', signed=False
            )
            yield key, entry - len(meta)
        assert stream.read() == b''


def semantic_key(name, sem=None):
    if USE_SEMANTIC_CONTEXT and sem:
        return f'{sem}-{name}'
    return str(name)


def decompile_script(elem, transform=True):
    if elem.tag == 'OBCD':
        obcd = elem
        elem = sputm.find('VERB', obcd)
    pref, script_data = script_map[elem.tag](elem.data)
    obj_id = None
    indent = '\t'
    if elem.tag == 'VERB':
        pref = list(parse_verb_meta(pref))
        obj_id = obcd.attribs['gid']
        obj_names[obj_id] = msg_to_print(sputm.find('OBNA', obcd).data.split(b'\0')[0])
    respath_comment = f'; {elem.tag} {elem.attribs["path"]}'
    titles = {
        'LSCR': 'script',
        'SCRP': 'script',
        'ENCD': 'enter',
        'EXCD': 'exit',
        'VERB': 'verb',
    }
    if elem.tag == 'VERB':
        yield ' '.join([f'object', semantic_key(obj_id, sem='object'), '{', os.path.dirname(respath_comment)])
        yield ' '.join([f'\tname is', f'"{obj_names[obj_id]}"'])
    else:
        scr_id = int.from_bytes(pref, byteorder='little', signed=False) if pref else None
        gid = elem.attribs['gid']
        assert scr_id is None or scr_id == gid
        gid_str = '' if gid is None else f' {semantic_key(gid, "script")}'
        yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])
    bytecode = descumm(script_data, OPCODES_v5)
    # print_bytecode(bytecode)

    refs = [off.abs for stat in bytecode.values() for off in stat.args if isinstance(off, RefOffset)]
    curref = f'_[{0 + 8:08d}]'
    sts = deque()
    asts = defaultdict(deque)
    if elem.tag == 'VERB':
        entries = {off: idx[0] for idx, off in pref}
    res = None
    for off, stat in bytecode.items():
        if elem.tag == 'VERB' and off + 8 in entries:
            if off + 8 in entries:
                if off + 8 > min(entries.keys()):
                    yield from print_locals(indent)
                l_vars.clear()
                yield from print_asts(indent, transform_asts(indent, asts, transform=transform))
                curref = f'_[{off + 8:08d}]'
                asts = defaultdict(deque)
            if off + 8 > min(entries.keys()):
                yield '\t}'
                l_vars.clear()
            yield ''  # new line
            yield f'\tverb {semantic_key(entries[off + 8], sem="verb")} {{'
            indent = 2 * '\t'
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            curref = f'_[{off + 8:08d}]'
        if off in refs:
            curref = f'[{off + 8:08d}]'
        res = ops.get(stat.name, str)(stat) or stat
        sts.append(res)
        asts[curref].append(res)
    yield from print_locals(indent)
    l_vars.clear()
    yield from print_asts(indent, transform_asts(indent, asts, transform=transform))
    if elem.tag == 'VERB' and entries:
        yield '\t}'
    yield '}'


if __name__ == '__main__':
    import argparse

    from nutcracker.sputm.tree import open_game_resource, narrow_schema
    from nutcracker.sputm.windex.scu import dump_script_file

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    filename = args.filename

    gameres = open_game_resource(filename)
    basename = gameres.basename

    root = gameres.read_resources(
        max_depth=5,
        schema=narrow_schema(
            SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}
        ),
    )

    rnam = gameres.rooms
    print(gameres.game)
    print(rnam)

    if USE_SEMANTIC_CONTEXT:
        semlog['room'].update(rnam)

    script_dir = os.path.join('scripts', gameres.game.basename)
    os.makedirs(script_dir, exist_ok=True)

    for disk in root:
        for room in sputm.findall('LFLF', disk):
            room_no = rnam.get(room.attribs['gid'], f"room_{room.attribs['gid']}")
            print(
                '==========================',
                room.attribs['path'],
                room_no,
            )
            fname = f"{script_dir}/{room.attribs['gid']:04d}_{room_no}.scu"

            with open(fname, 'w') as f:
                dump_script_file(room_no, room, decompile_script, f)

    if USE_SEMANTIC_CONTEXT:
        with open(f"{script_dir}/sem.def", 'w') as f:
            for sem, vals in semlog.items():
                for val in sorted(vals.keys()):
                    semval = semlog[sem][val]
                    if not semval:
                        continue
                    print(f'define {semval} = {val}', file=f)
                print(file=f)
