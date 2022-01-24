import io
import os
import operator
from collections import defaultdict, deque, OrderedDict
from dataclasses import dataclass
from string import printable
from typing import Iterable, Iterator, Optional
from nutcracker.kernel.element import Element

from nutcracker.sputm.preset import sputm
from nutcracker.sputm.script.parser import CString, DWordValue

from nutcracker.sputm.tree import narrow_schema
from nutcracker.sputm.schema import SCHEMA

from nutcracker.sputm.script.bytecode import script_map, descumm
from nutcracker.sputm.script.opcodes import ByteValue, RefOffset, WordValue
from nutcracker.sputm.strings import get_optable


class Value:

    suffix = {
        ByteValue: 'B',
        WordValue: 'W',
        DWordValue: 'D',
    }

    def __init__(self, orig, signed=True, cast=None):
        self.orig = orig
        self.num = int.from_bytes(orig.op, byteorder='little', signed=signed)
        self.cast = cast

    def __repr__(self):
        if self.cast == 'char':
            assert isinstance(self.orig, ByteValue)
            return f"'{chr(self.num)}'"
        suffix = self.suffix[type(self.orig)]
        return f'{self.num}'


def to_signed(arg):
    if isinstance(arg, Value):
        return Value(arg.orig, cast=arg.cast, signed=True)
    return arg


def to_unsigned(arg):
    if isinstance(arg, Value):
        return Value(arg.orig, cast=arg.cast, signed=False)
    return arg


class KeyString:
    def __init__(self, orig: CString):
        self.orig = orig
        self.cast = 'string'

    def __repr__(self):
        return f'"{self.orig.msg.decode()}"'


class Variable:

    names = {
        3: 's_overrideHit',
        9: 's_selectedActor',
        221: 's_debugMode',
        211: 'g_foo',
        # g_helogoRunning
        # g_lastRoom
        # g_staticCostume
    }

    def __init__(self, orig):
        self.orig = orig
        self.num = int.from_bytes(orig.op, byteorder='little', signed=False)
        self.cast = None

    def __repr__(self):

        pref = 'V'  # Global Variable
        if not self.num & 0xF000:
            assert self.num & 0xFFF == self.num, self.num
            if self.num in self.names:
                return self.names[self.num]
        elif self.num & 0x8000:
            pref = 'R'  # Room Variable
            # TODO: or bit varoable on < he80, B
        else:
            assert self.num & 0x4000, self.num
            pref = 'L'  # Local Variable
        num = self.num & 0xFFF
        return f'{pref}.{num}'  # [{self.cast}]'


g_vars = {}
l_vars = {}
def get_var(orig):
    while isinstance(orig, Dup):
        orig = orig.orig
    key = (type(orig), Value(orig).num)
    if not key in g_vars:
        g_vars[key] = Variable(orig)
    # print(g_vars)

    if isinstance(g_vars[key], Variable) and str(g_vars[key]).startswith('L.'):
        l_vars[str(g_vars[key])] = g_vars[key]

    return g_vars[key]


class Caster:
    def __init__(self, orig, cast=None):
        self.orig = orig
        self.cast = cast

    def __repr__(self):
        return f'{self.orig}'


class Dup:
    def __init__(self, orig):
        self.orig = orig
        self.cast = getattr(orig, 'cast', None)

    def __repr__(self):
        return f'{self.orig}'


pres = {
    '&': 2,
    '|': 2,
    '*': 3,
    '/': 3,
    '%': 3,
    '+': 4,
    '-': 4,
    '>': 6,
    '>=': 6,
    '<': 6,
    '<=': 6,
    '==': 7,
    '!=': 7,
    'and': 11,
    'or': 11,
}

class BinExpr:
    def __init__(self, op, left, right):
        self.op = op
        self.pre = pres.get(op, 1)

        while isinstance(left, Dup):
            left = left.orig
        while isinstance(right, Dup):
            right = right.orig

        self.left = left
        self.right = right

        lc = getattr(self.left, 'cast', None)
        rc = getattr(self.left, 'cast', None)

        # print(self.left, lc, self.right, rc)
        if lc is not None and not isinstance(right, str):
            self.right.cast = lc
        elif rc is not None and not isinstance(left, str):
            self.left.cast = rc


    def __repr__(self):
        left = self.left
        if isinstance(left, str) or isinstance(left, Negate) or (isinstance(left, BinExpr) and left.pre >= self.pre and left.op != self.op):
            left = f'({left})'
        right = self.right
        if isinstance(right, str) or isinstance(right, Negate) or (isinstance(right, BinExpr) and right.pre >= self.pre and right.op != self.op):
            right = f'({right})'
        return f'{left} {self.op} {right}'


class Negate:
    def __init__(self, op):
        self.op = op

    def __repr__(self):
        return f'!{self.op}'


class Abs:
    def __init__(self, op):
        self.op = op

    def __repr__(self):
        return f'abs({self.op})'


@dataclass
class ConditionalJump:
    expr: str
    ref: RefOffset

    def __str__(self) -> str:
        return f'if !( {self.expr} ) jump {adr(self.ref)}'

@dataclass
class UnconditionalJump:
    ref: RefOffset

    def __str__(self) -> str:
        return f'jump {adr(self.ref)}'


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
            elif c not in (printable.encode() + bytes(range(ord('\xE0'), ord('\xFA')))):
                c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c == b'\\':
                c = b'\\\\'
            yield c


def msg_to_print(msg: bytes, encoding: str = 'windows-1255') -> str:
    return b''.join(escape_message(msg, escape=b'\xff')).decode(encoding)


def msg_val(arg):
    # "\\xFF\\x06\\x6C\\x00" -> "%o108%"
    # "\\xFF\\x06\\x6D\\x00" -> "%o109%"
    # "\\xFF\\x06\\x07\\x00" -> "%o7%"
    # "\\xFF\\x04\\xC2\\x01" -> "%n450%"
    # "\\xFF\\x05\\x6B\\x00 \\xFF\\x06\\x6C\\x00 \\xFF\\x05\\x6E\\x00 \\xFF\\x06\\x6D\\x00" -> "%v107% %o108% %v110% %o109%"
    return f'"{msg_to_print(arg.msg)}"'


def push_str(stack, msg):
    ops['_strings'].append(msg)


def pop_str(stack):
    arr = stack.pop()
    return ops['_strings'].pop() if Value(arr.orig, signed=True).num == -1 else arr


def adr(arg):
    return f"&[{arg.abs + 8:08d}]"


ops = {'_strings': deque()}


def regop(op):
    ops[op.__name__] = op
    return op


def defop(op, stack, bytecode):
    raise NotImplementedError(f'{op} <{stack}>')
    return f'{op} <{stack}>'


@regop
def o6_startObject(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    verb = stack.pop()
    scr = stack.pop()
    flags = stack.pop()
    return f'start-object [{flags}] {scr} verb {verb}{param_str}'


@regop
def o72_startObject(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    verb = stack.pop()
    scr = stack.pop()
    assert len(op.args) == 1 and isinstance(op.args[0], ByteValue), op.args
    flags = Value(op.args[0])
    return f'start-object [{flags}] {scr} verb {verb}{param_str}'


@regop
def o6_pushByte(op, stack, bytecode):  # 0x00
    assert len(op.args) == 1 and isinstance(op.args[0], ByteValue), op.args
    stack.append(Value(op.args[0])) 


@regop
def o6_pushWord(op, stack, bytecode):  # 0x01
    assert len(op.args) == 1 and isinstance(op.args[0], WordValue), op.args
    stack.append(Value(op.args[0])) 


@regop
def o72_pushDWord(op, stack, bytecode):  # 0x02
    assert len(op.args) == 1 and isinstance(op.args[0], DWordValue), op.args
    stack.append(Value(op.args[0])) 


@regop
def o6_drawBox(op, stack, bytecode):
    color = stack.pop()
    y2 = stack.pop()
    x2 = stack.pop()
    y1 = stack.pop()
    x1 = stack.pop()
    return f'draw-box {x1},{y1} to {x2},{y2} color {color}'

@regop
def o6_setBoxFlags(op, stack, bytecode):
    # set-box box-number [box-numer ...] to box-status
    value = stack.pop()
    boxes = ' '.join(str(param) for param in get_params(stack))
    return f'set-box {boxes} to {value}'

@regop
def o6_setBoxSet(op, stack, bytecode):
    # set-box-set set
    setval = stack.pop()
    return f'set-box-set {setval}'

@regop
def o6_loadRoomWithEgo(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    room = stack.pop()
    obj = stack.pop()
    return f'come-out-door {obj} in-room {room} walk {xpos},{ypos}'


@regop
def o6_pushByteVar(op, stack, bytecode):  # 0x02
    assert len(op.args) == 1 and isinstance(op.args[0], ByteValue), op.args
    stack.append(get_var(op.args[0]))


@regop
def o6_pushWordVar(op, stack, bytecode):  # 0x03
    assert len(op.args) == 1 and isinstance(op.args[0], WordValue), op.args
    stack.append(get_var(op.args[0]))


@regop
def o6_wordArrayRead(op, stack, bytecode):  # 0x07
    arr = get_var(op.args[0])
    pos = stack.pop()
    cast = None
    if getattr(arr, 'cast', None) == 'string':
        cast = 'char'
    stack.append(Caster(f'{arr}[{pos}]', cast=cast))


@regop
def o6_byteArrayIndexedRead(op, stack, bytecode):  # 0x0A
    arr = get_var(op.args[0])
    idx = stack.pop()
    base = stack.pop()
    cast = None
    if getattr(arr, 'cast', None) == 'string':
        cast = 'char'
    stack.append(Caster(f'{arr}[{base}][{idx}]', cast=cast))


@regop
def o6_wordArrayIndexedRead(op, stack, bytecode):  # 0x0B
    arr = get_var(op.args[0])
    idx = stack.pop()
    base = stack.pop()
    cast = None
    if getattr(arr, 'cast', None) == 'string':
        cast = 'char'
    stack.append(Caster(f'{arr}[{base}][{idx}]', cast=cast))


@regop
def o6_wordArrayIndexedWrite(op, stack, bytecode):
    arr = get_var(op.args[0])
    val = stack.pop()
    idx = stack.pop()
    base = stack.pop()
    return f'{arr}[{base}][{idx}] = {val}'



@regop
def o6_dup(op, stack, bytecode):  # 0x0C
    val = stack.pop()
    if not isinstance(val, Dup):
        val = Dup(val)
    stack.append(val)
    stack.append(val)


@regop
def o6_not(op, stack, bytecode):  # 0x0D
    stack.append(Negate(stack.pop()))

@regop
def o6_abs(op, stack, bytecode):  # 0x0D
    stack.append(Abs(stack.pop()))


@regop
def o6_eq(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('==', first, second))


@regop
def o6_neq(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('!=', first, second))


@regop
def o6_gt(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('>', first, second))


@regop
def o6_ge(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('>=', first, second))


@regop
def o6_lt(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('<', first, second))


@regop
def o6_le(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('<=', first, second))


@regop
def o6_land(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('and', first, second))


@regop
def o6_lor(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('or', first, second))

@regop
def o6_band(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('&', first, second))


@regop
def o6_bor(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('|', first, second))


@regop
def o6_add(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('+', first, second))


@regop
def o6_sub(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('-', first, second))


@regop
def o6_mul(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('*', first, second))


@regop
def o6_div(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('/', first, second))


@regop
def o90_mod(op, stack, bytecode):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('%', first, second))

@regop
def o6_pop(op, stack, bytecode):
    val = stack.pop()
    if isinstance(val, Dup):
        stack.append(val)


@regop
def o6_ifNot(op, stack, bytecode):
    off, *rest = op.args
    assert not rest
    return ConditionalJump(stack.pop(), off)


@regop
def o6_if(op, stack, bytecode):
    off, *rest = op.args
    assert not rest
    return f'if ( {stack.pop()} ) jump {adr(off)}'

@regop
def o6_jump(op, stack, bytecode):
    off, *rest = op.args
    assert not rest
    return UnconditionalJump(off)


@regop
def o6_writeWordVar(op, stack, bytecode):
    assert len(op.args) == 1 and isinstance(op.args[0], WordValue), op.args
    value = stack.pop()
    var = get_var(op.args[0])
    var.cast = getattr(value, 'cast', None)
    return f'{var} = {value}'


def get_params(stack):
    num_params = stack.pop().num
    return [stack.pop() for _ in range(num_params)][::-1]


@regop
def o6_startScript(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    scr = stack.pop()
    flags = stack.pop()
    bak = ' bak' if flags.num & 1 else ''
    rec = ' rec' if flags.num & 2 else ''
    return f'start-script{bak}{rec} {scr}{param_str}'

@regop
def o6_jumpToScript(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    scr = stack.pop()
    flags = stack.pop()
    return f'chain-script [{flags}] {scr}{param_str}'


@regop
def o72_jumpToScript(op, stack, bytecode):
    params = get_params(stack)
    flags = Value(op.args[0])
    return f'chain-script [{flags}] {params}'


@regop
def o72_startScript(op, stack, bytecode):
    assert len(op.args) == 1 and isinstance(op.args[0], ByteValue), op.args
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    return f'start-script [{Value(op.args[0])}] {stack.pop()}{param_str}'


@regop
def o6_stopObjectScript(op, stack, bytecode):
    return f'stop-object {stack.pop()}'


@regop
def o6_stopScript(op, stack, bytecode):
    return f'stop-script {stack.pop()}'


@regop
def o6_arrayOps(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    arr = get_var(op.args[1])
    if sub.num == 205:
        base = stack.pop()
        base_str = '' if base.num == 0 else f'$${base}'
        return f'{arr}[{base_str}] = {msg_val(op.args[2])}' 
    if sub.num == 208:
        base = stack.pop()
        params = get_params(stack)
        param_str = f'{", ".join(str(param) for param in params)}'
        return f'{arr}[{base}] = {param_str}' 
    if sub.num == 212:
        col = stack.pop()
        params = get_params(stack)
        param_str = f'{", ".join(str(param) for param in params)}'
        base = stack.pop()
        return f'{arr}[{base}][{col}] = {param_str}' 
    return defop(op, stack, bytecode)


@regop
def o72_arrayOps(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    arr = get_var(op.args[1])
    if sub.num == 7:
        string = pop_str(stack)
        arr.cast = 'string'
        return f'{arr} = {string}'
    if sub.num == 194: # Formatted string
        num_params = stack.pop().num + 1
        params = [stack.pop() for _ in range(num_params)]
        string = pop_str(stack)
        arr.cast = 'string'
        return f'{arr} = {string} {" ".join(str(param) for param in params)}'
    if sub.num == 208:
        base = stack.pop()
        params = get_params(stack)
        return f'{arr}[{base}] = {params}'
    if sub.num == 212:
        params = get_params(stack)
        base = stack.pop()
        param_str = f'[{", ".join(str(param) for param in params)}]'
        return f'$ {arr}[{base}] = {param_str}' 
    return defop(op, stack, bytecode)


@regop
def o6_isAnyOf(op, stack, bytecode):
    params = get_params(stack)
    var = stack.pop()
    cast = getattr(var, 'cast', None)
    if cast:
        for param in params:
            param.cast = cast
    stack.append(f'{var} in [ {", ".join(str(param) for param in params)} ]')


@regop
def o72_isAnyOf(op, stack, bytecode):
    params = get_params(stack)
    var = stack.pop()
    cast = getattr(var, 'cast', None)
    if cast:
        for param in params:
            param.cast = cast
    stack.append(f'{var} in [ {", ".join(str(param) for param in params)} ]')


@regop
def o6_stopObjectCode(op, stack, bytecode):
    # TODO: this might also return the head of stack, windex: end-script / return L.{}
    return f'end-script'


@regop
def o72_getScriptString(op, stack, bytecode):
    push_str(stack, KeyString(op.args[0]))


@regop
def o72_readINI(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    string = pop_str(stack)
    if sub.num == 6:
        stack.append(Caster(f'read-ini number {string}', cast='number'))
    elif sub.num == 7:
        stack.append(Caster(f'read-ini string {string}', cast='string'))
    # raise NotImplementedError(op.args)


@regop
def o72_writeINI(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    if sub.num == 6:
        value = stack.pop()
        option = pop_str(stack)
        return f'write-ini {option} {value}'
    if sub.num == 7:
        value = pop_str(stack)
        option = pop_str(stack)
        return f'write-ini {option} {value}'
    return defop(op, stack, bytecode)


@regop
def o60_rename(op, stack, bytecode):
    target = op.args[1]
    source = op.args[0]
    return f'rename-file {msg_val(source)} to {msg_val(target)}'


@regop
def o72_rename(op, stack, bytecode):
    target = pop_str(stack)
    source = pop_str(stack)
    return f'rename-file {source} to {target}'


@regop
def o72_debugInput(op, stack, bytecode):
    string = pop_str(stack)
    stack.append(f'$ debug-input {string}')


@regop
def o72_traceStatus(op, stack, bytecode):
    string = pop_str(stack)
    return f'$ trace-status {string} {stack.pop()}'


def printer(action, op, stack):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 65:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\tat {xpos},{ypos} \\'
    if cmd.num == 66:
        return f'\tcolor {stack.pop()} \\'
    if cmd.num == 67:
        return f'\tclipped {stack.pop()} \\'
    if cmd.num == 69:
        return f'\tcenter \\'
    if cmd.num == 71:  # String
        return f'\tleft \\'
    if cmd.num == 72:  # String
        return f'\toverhead \\'
    if cmd.num == 74:  # String
        return f'\tno-talk-animation \\'
    if cmd.num == 75:  # String
        string = op.args[1]
        return f'\t{msg_val(string)}\n'
    if cmd.num == 194:  # Formatted string
        string = op.args[1]
        num_params = stack.pop().num + 1
        params = [stack.pop() for _ in range(num_params)]
        return f'\t{msg_val(string)} {" ".join(str(param) for param in params)}\n'
    if cmd.num == 225:
        res = stack.pop()
        return f'\ttalkie {res}'
    if cmd.num == 249:
        return f'\tcolors {get_params(stack)} \\'
    if cmd.num == 254:
        return f'{action} \\'
    if cmd.num == 255:
        return f'\tend'
    raise ValueError(cmd)


@regop
def o6_printDebug(op, stack, bytecode):
    return printer('print-debug', op, stack)

@regop
def o6_printText(op, stack, bytecode):
    return printer('print-text', op, stack)

@regop
def o6_printLine(op, stack, bytecode):
    return printer('print-line', op, stack)

@regop
def o6_printSystem(op, stack, bytecode):
    return printer('print-system', op, stack)

@regop
def o6_printEgo(op, stack, bytecode):
    # with io.BytesIO(b'\x09\x00') as stream:
    #     stack.append(get_var(WordValue(stream)))
    return printer('say-line', op, stack)


@regop
def o6_printActor(op, stack, bytecode):
    return printer('say-line', op, stack)


@regop
def o72_talkActor(op, stack, bytecode):
    act = stack.pop()
    return f'say-line {act} {msg_val(op.args[0])}'


@regop
def o72_talkEgo(op, stack, bytecode):
    return f'say-line {msg_val(op.args[0])}'


@regop
def o6_talkEgo(op, stack, bytecode):
    # with io.BytesIO(b'\x09\x00') as stream:
    #     stack.append(get_var(WordValue(stream)))
    return f'say-line {msg_val(op.args[0])}'


@regop
def o6_talkActor(op, stack, bytecode):
    act = stack.pop()
    return f'say-line {act} {msg_val(op.args[0])}'


@regop
def o6_setBlastObjectWindow(op, stack, bytecode):
    bottom = stack.pop()
    right = stack.pop()
    top = stack.pop()
    left = stack.pop()
    return f'& blast-object-window {left},{top} to {right},{bottom}'


@regop
def o71_getStringWidth(op, stack, bytecode):
    ln = stack.pop()
    pos = stack.pop()
    array = stack.pop()
    stack.append(f'$ string-width {array} {pos} {ln}')


@regop
def o71_getStringLenForWidth(op, stack, bytecode):
    ln = stack.pop()
    pos = stack.pop()
    array = stack.pop()
    stack.append(f'$ string-length-for-width {array} {pos} {ln}')


@regop
def o6_beginOverride(op, stack, bytecode):
    return f'override'


@regop
def o72_createDirectory(op, stack, bytecode):
    string = pop_str(stack)
    return f'$ mkdir {string}'

@regop
def o60_deleteFile(op, stack, bytecode):
    string = op.args[0]
    return f'delete-file {msg_val(string)}'


@regop
def o72_deleteFile(op, stack, bytecode):
    string = pop_str(stack)
    return f'delete-file {string}'


@regop
def o6_dimArray(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    types = {
        199: 'int',
        200: 'bit',
        201: 'nibble',
        202: 'byte',
        203: 'string',
    }
    arr = get_var(op.args[1])
    if cmd.num == 204:
        return f'undim {arr}'
    return f'dim {types[cmd.num]} array {arr}[{stack.pop()}]'


@regop
def o6_dummy(op, stack, byecode):
    return '$ dummy'


@regop
def o6_dim2dimArray(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    types = {
        199: 'int',
        200: 'bit',
        201: 'nibble',
        202: 'byte',
        203: 'string',
    }
    arr = get_var(op.args[1])
    dim2, dim1 =  stack.pop(), stack.pop()
    return f'dim {types[cmd.num]} array {arr}[{dim1}][{dim2}]'


@regop
def o72_dimArray(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    types = {
        2: 'bit',
        3: 'nibble',
        4: 'byte',
        5: 'int',
        6: 'dword',
        7: 'string',
    }
    arr = get_var(op.args[1])
    if cmd.num == 204:
        return f'undim {arr}'
    return f'dim {types[cmd.num]} array {arr}[{stack.pop()}]'


@regop
def o90_dim2dim2Array(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    types = {
        2: 'bit',
        3: 'nibble',
        4: 'byte',
        5: 'int',
        6: 'dword',
        7: 'string',
    }
    arr = get_var(op.args[1])
    order = stack.pop()  # row / column?

    dim1end = stack.pop()
    dim1start = stack.pop()
    dim2end = stack.pop()
    dim2start = stack.pop()
    return f'$ dim {types[cmd.num]} array {arr}[{dim1start}..{dim1end}][{dim2start}..{dim2end}] order {order}'


@regop
def o70_isResourceLoaded(op, stack, bytecode):
    types = {
        18: 'image',
        226: 'room',
        227: 'costume',
        228: 'sound',
        229: 'script'
    }
    sub = Value(op.args[0], signed=False)
    stack.append(f'$ {types[sub.num]}-loaded {stack.pop()}')

@regop
def o6_doSentence(op, stack, bytecode):
    obj_b = stack.pop()
    flags = stack.pop()
    obj_a = stack.pop()
    verb = stack.pop()
    return f'do-sentence {verb} {obj_a} [{flags}] {obj_b}'


@regop
def o6_soundKludge(op, stack, bytecode):
    params = get_params(stack)
    param_str = " ".join(str(param) for param in params)
    return f'sound {param_str}'


@regop
def o6_cutscene(op, stack, bytecode):
    params = get_params(stack)
    param_str = " ".join(str(param) for param in params)
    return f'cut-scene ({param_str})'


@regop
def o6_endCutscene(op, stack, bytecode):
    return 'end-cut-scene'


@regop
def o6_startSound(op, stack, bytecode):
    if False:  # >he60
        offset = stack.pop()
        return f'start-sound {stack.pop()} offset {offset}'
    return f'start-sound {stack.pop()}'


@regop
def o60_soundOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    arg = stack.pop()
    if cmd.num == 222:
        # windex shows empty string
        return f'$ set-volume {arg}'
    if cmd.num == 223:
        return f'$ unk-sound {arg}'
    if cmd.num == 224:
        # windex shows empty string
        return f'$ set-frequency {arg}'
    return defop(op, stack, bytecode)


@regop
def o70_soundOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 9:
        return f'\tsoft \\'
    if cmd.num == 23:
        val = stack.pop()
        var = stack.pop()
        res = stack.pop()
        return f'$ sfx-set {res} variable {var} to {val}'
    if cmd.num == 25:
        val = stack.pop()
        res = stack.pop()
        return f'$ sfx-set {res} volume to {val}'
    if cmd.num == 56:
        return f'\tquick \\'
    if cmd.num == 232:
        return f'$ sfx {stack.pop()} \\'
    if cmd.num == 230:
        return f'\tchannel {stack.pop()} \\'
    if cmd.num == 231:
        return f'\toffset {stack.pop()} \\'
    if cmd.num == 245:
        return f'\tloop \\'
    if cmd.num == 255:
        return f'\t(end-sfx)'
    return defop(op, stack, bytecode)


@regop
def o6_kernelSetFunctions(op, stack, bytecode):
    params = get_params(stack)
    return f'kludge {params[0]} {params[1:]}'


@regop
def o6_kernelGetFunctions(op, stack, bytecode):
    params = get_params(stack)
    stack.append(f'kludge {params[0]} {params[1:]}')


@regop
def o60_kernelSetFunctions(op, stack, bytecode):
    params = get_params(stack)
    return f'kludge {params[0]} {params[1:]}'


@regop
def o60_kernelGetFunctions(op, stack, bytecode):
    params = get_params(stack)
    stack.append(f'kludge {params[0]} {params[1:]}')


@regop
def o71_kernelSetFunctions(op, stack, bytecode):
    params = get_params(stack)
    return f'kludge {params[0]} {params[1:]}'
    # if params[0].num == 1:
    #     return f'$ restore-background {" ".join(params[1:])}'
    # if params[0].num == 21:
    #     return f'$ skip-draw on'
    # if params[0].num == 22:
    #     return f'$ skip-draw off'
    # if params[0].num == 23:
    #     return f'$ clear-charset-mask'
    # if params[0].num == 24:
    #     return f'$ redraw-all-actors-skip'
    # if params[0].num == 25:
    #     return f'$ redraw-all-actors-no-skip'
    # raise ValueError(params)

@regop
def o6_getActorFromXY(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-actor {xpos},{ypos}')


@regop
def o6_findObject(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-object {xpos},{ypos}')

@regop
def o6_findInventory(op, stack, bytecode):
    slot = stack.pop()
    act = stack.pop()
    stack.append(f'find-object {act},{slot}')


@regop
def o6_getVerbFromXY(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-verb {xpos},{ypos}')

@regop
def o6_stopSound(op, stack, bytecode):
    return f'stop-sound {stack.pop()}'


@regop
def o6_endOverride(op, stack, bytecode):
    return f'override off'


@regop
def o6_isSoundRunning(op, stack, bytecode):
    stack.append(f'sound-running {stack.pop()}')

@regop
def o6_isScriptRunning(op, stack, bytecode):
    stack.append(f'script-running {stack.pop()}')


@regop
def o6_isRoomScriptRunning(op, stack, bytecode):
    stack.append(f'object-running {stack.pop()}')


@regop
def o6_roomOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 172:
        x2 = stack.pop()
        x1 = stack.pop()
        return f'room-scroll is {x1} {x2}'
    if cmd.num == 174:
        h = stack.pop()
        b = stack.pop()
        return f'set-screen {b} to {h}'
    if cmd.num == 175:
        slot = stack.pop()
        blue = stack.pop()
        green = stack.pop()
        red = stack.pop()
        return f'palette {red} {green} {blue} in-slot {slot}'
    if cmd.num == 176:
        return 'shake on'
    if cmd.num == 177:
        return 'shake off'
    if cmd.num == 179:
        to_slot = stack.pop()
        from_slot = stack.pop()
        value = stack.pop()
        return f'palette intensity {value} in-slot {from_slot} to {to_slot}'
    if cmd.num == 180:
        slot = stack.pop()
        flags = stack.pop()
        return f'saveload-game {flags} {slot}'
    if cmd.num == 181:
        return f'fades {stack.pop()}'
    if cmd.num == 182:
        to_slot = stack.pop()
        from_slot = stack.pop()
        blue = stack.pop()
        green = stack.pop()
        red = stack.pop()
        return f'palette intensity {red},{green},{blue} in-slot {from_slot} to {to_slot}'
    if cmd.num == 187:
        speed = stack.pop()
        slot = stack.pop()
        return f'palette cycle-speed {slot} is {speed}'
    if cmd.num == 213:
        # windex show empty string here
        return f'$ room-color is {stack.pop()}'
    return defop(op, stack, bytecode)


@regop
def o60_roomOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 221:
        return f'save-game {stack.pop()} name {msg_val(op.args[1])}'
    return o6_roomOps(op, stack, bytecode)


@regop
def o72_roomOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 172:
        x2 = stack.pop()
        x1 = stack.pop()
        return f'room-scroll is {x1} {x2}'
    if cmd.num == 174:
        b = stack.pop()
        a = stack.pop()
        return f'set-screen {a} to {b}'
    if cmd.num == 175:
        slot = stack.pop()
        b = stack.pop()
        g = stack.pop()
        r = stack.pop()
        return f'palette {r} {g} {b} in-slot {slot}'
    if cmd.num == 179:
        to_slot = stack.pop()
        from_slot = stack.pop()
        value = stack.pop()
        return f'palette intensity {value} in-slot {from_slot} to {to_slot}'
    if cmd.num == 181:
        return f'fades {stack.pop()}'
    if cmd.num == 213:
        return f'$ room-color is {stack.pop()}'
    if cmd.num == 220:
        return f'$ room-color is {stack.pop()}'
    if cmd.num == 221:
        options = {1: 'save', 2: 'load'}
        savegame = pop_str(stack)
        action = options[stack.pop().num]
        return f'{action}-game {savegame}'
    if cmd.num == 234:
        a = stack.pop()
        b = stack.pop()
        return f'$ palette {b} in-slot {a}'
    return defop(op, stack, bytecode)


@regop
def o6_verbOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 196:
        verb = stack.pop()
        return f'verb {verb} \\'
    if cmd.num == 125:
        return f'\tname {msg_val(op.args[1])} \\'
    if cmd.num == 126:
        color = stack.pop()
        return f'\tcolor {color} \\'
    if cmd.num == 127:
        color = stack.pop()
        return f'\thicolor {color} \\'
    if cmd.num == 128:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\tat {xpos},{ypos} \\'
    if cmd.num == 129:
        return '\ton \\'
    if cmd.num == 130:
        return '\toff \\'
    if cmd.num == 131:
        return '\tdelete \\'
    if cmd.num == 132:
        return '\tnew \\'
    if cmd.num == 133:
        color = stack.pop()
        return f'\tdimcolor {color} \\'
    if cmd.num == 134:
        return '\tdim \\'
    if cmd.num == 135:
        return f'\tkey {stack.pop()} \\'
    if cmd.num == 136:
        return '\tcenter \\'
    if cmd.num == 139:
        room =stack.pop()
        im = stack.pop()
        return f'\timage {im} in-room {room} \\'
    if cmd.num == 140:
        color = stack.pop()
        return f'\tbakcolor {color} \\'
    if cmd.num == 255:
        return '\t(end-verb)'
    return defop(op, stack, bytecode)


@regop
def o72_verbOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    return o6_verbOps(op, stack, bytecode)


@regop
def o6_actorFollowCamera(op, stack, bytecode):
    return f'camera-follow {stack.pop()}'


@regop
def o6_pickupObject(op, stack, bytecode):
    room = stack.pop()
    obj = stack.pop()
    return f'pick-up-object {obj} in-room {room}'


@regop
def o70_pickupObject(op, stack, bytecode):
    room = stack.pop()
    obj = stack.pop()
    return f'pick-up-object {obj} in {room}'


@regop
def o6_getActorMoving(op, stack, bytecode):
    stack.append(f'actor-moving {stack.pop()}')


@regop
def o6_getInventoryCount(op, stack, bytecode):
    # might also be inventory-size {actor_name}
    stack.append(f'actor-inventory {stack.pop()}')


@regop
def o6_getOwner(op, stack, bytecode):
    stack.append(f'owner-of {stack.pop()}')


@regop
def o6_setOwner(op, stack, bytecode):
    act = stack.pop()
    obj = stack.pop()
    return f'owner-of {obj} is {act}'


@regop
def o6_faceActor(op, stack, bytecode):
    obj = stack.pop()  # might be another actor
    act = stack.pop()
    return f'do-animation {act} face-towards {obj}'


@regop
def o6_setObjectName(op, stack, bytecode):
    obj = stack.pop()
    return f'new-name-of {obj} is {msg_val(op.args[0])}'


@regop
def o72_printWizImage(op, stack, bytecode):
    return f'$ print-wiz-image {stack.pop()}'


@regop
def o6_cursorCommand(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 0x90:
        return 'cursor on'
    elif cmd.num == 0x91:
        return 'cursor off'
    elif cmd.num == 0x92:
        return 'userput on'
    elif cmd.num == 0x93:
        return 'userput off'
    elif cmd.num == 0x94:
        return 'cursor soft-on'
    elif cmd.num == 0x95:
        return 'cursor soft-off'
    elif cmd.num == 0x96:
        return 'userput soft-on'
    elif cmd.num == 0x97:
        return 'userput soft-off'
    elif cmd.num == 0x99:
        # TODO: another pop for non HE or HE < 70 games
        image = stack.pop()
        return f'cursor {stack.pop()} image {image}'
    elif cmd.num == 0x9A:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'cursor hotspot {xpos} {ypos}'
    elif cmd.num == 0x9C:
        return f'charset {stack.pop()}'
    elif cmd.num == 0x9D:
        params = get_params(stack)
        param_str = ', '.join(str(param) for param in params)
        return f'charset color {param_str}'
    elif cmd.num == 0xD6:
        # > cursor transparent color
        # This command sets transparent colors in the cursor.
        # It can be called multiple times for multiple transparent colors.
        return f'cursor transparent {stack.pop()}'
    return defop(op, stack, bytecode)


@regop
def o80_cursorCommand(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num in {0x13, 0x14}:
        return f'$ cursor-wiz-image {stack.pop()}'
    elif cmd.num == 0x90:
        return 'cursor on'
    elif cmd.num == 0x91:
        return 'cursor off'
    elif cmd.num == 0x92:
        return 'userput on'
    elif cmd.num == 0x93:
        return 'userput off'
    elif cmd.num == 0x94:
        return 'cursor soft-on'
    elif cmd.num == 0x95:
        return 'cursor soft-off'
    elif cmd.num == 0x96:
        return 'userput soft-on'
    elif cmd.num == 0x97:
        return 'userput soft-off'
    elif cmd.num == 0x99:
        return f'cursor image {stack.pop()}'
    elif cmd.num == 0x9A:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'cursor hotspot {xpos} {ypos}'
    elif cmd.num == 0x9C:
        return f'charset {stack.pop()}'
    elif cmd.num == 0x9D:
        params = get_params(stack)
        param_str = ', '.join(str(param) for param in params)
        return f'charset color {param_str}'
    return defop(op, stack, bytecode)


@regop
def o6_actorOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 76:
        return f'\tcostume {stack.pop()} \\'
    if cmd.num == 77:
        y = stack.pop()
        x = stack.pop()
        return f'\tstep-dist {x},{y} \\'
    if cmd.num == 78:
        return f'\tsound {get_params(stack)}'
    if cmd.num == 79:
        return f'\twalk-animation {stack.pop()} \\'
    if cmd.num == 80:
        stop = stack.pop()
        start = stack.pop()
        return f'\ttalk-animation {start} {stop} \\'
    if cmd.num == 81:
        return f'\tstand-animation {stack.pop()} \\'
    # TODO: 82 - animation - 3 pops
    if cmd.num == 83:
        return '\tdefault'
    if cmd.num == 84:
        return f'\televation {stack.pop()}'
    if cmd.num == 85:
        return '\tanimation default \\'
    if cmd.num == 86:
        new_color = stack.pop()
        old_color = stack.pop()
        return f'\tcolor {old_color} is {new_color}'
    if cmd.num == 87:
        color = stack.pop()
        return f'\ttalk-color {color} \\'
    if cmd.num == 88:
        return f'\tname {msg_val(op.args[1])}'
    if cmd.num == 89:
        return f'\tinit-animation {stack.pop()}'
    if cmd.num == 91:
        return f'\twidth {stack.pop()}'
    if cmd.num == 92:
        return f'\tscale {stack.pop()}'
    if cmd.num == 93:
        return f'\tnever-zclip'
    if cmd.num == 94:
        return f'\talways-zclip {stack.pop()}'
    if cmd.num == 95:
        return f'\tignore-boxes \\'
    if cmd.num == 96:
        return f'\tfollow-boxes \\'
    if cmd.num == 97:
        return f'\tanimation-speed {stack.pop()} \\'
    if cmd.num == 98:
        return f'\tspecial-draw {stack.pop()}'
    if cmd.num == 99:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\ttext-offset {xpos},{ypos} \\'
    if cmd.num == 197:
        return f'actor {stack.pop()} \\'
    if cmd.num == 198:
        value = stack.pop()
        var = stack.pop()
        return f'\tanimation-var {var} {value}'
    if cmd.num == 215:
        return f'\tignore-turns on \\'
    if cmd.num == 216:
        return f'\tignore-turns off \\'
    if cmd.num == 217:
        return f'\tnew \\'
    # TODO: 227 - actor-depth - 1 pop
    # TODO: 228 - actor-walk-script 1 pop
    # TODO: 229 - actor-stop - no pops
    # TODO: 230 - direction - 1 pop
    # TODO: 231 - turn-to - 1 pop
    # TODO: 233 - stop-walk - no pops
    # TODO: 234 - resume-walk - no pops
    # TODO: 235 - talk-script - 1 pop
    return defop(op, stack, bytecode)


@regop
def o60_actorOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 218:
        return f'\tbackground-on \\'
    if cmd.num == 219:
        return f'\tbackground-off \\'
    return o6_actorOps(op, stack, bytecode)


@regop
def o72_actorOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 21:
        return f'\tcondition {get_params(stack)}'
    if cmd.num == 24:
        return f'\ttalk-condition {stack.pop()}'
    # TODO: 43 - priority - 1 pop
    # TODO: 64 - default-clipped - 4 pops
    # TODO: 65 - at - 2 pops
    # TODO: 67 - clipped - 4 pops
    # TODO: 68 - erase - 1 pop
    # TODO: 156 - charset - 1 pop
    # TODO: 175 - room palette - 1 pop
    if cmd.num == 218:
        return f'\tbackground-on \\'
    if cmd.num == 219:
        return f'\tbackground-off \\'
    if cmd.num == 225:
        string = pop_str(stack)
        slot = stack.pop()
        return f'\tsay {slot} {string}\\'
    return o6_actorOps(op, stack, bytecode)


@regop
def o72_resetCutscene(op, stack, bytecode):
    return '$ reset-cut-scene'


@regop
def o90_setSpriteInfo(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 37:
        return f'\tgroup {stack.pop()}'
    if cmd.num == 43:
        return f'\tpriority {stack.pop()}'
    if cmd.num == 44:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\tmove {xpos},{ypos}'
    if cmd.num == 52:
        return f'$ state {stack.pop()} \\'
    if cmd.num == 57:
        return f'$ sprite {stack.pop()} \\'
    if cmd.num == 63:
        return f'\timage {stack.pop()} \\'
    if cmd.num == 65:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\tat {xpos},{ypos}'
    if cmd.num == 82:
        flags = stack.pop()
        return f'\tanimation {flags} \\'
    if cmd.num == 97:
        speed = stack.pop()
        return f'\tanimation-speed {speed} \\'
    if cmd.num == 98:
        flags = stack.pop()
        return f'\tspecial-draw {flags} \\'
    if cmd.num == 124:
        flags = stack.pop()
        return f'\tflags {flags} \\'
    if cmd.num == 125:
        params = get_params(stack)
        return f'\tclass is {params} \\'
    if cmd.num == 158:
        return f'\treset \\'
    if cmd.num == 217:
        return f'\tnew \\'
    return defop(op, stack, bytecode)


@regop
def o90_getSpriteInfo(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    if sub.num == 30:
        sprite = stack.pop()
        stack.append(f'$ sprite-x {sprite}')
        return
    if sub.num == 31:
        sprite = stack.pop()
        stack.append(f'$ sprite-y {sprite}')
        return
    if sub.num == 32:
        sprite = stack.pop()
        stack.append(f'$ sprite-width {sprite}')
        return
    if sub.num == 33:
        sprite = stack.pop()
        stack.append(f'$ sprite-height {sprite}')
        return
    if sub.num == 36:
        sprite = stack.pop()
        stack.append(f'$ sprite-num-states {sprite}')
        return
    if sub.num == 37:
        sprite = stack.pop()
        stack.append(f'$ sprite-group {sprite}')
        return
    if sub.num == 38:
        sprite = stack.pop()
        stack.append(f'$ sprite-display-x {sprite}')
        return
    if sub.num == 39:
        sprite = stack.pop()
        stack.append(f'$ sprite-display-y {sprite}')
        return
    if sub.num == 43:
        sprite = stack.pop()
        stack.append(f'$ sprite-priority {sprite}')
        return
    if sub.num == 45:
        # TODO: extra argument for he 98 + another extra for he 99
        # flags = stack.pop()
        # stype = stack.pop()
        group = stack.pop()
        ypos = stack.pop()
        xpos = stack.pop()
        stack.append(f'$ find-sprite {xpos},{ypos} in {group}')
        return
    if sub.num == 52:
        sprite = stack.pop()
        stack.append(f'$ sprite-state {sprite}')
        return
    if sub.num == 124:
        sprite = stack.pop()
        stack.append(f'$ sprite-flags {sprite}')
        return
    if sub.num == 63:
        sprite = stack.pop()
        stack.append(f'$ sprite-image {sprite}')
        return
    if sub.num == 125:
        params = get_params(stack)
        param_str = ' '.join(str(param) for param in params)
        sprite = stack.pop()
        stack.append(f'$ class-of-sprite {sprite} {params}')
        return
    return defop(op, stack, bytecode)


@regop
def o90_setSpriteGroupInfo(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 44:
        dy = stack.pop()
        dx = stack.pop()
        return f'\tmove {dx},{dy}'
    if cmd.num == 57:
        return f'$ sprite-group {stack.pop()} \\'
    if cmd.num == 67:
        bottom = stack.pop()
        right = stack.pop()
        top = stack.pop()
        left = stack.pop()
        return f'\tbox {left},{top} to {right},{bottom}'
    return defop(op, stack, bytecode)


@regop
def o90_getSpriteGroupInfo(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    if sub.num == 30:
        group = stack.pop()
        stack.append(f'$ sprite-group-x {group}')
        return
    if sub.num == 31:
        group = stack.pop()
        stack.append(f'$ sprite-group-y {group}')
        return
    return defop(op, stack, bytecode)


@regop
def o80_drawLine(op, stack, bytecode):
    step = stack.pop()
    id = stack.pop()
    y = stack.pop()
    x = stack.pop()
    y1 = stack.pop()
    x1 = stack.pop()
    sub = Value(op.args[0], signed=False)
    return f'$ draw-line {sub} {x1},{y1} to {x},{y} {id} {step}'


@regop
def o90_floodFill(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    if sub.num == 57:
        return f'$ flood-fill-box \\'
    if sub.num == 65:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\tat {xpos},{ypos} \\'
    if sub.num == 66:
        return f'\tflags {stack.pop()} \\'
    if sub.num == 67:
        bottom = stack.pop()
        right = stack.pop()
        top = stack.pop()
        left = stack.pop()
        return f'$ flood-fill-box {left},{top} to {right},{bottom}'
    if sub.num == 255:
        return f'\tdraw'
    return defop(op, stack, bytecode)


@regop
def o6_getAnimateVariable(op, stack, barcode):
    var = stack.pop()
    act = stack.pop()
    stack.append(f'actor {act} variable {var}')


@regop
def o6_animateActor(op, stack, barcode):
    chore = stack.pop()
    act = stack.pop()
    return f'do-animation {act} {chore}'


@regop
def o80_readConfigFile(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    option = pop_str(stack)
    section = pop_str(stack)
    filename = pop_str(stack)
    if cmd.num == 6:
        stack.append(Caster(f'(read-ini {filename} {section} {option})', cast='number'))
        return
    return defop(op, stack, bytecode)


@regop
def o72_getNumFreeArrays(op, stack, bytecode):
    stack.append('$ num-free-arrays')


@regop
def o72_getObjectImageX(op, stack, bytecode):
    stack.append(f'object-image-x {stack.pop()}')


@regop
def o72_getObjectImageY(op, stack, bytecode):
    stack.append(f'object-image-y {stack.pop()}')


@regop
def o6_getObjectX(op, stack, bytecode):
    stack.append(f'object-x {stack.pop()}')

@regop
def o6_getObjectY(op, stack, bytecode):
    stack.append(f'object-y {stack.pop()}')

@regop
def o6_stampObject(op, stack, bytecode):
    state = stack.pop()
    ypos = stack.pop()
    xpos = stack.pop()
    obj = stack.pop()
    return f'stamp-object {obj} at {xpos},{ypos} image {state}'




@regop
def o72_redimArray(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    arr = get_var(op.args[1])
    dim2, dim1 =  stack.pop(), stack.pop()
    if cmd.num == 4:  # byte array
        return f'$ redim byte array {arr}[{dim1}][{dim2}]'
    if cmd.num == 5:  # int/word array
        return f'$ redim int array {arr}[{dim1}][{dim2}]'
    if cmd.num == 6:  # dword array
        return f'$ redim dword array {arr}[{dim1}][{dim2}]'


@regop
def o72_dim2dimArray(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    arr = get_var(op.args[1])
    dim2, dim1 =  stack.pop(), stack.pop()
    if isinstance(dim2, BinExpr):
        with io.BytesIO(b'\x01') as sr:
            dim2 = BinExpr('+', dim2, Value(ByteValue(sr)))
    else:
        dim2 = dim2.num + 1
    if isinstance(dim1, BinExpr):
        with io.BytesIO(b'\x01') as sr:
            dim1 = BinExpr('+', dim1, Value(ByteValue(sr)))
    else:
        dim1 = dim1.num + 1
    if cmd.num == 2:  # bit array
        return f'$ dim bit array {arr}[{dim1}][{dim2}]'
    if cmd.num == 3:  # nibble array
        return f'$ dim nibble array {arr}[{dim1}][{dim2}]'
    if cmd.num == 4:  # byte array
        return f'$ dim byte array {arr}[{dim1}][{dim2}]'
    if cmd.num == 5:  # int/word array
        return f'$ dim int array {arr}[{dim1}][{dim2}]'
    if cmd.num == 6:  # dword array
        return f'$ dim dword array {arr}[{dim1}][{dim2}]'
    if cmd.num == 7:  # int array
        return f'$ dim string array {arr}[{dim1}][{dim2}]'
    return defop(op, stack, bytecode)


@regop
def o72_drawWizImage(op, stack, bytecode):
    flags = stack.pop()
    x1 = stack.pop()
    y1 = stack.pop()
    res = stack.pop()
    return f'$ draw-wiz-image {res} at {x1},{y1} flags {flags}'


@regop
def o72_captureWizImage(op, stack, bytecode):
    bottom = stack.pop()
    right = stack.pop()
    top = stack.pop()
    left = stack.pop()
    res = stack.pop()
    return f'$ capture-wiz-image {res} {left},{top} to {right},{bottom}'


@regop
def o90_wizImageOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 48:
        return f'\tmode 1 \\'
    if cmd.num == 51:
        bottom = stack.pop()
        right = stack.pop()
        top = stack.pop()
        left = stack.pop()
        comp = stack.pop()
        return f'\tcompressed-box {comp} {left},{top} to {right},{bottom} \\'
    if cmd.num == 52:
        state = stack.pop()
        return f'\tstate {state} \\'
    if cmd.num == 54:
        flags = stack.pop()
        return f'\tflags {flags} \\'
    if cmd.num == 56:
        flags = stack.pop()
        state = stack.pop()
        x1 = stack.pop()
        y1 = stack.pop()
        res = stack.pop()
        return f'$ draw-wiz-image {res} state {state} at {x1},{y1} flags {flags}'
    if cmd.num == 57:
        res = stack.pop()
        return f'$ load-wiz-image {res} \\'
    if cmd.num == 65:
        y1 = stack.pop()
        x1 = stack.pop()
        if isinstance(x1, str):
            x1 = f'({x1})'
        if isinstance(y1, str):
            y1 = f'({y1})'
        return f'\tat {x1},{y1} \\'
    if cmd.num == 66:
        a = stack.pop()
        b = stack.pop()
        return f'\tpalette {b} in-slot {a} \\'
    if cmd.num == 67:
        bottom = stack.pop()
        right = stack.pop()
        top = stack.pop()
        left = stack.pop()
        return f'\tbox {left},{top} to {right},{bottom} \\'
    if cmd.num == 246:
        return f'\tpolygon {stack.pop()} \\'
    if cmd.num == 255:
        return f'\t(end-wiz)'
    return defop(op, stack, bytecode)


@regop
def o6_delayFrames(op, stack, bytecode):
    return f'break-here {stack.pop()} times'


@regop
def o6_delayMinutes(op, stack, bytecode):
    return f'sleep-for {stack.pop()} minutes'


@regop
def o6_delay(op, stack, bytecode):
    return f'sleep-for {stack.pop()} jiffies'


@regop
def o6_delaySeconds(op, stack, bytecode):
    return f'sleep-for {stack.pop()} seconds'


@regop
def o6_wait(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    if sub.num == 168:
        return f'wait-for-actor {stack.pop()} [ref {adr(op.args[1])}]'
    if sub.num == 169:
        return 'wait-for-message'
    if sub.num == 170:
        return 'wait-for-camera'
    return defop(op, stack, bytecode)


@regop
def o6_pseudoRoom(op, stack, bytecode):
    params = get_params(stack)
    room = stack.pop()
    return f'pseudo-room {room} is {params}'


@regop
def o72_setTimer(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    return f'$ start-timer {stack.pop()} {cmd}'

@regop
def o6_wordVarInc(op, stack, bytecode):
    var = get_var(op.args[0])
    return f'++{var}'


@regop
def o6_wordVarDec(op, stack, bytecode):
    var = get_var(op.args[0])
    return f'--{var}'


@regop
def o90_cond(op, stack, bytecode):
    a = stack.pop()
    b = stack.pop()
    c = stack.pop()
    stack.append(f'{c} ? {b} : {a}')


@regop
def o6_wordArrayInc(op, stack, bytecode):
    var = get_var(op.args[0])
    return f'++{var}[{stack.pop()}]'


@regop
def o6_wordArrayDec(op, stack, bytecode):
    var = get_var(op.args[0])
    return f'--{var}[{stack.pop()}]'


@regop
def o6_breakHere(op, stack, bytecode):
    return 'break-here'


@regop
def o72_getTimer(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    stack.append(f'$ get-timer {stack.pop()} {cmd}')


@regop
def o6_isActorInBox(op, stack, bytecode):
    box = stack.pop()
    actor = stack.pop()
    stack.append(f'{actor} in-box {box}')


@regop
def o6_createBoxMatrix(op, stack, bytecide):
    return f'$ create-box-matrix'


@regop
def o6_systemOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 158:
        return 'restart'
    if cmd.num == 159:
        return 'pause'
    if cmd.num == 160:
        return 'quit'
    return defop(op, stack, bytecode)


@regop
def o6_saveRestoreVerbs(op, stack, bytecode):
    setval = stack.pop()
    end = stack.pop()
    start = stack.pop()
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 141:
        return f'verbs-save {start} to {end} set {setval}'
        # return f'save-verbs {start} to {end} set {setval}'
    if cmd.num == 142:
        return f'verbs-restore {start} to {end} set {setval}'
        # return f'restore-verbs {start} to {end} set {setval}'
    # TODO: 143: verbs-delete {start} to {end} set {setval}
    return defop(op, stack, bytecode)


@regop
def o72_systemOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 22:
        return '$ clear-draw-queue'
    if cmd.num == 26:
        return '$ restore-background'
    if cmd.num == 158:
        return '$ restart'
    if cmd.num == 160:
        return '$ prompt-exit'
    if cmd.num == 244:
        return '$ quit'
    return defop(op, stack, bytecode)


@regop
def o70_setSystemMessage(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    string = op.args[1]
    if sub.num == 243:
        return f'$ window-title {string}'



@regop
def o72_setSystemMessage(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    string = pop_str(stack)
    if sub.num == 243:
        return f'$ window-title {string}'
    # raise NotImplementedError(op.args)


@regop
def o6_resourceRoutines(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 100:
        return f'load-script {stack.pop()}'
    if cmd.num == 101:
        return f'load-sound {stack.pop()}'
    if cmd.num == 102:
        return f'load-costume {stack.pop()}'
    if cmd.num == 103:
        return f'load-room {stack.pop()}'
    if cmd.num == 104:
        return f'nuke-script {stack.pop()}'
    if cmd.num == 105:
        return f'nuke-sound {stack.pop()}'
    if cmd.num == 106:
        return f'nuke-costume {stack.pop()}'
    if cmd.num == 107:
        return f'nuke-room {stack.pop()}'
    if cmd.num == 108:
        return f'lock-script {stack.pop()}'
    if cmd.num == 109:
        return f'lock-sound {stack.pop()}'
    if cmd.num == 110:
        return f'lock-costume {stack.pop()}'
    if cmd.num == 111:
        return f'lock-room {stack.pop()}'
    if cmd.num == 112:
        return f'unlock-script {stack.pop()}'
    if cmd.num == 113:
        return f'unlock-sound {stack.pop()}'
    if cmd.num == 114:
        return f'unlock-costume {stack.pop()}'
    if cmd.num == 115:
        return f'unlock-room {stack.pop()}'
    if cmd.num == 117:
        return f'load-charset {stack.pop()}'
    if cmd.num == 119:
        room = stack.pop()
        obj = stack.pop()
        return f'load-object {obj} in-room {room}'
    return defop(op, stack, bytecode) 


@regop
def o70_resourceRoutines(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 100:
        return f'load-script {stack.pop()}'
    if cmd.num == 101:
        return f'load-sound {stack.pop()}'
    if cmd.num == 102:
        return f'load-costume {stack.pop()}'
    if cmd.num == 103:
        return f'$ load-room {stack.pop()}'
    if cmd.num == 104:
        return f'nuke-script {stack.pop()}'
    if cmd.num == 105:
        return f'nuke-sound {stack.pop()}'
    if cmd.num == 106:
        return f'nuke-costume {stack.pop()}'
    if cmd.num == 107:
        return f'$ nuke-room {stack.pop()}'
    if cmd.num == 108:
        return f'lock-script {stack.pop()}'
    if cmd.num == 109:
        return f'lock-sound {stack.pop()}'
    if cmd.num == 110:
        return f'lock-costume {stack.pop()}'
    if cmd.num == 111:
        return f'$ lock-room {stack.pop()}'
    if cmd.num == 112:
        return f'unlock-script {stack.pop()}'
    if cmd.num == 113:
        return f'unlock-sound {stack.pop()}'
    if cmd.num == 114:
        return f'unlock-costume {stack.pop()}'
    if cmd.num == 115:
        return f'$ unlock-room {stack.pop()}'
    if cmd.num == 117:
        return f'charset {stack.pop()}'
    if cmd.num == 119:
        return f'$ load-object {stack.pop()}'
    if cmd.num == 120:
        return f'$ queue-script {stack.pop()}'
    if cmd.num == 121:
        return f'$ queue-sound {stack.pop()}'
    if cmd.num == 122:
        return f'$ queue-costume {stack.pop()}'
    if cmd.num == 123:
        return f'$ queue-room {stack.pop()}'
    if cmd.num == 159:
        return f'$ unlock-image {stack.pop()}'
    if cmd.num == 192:
        return f'$ nuke-image {stack.pop()}'
    if cmd.num == 201:
        return f'$ load-image {stack.pop()}'
    if cmd.num == 202:
        return f'$ lock-image {stack.pop()}'
    if cmd.num == 203:
        return f'$ queue-image {stack.pop()}'
    if cmd.num == 233:
        return f'$ lock-object {stack.pop()}'
    if cmd.num == 235:
        return f'$ unlock-object {stack.pop()}'
    return defop(op, stack, bytecode)


@regop
def o6_loadRoom(op, stack, bytecode):
    return f'current-room {stack.pop()}'


@regop
def o6_getDateTime(op, stack, bytecode):
    stack.append('get-time-date')


@regop
def o6_getRandomNumber(op, stack, bytecode):
    stack.append(f'random {stack.pop()}')


@regop
def o6_getRandomNumberRange(op, stack, bytecode):
    upper = stack.pop()
    lower = stack.pop()
    stack.append(Caster(f'random-between {lower} to {upper}', cast='number'))


@regop
def o70_getStringLen(op, stack, bytecode):
    stack.append(f'$ string-length {stack.pop()}')

@regop
def o6_wordArrayWrite(op, stack, bytecode):
    val = stack.pop()
    base = stack.pop()
    arr = get_var(op.args[0])
    return f'{arr}[{base}] = {val}'


@regop
def o6_pickVarRandom(op, stack, bytecode):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    value = Value(op.args[0])
    stack.append(f'pick var [{value}] random [ {param_str} ]')


@regop
def o80_pickVarRandom(op, stack, bytecode):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    value = Value(op.args[0])
    stack.append(f'pick var [{value}] random [ {param_str} ]')


@regop
def o6_pickOneOf(op, stack, bytecode):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    value = stack.pop()
    stack.append(f'pick ({value}) of [ {param_str} ]')


@regop
def o6_pickOneOfDefault(op, stack, bytecode):
    default = stack.pop()
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    value = stack.pop()
    stack.append(f'pick ({value}) of [ {param_str} ] default {default}')


@regop
def o6_shuffle(op, stack, bytecode):
    end = stack.pop()
    start = stack.pop()
    arr = get_var(op.args[0])
    return f'array-shuffle {arr}[{start}] to {arr}[{end}]'


@regop
def o72_getResourceSize(op, stack, bytecode):
    res = stack.pop()
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 13:
        stack.append(f'$ size-of sfx {res}')
        return
    return defop(op, stack, bytecode)


@regop
def o6_setClass(op, stack, bytecode):
    params = get_params(stack)
    obj = stack.pop()
    return f'class-of {obj} is {" ".join(str(param) for param in params)}'


@regop
def o6_ifClassOfIs(op, stack, bytecode):
    params = get_params(stack)
    obj = stack.pop()
    stack.append(f'class-of {obj} is {" ".join(str(param) for param in params)}')


@regop
def o6_stopTalking(op, stack, bytecode):
    return 'stop-talking'


@regop
def o6_getVerbEntrypoint(op, stack, bytecode):
    verb = stack.pop()
    obj = stack.pop()
    stack.append(f'valid-verb {obj} {verb}')


@regop
def o6_getObjectOldDir(op, stack, bytecode):
    obj = stack.pop()
    stack.append(f'actor-facing {obj}')

@regop
def o70_getActorRoom(op, stack, bytecode):
    stack.append(f'actor-room {stack.pop()}')


@regop
def o6_getPixel(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'pixel {xpos}, {ypos}')


@regop
def o72_getPixel(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    sources = {9: 'background', 218: 'background', 8: 'foreground', 219: 'foreground'}
    src = Value(op.args[0], signed=False)
    stack.append(f'pixel {xpos}, {ypos} of {sources[src.num]}')


@regop
def o71_polygonHit(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'$ polygon-hit {xpos} {ypos}')


@regop
def o60_closeFile(op, stack, bytecode):
    return f'close-file {stack.pop()}'


@regop
def o60_openFile(op, stack, bytecode):
    modes = {
        1: 'read',
        2: 'write',
        6: 'append',
    }
    mode = modes[stack.pop().num]
    string = op.args[0]
    stack.append(f'open-file {msg_val(string)} for {mode}')


@regop
def o72_openFile(op, stack, bytecode):
    modes = {
        1: 'read',
        2: 'write',
        6: 'append',
    }
    mode = modes[stack.pop().num]
    string = pop_str(stack)
    stack.append(f'open-file {string} for {mode}')


@regop
def o60_writeFile(op, stack, bytecode):
    size = stack.pop()
    res = stack.pop()
    slot = stack.pop()
    return f'write-file {slot} size {size} value {res}'


@regop
def o72_writeFile(op, stack, bytecode):
    res = stack.pop()
    slot = stack.pop()
    sub = Value(op.args[0], signed=False)
    if sub.num == 8:
        return f'$ write-file {Value(op.args[1])} {slot} {res}'


@regop
def o72_readFile(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    if sub.num == 8:
        size = stack.pop()
        slot = stack.pop()
        stack.append(f'$ read-file {Value(op.args[1])} {slot} size {size}')
        return
    return defop(op, stack, bytecode)


@regop
def o60_readFile(op, stack, bytecode):
    size = stack.pop()
    slot = stack.pop()
    stack.append(f'read-file {slot} size {size}')


@regop
def o60_seekFilePos(op, stack, bytecode):
    modes = {
        1: 'start',
        2: 'current',
        3: 'end',
    }
    mode = modes[stack.pop().num]
    offset = stack.pop()
    slot = stack.pop()
    return f'seek-file {offset} {slot} type {mode}'


@regop
def o71_appendString(op, stack, bytecode):
    ln = stack.pop()
    src_offs = stack.pop()
    src = stack.pop()
    stack.append(f'$ concat {src} {src_offs} {ln}')


@regop
def o80_stringToInt(op, stack, bytecode):
    string = stack.pop()
    stack.append(Caster(f'$ string-to-number {string}', cast='number'))


@regop
def o6_findAllObjects(op, stack, bytecode):
    stack.append(f'find-all-objects {stack.pop()}')


@regop
def o72_findAllObjects(op, stack, bytecode):
    stack.append(f'find-all-objects {stack.pop()}')


@regop
def o90_findAllObjectsWithClassOf(op, stack, bytecode):
    classes = get_params(stack)
    room = stack.pop()
    stack.append(f'find-all-objects {room} of-class {classes}')


@regop
def o6_putActorAtXY(op, stack, bytecode):
    room = stack.pop()
    ypos = stack.pop()
    xpos = stack.pop()
    act = stack.pop()
    room = '' if room == 0 else f' in-room {room}'
    return f'put-actor {act} at {xpos},{ypos}{room}'


@regop
def o71_getCharIndexInString(op, stack, bytecode):
    value = stack.pop()
    value.cast = 'char'
    end = stack.pop()
    pos = stack.pop()
    arr = stack.pop()
    stack.append(f'$ index {arr} from {pos} to {end} find {value}')


@regop
def o6_putActorAtObject(op, stack, bytecode):
    room = stack.pop()
    obj = stack.pop()
    act = stack.pop()
    room = '' if room == 0 else f' in room {room}'
    return f'put-actor {act} at-object {obj}{room}'


@regop
def o6_startScriptQuick(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    scr = stack.pop()
    return f'start-script {scr}{param_str}'


@regop
def o6_startScriptQuick2(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    scr = stack.pop()
    stack.append(f'@{scr}{param_str}')
    # stack.append(f'start-script rec {scr}{param_str}')



@regop
def o6_panCameraTo(op, stack, bytecode):
    # TODO: v7 uses 2 pops, x y
    xpos = stack.pop()
    return f'camera-pan-to {xpos}'


@regop
def o6_startObjectQuick(op, stack, bytecode):
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    entry = stack.pop()
    scr = stack.pop()
    stack.append(f'start-object rec {scr} verb {entry}{param_str}')


@regop
def o6_stopSentence(op, stack, bytecode):
    return 'stop-sentence'


@regop
def o72_getArrayDimSize(op, stack, bytecode):
    sub = Value(op.args[0], signed=False)
    arr = get_var(op.args[1])
    if sub.num == 1:
        stack.append(f'$ array-dimension-base {arr}')
        return
    return defop(op, stack, bytecode)


@regop
def o80_getSoundVar(op, stack, bytecode):
    var = stack.pop()
    sound = stack.pop()
    stack.append(f'$ sfx-var {sound} {var}')


@regop
def o80_createSound(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 27:
        return f'\tfrom {stack.pop()} \\'
    if cmd.num == 217:
        return f'\tempty \\'
    if cmd.num == 232:
        return f'$ create-sound {stack.pop()} \\'
    if cmd.num == 255:
        return f'\t(end-create-sound)'
    return defop(op, stack, bytecode)


@regop
def o6_getActorCostume(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-costume {act}')

@regop
def o6_getActorWidth(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-width {act}')

@regop
def o6_getActorElevation(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-elevation {act}')


@regop
def o6_getActorRoom(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-room {act}')


@regop
def o6_getActorAnimCounter(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-chore {act}')


@regop
def o6_getActorScaleX(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-scale {act}')


@regop
def o6_getActorWalkBox(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-box {act}')


@regop
def o60_localizeArrayToScript(op, stack, bytecode):
    return f'localize array {stack.pop()}'


@regop
def o80_localizeArrayToRoom(op, stack, bytecode):
    return f'localize array [room] {stack.pop()}'


@regop
def o6_freezeUnfreeze(op, stack, bytecode):
    scr = stack.pop()
    if scr.num == 0:
        return 'unfreeze-scripts'
    return f'freeze-scripts {scr}'


@regop
def o71_polygonOps(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 247:
        to = stack.pop()
        src = stack.pop()
        return f'$ erase-polygon from {src} to {to}'
    if cmd.num in {246, 248}:
        vert4y = stack.pop()
        vert4x = stack.pop()
        vert3y = stack.pop()
        vert3x = stack.pop()
        vert2y = stack.pop()
        vert2x = stack.pop()
        vert1y = stack.pop()
        vert1x = stack.pop()
        id = stack.pop()
        return f'$ draw-polygon {id} [{cmd}] {vert1x},{vert1y} {vert2x},{vert2y} {vert3x},{vert3y} {vert4x},{vert4y}'
    return defop(op, stack, bytecode)


@regop
def o6_drawObject(op, stack, bytecode):
    state = stack.pop()
    obj = stack.pop()
    return f'draw-object {obj} image {state}'


@regop
def o6_drawObjectAt(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    obj = stack.pop()
    return f'draw-object {obj} at {xpos},{ypos}'


@regop
def o72_drawObject(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 62:
        state = stack.pop()
        ypos = stack.pop()
        xpos = stack.pop()
        obj = stack.pop()
        return f'draw-object {obj} at {xpos},{ypos} image {state}'
    if cmd.num == 63:
        state = stack.pop()
        obj = stack.pop()
        return f'draw-object {obj} image {state}'
    if cmd.num == 65:
        ypos = stack.pop()
        xpos = stack.pop()
        obj = stack.pop()
        return f'draw-object {obj} at {xpos},{ypos}'
    return defop(op, stack, bytecode)


@regop
def o6_setState(op, stack, bytecode):
    state = stack.pop()
    obj = stack.pop()
    return f'state-of {obj} is {state}'


@regop
def o80_setState(op, stack, bytecode):
    state = stack.pop()
    obj = stack.pop()
    return f'state-of {obj} is {state}'


@regop
def o60_setState(op, stack, bytecode):
    state = stack.pop()
    obj = stack.pop()
    return f'state-of {obj} is {state}'

@regop
def o6_getState(op, stack, bytecode):
    obj = stack.pop()
    stack.append(f'state-of {obj}')


@regop
def o72_getSoundPosition(op, stack, bytecode):
    snd = stack.pop()
    stack.append(f'$ sfx-position {snd}')


@regop
def o6_getObjectY(op, stack, bytecode):
    obj = stack.pop()
    stack.append(f'object-y {obj}')


@regop
def o90_getWizData(op, stack, bytecode):
    cmd = Value(op.args[0], signed=False)
    if cmd.num == 30:
        state = stack.pop()
        res = stack.pop()
        stack.append(f'$ wiz-image-x {res} {state}')
        return
    if cmd.num == 31:
        state = stack.pop()
        res = stack.pop()
        stack.append(f'$ wiz-image-y {res} {state}')
        return
    if cmd.num == 32:
        state = stack.pop()
        res = stack.pop()
        stack.append(f'$ wiz-image-width {res} {state}')
        return
    if cmd.num == 33:
        state = stack.pop()
        res = stack.pop()
        stack.append(f'$ wiz-image-height {res} {state}')
        return
    if cmd.num == 45:
        y = stack.pop()
        x = stack.pop()
        state = stack.pop()
        res = stack.pop()
        stack.append(f'$ wiz-image-pixel-color {res} {state} at {x},{y} is transparent')
        return
    if cmd.num == 46:
        y = stack.pop()
        x = stack.pop()
        state = stack.pop()
        res = stack.pop()
        stack.append(f'$ wiz-image-pixel-color {res} {state} at {x},{y}')
        return
    return defop(op, stack, bytecode)


@regop
def o6_walkActorTo(op, stack, bytecode):
    # walk actor-name to x-coord,y-coord
    # walk actor-name to actor-name within number
    # walk actor-name to-object object-name
    ypos = stack.pop()
    xpos = stack.pop()
    act = stack.pop()
    return f'walk {act} to {xpos},{ypos}'


@regop
def o6_walkActorToObj(op, stack, bytecode):
    dist = stack.pop()
    obj = stack.pop()
    act = stack.pop()
    return f'walk {act} to-object {obj} within {dist}'


@regop
def o6_distObjectObject(op, stack, bytecode):
    another = stack.pop()
    obj = stack.pop()
    stack.append(f'proximity {obj} {another}')


@regop
def o6_setCameraAt(op, stack, bytecode):
    # ypos = stack.pop()  # v7+
    xpos = stack.pop()
    return f'camera-at {xpos}'


def get_element_by_path(path: str, root: Iterable[Element]) -> Optional[Element]:
    for elem in root:
        if elem.attribs['path'] == path:
            return elem
        if path.startswith(elem.attribs['path']):
            return get_element_by_path(path, elem)
    return None


def collapse_override(asts):
    for _, seq in asts.items():
        stats = iter(list(seq))
        seq.clear()
        for st in stats:
            if str(st) == 'override':
                jmp = next(stats)
                assert str(jmp).startswith('jump &'), jmp
                seq.append(str(jmp).replace('jump', 'override'))
            else:
                seq.append(st)
    return asts


def transform_asts(indent, asts):
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
                            if step == '++' and f'{var} > ' in str(cond.expr):
                                asts[label].pop()  # cond
                                asts[label].pop()  # adv
                                end = str(cond.expr).replace(f'{var} > ', '')
                            elif step == '--' and f'{var} < ' in str(cond.expr):
                                asts[label].pop()  # cond
                                asts[label].pop()  # adv
                                end = str(cond.expr).replace(f'{var} < ', '')
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
                            asts[label].append(f'if ( {ex.expr} ) {{')
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


def print_locals(indent):
    for var in sorted(l_vars.values(), key=operator.attrgetter('num')):
        yield f'{indent[:-1]}local variable {var}'
    if l_vars:
        yield ''  # new line


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


def decompile_script(elem, optable, verbose=False):
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
        'LSC2': 'script',
        'LSCR': 'script',
        'SCRP': 'script',
        'ENCD': 'enter',
        'EXCD': 'exit',
        'VERB': 'verb',
    }
    if elem.tag == 'VERB':
        yield ' '.join([f'object', f'{obj_id}', '{', os.path.dirname(respath_comment)])
        yield ' '.join([f'\tname is', f'"{obj_names[obj_id]}"'])
    else:
        scr_id = int.from_bytes(pref, byteorder='little', signed=False) if pref else None
        gid = elem.attribs['gid']
        assert scr_id is None or scr_id == gid
        gid_str = '' if gid is None else f' {gid}'
        yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])
    bytecode = descumm(script_data, optable)
    # print_bytecode(bytecode)

    refs = [off.abs for stat in bytecode.values() for off in stat.args if isinstance(off, RefOffset)]
    curref = f'_[{0 + 8:08d}]'
    stack = deque(
        # ['**ERROR**'] * 3
    )
    asts = defaultdict(deque)
    if elem.tag == 'VERB':
        entries = {off: idx[0] for idx, off in pref}
    res = None

    # # clear local variables:
    # for key in g_vars:  # NOTE: dict key is tuple, we iterates on keys only
    #     _, var = key
    #     if str(var).startswith('L.'):
    #         del g_vars[key]
    g_vars.clear()

    # print('====================')
    for off, stat in bytecode.items():
        if elem.tag == 'VERB' and off + 8 in entries:
            if off + 8 in entries:
                yield from print_locals(indent)
                l_vars.clear()
                yield from print_asts(indent, transform_asts(indent, asts))
                curref = f'_[{off + 8:08d}]'
                asts = defaultdict(deque)
            if off + 8 > min(entries.keys()):
                yield '\t}'
                l_vars.clear()
            yield ''  # new line
            yield f'\tverb {entries[off + 8]} {{'
            indent = 2 * '\t'
            stack.clear()
        if verbose:
            yield ' '.join([
                f'[{stat.offset + 8:08d}]',
                '\t\t\t\t\t\t\t\t',
                f'{stat} <{list(stack)}>',
            ])
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            curref = f'_[{off + 8:08d}]'
        if off in refs:
            curref = f'[{off + 8:08d}]'
        res = ops.get(stat.name, defop)(stat, stack, bytecode)
        if res:
            asts[curref].append(res)
            # print(
            #     # f'[{stat.offset + 8:08d}]',
            #     f'{indent}{res}',
            #     # res,
            #     # '\t\t\t\t',
            #     # defop(stat, stack, bytecode),
            # )
    yield from print_locals(indent)
    l_vars.clear()
    yield from print_asts(indent, transform_asts(indent, asts))
    if elem.tag == 'VERB' and entries:
        yield '\t}'
    yield '}'



def get_global_scripts(root: Iterable[Element]) -> Iterator[Element]:
    for elem in root:
        if elem.tag in {'LECF', 'LFLF', 'OBCD', *script_map}:
            if elem.tag in {*script_map}:
                yield elem
            else:
                yield from get_global_scripts(elem.children)


def get_room_scripts(root: Iterable[Element]) -> Iterator[Element]:
    for elem in root:
        if elem.tag in {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}:
            if elem.tag == 'SCRP':
                assert 'ROOM' not in elem.attribs['path'], elem
                assert 'RMDA' not in elem.attribs['path'], elem
                continue
            elif elem.tag in {*script_map, 'OBCD'}:
                yield elem
            else:
                yield from get_room_scripts(elem.children)


obj_names = {}

if __name__ == '__main__':
    import argparse
    import os

    from nutcracker.sputm.tree import open_game_resource, narrow_schema
    from nutcracker.sputm.schema import SCHEMA

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('-v', '--verbose', action='count', help='output every opcode')
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

            optable = get_optable(gameres.game)
            with open(fname, 'w') as f:
                for elem in get_global_scripts(room):
                    for line in decompile_script(elem, optable, verbose=args.verbose):
                        print(line, file=f)
                    print('', file=f)  # end with new line
                print(f'room {room_no}', '{', file =f)
                for elem in get_room_scripts(room):
                    print('', file=f)  # end with new line
                    for line in decompile_script(elem, optable, verbose=args.verbose):
                        print(line if line.endswith(']:') or not line else f'\t{line}', file=f)
                print('}', file=f)
                print('', file=f)  # end with new line
