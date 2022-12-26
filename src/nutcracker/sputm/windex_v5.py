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

from .script.bytecode import refresh_offsets, script_map, to_bytes
from .script.opcodes import ByteValue, RefOffset, WordValue
from .script.opcodes_v5 import PARAM_1, PARAM_2, OPCODES_v5, Variable, value as ovalue


USE_SEMANTIC_CONTEXT = False

l_vars = {}
semlog = defaultdict(dict)

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


def build_print(args, version=5):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x00:
                posx = next(args)
                posy = next(args)
                assert isinstance(posx, Variable if arg.op[0] & 0x80 else WordValue), (hex(arg.op[0]), type(posx))
                assert isinstance(posy, Variable if arg.op[0] & 0x40 else WordValue), (hex(arg.op[0]), type(posy))
                yield f'at {value(posx)},{value(posy)}'
                continue
            if masked == 0x01:
                color = next(args)
                yield f'color {colored(color)}'
                continue
            if masked == 0x02:
                clip = next(args)
                yield f'clipped {value(clip)}'
                continue
            if masked == 0x04:
                assert not arg.op[0] & 0x80
                yield 'center'
                continue
            if masked == 0x06:
                if version == 3:
                    yield f'height {value(next(args))}'
                    continue
                assert not arg.op[0] & 0x80
                yield 'left'
                continue
            if masked == 0x07:
                assert not arg.op[0] & 0x80
                yield 'overhead'
                continue
            if masked == 0x08:
                yield f'voice {value(next(args))} delay {value(next(args))}'
                continue
            if masked == 0x0F:
                assert not arg.op[0] & 0x80
                yield f'{msg_val(next(args))}'
                assert not next(args, None)
                break
        yield str(arg)


def build_expr(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                val = next(args)
                yield str(value(val))
                continue
            if masked == 0x02:
                assert not arg.op[0] & 0x80
                yield '+'
                continue
            if masked == 0x03:
                assert not arg.op[0] & 0x80
                yield '-'
                continue
            if masked == 0x04:
                assert not arg.op[0] & 0x80
                yield '*'
                continue
            if masked == 0x05:
                assert not arg.op[0] & 0x80
                yield '/'
                continue
            if masked == 0x06:
                assert not arg.op[0] & 0x80
                op = next(args)
                yield f'({ops.get(op.opcode & 0x1F, str)(op) or str(op)})'
                continue
        yield str(arg)


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


def build_verb(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                yield f'image {value(next(args))}'
                continue
            if masked == 0x02:
                assert not arg.op[0] & 0x80
                yield f'name {msg_val(next(args))}'
                continue
            if masked == 0x03:
                color = next(args)
                assert isinstance(color, Variable if arg.op[0] & 0x80 else ByteValue)
                yield f'color {colored(color)}'
                continue
            if masked == 0x04:
                color = next(args)
                assert isinstance(color, Variable if arg.op[0] & 0x80 else ByteValue)
                yield f'hicolor {colored(color)}'
                continue
            if masked == 0x05:
                posx = next(args)
                posy = next(args)
                assert isinstance(posx, Variable if arg.op[0] & 0x80 else WordValue), (hex(arg.op[0]), type(posx))
                assert isinstance(posy, Variable if arg.op[0] & 0x40 else WordValue), (hex(arg.op[0]), type(posy))
                yield f'at {value(posx)},{value(posy)}'
                continue
            if masked == 0x06:
                assert not arg.op[0] & 0x80
                yield 'on'
                continue
            if masked == 0x07:
                assert not arg.op[0] & 0x80
                yield 'off'
                continue
            if masked == 0x08:
                assert not arg.op[0] & 0x80
                yield 'delete'
                continue
            if masked == 0x09:
                assert not arg.op[0] & 0x80
                yield 'new'
                continue
            if masked == 0x10:
                color = next(args)
                assert isinstance(color, Variable if arg.op[0] & 0x80 else ByteValue)
                yield f'dimcolor {colored(color)}'
                continue
            if masked == 0x11:
                assert not arg.op[0] & 0x80
                yield 'dim'
                continue
            if masked == 0x12:
                key = next(args)
                assert isinstance(key, Variable if arg.op[0] & 0x80 else ByteValue)
                yield f'key {value(key)}'
                continue
            if masked == 0x13:
                assert not arg.op[0] & 0x80
                yield 'center'
                continue
            if masked == 0x14:
                # windex displays ?????????
                string = next(args)
                yield f'name *{value(string)}'
                continue
            if masked == 0x16:
                # assert not arg.op[0] & 0x80
                yield f'image {value(next(args), sem="image")} in-room {value(next(args), sem="room")}'
                continue
            if masked == 0x17:
                color = next(args)
                assert isinstance(color, Variable if arg.op[0] & 0x80 else ByteValue)
                yield f'bakcolor {colored(color)}'
                continue
        yield str(arg)


def build_sound(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                yield str(value(next(args)))
                continue
        yield str(arg)


def build_charset_color(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                yield str(value(next(args)))
                continue
        yield str(arg)

def build_script(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                yield str(value(next(args)))
                continue
        yield str(arg)

actor_convert = [
    1, 0, 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20,
]

def build_actor(args, version=5):
    args = iter(args)
    while True:
        # [00000008] actor #12 costome #208 BYTE hex=0x15 dec=21 BYTE hex=0x13 dec=19 BYTE hex=0x02 dec=2 BYTE hex=0x02 dec=2 default BYTE hex=0x02 dec=2
        # actor #12 costume #208 follow-boxes always-zclip #2 step-dist #8,#2
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            op = arg.op[0]
            if version < 5:
                op = (op & 0xE0) | actor_convert[(op & 0x1F) - 1]
            masked = op & 0x1F
            if masked == 0x01:
                yield f'costume {value(next(args), sem="costume")}'
                continue
            if masked == 0x02:
                yield f'step-dist {value(next(args))},{value(next(args))}'
                continue
            if masked == 0x03:
                yield f'sound {value(next(args), sem="sound")}'
                continue
            if masked == 0x04:
                yield f'walk-animation {value(next(args), sem="chore")}'
                continue
            if masked == 0x05:
                yield f'talk-animation {value(next(args), sem="chore")},{value(next(args), sem="chore")}'
                continue
            if masked == 0x06:
                yield f'stand-animation {value(next(args), sem="chore")}'
                continue
            if masked == 0x07:  # SO_ANIMATION  # text-offset, stop, turn, face????
                yield f'text-offset {value(next(args))},{value(next(args))}'
                continue
            if masked == 0x08:
                yield 'default'
                continue
            if masked == 0x09:
                yield f'elevation {value(next(args))}'
                continue
            if masked == 0x0A:
                yield 'animation default'
                continue
            if masked == 0x0B:
                # yield f'color {value(next(args))} is {value(next(args))}'
                yield f'palette {colored(next(args))} in-slot {colored(next(args))}'
                continue
            if masked == 0x0C:
                yield f'talk-color {colored(next(args))}'
                continue
            if masked == 0x0D:
                yield f'name {msg_val(next(args))}'
                continue
            if masked == 0x0E:
                yield f'init-animation {value(next(args), sem="chore")}'
                continue
            if masked == 0x10:
                yield f'width {value(next(args))}'
                continue
            if masked == 0x11:
                ax1 = next(args)
                if version < 5:
                    yield f'scale {value(ax1)}'
                    continue
                ax2 = next(args)
                assert isinstance(
                    ax1, Variable if arg.op[0] & PARAM_1 else ByteValue
                ) and isinstance(ax2, Variable if arg.op[0] & PARAM_2 else ByteValue)
                yield f'scale {value(ax1)} {value(ax2)}'
                continue
            if masked == 0x12:
                yield 'never-zclip'
                continue
            if masked == 0x13:
                yield f'always-zclip {value(next(args))}'
                continue
            if masked == 0x14:
                yield 'ignore-boxes'
                continue
            if masked == 0x15:
                yield 'follow-boxes'
                continue
            if masked == 0x16:
                yield f'animation-speed {value(next(args))}'
                continue
            if masked == 0x17:  # SO_SHADOW
                yield f'special-draw {value(next(args), sem="effect")}'
                continue
        yield str(arg)


def build_classes(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                yield str(value(next(args)))
                continue
        yield str(arg)


def build_draw(args):
    args = iter(args)
    while True:
        try:
            arg = next(args)
        except StopIteration:
            break
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x1:
                yield f'at {value(next(args))},{value(next(args))}'
                continue
            if masked == 0x2:
                yield f'image {value(next(args), sem="image")}'
                continue
        yield str(arg)


def build_obj(args):
    args = iter(args)
    while True:
        arg = next(args)
        if isinstance(arg, ByteValue):
            if arg.op[0] == 0xFF:
                break
            masked = arg.op[0] & 0x1F
            if masked == 0x01:
                yield str(value(next(args)))
                continue
        yield str(arg)


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


@regop(0x00)
def o5_stop_wd(op):
    if op.opcode == 0x00:
        return 'end-object'
    if op.opcode == 0x80:
        return BreakHere()
    if op.opcode == 0x60:
        scr = op.args[0]
        if scr.op[0] == 0:
            return 'unfreeze-scripts'
        return f'freeze-scripts {value(scr, sem="script")}'
    if op.opcode == 0xA0:
        return 'end-script'
    if op.opcode == 0x40:
        return 'cut-scene'
    if op.opcode == 0xC0:
        return 'end-cut-scene'


@regop(0x01)
def o5_put_act_wd(op):
    assert op.opcode & 0x1F == 0x01
    actor = op.args[0]
    posx = op.args[1]
    posy = op.args[2]
    return f'put-actor {value(actor, sem="object")} at {value(posx)},{value(posy)}'


@regop(0x02)
def o5_mus_wd(op):
    if op.opcode in {0x02, 0x82}:
        return f'start-music {value(op.args[0], sem="music")}'
    if op.opcode in {0x62, 0xE2}:
        return f'stop-script {value(op.args[0], sem="script")}'
    if op.opcode in {0x42, 0xC2}:
        scr = op.args[0]
        assert op.args[-1].op[0] == 0xFF
        params = f"({','.join(build_script(op.args[1:]))})"
        # TODO: how to detect background/recursive in chain script?
        background = ''
        recursive = ''
        # background = 'bak ' if op.opcode & 0x20 else ''
        # recursive = 'rec ' if op.opcode & 0x40 else ''
        return f'chain-script {background}{recursive}{value(scr, sem="script")} {params}'


@regop(0x03)
def o5_face_wd(op):
    if op.opcode in {0x63, 0xE3}:
        var = op.args[0]
        actor = op.args[1]
        assert isinstance(var, Variable)
        assert isinstance(actor, Variable if op.opcode & PARAM_1 else ByteValue)
        return f'{value(var)} = actor-facing {value(actor, sem="object")}'
    if op.opcode in {0x03, 0x83}:
        var = op.args[0]
        actor = op.args[1]
        assert isinstance(var, Variable)
        assert isinstance(actor, Variable if op.opcode & PARAM_1 else ByteValue)
        return f'{value(var)} = actor-room {value(actor, sem="object")}'
    if op.opcode in {0x43, 0xC3}:
        var = op.args[0]
        actor = op.args[1]
        assert isinstance(var, Variable)
        assert isinstance(actor, Variable if op.opcode & PARAM_1 else WordValue)
        return f'{value(var)} = actor-x {value(actor, sem="object")}'
    if op.opcode in {0x23, 0xA3}:
        var = op.args[0]
        actor = op.args[1]
        assert isinstance(var, Variable)
        assert isinstance(actor, Variable if op.opcode & PARAM_1 else WordValue)
        return f'{value(var)} = actor-y {value(actor, sem="object")}'


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


@regop(0x04)
def o5_greater_wd(op):
    if op.opcode in {0x04, 0x84}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return ConditionalJump(
            f'{value(op.args[0])} <= {value(op.args[1])}',
            op.args[2]
        )
    if op.opcode in {0x24, 0x64, 0xA4, 0xE4}:
        # TODO: don't display optional  'walk-to x,y' part when x,y are -1,-1
        # windex:   come-out #161 in-room #13 walk-to #202,#202 (actual value #202,#116)
        #           come-out #1035 in-room #76
        # SCUMM refrence: come-out-door object-name in-room room-name [walk x-coord,y-coord]
        return (
            f'come-out {value(op.args[0], sem="object")} in-room {value(op.args[1], sem="room")} walk-to {value(op.args[2])},{value(op.args[3])}'
        )
    if op.opcode in {0x44, 0xC4}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return ConditionalJump(
            f'{value(op.args[0])} > {value(op.args[1])}',
            op.args[2]
        )


@regop(0x05)
def o5_draw_wd(op):
    if op.opcode in {0x05, 0x45, 0x85, 0xC5}:
        obj = op.args[0]
        # assert op.args[-1].op[0] == 0xFF
        rest_params = ' '.join(build_draw(op.args[1:]))
        return f'draw-object {value(obj, sem="object")} {rest_params}'
    if op.opcode in {0x25, 0x65, 0xA5, 0xE5}:
        obj = op.args[0]
        room = op.args[1]
        return f'pick-up-object {value(obj, sem="object")} in-room {value(room, sem="room")}'


@regop(0x06)
def o5_elavation_wd(op):
    if op.opcode in {0x06, 0x86}:
        target = op.args[0]
        actor = op.args[1]
        return f'{value(target)} = actor-elevation {value(actor, sem="object")}'
    if op.opcode in {0x26, 0xA6}:
        target = op.args[0]
        num = op.args[1]
        assert len(op.args[2:]) == num.op[0]
        values = ' '.join(value(val) for val in op.args[2:])
        return f'{value(target)} = {values}'
    if op.opcode == 0x46:
        return f'++{value(op.args[0])}'
    if op.opcode == 0xC6:
        return f'--{value(op.args[0])}'


@regop(0x07)
def o5_state_wd(op):
    if op.opcode in {0x07, 0x47, 0x87, 0xC7}:
        return f'state-of {value(op.args[0], sem="object")} is {value(op.args[1], sem="state")}'
    if op.opcode == 0x27:
        sub = op.args[0]
        masked = sub.op[0] & 0x1F
        if masked == 0x01:
            return f'*{value(op.args[1])} = {msg_val(op.args[2])}'

        # 0x27 o5_setState { BYTE hex=0x02 dec=2 BYTE hex=0x2f dec=47 BYTE hex=0x30 dec=48 }
        # *#47 = *#48
        if masked == 0x02:
            return f'*{value(op.args[1])} = *{value(op.args[2])}'

        # 0x27 o5_setState { BYTE hex=0x03 dec=3 BYTE hex=0x15 dec=21 BYTE hex=0x00 dec=0 VAR_9991 }
        # *#21[#0] = #7
        if masked == 0x03:
            return f'*{value(op.args[1])}[{value(op.args[2])}] = {value(op.args[3])}'

        if masked == 0x04:
            # 0x27 o5_setState { BYTE hex=0x44 dec=68 L.2 BYTE hex=0x1e dec=30 L.0 }
            # L.{0} = *#30[L.{0}]
            return f'{value(op.args[1])} = *{value(op.args[2])}[{value(op.args[3])}]'

        if masked == 0x05:
            return f'*{value(op.args[1])}[{value(op.args[2])}]'

    else:
        return str(op)


@regop(0x08)
def o5_compare_wd(op):
    if op.opcode in {0x08, 0x88}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return ConditionalJump(
            f'{value(op.args[0])} is-not {value(op.args[1])}',
            # f'{value(op.args[0])} != {value(op.args[1])}',
            op.args[2]
        )
    if op.opcode in {0x48, 0xC8}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return ConditionalJump(
            f'{value(op.args[0])} is {value(op.args[1])}',
            # f'{value(op.args[0])} == {value(op.args[1])}',
            op.args[2]
        )
    if op.opcode == 0x28:
        return ConditionalJump(
            f'!{value(op.args[0])}',
            op.args[1]
        )
    if op.opcode == 0xA8:
        return ConditionalJump(
            f'{value(op.args[0])}',
            op.args[1]
        )
    if op.opcode in {0x68, 0xE8}:
        return f'{value(op.args[0])} = script-running {value(op.args[1], sem="script")}'


@regop(0x09)
def o5_put_owner_wd(op):
    if op.opcode in {0x29, 0x69, 0xA9, 0xE9}:
        obj = op.args[0]
        actor = op.args[1]
        return f'owner-of {value(obj, sem="object")} is {value(actor, sem="object")}'
    if op.opcode in {0x09, 0x49, 0x89, 0xC9}:
        # windex shows actor {} face-towards {}
        # SCUMM reference shows: do-animation actor-name face-towards actor-name
        # NOTE: obj value might be actually actor, as seen in: ... face-towards selected-actor
        actor = op.args[0]
        obj = op.args[1]
        return f'do-animation {value(actor, sem="object")} face-towards {value(obj, sem="object")}'
        # return f'actor {value(actor)} face-towards {value(obj)}'


@regop(0x0A)
def o5_start_script_wd(op):
    assert op.opcode & 0x1F == 0x0A
    scr = op.args[0]
    assert op.args[-1].op[0] == 0xFF
    params = f"({','.join(build_script(op.args[1:]))})"
    background = 'bak ' if op.opcode & 0x20 else ''
    recursive = 'rec ' if op.opcode & 0x40 else ''
    return f'start-script {background}{recursive}{value(scr, sem="script")} {params}'


@regop(0x0B)
def o5_wait_wd(op):
    if op.opcode == 0x2B:
        return f'sleep-for {value(op.args[0])} jiffies'
    if op.opcode in {0x0B, 0x4B, 0x8B, 0xCB}:
        return (
            f'{value(op.args[0])} = valid-verb {value(op.args[1], sem="object")}, {value(op.args[2], sem="verb")}'
        )
    if op.opcode == 0xAB:
        action = op.args[0]
        if action.op[0] == 1:
            return f'save-verbs {value(op.args[1])} to {value(op.args[2])} set {value(op.args[3])}'
        if action.op[0] == 2:
            return f'restore-verbs {value(op.args[1])} to {value(op.args[2])} set {value(op.args[3])}'
    if op.opcode in {0x6B, 0xEB}:
        return f'debug {value(op.args[0])}'


@regop(0x0C)
def o5_resource_wd(op):
    if op.opcode in {
        0x0C,
        # 0x8C  # TODO: commented out to check if this really happens
    }:
        sub = op.args[0]
        masked = ord(sub.op) & 0x1F
        if masked == 0x01:
            return f'load-script {value(op.args[1], sem="script")}'
        if masked == 0x02:
            return f'load-sound {value(op.args[1], sem="sound")}'
        if masked == 0x03:
            return f'load-costume {value(op.args[1], sem="costume")}'
        if masked == 0x04:
            return f'load-room {value(op.args[1], sem="room")}'
        if masked == 0x05:
            return f'nuke-script {value(op.args[1], sem="script")}'
        if masked == 0x06:
            return f'nuke-sound {value(op.args[1], sem="sound")}'
        if masked == 0x07:
            return f'nuke-costume {value(op.args[1], sem="costume")}'
        if masked == 0x08:
            return f'nuke-room {value(op.args[1], sem="room")}'
        if masked == 0x09:
            return f'lock-script {value(op.args[1], sem="script")}'
        if masked == 0x0A:
            return f'lock-sound {value(op.args[1], sem="sound")}'
        if masked == 0x0B:
            return f'lock-costume {value(op.args[1], sem="costume")}'
        if masked == 0x0C:
            return f'lock-room {value(op.args[1], sem="room")}'
        if masked == 0x0D:
            return f'unlock-script {value(op.args[1], sem="script")}'
        if masked == 0x0E:
            return f'unlock-sound {value(op.args[1], sem="sound")}'
        if masked == 0x0F:
            return f'unlock-costume {value(op.args[1], sem="costume")}'
        if masked == 0x10:
            return f'unlock-room {value(op.args[1], sem="room")}'
        if masked == 0x11:
            return 'clear-heap'
        if masked == 0x12:
            # for some reason, places which should have logical nuke-charset
            # also go here (probably bug in original scripts) (should go to 0x13)
            return f'load-charset {value(op.args[1], sem="charset")}'
        if masked == 0x14:
            # windex just says '???'
            return f'load-object {value(op.args[2], sem="object")} in-room {value(op.args[1], sem="room")}'
    if op.opcode == 0x2C:
        sub = op.args[0]
        masked = ord(sub.op) & 0x1F
        if masked == 0x01:
            return 'cursor on'
        if masked == 0x02:
            return 'cursor off'
        if masked == 0x03:
            return 'userput on'
        if masked == 0x04:
            return 'userput off'
        if masked == 0x05:
            return 'cursor soft-on'
        if masked == 0x06:
            return 'cursor soft-off'
        if masked == 0x07:
            return 'userput soft-on'
        if masked == 0x08:
            return 'userput soft-off'
        if masked == 0x0A:
            return f'cursor {value(op.args[1])} image {value(op.args[2])}'
        if masked == 0x0B:
            return f'cursor {value(op.args[1])} hotspot {value(op.args[2])},{value(op.args[3])}'
        if masked == 0x0C:
            return f'cursor {value(op.args[1])}'
        if masked == 0x0D:
            return f'charset {value(op.args[1], sem="charset")}'
        if masked == 0x0E:
            # windex just says '???'
            assert op.args[-1].op[0] == 0xFF
            colors = ', '.join(build_charset_color(op.args[1:]))
            return f'charset color {colors}'
    if op.opcode == 0x4C:
        params = ' '.join(build_sound(op.args))
        return f'sound-kludge {params}'
    if op.opcode == 0xCC:
        assert op.args[-1].op[0] == 0
        rooms = ' '.join(value(val, sem="room") for val in op.args[1:-1])
        return f'pseudo-room {value(op.args[0], sem="room")} is {rooms}'
    if op.opcode == 0xAC:
        rpn = list(build_expr(op.args[1:]))
        infix = rpn_to_infix(rpn)
        return f'{value(op.args[0])} = {resolve_expr(infix)}'
    if op.opcode in {0x6C, 0xEC}:
        return f'{value(op.args[0])} = actor-width {value(op.args[1], sem="object")}'


@regop(0x0D)
def o5_put_wd(op):
    if op.opcode in {0x0D, 0x4D, 0x8D, 0xCD}:
        actor = op.args[0]
        actor2 = op.args[1]
        rng = op.args[2]
        # windex: walk #2 to-actor #1 with-in 40
        # SCUMM reference: walk actor-name to actor-name within number
        return f'walk {value(actor, sem="object")} to-actor {value(actor2, sem="object")} within {value(rng)}'

    if op.opcode in {0x2D, 0x6D, 0xAD, 0xED}:
        actor = op.args[0]
        room = op.args[1]
        return f'put-actor {value(actor, sem="object")} in-room {value(room, sem="room")}'


@regop(0x0E)
def o5_delay_wd(op):
    if op.opcode in {0x0E, 0x4E, 0x8E, 0xCE}:
        actor = op.args[0]
        obj = op.args[1]
        return f'put-actor {value(actor, sem="object")} at-object {value(obj, sem="object")}'
    if op.opcode == 0x2E:
        delay = int.from_bytes(
            op.args[2].op + op.args[1].op + op.args[0].op,
            byteorder='big',
            signed=False,
        )
        return f'sleep-for {delay} jiffies'
    if op.opcode == 0xAE:
        sub = op.args[0]
        masked = sub.op[0] & 0x1F
        if masked == 0x01:
            actor = op.args[1]
            return f'wait-for-actor {value(actor, sem="object")}'
        if masked == 0x02:
            return 'wait-for-message'
        if masked == 0x03:
            return 'wait-for-camera'
        if masked == 0x04:
            return 'wait-for-sentence'


@regop(0x0F)
def o5_stateof_wd(op):
    if op.opcode in {0x0F, 0x8F}:
        var = op.args[0]
        obj = op.args[1]
        return f'{value(var)} = state-of {value(obj, sem="object")}'


@regop(0x10)
def o5_owner_wd(op):
    if op.opcode in {0x10, 0x90}:
        var = op.args[0]
        obj = op.args[1]
        if op.opcode & 0x80:
            assert isinstance(var, Variable) and isinstance(obj, Variable)
        # elif op.opcode & 0x40:
        #     assert isinstance(var, WordValue) and isinstance(obj, Variable)
        else:
            assert isinstance(var, Variable) and isinstance(obj, WordValue), (
                type(var),
                type(obj),
            )
        return f'{value(var)} = owner-of {value(obj, sem="object")}'
    if op.opcode in {0x30, 0xB0}:
        assert not op.opcode & 0x80
        sub = op.args[0]
        masked = sub.op[0] & 0x1F
        if masked == 1:
            return f'set-box {value(op.args[1])} to {value(op.args[2], sem="box-status")}'
        if masked == 4:
            return 'set-box-path'


@regop(0x11)
def o5_inv_wd(op):
    if op.opcode in {0x11, 0x51, 0x91, 0xD1}:
        actor = op.args[0]
        chore = op.args[1]
        assert isinstance(
            actor, Variable if op.opcode & PARAM_1 else ByteValue
        ) and isinstance(chore, Variable if op.opcode & PARAM_2 else ByteValue)
        return f'do-animation {value(actor, sem="object")} {value(chore, sem="chore")}'
    if op.opcode == 0xB1:
        return f'{value(op.args[0])} = inventory-size {value(op.args[1], sem="object")}'
    if op.opcode in {0x71, 0xF1}:
        return f'{value(op.args[0])} = actor-costume {value(op.args[1], sem="object")}'


@regop(0x12)
def o5_camera_wd(op):
    if op.opcode in {0x12, 0x92}:
        return f'camera-pan-to {value(op.args[0])}'
    if op.opcode in {0x32, 0xB2}:
        return f'camera-at {value(op.args[0])}'
    if op.opcode in {0x72, 0xF2}:
        return f'current-room {value(op.args[0], sem="room")}'
    if op.opcode in {0x52, 0xD2}:
        return f'camera-follow {value(op.args[0], sem="object")}'


@regop(0x13)
def o5_room_wd(op):
    if op.opcode in {0x13, 0x53, 0x93, 0xD3}:
        actor = op.args[0]
        assert op.args[-1].op[0] == 0xFF
        rest_params = ' '.join(build_actor(op.args[1:]))
        return f'actor {value(actor, sem="object")} {rest_params}'
    if op.opcode in {0x33, 0x73, 0xB3, 0xF3}:
        sub = op.args[0]
        masked = sub.op[0] & 0x1F
        if masked == 0x01:
            return f'room-scroll {value(op.args[1])} to {value(op.args[2])}'
        if masked == 0x02:
            return f'room-color {value(op.args[1])} in-slot {value(op.args[2])}'
        if masked == 0x03:
            return f'set-screen {value(op.args[1])} to {value(op.args[2])}'
        if masked == 0x04:
            return f'palette {value(op.args[1])} in-slot {value(op.args[2])}'
        if masked == 0x05:
            return f'shake on'
        if masked == 0x06:
            return f'shake off'
        if masked == 0x08:
            # windex displays empty string here for some reason
            return f'palette intensity {value(op.args[1])} in-slot {value(op.args[2])} to {value(op.args[3])}'
        if masked == 0x09:
            # windex output: saveload-game #1 in-slot #26
            # according to SCUMM reference, original scripts might have save-game / load-game according to first arg (1 for save 2 for load)
            return f'saveload-game {value(op.args[1])} in-slot {value(op.args[2])}'
        if masked == 0x0A:
            # TODO: map fades value to name
            return f'fades {value(op.args[1], sem="fade")}'
        if masked == 0x0B:
            # windex displays empty string here for some reason
            # not found in SCUMM refrence, string is made up
            return f'palette intensity [rgb] {value(op.args[1])} {value(op.args[2])} {value(op.args[3])} in-slot {value(op.args[5])} to {value(op.args[6])}'
        if masked == 0x0C:
            # windex displays empty string here for some reason
            # not found in SCUMM refrence, string is made up
            return f'room-shadow [rgb] {value(op.args[1])} {value(op.args[2])} {value(op.args[3])} in-slot {value(op.args[5])} to {value(op.args[6])}'
        if masked == 0x0D:
            return f'save-string {value(op.args[1])} {msg_val(op.args[2])}'
        if masked == 0x0E:
            return f'load-string {value(op.args[1])} {msg_val(op.args[2])}'
        if masked == 0x0F:
            # windex displays empty string here for some reason
            number = op.args[1]
            start = op.args[3]
            end = op.args[4]
            time = op.args[6]
            return f'palette transform {value(number)} {value(start)} to {value(end)} within {value(time)}'
        if masked == 0x10:
            # unverified
            slot = op.args[1]
            speed = op.args[2]
            return f'palette cycle-speed {value(slot)} is {value(speed)}'



@regop(0x14)
def o5_print_wd(op, version=5):
    if op.opcode in {0x14, 0x94}:
        # 0x14 o5_print { BYTE hex=0xfd dec=253 BYTE hex=0x0f dec=15 MSG b'\xff\n\x02#\xff\n\xad\x04\xff\n\x08\x00\xff\n\x00\x00' }
        # -> print-debug "....."

        # 0x14 o5_print { BYTE hex=0xff dec=255 BYTE hex=0x00 dec=0 WORD hex=0x00a0 dec=160 WORD hex=0x0008 dec=8 BYTE hex=0x04 dec=4 BYTE hex=0x07 dec=7 BYTE hex=0xff dec=255 }
        # -> print-line at #160,#8 center overhead
        actor = op.args[0]
        params = ' '.join(build_print(op.args[1:], version=version))
        if isinstance(actor, ByteValue):
            if actor.op[0] == 0xFC:
                return f'print-system {params}'
            if actor.op[0] == 0xFD:
                return f'print-debug {params}'
            if actor.op[0] == 0xFE:
                return f'print-text {params}'
            if actor.op[0] == 0xFF:
                return f'print-line {params}'
        return f'say-line {value(actor, sem="object")} {params}'
    if op.opcode in {0x54, 0xD4}:
        return f'new-name-of {value(op.args[0])} is {msg_val(op.args[1])}'
    if op.opcode in {0x34, 0x74, 0xB4, 0xF4}:
        var = op.args[0]
        return f'{value(var)} = proximity {value(op.args[1], sem="object")},{value(op.args[2], sem="object")}'
    else:
        return str(op)


@regop(0x15)
def o5_pos_wd(op):
    if op.opcode in {0x35, 0x75, 0xB5, 0xF5}:
        obj = op.args[0]
        return f'{value(obj)} = find-object {value(op.args[1])},{value(op.args[2])}'
    if op.opcode in {0x15, 0x55, 0x95, 0xD5}:
        obj = op.args[0]
        return f'{value(obj)} = find-actor {value(op.args[1])},{value(op.args[2])}'


@regop(0x16)
def o5_random_wd(op):
    if op.opcode in {0x16, 0x96}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else ByteValue)
        return f'{value(op.args[0])} = random {value(op.args[1])}'
    if op.opcode in {0x56, 0xD6}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else ByteValue)
        return f'{value(op.args[0])} = actor-moving {value(op.args[1], sem="object")}'
    if op.opcode in {0x36, 0x76, 0xB6, 0xF6}:
        actor = op.args[0]
        obj = op.args[1]
        return f'walk {value(actor, sem="object")} to-object {value(obj, sem="object")}'


@regop(0x17)
def o5_and_wd(op):
    if op.opcode in {0x17, 0x97}:
        var = op.args[0]
        val = op.args[1]
        return f'{value(var)} &= {value(val)}'
    if op.opcode in {0x57, 0xD7}:
        var = op.args[0]
        val = op.args[1]
        return f'{value(var)} |= {value(val)}'
    if op.opcode in {0x37, 0x77, 0xB7, 0xF7}:
        scr = op.args[0]
        ver = op.args[1]
        assert op.args[-1].op[0] == 0xFF
        params = f"({','.join(build_obj(op.args[2:]))})"
        return f'start-object {value(scr, sem="object")} verb {value(ver, sem="verb")} {params}'


@regop(0x18)
def o5_jump_wd(op):
    if op.opcode == 0x18:
        return UnconditionalJump(op.args[0])
        # return f'jump {adr(op.args[0])}'
    if op.opcode == 0x58:
        assert isinstance(op.args[0], ByteValue)
        if op.args[0].op[0] != 0:
            assert op.args[0].op[0] == 1, op.args[0]
            return f'override {value(op.args[0])}'
        else:
            return 'override off'
    if op.opcode in {0x38, 0xB8}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return ConditionalJump(
            f'{value(op.args[0])} >= {value(op.args[1])}',
            op.args[2]
        )
    if op.opcode in {0x78, 0xF8}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return ConditionalJump(
            f'{value(op.args[0])} < {value(op.args[1])}',
            op.args[2]
        )
    if op.opcode == 0xD8:
        params = ' '.join(build_print(op.args))
        return f'say-line {params}'
    if op.opcode == 0x98:
        return ['restart', 'pause', 'quit'][op.args[0].op[0] - 1]


@regop(0x19)
def o5_do_sentence_wd(op):
    var = op.args[0]
    if isinstance(var, ByteValue) and var.op[0] == 254:
        return 'stop-sentence'
    return f'do-sentence {value(var, sem="verb")} {value(op.args[1], sem="object")} with {value(op.args[2], sem="object")}'


@regop(0x1A)
def o5_move_wd(op):
    if op.opcode == 0x1A:  # VAR = WORD
        # assert isinstance(op.args[1], WordValue), op.args[1]
        return f'{value(op.args[0])} = {value(op.args[1])}'
    if op.opcode == 0x9A:  # VAR = VAR
        # assert isinstance(op.args[1], Variable), op.args[1]
        return f'{value(op.args[0])} = {value(op.args[1])}'
    if op.opcode in {0x7A, 0xFA}:
        verb = op.args[0]
        assert isinstance(op.args[0], Variable if op.opcode & 0x80 else ByteValue)
        assert op.args[-1].op[0] == 0xFF
        rest_params = ' '.join(build_verb(op.args[1:]))
        return f'verb {value(verb, sem="verb")} {rest_params}'
    if op.opcode in {0x3A, 0xBA}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return f'{value(op.args[0])} -= {value(op.args[1])}'
    if op.opcode in {0x5A, 0xDA}:
        assert isinstance(op.args[1], Variable if op.opcode & 0x80 else WordValue)
        return f'{value(op.args[0])} += {value(op.args[1])}'
    else:
        return str(op)


@regop(0x1B)
def o5_mult_wd(op):
    if op.opcode in {0x1B, 0x9B}:
        left = op.args[0]
        right = op.args[1]
        if op.opcode & 0x80:
            assert isinstance(left, Variable) and isinstance(right, Variable)
        else:
            assert isinstance(left, Variable) and isinstance(right, WordValue)
        return f'{left} *= {value(right)}'
    if op.opcode in {0x5B, 0xDB}:
        left = op.args[0]
        right = op.args[1]
        if op.opcode & 0x80:
            assert isinstance(left, Variable) and isinstance(right, Variable)
        else:
            assert isinstance(left, Variable) and isinstance(right, WordValue)
        return f'{left} /= {value(right)}'
    if op.opcode in {0x3B, 0xBB}:
        var = op.args[0]
        actor = op.args[1]
        return f'{value(var)} = actor-scale {value(actor, sem="object")}'
    if op.opcode in {0x7B, 0xFB}:
        var = op.args[0]
        actor = op.args[1]
        return f'{value(var)} = actor-box {value(actor, sem="object")}'


@regop(0x1C)
def o5_sound_wd(op):
    if op.opcode in {0x1C, 0x9C}:
        sound = op.args[0]
        assert isinstance(sound, Variable if op.opcode & 0x80 else ByteValue)
        return f'start-sound {value(sound, sem="sound")}'
    if op.opcode in {0x3C, 0xBC}:
        sound = op.args[0]
        assert isinstance(sound, Variable if op.opcode & 0x80 else ByteValue)
        return f'stop-sound {value(sound, sem="sound")}'
    if op.opcode in {0x7C, 0xFC}:
        var = op.args[0]
        scr = op.args[1]
        return f'{value(var)} = sound-running {value(scr, sem="sound")}'


@regop(0x1D)
def o5_class_wd(op):
    if op.opcode in {0x5D, 0xDD}:
        obj = op.args[0]
        assert isinstance(obj, Variable if op.opcode & 0x80 else WordValue)
        assert op.args[-1].op[0] == 0xFF
        classes = ' '.join(build_classes(op.args[1:]))
        return f'class-of {value(obj, sem="object")} is {classes}'
    if op.opcode in {0x1D, 0x9D}:
        obj = op.args[0]
        assert op.args[-2].op[0] == 0xFF
        classes = ' '.join(build_classes(op.args[1:-1]))
        return ConditionalJump(
            f'class-of {value(obj, sem="object")} is {classes}',
            op.args[-1]
        )
    if op.opcode in {0x3D, 0x7D, 0xBD, 0xFD}:
        var = op.args[0]
        posx = op.args[1]
        posy = op.args[2]
        return f'{value(var)} = find-inventory {value(posx)},{value(posy)}'


@regop(0x1E)
def o5_walk_wd(op):
    assert op.opcode & 0x1F == 0x1E
    actor = op.args[0]
    posx = op.args[1]
    posy = op.args[2]
    return f'walk {value(actor, sem="object")} to {value(posx)},{value(posy)}'


@regop(0x1F)
def o5_box_wd(op):
    if op.opcode in {
        0x3F,  # o5_drawBox
        0x7F,  # o5_drawBox
        0xBF,  # o5_drawBox
        0xFF,  # o5_drawBox
    }:
        x = op.args[0]
        y = op.args[1]

        _opcode = op.args[2]
        x2 = op.args[3]
        y2 = op.args[4]
        color = op.args[5]
        return f'draw-box {value(x)},{value(y)} to {value(x2)},{value(y2)} color {colored(color)}'


def descumm_v5(data: bytes, opcodes):
    with io.BytesIO(data) as stream:
        bytecode = {}
        while True:
            next_byte = stream.read(1)
            if not next_byte:
                break
            opcode = ord(next_byte)
            try:
                op = opcodes[opcode & 0x1F](opcode, stream)
                bytecode[op.offset] = op
                # print(
                #     '=============', f'0x{op.offset:04x}', f'0x{op.offset + 8:04d}', op
                # )
                # print(
                #     f'[{op.offset + 8:08d}]', ops.get(op.opcode & 0x1F, str)(op) or op
                # )

            except Exception as e:
                print(f'{type(e)}: {str(e)}')
                print(f'{stream.tell():04x}', f'0x{opcode:02x}')
                raise e

        for _off, stat in bytecode.items():
            for arg in stat.args:
                if isinstance(arg, RefOffset):
                    assert arg.abs in bytecode, hex(arg.abs)

        assert to_bytes(bytecode) == data
        assert to_bytes(refresh_offsets(bytecode)) == data, (
            to_bytes(refresh_offsets(bytecode)),
            data,
        )
        return bytecode



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


def transform_asts(indent, asts):
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


def decompile_script(elem):
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
    bytecode = descumm_v5(script_data, OPCODES_v5)
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
                yield from print_asts(indent, transform_asts(indent, asts))
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
        res = ops.get(stat.opcode & 0x1F, str)(stat) or stat
        sts.append(res)
        asts[curref].append(res)
    yield from print_locals(indent)
    l_vars.clear()
    yield from print_asts(indent, transform_asts(indent, asts))
    if elem.tag == 'VERB' and entries:
        yield '\t}'
    yield '}'


if __name__ == '__main__':
    import argparse

    from nutcracker.sputm.tree import open_game_resource, narrow_schema
    from nutcracker.sputm.schema import SCHEMA
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
