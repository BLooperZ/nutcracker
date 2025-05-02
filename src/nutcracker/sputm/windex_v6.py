import functools
import io
import operator
import os
from collections import OrderedDict, deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from string import printable

from nutcracker.kernel2.element import Element
from nutcracker.sputm.preset import sputm
from nutcracker.sputm.schema import SCHEMA
from nutcracker.sputm.script.bytecode import (
    BytecodeParseError,
    descumm_iter,
    get_argtype,
)
from nutcracker.sputm.script.opcodes import ByteValue, RefOffset, WordValue
from nutcracker.sputm.script.parser import CString, DWordValue
from nutcracker.sputm.script.shared import BytecodeError, ScriptError, realize_refs
from nutcracker.sputm.strings import (
    RAW_ENCODING,
    EncodingSetting,
    get_optable,
    get_script_map,
)
from nutcracker.sputm.tree import narrow_schema


class Value:
    suffix = {
        ByteValue: 'B',
        WordValue: 'W',
        DWordValue: 'D',
    }

    def __init__(self, orig, *, signed=True, cast=None):
        self.orig = orig
        self.num = int.from_bytes(orig.op, byteorder='little', signed=signed)
        self.cast = cast

    def __repr__(self):
        if self.cast == 'char':
            # NOTE: in HE v71 games, they put the "/" char as a
            # WordValue.
            assert isinstance(self.orig, (ByteValue, WordValue))
            if self.num < 128:
                # ASCII Char
                return f"'{chr(self.num)}'"
            return f"'\\x{ord(chr(self.num)):02X}'"
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
        return f'"{self.orig.msg.decode(**RAW_ENCODING)}"'


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
        if isinstance(self.orig, DWordValue):
            if not self.num & 0xF0000000:
                assert self.num & 0xFFFFFFF == self.num, self.num
                if self.num in self.names:
                    return self.names[self.num]
            elif self.num & 0x80000000:
                pref = 'R'  # Room Variable
                # TODO: or bit varoable on < he80, B
            else:
                assert self.num & 0x40000000, self.num
                pref = 'L'  # Local Variable
            num = self.num & 0xFFFFFFF
            return f'{pref}.{num}'  # [{self.cast}]'

        if isinstance(self.orig, ByteValue):
            pref = 'B'
            num = self.num & 0xFF
            return f'{pref}.{num}'

        assert isinstance(self.orig, WordValue), self.orig
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


def get_params(stack):
    num_params = stack.pop().num
    return [stack.pop() for _ in range(num_params)][::-1]


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
        if (
            isinstance(left, str)
            or isinstance(left, Negate)
            or (
                isinstance(left, BinExpr)
                and left.pre >= self.pre
                and left.op != self.op
            )
        ):
            left = f'({left})'
        right = self.right
        if (
            isinstance(right, str)
            or isinstance(right, Negate)
            or (
                isinstance(right, BinExpr)
                and right.pre >= self.pre
                and right.op != self.op
            )
        ):
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
class ConditionalNotJump:
    expr: str
    ref: RefOffset

    def __str__(self) -> str:
        return f'if ( {self.expr} ) jump {adr(self.ref)}'


@dataclass
class UnconditionalJump:
    ref: RefOffset

    def __str__(self) -> str:
        return f'jump {adr(self.ref)}'


def escape_message(
    msg: bytes,
    escape: bytes | None = None,
    var_size: int = 2,
) -> Iterator[bytes]:
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
                        stream.read(var_size),
                        byteorder='little',
                        signed=False,
                    )
                    c = f'%{control}{num}%'.encode()
                else:
                    c += t
                    if ord(t) not in {1, 2, 3, 8}:
                        c += stream.read(var_size)
                    c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c not in (
                printable.encode() + bytes(range(ord('\xe0'), ord('\xfa') + 1))
            ):
                c = b''.join(f'\\x{v:02X}'.encode() for v in c)
            elif c == b'\\':
                c = b'\\\\'
            yield c


def msg_to_print(msg: bytes, encoding: EncodingSetting = RAW_ENCODING) -> str:
    return b''.join(escape_message(msg, escape=b'\xff')).decode(**encoding)


def msg_val(arg: CString) -> str:
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
    if isinstance(arr.orig, str):
        return arr
    return ops['_strings'].pop() if Value(arr.orig, signed=True).num == -1 else arr


def adr(arg: RefOffset) -> str:
    return f'&[{arg.abs + 8:08d}]'


ops = {'_strings': deque()}


def regop(op):
    ops[op.__name__] = op
    return op


def defop(op, stack, game):
    raise NotImplementedError(f'{op} <{stack}>')
    return f'{op} <{stack}>'


def fstack(pattern, *args, **kwargs):
    def inner(op, stack):
        return pattern.format(*(PrintArg(f(op, stack)) for f in args), **kwargs)
    return inner


class PrintArg:
    def __init__(self, arg) -> None:
        self.arg = arg

    def __format__(self, format_spec: str) -> str:
        if format_spec == 'var':
            assert isinstance(self.arg, (WordValue, DWordValue)), self.arg
            return str(get_var(self.arg))
        if format_spec == 'ref':
            assert isinstance(self.arg, RefOffset), self.arg
            return adr(self.arg)
        if format_spec == 'msg':
            assert isinstance(self.arg, CString), self.arg
            return msg_val(self.arg)
        if format_spec == 'hzero':
            if self.arg.num == 0:
                return ''
            return str(self.arg)
        if format_spec == 'cvargs':
            return ','.join(str(arg) for arg in self.arg)
        if format_spec == 'csvargs':
            return ', '.join(str(arg) for arg in self.arg)
        if format_spec == 'svargs':
            return ' '.join(str(arg) for arg in self.arg)
        if format_spec == 'psvargs':
            params_str = ' '.join(str(arg) for arg in self.arg)
            return ' ' + params_str if params_str else ''
        if format_spec == 'pvargs':
            params_str = ', '.join(str(param) for param in self.arg)
            return f' ( {params_str} )' if params_str else ''
        if format_spec == 'sflags':
            background = 'bak ' if self.arg.num & 1 else ''
            recursive = 'rec ' if self.arg.num & 2 else ''
            return f'{background}{recursive}'
        if format_spec == 'operation':
            return ' +-&|^'[self.arg.num]
        if isinstance(self.arg, str) and ' ':
            return f'({self.arg})'
        if isinstance(self.arg, BinExpr):
            return f'({self.arg})'
        return str(self.arg)


def POP(op, stack):
    return stack.pop()

def NPOP(num):
    return num * [POP]

def POP_STR(op, stack):
    return pop_str(stack)

def MSG_ARG(num):
    def inner(op, stack):
        assert isinstance(op.args[num], CString), op.args
        return op.args[num]
    return inner

def ARG(num):
    def inner(op, stack):
        return op.args[num]
    return inner

def BYTE_ARG(num):
    def inner(op, stack):
        assert isinstance(op.args[num], ByteValue), op.args
        return Value(op.args[num])
    return inner

def WORD_ARG(num):
    def inner(op, stack):
        assert isinstance(op.args[num], (WordValue, DWordValue)), op.args
        return Value(op.args[num])
    return inner

def DWORD_ARG(num):
    def inner(op, stack):
        assert isinstance(op.args[num], DWordValue), op.args
        return Value(op.args[num])
    return inner

def BYTE_VAR(num):
    def inner(op, stack):
        assert isinstance(op.args[num], ByteValue), op.args
        return get_var(op.args[num])
    return inner

def SCRIPT_VAR(num):
    def inner(op, stack):
        assert isinstance(op.args[num], (WordValue, DWordValue)), op.args
        return get_var(op.args[num])
    return inner

def REF_ARG(num):
    def inner(op, stack):
        assert isinstance(op.args[num], RefOffset), op.args
        return adr(op.args[num])
    return inner

def POP_PARAMS(op, stack):
    return get_params(stack)


def BUILD(mapping):
    def inner(op, stack):
        assert len(op.args), op.args
        subop, *rest = op.args
        assert not rest, rest
        return mapping[subop.name](subop, stack)
    return inner


def F_PUSH(func):
    def inner(op, stack):
        stack.append(func(op, stack))
    return inner


def PBUILD(mapping):
    def inner(op, stack):
        sub = stack.pop()
        return mapping[sub.num](op, stack)
    return inner


def GUARD(condtion, option, fallback=None):
    if condtion:
        return option
    return fallback


## OPCODES

@regop
def o6_pushByte(op, stack, game):
    F_PUSH(BYTE_ARG(0))(op, stack)


@regop
def o6_pushWord(op, stack, game):
    F_PUSH(WORD_ARG(0))(op, stack)


@regop
def o72_pushDWord(op, stack, game):
    F_PUSH(DWORD_ARG(0))(op, stack)


@regop
def o6_pushByteVar(op, stack, game):
    F_PUSH(BYTE_VAR(0))(op, stack)


@regop
def o6_pushWordVar(op, stack, game):
    F_PUSH(SCRIPT_VAR(0))(op, stack)


@regop
def o6_wordArrayRead(op, stack, game):
    arr = get_var(op.args[0])
    pos = stack.pop()
    cast = None
    if getattr(arr, 'cast', None) == 'string':
        cast = 'char'
    stack.append(Caster(f'{arr}[{pos}]', cast=cast))


@regop
def o6_byteArrayIndexedRead(op, stack, game):  # 0x0A
    arr = get_var(op.args[0])
    idx = stack.pop()
    base = stack.pop()
    cast = None
    if getattr(arr, 'cast', None) == 'string':
        cast = 'char'
    stack.append(Caster(f'{arr}[{base}][{idx}]', cast=cast))


@regop
def o6_wordArrayIndexedRead(op, stack, game):  # 0x0B
    arr = get_var(op.args[0])
    idx = stack.pop()
    base = stack.pop()
    cast = None
    if getattr(arr, 'cast', None) == 'string':
        cast = 'char'
    stack.append(Caster(f'{arr}[{base}][{idx}]', cast=cast))


@regop
def o6_dup(op, stack, game):
    val = stack.pop()
    if not isinstance(val, Dup):
        val = Dup(val)
    stack.append(val)
    stack.append(val)


@regop
def o90_dup_n(op, stack, game):
    stack.append(Value(op.args[0], signed=True))
    params = get_params(stack)
    for param in params:
        stack.extend([param] * 2)


@regop
def o6_not(op, stack, game):
    arg = stack.pop()
    if isinstance(arg, str) and ' ' in arg:
        arg = f'({arg})'
    stack.append(Negate(arg))


@regop
def o6_abs(op, stack, game):
    stack.append(Abs(stack.pop()))


@regop
def o6_eq(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('==', first, second))


@regop
def o6_neq(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('!=', first, second))


@regop
def o6_gt(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('>', first, second))


@regop
def o6_ge(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('>=', first, second))


@regop
def o6_lt(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('<', first, second))


@regop
def o6_le(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('<=', first, second))


@regop
def o6_land(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('and', first, second))


@regop
def o6_lor(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('or', first, second))


@regop
def o6_band(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('&', first, second))


@regop
def o6_bor(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('|', first, second))


@regop
def o6_add(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('+', first, second))


@regop
def o6_sub(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('-', first, second))


@regop
def o6_mul(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('*', first, second))


@regop
def o6_div(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('/', first, second))


@regop
def o8_mod(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('%', first, second))


@regop
def o90_mod(op, stack, game):
    second, first = stack.pop(), stack.pop()
    stack.append(BinExpr('%', first, second))


@regop
def o6_pop(op, stack, game):
    val = stack.pop()
    if isinstance(val, Dup):
        stack.append(val)


@regop
def o6_ifNot(op, stack, game):
    off, *rest = op.args
    assert not rest
    return ConditionalJump(stack.pop(), off)


@regop
def o6_if(op, stack, game):
    off, *rest = op.args
    assert not rest
    return ConditionalNotJump(stack.pop(), off)


@regop
def o6_jump(op, stack, game):
    off, *rest = op.args
    assert not rest
    return UnconditionalJump(off)


@regop
def o6_writeByteVar(op, stack, game):
    assert len(op.args) == 1 and isinstance(op.args[0], ByteValue), op.args
    value = stack.pop()
    var = get_var(op.args[0])
    var.cast = getattr(value, 'cast', None)
    if isinstance(value, Caster):
        value = value.orig
    return f'{var} = {PrintArg(value)}'


@regop
def o6_writeWordVar(op, stack, game):
    assert len(op.args) == 1 and isinstance(
        op.args[0],
        (WordValue, DWordValue),
    ), op.args
    value = stack.pop()
    var = get_var(op.args[0])
    var.cast = getattr(value, 'cast', None)
    if isinstance(value, Caster):
        value = value.orig
    return f'{var} = {PrintArg(value)}'


@regop
def o6_startObject(op, stack, game):
    return fstack('start-object {3:sflags} {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(3))(op, stack)


@regop
def o72_startObject(op, stack, game):
    return BUILD({
        'SO_NONE': fstack('start-object {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        'SO_BAK': fstack('start-object bak {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        'SO_REC': fstack('start-object rec {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        'SO_BAK_REC': fstack('start-object bak rec {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
    })(op, stack)


@regop
def o6_drawBox(op, stack, game):
    # draw-box {x1},{y1} to {x2},{y2} color {color}
    return fstack('draw-box {4},{3} to {2},{1} color {0}', *NPOP(5))(op, stack)


@regop
def o6_setBoxFlags(op, stack, game):
    # set-box box-number [box-numer ...] to box-status
    return fstack('set-box {1:svargs} to {0}', POP, POP_PARAMS)(op, stack)


@regop
def o6_setBoxSet(op, stack, game):
    # set-box-set set
    return fstack('set-box-set {0}', POP)(op, stack)


@regop
def o6_loadRoomWithEgo(op, stack, game):
    if game.version < 7:
        # come-out-door {door} in-room {room} walk {x},{y}
        return fstack('come-out-door {3} in-room {2} walk {1},{0}', *NPOP(4))(op, stack)
    # come-out-door {door} walk {x},{y}
    return fstack('come-out-door {2} walk {1},{0}', *NPOP(3))(op, stack)


@regop
def o6_wordArrayIndexedWrite(op, stack, game):
    return fstack('{0}[{3}][{2}] = {1}', SCRIPT_VAR(0), *NPOP(3))(op, stack)


@regop
def o90_max(op, stack, game):
    F_PUSH(fstack('max {1} {0}', *NPOP(2)))(op, stack)


@regop
def o90_atan2(op, stack, game):
    F_PUSH(fstack('angle-from-delta {1},{0}', *NPOP(2)))(op, stack)


@regop
def o90_getSegmentAngle(op, stack, game):
    F_PUSH(
        fstack('angle-from-line {3},{2} to {1},{0}', *NPOP(4))
    )(op, stack)


@regop
def o90_sin(op, stack, game):
    F_PUSH(fstack('sin {0}', POP))(op, stack)


@regop
def o90_sqrt(op, stack, game):
    F_PUSH(fstack('sqrt {0}', POP))(op, stack)


@regop
def o90_cos(op, stack, game):
    F_PUSH(fstack('cos {0}', POP))(op, stack)


@regop
def o90_shl(op, stack, game):
    F_PUSH(fstack('{1} << {0}', *NPOP(2)))(op, stack)


@regop
def o90_shr(op, stack, game):
    F_PUSH(fstack('{1} >> {0}', *NPOP(2)))(op, stack)


@regop
def o90_xor(op, stack, game):
    F_PUSH(fstack('{1} bxor {0}', *NPOP(2)))(op, stack)


@regop
def o90_min(op, stack, game):
    F_PUSH(fstack('min {1} {0}', *NPOP(2)))(op, stack)


@regop
def o6_startScript(op, stack, game):
    return fstack(
        'start-script {2:sflags}{1:script}{0:pvargs}',
        POP_PARAMS,
        *NPOP(2),
    )(op, stack)


@regop
def o6_jumpToScript(op, stack, game):
    return fstack(
        'chain-script {2:sflags} {1:script}{0:pvargs}',
        POP_PARAMS,
        *NPOP(2),
    )(op, stack)


@regop
def o72_jumpToScript(op, stack, game):
    return BUILD({
        'SO_NONE': fstack('chain-script {1}{0:pvargs}', POP_PARAMS, POP),
        # 'SO_BAK': fstack('chain-script bak {1}{0:pvargs}', POP_PARAMS, POP),
        'SO_REC': fstack('chain-script rec {1}{0:pvargs}', POP_PARAMS, POP),
        # 'SO_BAK_REC': fstack('chain-script bak rec {1}{0:pvargs}', POP_PARAMS, POP),
    })(op, stack)


@regop
def o72_startScript(op, stack, game):
    return BUILD({
        'SO_NONE': fstack('start-script {1}{0:pvargs}', POP_PARAMS, POP),
        'SO_BAK': fstack('start-script bak {1}{0:pvargs}', POP_PARAMS, POP),
        'SO_REC': fstack('start-script rec {1}{0:pvargs}', POP_PARAMS, POP),
        # 'SO_BAK_REC': fstack('start-script bak rec {1}{0:pvargs}', POP_PARAMS, POP),
    })(op, stack)


@regop
def o6_startScriptQuick(op, stack, game):
    return fstack('start-script {1}{0:pvargs}', POP_PARAMS, POP)(op, stack)


@regop
def o6_startScriptQuick2(op, stack, game):
    F_PUSH(
        fstack('@{1}{0:pvargs}', POP_PARAMS, POP)
    )(op, stack)


@regop
def o90_priorityChainScript(op, stack, game):
    return BUILD({
        'SO_NONE': fstack('chain-script {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        # 'SO_BAK': fstack('chain-script bak {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        # 'SO_REC': fstack('chain-script rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        # 'SO_BAK_REC': fstack('chain-script bak rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
    })(op, stack)


@regop
def o90_priorityStartScript(op, stack, game):
    return BUILD({
        'SO_NONE': fstack('start-script {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        # 'SO_BAK': fstack('start-script bak {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        'SO_REC': fstack('start-script rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        # 'SO_BAK_REC': fstack('start-script bak rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
    })(op, stack)


@regop
def o6_stopObjectScript(op, stack, game):
    return fstack('stop-object {0}', POP)(op, stack)


@regop
def o6_stopScript(op, stack, game):
    return fstack('stop-script {0}', POP)(op, stack)


@regop
def o72_getHeap(op, stack, game):
    F_PUSH(
        BUILD({
        # 'SO_HEAP_FREE': fstack('heap-free'),
        'SO_HEAP_LARGEST_FREE': fstack('heap-largest-free'),
        }),
    )(op, stack)


@regop
def videoOps(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('video {0}', POP),
        'SO_CLOSE': fstack('\tclose-file'),
        'SO_IMAGE': fstack('\timage {0}', POP),
        'SO_LOAD': fstack('\topen-file {0}', POP_STR),
        'SO_SET_FLAGS': PBUILD({
            1: fstack('\tbackground'),
            4: fstack('\tforeground'),
            # 8: fstack('\tlooping'),
            16: fstack('\tset-flags 16'),
        }),
        'SO_END': fstack('\t(end)'),
    })(op, stack)


@regop
def getVideoData(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_COUNT': fstack('video {0} state-count', POP),
            # 'SO_HEIGHT': fstack('video {0} height', POP),
            # 'SO_IMAGE': fstack('video {0} image', POP),
            # 'SO_NEW_GENERAL_PROPERTY': fstack('video {1} propery {0}', *NPOP(2)),
            'SO_STATE': fstack('video {0} state', POP),
            # 'SO_WIDTH': fstack('video {0} width', POP),
        })
    )(op, stack)


@regop
def arrayOps(op, stack, game):
    return BUILD({
        'SO_ASSIGN_STRING': fstack('{0}[{1:hzero}] = {2:msg}', SCRIPT_VAR(0), POP, MSG_ARG(1)),
        'SO_ASSIGN_INT_LIST': fstack('{0}[{1:hzero}] = [{2:csvargs}]', SCRIPT_VAR(0), POP, POP_PARAMS),
        'SO_ASSIGN_2DIM_LIST': fstack('{0}[{3}][{1:hzero}] = [{2:csvargs}]', SCRIPT_VAR(0), POP, POP_PARAMS, POP),
    })(op, stack)


@regop
def o72_arrayOps(op, stack, game):
    return BUILD({
        'SO_STRING': fstack('{0} = {1}', SCRIPT_VAR(0), POP_STR),
        'SO_COMPLEX_ARRAY_ASSIGNMENT': fstack('{0}[{5} to {4}][{3} to {2}] = [{1:csvargs}]', SCRIPT_VAR(0), POP_PARAMS, *NPOP(4)),
        'SO_COMPLEX_ARRAY_COPY_OPERATION': fstack('{0}[{9} to {8}][{7} to {6}] = {1}[{5} to {4}][{3} to {2}]', SCRIPT_VAR(0), SCRIPT_VAR(1), *NPOP(8)),
        'SO_RANGE_ARRAY_ASSIGNMENT': fstack('{0}[{6} to {5}][{4} to {3}] = ({2} to {1})', SCRIPT_VAR(0), *NPOP(6)),
        'SO_COMPLEX_ARRAY_MATH_OPERATION': fstack('{0}[{15} to {14}][{13} to {12}] := ({1}[{11} to {10}][{9} to {8}] {3:operation} {2}[{7} to {6}][{5} to {4}])', SCRIPT_VAR(0), SCRIPT_VAR(1), SCRIPT_VAR(2), *NPOP(13)),
        'SO_FORMATTED_STRING': fstack('{0} = {3} {2}{1:psvargs}', SCRIPT_VAR(0), POP_PARAMS, POP, POP_STR),
        'SO_ASSIGN_INT_LIST': fstack('{0}[{1:hzero}] = [{2:csvargs}]', SCRIPT_VAR(0), POP, POP_PARAMS),
        'SO_ASSIGN_2DIM_LIST': fstack('{0}[{2}][] = [{1:csvargs}]', SCRIPT_VAR(0), POP_PARAMS, POP),
    })(op, stack)


@regop
def o6_isAnyOf(op, stack, game):
    if getattr(stack[-1], 'cast', None):
        raise ValueError(getattr(stack[-1], 'cast', None), stack)
    params = get_params(stack)
    var = stack.pop()
    cast = getattr(var, 'cast', None)
    if cast:
        for param in params:
            param.cast = cast
    stack.append(f'{var} in [ {", ".join(str(param) for param in params)} ]')


@regop
def o90_disabled_windowOps(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('window {0}', POP),
        'SO_NEW': fstack('\tnew'),
        'SO_IMAGE': fstack('\timage {0}', POP),
        'SO_TITLE_BAR': fstack('\ttitle-bar {0}', POP_STR),
        'SO_SCRIPT': fstack('\tscript {0}', POP),
        'SO_END': fstack('\t(end)'),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_MOVE': fstack('\tmove {1},{0}', *NPOP(2)),
        'SO_SHOW': fstack('\tshow {0}', POP),
        # 'SO_CLEAR_FLAGS': fstack('\tclear-flags {0}', POP),
        # 'SO_HEIGHT': fstack('\theight {0}', POP),
        # 'SO_SET_FLAGS': fstack('\tset-flags {0}', POP),
        # 'SO_WIDTH': fstack('\twidth {0}', POP),
    })(op, stack)


@regop
def o6_stopObjectCodeReturn(op, stack, game):
    return fstack('return {0}', POP)(op, stack)


@regop
def o6_stopObjectCodeObject(op, stack, game):
    return 'end-object'


@regop
def o6_stopObjectCodeScript(op, stack, game):
    return 'end-script'


@regop
def o72_getScriptString(op, stack, game):
    push_str(stack, KeyString(op.args[0]))


@regop
def o70_readINI(op, stack, game):
    sub = stack.pop()
    string = op.args[0]
    if sub.num == 1:
        stack.append(Caster(f'read-ini {string}', cast='number'))
        return
    if sub.num == 2:
        stack.append(Caster(f'read-ini string {string}', cast='string'))
        return
    return defop(op, stack, game)


@regop
def o70_writeINI(op, stack, game):
    sub = stack.pop()
    value = stack.pop()
    option = op.args[0]
    if sub.num == 1:
        return f'write-ini {option} = {value}'
    if sub.num == 2:
        value = op.args[1]
        return f'write-ini string {option} = {value}'
    return defop(op, stack, game)


def CAST(cast, func):
    def inner(op, stack):
        return Caster(func(op, stack), cast=cast)
    return inner


@regop
def o72_readINI(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_DWORD': CAST('number', fstack('read-ini {0}', POP_STR)),
            'SO_STRING': CAST('string', fstack('read-ini string {0}', POP_STR)),
        })
    )(op, stack)


@regop
def o72_writeINI(op, stack, game):
    return BUILD({
        'SO_DWORD': fstack('write-ini {1} = {0}', POP, POP_STR),
        'SO_STRING': fstack('write-ini string {1} = {0}', POP_STR, POP_STR),
    })(op, stack)


@regop
def o60_rename(op, stack, game):
    target = op.args[1]
    source = op.args[0]
    return f'rename-file {msg_val(source)} to {msg_val(target)}'


@regop
def o72_rename(op, stack, game):
    target = pop_str(stack)
    source = pop_str(stack)
    return f'rename-file {source} to {target}'


@regop
def o72_debugInput(op, stack, game):
    string = pop_str(stack)
    stack.append(f'debug-input {string}')


@regop
def o8_debug(op, stack, game):
    level = stack.pop()
    return f'debug {level}'


@regop
def o80_getFileSize(op, stack, game):
    F_PUSH(fstack('file-size {0}', POP_STR))(op, stack)


@regop
def o72_traceStatus(op, stack, game):
    return fstack('debug {1} {0}', POP, POP_STR)(op, stack)


def printer(action, op, stack, *, pop_actor=False):
    return BUILD({
        'SO_BASEOP': fstack(f'{action} {{0}}', POP) if pop_actor else fstack(f'{action}'),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_CLIPPED': fstack('\tclipped {0}', POP),
        'SO_CENTER': fstack('\tcenter'),
        'SO_LEFT': fstack('\tleft'),
        'SO_OVERHEAD': fstack('\toverhead'),
        'SO_MUMBLE': fstack('\tmumble'),
        'SO_TEXTSTRING': fstack('\t{0:msg}', MSG_ARG(0)),
        'SO_FORMATTED_STRING': fstack('\t{0:msg} {2}{1:psvargs}', MSG_ARG(0), POP_PARAMS, POP),
        'SO_TALKIE': fstack('\ttalkie {0}', POP),
        'SO_COLOR': fstack('\tcolor {0}', POP),
        'SO_COLOR_LIST': fstack('\tcolor {0:csvargs}', POP_PARAMS),
        'SO_END': fstack('\tend'),

        # V8
        'SO_PRINT_CHARSET': fstack('\tcharset {0}', POP),
        'SO_PRINT_WRAP': fstack('\twrap'),
    })(op, stack)


@regop
def o8_printDebug(op, stack, game):
    return printer('print-debug', op, stack)


@regop
def o8_printText(op, stack, game):
    return printer('print-text', op, stack)


@regop
def o8_blastText(op, stack, game):
    return printer('blast-text', op, stack)


@regop
def o8_printLine(op, stack, game):
    return printer('print-line', op, stack)


@regop
def o8_printSystem(op, stack, game):
    return printer('print-system', op, stack)


@regop
def o8_printEgo(op, stack, game):
    # with io.BytesIO(b'\x09\x00') as stream:
    #     stack.append(get_var(WordValue(stream)))
    return printer('say-line', op, stack)


@regop
def o8_printActor(op, stack, game):
    return printer('say-line', op, stack, pop_actor=True)


@regop
def o6_printDebug(op, stack, game):
    return printer('print-debug', op, stack)


@regop
def o6_printText(op, stack, game):
    return printer('print-text', op, stack)


@regop
def o6_printLine(op, stack, game):
    return printer('print-line', op, stack)


@regop
def o6_printSystem(op, stack, game):
    return printer('print-system', op, stack)


@regop
def o6_printEgo(op, stack, game):
    return printer('say-line', op, stack)


@regop
def o6_printActor(op, stack, game):
    return printer('say-line', op, stack, pop_actor=True)


@regop
def o72_talkActor(op, stack, game):
    act = stack.pop()
    return f'say-line {act} {msg_val(op.args[0])}'


@regop
def o72_talkEgo(op, stack, game):
    return f'say-line {msg_val(op.args[0])}'


@regop
def o6_talkEgo(op, stack, game):
    # with io.BytesIO(b'\x09\x00') as stream:
    #     stack.append(get_var(WordValue(stream)))
    return f'say-line {msg_val(op.args[0])}'


@regop
def o6_talkActor(op, stack, game):
    act = stack.pop()
    return f'say-line {act} {msg_val(op.args[0])}'


@regop
def o8_talkActor(op, stack, game):
    act = stack.pop()
    return f'say-line {act} {msg_val(op.args[0])}'


@regop
def o6_setBlastObjectWindow(op, stack, game):
    bottom = stack.pop()
    right = stack.pop()
    top = stack.pop()
    left = stack.pop()
    return f'& blast-object-window {left},{top} to {right},{bottom}'


@regop
def o71_getStringWidth(op, stack, game):
    ln = stack.pop()
    pos = stack.pop()
    array = stack.pop()
    stack.append(f'string-width {array} from {pos} to {ln}')


@regop
def o8_getStringWidth(op, stack, game):
    charset = stack.pop()
    stack.append(f'string-width charset {charset} {msg_val(op.args[0])}')


@regop
def o71_getStringLenForWidth(op, stack, game):
    F_PUSH(
        fstack('string-margin {2} from {1} margin {0}', *NPOP(3))
    )(op, stack)


@regop
def o6_beginOverride(op, stack, game):
    return 'override'


@regop
def o6_endOverride(op, stack, game):
    return 'override off'


@regop
def o72_resetCutscene(op, stack, game):
    return 'override off off'


@regop
def o70_createDirectory(op, stack, game):
    string = op.args[0]
    return f'create-directory {string}'


@regop
def o72_createDirectory(op, stack, game):
    string = pop_str(stack)
    return f'create-directory {string}'


@regop
def o60_deleteFile(op, stack, game):
    string = op.args[0]
    return f'delete-file {msg_val(string)}'


@regop
def o72_deleteFile(op, stack, game):
    string = pop_str(stack)
    return f'delete-file {string}'


@regop
def dimArray(op, stack, game):
    return BUILD({
        'SO_UNDIM_ARRAY': fstack('undim {0}', SCRIPT_VAR(0)),
        'SO_INT': fstack('dim int array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_BIT': fstack('dim bit array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_NIBBLE': fstack('dim nibble array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_BYTE': fstack('dim byte array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_STRING': fstack('dim string array {0}[{1}]', SCRIPT_VAR(0), POP),
    })(op, stack)


@regop
def dim2dimArray(op, stack, game):
    return BUILD({
        'SO_INT': fstack('dim int array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_BIT': fstack('dim bit array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_NIBBLE': fstack('dim nibble array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_BYTE': fstack('dim byte array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_STRING': fstack('dim string array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
    })(op, stack)


@regop
def o72_dim2dimArray(op, stack, game):
    return BUILD({
        'SO_BIT': fstack('dim bit array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_NIBBLE': fstack('dim nibble array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_BYTE': fstack('dim byte array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_INT': fstack('dim int array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_DWORD': fstack('dim dword array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_STRING': fstack('dim string array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
    })(op, stack)


@regop
def o72_dimArray(op, stack, game):
    return BUILD({
        'SO_UNDIM_ARRAY': fstack('undim {0}', SCRIPT_VAR(0)),
        'SO_BIT': fstack('dim int array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_NIBBLE': fstack('dim bit array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_BYTE': fstack('dim byte array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_INT': fstack('dim int array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_DWORD': fstack('dim dword array {0}[{1}]', SCRIPT_VAR(0), POP),
        'SO_STRING': fstack('dim string array {0}[{1}]', SCRIPT_VAR(0), POP),
    })(op, stack)


@regop
def o90_dim2dim2Array(op, stack, game):
    return BUILD({
        'SO_BIT': fstack('dim bit array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
        'SO_NIBBLE': fstack('dim nibble array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
        'SO_BYTE': fstack('dim byte array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
        'SO_INT': fstack('dim int array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
        'SO_DWORD': fstack('dim dword array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
        'SO_STRING': fstack('dim string array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
    })(op, stack)


@regop
def o90_redim2dimArray(op, stack, game):
    return BUILD({
        'SO_BIT': fstack('redim bit array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        'SO_NIBBLE': fstack('redim nibble array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        'SO_BYTE': fstack('redim byte array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        'SO_INT': fstack('redim int array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        'SO_DWORD': fstack('redim dword array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        'SO_STRING': fstack('redim string array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
    })(op, stack)


@regop
def o70_isResourceLoaded(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_IMAGE_LOADED': fstack('image-loaded {0}', POP),
            'SO_ROOM_LOADED': fstack('room-loaded {0}', POP),
            'SO_COSTUME_LOADED': fstack('costume-loaded {0}', POP),
            'SO_SOUND_LOADED': fstack('sound-loaded {0}', POP),
            'SO_SCRIPT_LOADED': fstack('script-loaded {0}', POP),
        })
    )(op, stack)


@regop
def o100_isResourceLoaded(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_IMAGE': fstack('image-loaded {0}', POP),
            # 'SO_ROOM': fstack('room-loaded {0}', POP),
            'SO_COSTUME': fstack('costume-loaded {0}', POP),
            'SO_SOUND': fstack('sound-loaded {0}', POP),
            # 'SO_SCRIPT': fstack('script-loaded {0}', POP),
        })
    )(op, stack)


@regop
def o6_doSentence(op, stack, game):
    obj_b = stack.pop()
    flags = stack.pop()
    obj_a = stack.pop()
    verb = stack.pop()
    return f'do-sentence {verb} {obj_a} [{flags}] {obj_b}'


@regop
def o8_doSentence(op, stack, game):
    obj_b = stack.pop()
    obj_a = stack.pop()
    verb = stack.pop()
    return f'do-sentence {verb} {obj_a} with {obj_b}'


@regop
def o6_soundKludge(op, stack, game):
    params = get_params(stack)
    param_str = ' '.join(str(param) for param in params)
    return f'sound {param_str}'


@regop
def o6_cutscene(op, stack, game):
    params = get_params(stack)
    param_str = ' '.join(str(param) for param in params)
    return f'cut-scene ({param_str})'


@regop
def o6_endCutscene(op, stack, game):
    return 'end-cut-scene'


@regop
def o6_startSound(op, stack, game):
    if game.he_version > 60:  # >he60
        offset = stack.pop()
        return f'start-sound {stack.pop()} offset {offset}'
    return f'start-sound {stack.pop()}'


@regop
def o60_soundOps(op, stack, game):
    return BUILD({
        'SO_SOUND_START_VOLUME': (
            # windex shows empty string
            fstack('sound volume {0}', POP)
        ),
        'SO_SOUND_VOLUME_RAMP': fstack('sound volume-ramp {0}', POP),
        'SO_SOUND_FREQUENCY': (
            # windex shows empty string
            fstack('sound frequency {0}', POP)
        ),
    })(op, stack)


@regop
def o70_soundOps(op, stack, game):
    return BUILD({
        'SO_SOFT': fstack('\tsoft'),
        'SO_VARIABLE': fstack('sound {2} variable {1} is {0}', *NPOP(3)),
        'SO_SOUND_VOLUME': fstack('sound {1} volume {0}', *NPOP(2)),
        'SO_SOUND_START_VOLUME': (
            fstack('\tvolume {0}', POP)
        ),
        'SO_NOW': fstack('\tnow'),
        'SO_SOUND_START': fstack('start-sound {0}', POP),
        'SO_SOUND_CHANNEL': fstack('\tchannel {0}', POP),
        'SO_AT': fstack('\tat {0}', POP),
        'SO_SOUND_LOOPING': fstack('\tloop'),
        'SO_END': fstack('\t(end-sound)'),
        'SO_SOUND_MODIFY': fstack('sound {0}', POP),
        'SO_SOUND_SOFT': fstack('\tsoft'),
        'SO_SOUND_VOLUME': fstack('\tvolume {0}', POP),
        'SO_SOUND_PAN': fstack('\tpan {0}', POP),
        'SO_SOUND_FREQUENCY': fstack('\tfrequency {0}', POP),
    })(op, stack)


@regop
def kernelSetFunctions(op, stack, game):
    return fstack('kludge {0:svargs}', POP_PARAMS)(op, stack)


@regop
def kernelGetFunctions(op, stack, game):
    F_PUSH(fstack('kludge {0:svargs}', POP_PARAMS))(op, stack)


@regop
def o6_getActorFromXY(op, stack, game):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-actor {xpos},{ypos}')


@regop
def o6_findObject(op, stack, game):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-object {xpos},{ypos}')


@regop
def o71_findBox(op, stack, game):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-box {xpos},{ypos}')


@regop
def o72_findObject(op, stack, game):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-object {xpos},{ypos}')


@regop
def o6_findInventory(op, stack, game):
    slot = stack.pop()
    act = stack.pop()
    stack.append(f'find-object {act},{slot}')


@regop
def o6_getVerbFromXY(op, stack, game):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'find-verb {xpos},{ypos}')


@regop
def o6_stopSound(op, stack, game):
    return f'stop-sound {stack.pop()}'


@regop
def o6_isSoundRunning(op, stack, game):
    stack.append(f'sound-running {stack.pop()}')


@regop
def o6_isScriptRunning(op, stack, game):
    stack.append(f'script-running {stack.pop()}')


@regop
def o6_isRoomScriptRunning(op, stack, game):
    stack.append(f'object-running {stack.pop()}')


@regop
def o6_roomOps(op, stack, game):
    return BUILD({
        'SO_ROOM_SCROLL': fstack('room-scroll is {1} {0}', *NPOP(2)),
        'SO_ROOM_SCREEN': fstack('set-screen {1} to {0}', *NPOP(2)),
        'SO_ROOM_PALETTE': fstack('palette {3} {2} {1} in-slot {0}', *NPOP(4)),
        'SO_ROOM_SHAKE_ON': fstack('shake on'),
        'SO_ROOM_SHAKE_OFF': fstack('shake off'),
        'SO_ROOM_INTENSITY': fstack('palette intensity {2} in-slot {1} to {0}', *NPOP(3)),
        'SO_ROOM_SAVEGAME': fstack('saveload-game {1} in-slot {0}', *NPOP(2)),
        'SO_ROOM_FADE': fstack('fades {0}', POP),
        'SO_RGB_ROOM_INTENSITY': fstack('palette intensity {4} {3} {2} in-slot {1} to {0}', *NPOP(5)),
        'SO_ROOM_TRANSFORM': fstack('palette transform {3} in-slot {2} to {1} steps {0}', *NPOP(4)),
        'SO_CYCLE_SPEED': fstack('palette cycle-speed {1} is {0}', *NPOP(2)),
        'SO_ROOM_NEW_PALETTE': (
            # windex show empty string here
            fstack('palette {0}', POP)
        ),

        # Since HE 60
        **GUARD(
            game.he_version >= 60,
            {
                'SO_ROOM_SAVEGAME_BY_NAME': GUARD(
                    game.he_version < 72,
                    fstack('saveload-game {0:msg} name {1}', MSG_ARG(0), POP),
                    fstack('saveload-game {1} name {0}', POP_STR, POP),
                ),
                'SO_ROOM_PALETTE_IN_ROOM': fstack('palette {1} in-room {0}', *NPOP(2)),
                'SO_OBJECT_ORDER': fstack('object-order {1} {0}', *NPOP(2)),
                'SO_ROOM_COPY_PALETTE': fstack('palette {1} in-slot {0}', *NPOP(2)),
            }, {})

    })(op, stack)


@regop
def o8_roomOps(op, stack, game):
    return BUILD({
        'SO_ROOM_PALETTE': fstack('palette {3} {2} {1} in-slot {0}', *NPOP(4)),
        'SO_ROOM_FADE': fstack('fades {0}', POP),
        'SO_RGB_ROOM_INTENSITY': fstack('palette intensity {4} {3} {2} in-slot {1} to {0}', *NPOP(5)),
        'SO_ROOM_TRANSFORM': fstack('palette transform {3} in-slot {2} to {1} steps {0}', *NPOP(4)),
        'SO_ROOM_NEW_PALETTE': fstack('palette {0}', POP),
        'SO_ROOM_SAVE_GAME': fstack('save-game'),
        'SO_ROOM_LOAD_GAME': fstack('load-game'),
    })(op, stack)


@regop
def verbOps(op, stack, game):
    return BUILD({
        'SO_VERB_INIT': fstack('verb {0}', POP),
        'SO_VERB_IMAGE': fstack('\timage {0}', POP),
        'SO_VERB_NAME': GUARD(
            game.he_version < 72,
            fstack('\tname {0:msg}', MSG_ARG(0)),
            fstack('\tname {0}', POP_STR),
        ),
        'SO_VERB_COLOR': fstack('\tcolor {0}', POP),
        'SO_VERB_HICOLOR': fstack('\thicolor {0}', POP),
        'SO_VERB_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_VERB_ON': fstack('\ton'),
        'SO_VERB_OFF': fstack('\toff'),
        'SO_VERB_DELETE': fstack('\tdelete'),
        'SO_VERB_NEW': fstack('\tnew'),
        'SO_VERB_DIMCOLOR': fstack('\tdimcolor {0}', POP),
        'SO_VERB_DIM': fstack('\tdim'),
        'SO_VERB_KEY': fstack('\tkey {0}', POP),
        'SO_VERB_CENTER': fstack('\tcenter'),
        # 'SO_VERB_NAME_STR': fstack('\tname {0}', POP),
        'SO_VERB_IMAGE_IN_ROOM': fstack('\timage {1} in-room {0}', *NPOP(2)),
        'SO_VERB_BAKCOLOR': fstack('\tbakcolor {0}', POP),
        'SO_END': fstack('\t(end-verb)'),
        # V8
        'SO_VERB_LINE_SPACING': fstack('\tspacing {0}', POP),
    })(op, stack)


@regop
def o6_actorFollowCamera(op, stack, game):
    return f'camera-follow {stack.pop()}'


@regop
def o6_pickupObject(op, stack, game):
    if game.version < 7:
        room = stack.pop()
        obj = stack.pop()
        return f'pick-up-object {obj} in-room {room}'
    obj = stack.pop()
    return f'pick-up-object {obj}'


@regop
def o70_pickupObject(op, stack, game):
    room = stack.pop()
    obj = stack.pop()
    return f'pick-up-object {obj} in {room}'


@regop
def o6_getActorMoving(op, stack, game):
    stack.append(f'actor-moving {stack.pop()}')


@regop
def o6_getInventoryCount(op, stack, game):
    # might also be inventory-size {actor_name}
    stack.append(f'actor-inventory {stack.pop()}')


@regop
def o6_getOwner(op, stack, game):
    stack.append(f'owner-of {stack.pop()}')


@regop
def o6_setOwner(op, stack, game):
    act = stack.pop()
    obj = stack.pop()
    return f'owner-of {obj} is {act}'


@regop
def o6_faceActor(op, stack, game):
    obj = stack.pop()  # might be another actor
    act = stack.pop()
    return f'do-animation {act} face-towards {obj}'


@regop
def o6_setObjectName(op, stack, game):
    obj = stack.pop()
    return f'new-name-of {obj} is {msg_val(op.args[0])}'


@regop
def o72_printWizImage(op, stack, game):
    return f'print-image {stack.pop()}'


@regop
def o6_cursorCommand(op, stack, game):
    return BUILD({
        'SO_CURSOR_ON': fstack('cursor on'),
        'SO_CURSOR_OFF': fstack('cursor off'),
        'SO_USERPUT_ON': fstack('userput on'),
        'SO_USERPUT_OFF': fstack('userput off'),
        'SO_CURSOR_SOFT_ON': fstack('cursor soft-on'),
        'SO_CURSOR_SOFT_OFF': fstack('cursor soft-off'),
        'SO_USERPUT_SOFT_ON': fstack('userput soft-on'),
        'SO_USERPUT_SOFT_OFF': fstack('userput soft-off'),
        'SO_CURSOR_IMAGE': (
            # TODO: Figure out object?
            fstack('cursor {0}', POP)
            if game.he_version >= 70 or game.version >= 7
            # TODO: another pop for non HE or HE < 70 games
            else fstack('cursor {1} image {0}', *NPOP(2))
        ),
        'SO_CURSOR_HOTSPOT': fstack('cursor hotspot {1},{0}', *NPOP(2)),
        'SO_CHARSET_SET': fstack('charset {0}', POP),
        'SO_CHARSET_COLOR': fstack('charset color {0:csvargs}', POP_PARAMS),
        'SO_CURSOR_TRANSPARENT': (
            # > cursor transparent color
            # This command sets transparent colors in the cursor.
            # It can be called multiple times for multiple transparent colors.
            fstack('cursor transparent {0}', POP)
        ),
    })(op, stack)


@regop
def o80_cursorCommand(op, stack, game):
    return BUILD({
        'SO_CURSOR_ON': fstack('cursor on'),
        'SO_CURSOR_OFF': fstack('cursor off'),
        'SO_USERPUT_ON': fstack('userput on'),
        'SO_USERPUT_OFF': fstack('userput off'),
        'SO_CURSOR_SOFT_ON': fstack('cursor soft-on'),
        'SO_CURSOR_SOFT_OFF': fstack('cursor soft-off'),
        'SO_USERPUT_SOFT_ON': fstack('userput soft-on'),
        'SO_USERPUT_SOFT_OFF': fstack('userput soft-off'),
        # 'SO_CURSOR_IMAGE': fstack('cursor image {0}', POP),
        'SO_CURSOR_HOTSPOT': fstack('cursor hotspot {1},{0}', *NPOP(2)),
        'SO_CHARSET_SET': fstack('charset {0}', POP),
        'SO_CHARSET_COLOR': fstack('charset color {0:csvargs}', POP_PARAMS),
        'SO_CURSOR_IMAGE': fstack('cursor image {0}', POP),
        'SO_CURSOR_COLOR_IMAGE': fstack('cursor color image {0}', POP),
        'SO_BUTTON': fstack('button {1} image {0}', *NPOP(2)),
        'SO_CURSOR_COLOR_PAL_IMAGE': fstack('cursor color image {1} palette {0}', *NPOP(2)),
        'SO_CHARSET': fstack('charset {0}', POP),
    })(op, stack)


@regop
def o8_cursorCommand(op, stack, game):
    return BUILD({
        'SO_CURSOR_ON': fstack('cursor on'),
        'SO_CURSOR_OFF': fstack('cursor off'),
        'SO_CURSOR_SOFT_ON': fstack('cursor soft-on'),
        'SO_CURSOR_SOFT_OFF': fstack('cursor soft-off'),
        'SO_USERPUT_ON': fstack('userput on'),
        'SO_USERPUT_OFF': fstack('userput off'),
        'SO_USERPUT_SOFT_ON': fstack('userput soft-on'),
        'SO_USERPUT_SOFT_OFF': fstack('userput soft-off'),
        'SO_CURSOR_IMAGE': fstack('cursor {1} image {0}', *NPOP(2)),
        'SO_CURSOR_HOTSPOT': fstack('cursor hotspot {1},{0}', *NPOP(2)),
        # > cursor transparent color
        # This command sets transparent colors in the cursor.
        # It can be called multiple times for multiple transparent colors.
        'SO_CURSOR_TRANSPARENT': fstack('cursor transparent {0}', POP),
        'SO_CHARSET_SET': fstack('charset {0}', POP),
        'SO_CHARSET_COLOR': fstack('charset color {0:csvargs}', POP_PARAMS),
        'SO_CURSOR_PUT': fstack('put-cursor {1},{0}', *NPOP(2)),
    })(op, stack)


@regop
def actorOps(op, stack, game):
    return BUILD({
        'SO_COSTUME': fstack('\tcostume {0}', POP),
        'SO_STEP_DIST': fstack('\tstep-dist {1},{0}', *NPOP(2)),
        'SO_SOUND': fstack('\tsound [{0:csvargs}]', POP_PARAMS),
        'SO_WALK_ANIMATION': fstack('\twalk-animation {0}', POP),
        'SO_TALK_ANIMATION': fstack('\ttalk-animation {1} {0}', *NPOP(2)),
        'SO_STAND_ANIMATION': fstack('\tstand-animation {0}', POP),
        # # 'SO_ANIMATION': fstack('\tanimation {2} {1} {0}', *NPOP(3)),
        'SO_DEFAULT': fstack('\tdefault'),
        'SO_ELEVATION': fstack('\televation {0}', POP),
        'SO_ANIMATION_DEFAULT': fstack('\tanimation default'),
        'SO_PALETTE': fstack('\tcolor {1} is {0}', *NPOP(2)),
        'SO_TALK_COLOR': fstack('\ttalk-color {0}', POP),
        'SO_ACTOR_NAME': fstack('\tname {0:msg}', MSG_ARG(0)),
        'SO_INIT_ANIMATION': fstack('\tinit-animation {0}', POP),
        'SO_ACTOR_WIDTH': fstack('\twidth {0}', POP),
        'SO_SCALE': fstack('\tscale {0}', POP),
        'SO_NEVER_ZCLIP': fstack('\tnever-zclip'),
        'SO_ALWAYS_ZCLIP_FT_DEMO': fstack('\talways-zclip {0}', POP),
        'SO_ALWAYS_ZCLIP': fstack('\talways-zclip {0}', POP),
        'SO_IGNORE_BOXES': fstack('\tignore-boxes'),
        'SO_FOLLOW_BOXES': fstack('\tfollow-boxes'),
        'SO_SHADOW': fstack('\tshadow {0}', POP) if game.version < 8 else fstack('\tspecial-draw {0}', POP),
        'SO_TEXT_OFFSET': fstack('\ttext-offset {1},{0}', *NPOP(2)),
        'SO_ACTOR_INIT': fstack('actor {0}', POP),
        'SO_ACTOR_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
        'SO_ACTOR_IGNORE_TURNS_ON': fstack('\tignore-turns on'),
        'SO_ACTOR_IGNORE_TURNS_OFF': fstack('\tignore-turns off'),
        'SO_NEW': fstack('\tnew'),
        'SO_ACTOR_WALK_SCRIPT': fstack('\twalk-script {0}', POP),
        'SO_ACTOR_TALK_SCRIPT': fstack('\ttalk-script {0}', POP),
        'SO_ANIMATION_SPEED': fstack('\tanimation-speed {0}', POP),
        'SO_ACTOR_FACE': fstack('\tdirection {0}', POP),
        'SO_ACTOR_TURN': fstack('\tturn-to {0}', POP),
        'SO_ACTOR_WALK_PAUSE': fstack('\tstop-walk'),
        'SO_ACTOR_WALK_RESUME': fstack('\tresume-walk'),
        'SO_ACTOR_DEPTH': fstack('\tto-zplane {0}', POP),
        'SO_ACTOR_STOP': fstack('\tstop'),

        # Since HE60
        'SO_ACTOR_DEFAULT_CLIPPED': fstack('\tdefault-box {3},{2} to {1},{0}', *NPOP(4)),

        # Since HE72
        'SO_CONDITION': fstack('\tcondition {0:csvargs}', POP_PARAMS),
        'SO_TALK_CONDITION': fstack('\ttalk-condition {0}', POP),
        'SO_PRIORITY': fstack('\torder {0}', POP),
        'SO_TALKIE': (
            fstack('\ttalkie {1} {0}', POP_STR, POP) if game.he_version >= 72
            else fstack('\ttalkie {1} {0}', MSG_ARG(0), POP)
        ),
        'SO_BACKGROUND_ON': fstack('\tbak on'),
        # 'SO_BACKGROUND_OFF': fstack('\tbak off'),
        'SO_CHARSET_SET': fstack('\tcharset {0}', POP),

        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
        'SO_ERASE': fstack('\terase {0}', POP),

        # Since HE 90
        'SO_NEW_GENERAL_PROPERTY': fstack('\tproperty {1} is {0}', *NPOP(2)),

        # Since HE 100
        'SO_ACTOR_SOUNDS': fstack('\tsound {0:csvargs}', POP_PARAMS),
        'SO_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
        'SO_ROOM_PALETTE': fstack('\tpalette {0}', POP),
    })(op, stack)


@regop
def o8_actorOps(op, stack, game):
    return BUILD({
        'SO_ACTOR_INIT': fstack('actor {0}', POP),
        'SO_COSTUME': fstack('\tcostume {0}', POP),
        'SO_STEP_DIST': fstack('\tstep-dist {1},{0}', *NPOP(2)),
        # 'SO_ANIMATION_DEFAULT': fstack('\tanimation default'),
        'SO_INIT_ANIMATION': fstack('\tinit-animation {0}', POP),
        'SO_TALK_ANIMATION': fstack('\ttalk-animation {1} {0}', *NPOP(2)),
        'SO_WALK_ANIMATION': fstack('\twalk-animation {0}', POP),
        'SO_STAND_ANIMATION': fstack('\tstand-animation {0}', POP),
        # 'SO_ANIMATION_SPEED': fstack('\tanimation-speed {0}', POP),
        'SO_DEFAULT': fstack('\tdefault'),
        'SO_ELEVATION': fstack('\televation {0}', POP),
        'SO_PALETTE': fstack('\tcolor {1} is {0}', *NPOP(2)),
        'SO_TALK_COLOR': fstack('\ttalk-color {0}', POP),
        # 'SO_ACTOR_NAME': fstack('\tname {0:msg}', MSG_ARG(0)),
        # 'SO_ACTOR_WIDTH': fstack('\twidth {0}', POP),
        'SO_SCALE': fstack('\tscale {0}', POP),
        'SO_NEVER_ZCLIP': fstack('\tnever-zclip'),
        'SO_ALWAYS_ZCLIP': fstack('\talways-zclip {0}', POP),
        'SO_IGNORE_BOXES': fstack('\tignore-boxes'),
        'SO_FOLLOW_BOXES': fstack('\tfollow-boxes'),
        'SO_SHADOW': fstack('\tspecial-draw {0}', POP),
        'SO_TEXT_OFFSET': fstack('\ttext-offset {1},{0}', *NPOP(2)),
        'SO_ACTOR_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
        # 'SO_ACTOR_IGNORE_TURNS_ON': fstack('\tignore-turns on'),
        # 'SO_ACTOR_IGNORE_TURNS_OFF': fstack('\tignore-turns off'),
        # 'SO_NEW': fstack('\tnew'),
        'SO_ACTOR_DEPTH': fstack('\tto-zplane {0}', POP),
        'SO_ACTOR_STOP': fstack('\tstop'),
        'SO_ACTOR_FACE': fstack('\tdirection {0}', POP),
        'SO_ACTOR_TURN': fstack('\tturn-to {0}', POP),
        'SO_ACTOR_VOLUME': fstack('\tvolume {0}', POP),
        'SO_ACTOR_FREQUENCY': fstack('\tfrequency {0}', POP),
        'SO_ACTOR_PAN': fstack('\tpan {0}', POP),
    })(op, stack)


@regop
def o90_getLinesIntersectionPoint(op, stack, game):
    F_PUSH(
        fstack('find-segment-intersection {9},{8} ({7},{6} to {5},{4}), ({3},{2} to {1},{0})', *NPOP(8), SCRIPT_VAR(1), SCRIPT_VAR(0))
    )(op, stack)


@regop
def o6_getActorLayer(op, stack, game):
    F_PUSH(
        fstack('actor-zplane {0}', POP)
    )(op, stack)


@regop
def o90_setSpriteInfo(op, stack, game):
    return BUILD({
        'SO_STEP_DIST_X': fstack('\tstep-dist-x {0}', POP),
        'SO_STEP_DIST_Y': fstack('\tstep-dist-y {0}', POP),
        'SO_GROUP': fstack('\tgroup {0}', POP),
        'SO_INIT': fstack('sprite {1} to {0}', *NPOP(2)) if game.version > 98 else fstack('sprite {0}', POP),
        'SO_ANGLE': fstack('\tangle {0}', POP),
        'SO_ANIMATION': fstack('\tanimation {0}', POP),
        'SO_ANIMATION_SPEED': fstack('\tanimation-speed {0}', POP),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_AT_IMAGE': fstack('\tsource image {0}', POP),
        'SO_CLASS': fstack('\tclass [{0:csvargs}]', POP_PARAMS),
        'SO_ERASE': fstack('\terase {0}', POP),
        'SO_IMAGE': fstack('\timage {0}', POP),
        'SO_MASK': fstack('\tmask image {0}', POP),
        'SO_MOVE': fstack('\tmove {1},{0}', *NPOP(2)),
        'SO_NEW': fstack('\tnew'),
        'SO_NEW_GENERAL_PROPERTY': fstack('\tproperty {1} is {0}', *NPOP(2)),
        'SO_PALETTE': fstack('\tpalette {0}', POP),
        'SO_PRIORITY': fstack('\torder {0}', POP),
        'SO_PROPERTY': fstack('\tflag {1} is {0}', *NPOP(2)),
        'SO_RESTART': fstack('\trestart restart'),
        'SO_SCALE': fstack('\tscale {0}', POP),
        'SO_SHADOW': fstack('\tshadow {0}', POP),
        'SO_STATE': fstack('\tstate {0}', POP),
        'SO_STEP_DIST': fstack('\tstep-dist {1},{0}', *NPOP(2)),
        'SO_UPDATE': fstack('\tupdate-type {0}', POP),
        'SO_ACTOR_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
        'SO_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
    })(op, stack)


@regop
def o90_getSpriteInfo(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_XPOS': fstack('sprite {0} object-x', POP),
            'SO_YPOS': fstack('sprite {0} object-y', POP),
            'SO_WIDTH': fstack('sprite {0} width', POP),
            'SO_HEIGHT': fstack('sprite {0} height', POP),
            'SO_STEP_DIST_X': fstack('sprite {0} step-dist-x', POP),
            'SO_STEP_DIST_Y': fstack('sprite {0} step-dist-y', POP),
            'SO_COUNT': fstack('sprite {0} state-count', POP),
            'SO_GROUP': fstack('sprite {0} group', POP),
            'SO_DRAW_XPOS': fstack('sprite {0} object-draw-x', POP),
            'SO_DRAW_YPOS': fstack('sprite {0} object-draw-y', POP),
            'SO_PRIORITY': fstack('sprite {0} order', POP),
            'SO_FIND': PBUILD({
                0: fstack('find-sprite {3},{2} group {1} class [{0:csvargs}]', POP_PARAMS, *NPOP(3)),
                1: fstack('find-sprite rectangle {3},{2} group {1} class [{0:csvargs}]', POP_PARAMS, *NPOP(3)),
            }) if game.version >= 99 else PBUILD({
                0: fstack('find-sprite {2},{1} group {0}', *NPOP(3)),
                1: fstack('find-sprite rectangle {2},{1} group {0}', *NPOP(3)),
            }) if game.version >= 98 else fstack('find-sprite {2},{1} group {0}', *NPOP(3)),
            'SO_STATE': fstack('sprite {0} state', POP),
            'SO_IMAGE': fstack('sprite {0} image', POP),
            'SO_ANIMATION': fstack('sprite {0} animation-type', POP),
            'SO_PALETTE': fstack('sprite {0} palette', POP),
            'SO_UPDATE': fstack('sprite {0} update-type', POP),
            'SO_SCALE': fstack('sprite {0} scale', POP),
            'SO_CLASS': fstack('sprite {1} class [{0:csvargs}]', POP_PARAMS, POP),
            'SO_ACTOR_VARIABLE': (fstack('sprite {1} variable {0}', *NPOP(2)) if game.he_version < 100 else None),
            'SO_VARIABLE': (fstack('sprite {1} variable {0}', *NPOP(2)) if game.he_version >= 100 else None),

            'SO_MASK': fstack('sprite {0} mask image', POP),
            'SO_AT_IMAGE': fstack('sprite {0} source image', POP),
            'SO_NEW_GENERAL_PROPERTY': fstack('sprite {1} property {0}', *NPOP(2)),
            'SO_PROPERTY': PBUILD({
                0: fstack('sprite {0} hflip', POP),
                1: fstack('sprite {0} vflip', POP),
                # 2: fstack('sprite {0} show', POP),
                4: fstack('sprite {0} image remap', POP),
            }),
        })
    )(op, stack)


@regop
def o90_setSpriteGroupInfo(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('sprite group {0}', POP),
        'SO_GROUP': PBUILD({
            1: fstack('\tgroup move {1},{0}', *NPOP(2)),
            2: fstack('\tgroup order {0}', POP),
            3: fstack('\tgroup group {0}', POP),
            4: fstack('\tgroup update-type {0}', POP),
            5: fstack('\tgroup new'),
            # 6: fstack('\tgroup animation-speed {0}', POP),
            7: fstack('\tgroup animation-type {0}', POP),
            8: fstack('\tgroup shadow {0}', POP),
        }),
        'SO_NEW': fstack('\tnew'),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_MOVE': fstack('\tmove {1},{0}', *NPOP(2)),
        'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
        'SO_IMAGE': fstack('\timage {0}', POP),
        'SO_PRIORITY': fstack('\torder {0}', POP),
        'SO_PROPERTY': fstack('\tflag {1} is {0}', *NPOP(2)),
        'SO_NEVER_ZCLIP': fstack('\tnever-zclip'),
    })(op, stack)


@regop
def o90_getDistanceBetweenPoints(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_COORD_2D': fstack('line-length {3},{2} to {1},{0}', *NPOP(4)),
            'SO_COORD_3D': fstack('line-length {5},{4},{3} to {2},{1},{0}', *NPOP(6)),
        })
    )(op, stack)


@regop
def o90_getPolygonOverlap(op, stack, game):
    F_PUSH(
        fstack('overlap {2} ([{1:csvargs}],[{0:csvargs}])', POP_PARAMS, POP_PARAMS, POP)
    )(op, stack)


@regop
def o90_getSpriteGroupInfo(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_ARRAY': fstack('sprite group {0} sprite []', POP),
            'SO_PRIORITY': fstack('sprite group {0} order', POP),
            'SO_XPOS': fstack('sprite group {0} object-x', POP),
            'SO_YPOS': fstack('sprite group {0} object-y', POP),
        })
    )(op, stack)


@regop
def o80_drawLine(op, stack, game):
    return BUILD({
        'SO_ACTOR': fstack('draw-line {5},{4} to {3},{2} actor {1} step-dist {0}', *NPOP(6)),
        # 'SO_IMAGE': fstack('draw-line {5},{4} to {3},{2} image {1} step-dist {0}', *NPOP(6)),
        'SO_COLOR': fstack('draw-line {5},{4} to {3},{2} color {1} step-dist {0}', *NPOP(6)),
    })(op, stack)


@regop
def o90_floodFill(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('flood-fill'),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_COLOR': fstack('\tcolor {0}', POP),
        'SO_END': fstack('\t(end)'),
        'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
    })(op, stack)


@regop
def o6_getAnimateVariable(op, stack, game):
    var = stack.pop()
    act = stack.pop()
    stack.append(f'actor {act} variable {var}')


@regop
def o6_animateActor(op, stack, game):
    chore = stack.pop()
    act = stack.pop()
    return f'do-animation {act} {chore}'


@regop
def o80_readConfigFile(op, stack, game):
    cmd = op.args[0]
    option = pop_str(stack)
    section = pop_str(stack)
    filename = pop_str(stack)
    if cmd.name == 'SO_DWORD':
        stack.append(Caster(f'(read-ini {filename} {section} {option})', cast='number'))
        return
    if cmd.name == 'SO_STRING':
        stack.append(Caster(f'(read-ini string {filename} {section} {option})', cast='string'))
        return
    return defop(op, stack, game)


@regop
def o80_writeConfigFile(op, stack, game):
    return BUILD({
        'SO_DWORD': fstack('write-ini {3} {2} {1} is {0}', POP, POP_STR, POP_STR, POP_STR),
        'SO_STRING': fstack('write-ini string {3} {2} {1} is {0}', POP_STR, POP_STR, POP_STR, POP_STR),
    })


@regop
def o71_compareString(op, stack, game):
    F_PUSH(
        fstack('string-compare {1} {0}', *NPOP(2))
    )(op, stack)


@regop
def o8_getObjectImageX(op, stack, game):
    F_PUSH(
        fstack('object-image-x {0}', POP),
    )(op, stack)


@regop
def o8_getObjectImageY(op, stack, game):
    F_PUSH(
        fstack('object-image-y {0}', POP),
    )(op, stack)


@regop
def o8_getObjectImageHeight(op, stack, game):
    F_PUSH(
        fstack('object-image-height {0}', POP),
    )(op, stack)


@regop
def o8_getObjectImageWidth(op, stack, game):
    F_PUSH(
        fstack('object-image-width {0}', POP),
    )(op, stack)


@regop
def o72_getNumFreeArrays(op, stack, game):
    stack.append('free-arrays')


@regop
def o72_getObjectImageX(op, stack, game):
    stack.append(f'object-image-x {stack.pop()}')


@regop
def o72_getObjectImageY(op, stack, game):
    stack.append(f'object-image-y {stack.pop()}')


@regop
def o6_getObjectX(op, stack, game):
    stack.append(f'object-x {stack.pop()}')


@regop
def o6_getObjectY(op, stack, game):
    stack.append(f'object-y {stack.pop()}')


@regop
def o90_getObjectData(op, stack, game):
    F_PUSH(BUILD({
        # Hack to get the object when reading the second subop
        'SO_INIT': POP,
        'SO_DRAW_YPOS': fstack('object {0} object-draw-y', POP),
        'SO_DRAW_XPOS': fstack('object {0} object-draw-x', POP),
        'SO_STATE': fstack('object {0} state', POP),
        'SO_WIDTH': fstack('object {0} width', POP),
        'SO_HEIGHT': fstack('object {0} height', POP),
        # 'SO_STATE_COUNT': fstack('object {0} state-count'),
        # 'SO_NEW_GENERAL_PROPERTY': fstack('object {1} property {0}', *NPOP(2)),  # TODO: verify order is correct
    }))(op, stack)


@regop
def o6_stampObject(op, stack, game):
    return fstack('stamp-object {3} at {2},{1} image {0}', *NPOP(4))


@regop
def o60_redimArray(op, stack, game):
    return BUILD({
        'SO_BYTE': fstack('redim byte array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_INT': fstack('redim int array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
    })(op, stack)


@regop
def o72_redimArray(op, stack, game):
    return BUILD({
        'SO_BYTE': fstack('redim byte array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_INT': fstack('redim int array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'SO_DWORD': fstack('redim dword array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
    })(op, stack)


@regop
def o72_drawWizImage(op, stack, game):
    F_PUSH(
        fstack('draw-image {3} at {2},{1} {0}', *NPOP(4)),
    )(op, stack)


@regop
def o72_captureWizImage(op, stack, game):
    return fstack('capture-image {4} at {3},{2} to {1},{0}', *NPOP(5))(op, stack)


@regop
def o90_wizImageOps(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('image {0}', POP),
        'SO_WIDTH': fstack('\twidth {0}', POP),
        'SO_HEIGHT': fstack('\theight {0}', POP),
        'SO_DRAW': fstack('\tdraw'),
        'SO_LOAD': fstack('\tload {0}', POP_STR),
        'SO_CAPTURE': fstack('\tcapture {4} at {3},{2} to {1},{0}', *NPOP(5)),
        'SO_STATE': fstack('\tstate {0}', POP),
        'SO_SET_FLAGS': fstack('\tset-flags {0}', POP),
        'SO_NOW': fstack('draw-image {4} at {3},{2} state {1} {0}', *NPOP(5)),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_AT_IMAGE': fstack('\tsource image {0}', POP),
        'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
        'SO_COLOR': (fstack('\tcolor {1} to {0}', *NPOP(2)) if game.he_version <= 98 else None),
        'SO_COLOR_LIST': (fstack('\tcolor {1} to {0}', *NPOP(2)) if game.he_version >= 98 else None),  # HE 98+
        'SO_NEW': fstack('\tnew'),
        'SO_PALETTE':  fstack('\tpalette {0}', POP),
        'SO_POLY_TO_POLY': fstack('\tcapture {2} from polygon {1} to polygon {0}', *NPOP(3)),
        'SO_SAVE': fstack('\tsave {1} {0}', POP_STR, POP),
        'SO_SCALE': fstack('\tscale {0}', POP),
        'SO_END': fstack('\t(end-wiz)'),
        'SO_FONT_CREATE': fstack('\tfont-create font {4} style {3} size {2} foreground {1} background {0}', *NPOP(4), POP_STR),
        'SO_FONT_END': fstack('\tfont-end'),
        'SO_FONT_RENDER': fstack('\tfont-render {2} at {1},{0}', *NPOP(2), POP_STR),
        'SO_FONT_START': fstack('\tfont-start'),
        'SO_RENDER_FLOOD_FILL': fstack('\tflood-fill {2},{1} color {0}', *NPOP(3)),
        'SO_RENDER_INTO_IMAGE': fstack('\timage {0}', POP),
        'SO_RENDER_RECTANGLE': fstack('\tdraw-box {4},{3} to {2},{1} color {0}', *NPOP(5)),
        'SO_CURSOR_HOTSPOT': fstack('\thotspot {1},{0}', *NPOP(2)),
        'SO_HISTOGRAM': fstack('\thotspot {1},{0}', *NPOP(2)),  # SO_CURSOR_HOTSPOT
        'SO_RENDER_LINE': fstack('\tdraw-line {4},{3} to {2},{1} color {0}', *NPOP(5)),
        'SO_SET_POLYGON': fstack('\tpolygon {0}', POP),
        'SO_SHADOW': fstack('\tshadow {0}', POP),
        'SO_ANGLE': fstack('\tangle {0}', POP),
        'SO_NEW_GENERAL_PROPERTY': fstack('\tproperty {1} is {0}', *NPOP(2)),
        'SO_RENDER_ELLIPSE': fstack('\tdraw-ellipse {7},{6} to {5},{4} at {3},{2} steps {1} color {0}', *NPOP(8)),
    })(op, stack)


@regop
def o90_getPaletteData(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_COLOR': fstack('palette {1} slot {0} color', *NPOP(2)),
            'SO_NEW': fstack('rgb {2},{1},{0}', *NPOP(3)),
            'SO_STATE': fstack('palette {2} slot {1} channel {0}', *NPOP(3)),
            # HE 100
            'SO_CHANNEL': fstack('rgb {1} channel {0}', *NPOP(2)),
        }),
    )(op, stack)


@regop
def o90_paletteOps(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('new palette {0}', POP),
        'SO_COLOR': fstack('\tslot {4} to {3} rgb {2},{1},{0}', *NPOP(5)),
        'SO_COSTUME': fstack('\tfrom costume {0}', POP),
        'SO_PALETTE': fstack('\tfrom palette {0}', POP),
        'SO_TO': fstack('\tslot {2} to {1} color {0}', *NPOP(3)),
        'SO_IMAGE': fstack('\tfrom image {1} state {0}', *NPOP(2)),
        'SO_NEW': fstack('\tnew'),
        'SO_END': fstack('\t(end)'),
    })(op, stack)


@regop
def o6_delayFrames(op, stack, game):
    return fstack('break-here {0} times', POP)(op, stack)


@regop
def o6_delayMinutes(op, stack, game):
    return fstack('sleep-for {0} minutes', POP)(op, stack)


@regop
def o6_delay(op, stack, game):
    return fstack('sleep-for {0} jiffies', POP)(op, stack)


@regop
def o6_delaySeconds(op, stack, game):
    return fstack('sleep-for {0} seconds', POP)(op, stack)


@regop
def o6_wait(op, stack, game):
    return BUILD({
        'SO_WAIT_FOR_ACTOR': fstack('wait-for-actor {0} ; [ref {1}]', POP, REF_ARG(0)),
        'SO_WAIT_FOR_MESSAGE': fstack('wait-for-message'),
        'SO_WAIT_FOR_CAMERA': fstack('wait-for-camera'),
        'SO_WAIT_FOR_SENTENCE': fstack('wait-for-sentence'),

        # not for HE
        'SO_WAIT_FOR_ANIMATION': fstack('wait-for-animation {0} ; [ref {1}]', POP, REF_ARG(0)),
        'SO_WAIT_FOR_TURN': fstack('wait-for-turn {0} ; [ref {1}]', POP, REF_ARG(0)),
    })(op, stack)


@regop
def o8_wait(op, stack, game):
    return BUILD({
        'SO_WAIT_FOR_ACTOR': fstack('wait-for-actor {0} ; [ref {1}]', POP, REF_ARG(0)),
        'SO_WAIT_FOR_MESSAGE': fstack('wait-for-message'),
        'SO_WAIT_FOR_CAMERA': fstack('wait-for-camera'),
        'SO_WAIT_FOR_ANIMATION': fstack('wait-for-animation {0} ; [ref {1}]', POP, REF_ARG(0)),
    })(op, stack)


@regop
def o80_sourceDebug(op, stack, game):
    return fstack('source-debug {1} {0}', ARG(0), ARG(1))(op, stack)


@regop
def o8_cameraOps(op, stack, game):
    return BUILD({
        'SO_CAMERA_PAUSE': fstack('camera pause'),
        'SO_CAMERA_RESUME': fstack('camera resume'),
    })(op, stack)


@regop
def o6_pseudoRoom(op, stack, game):
    params = get_params(stack)
    room = stack.pop()
    return f'pseudo-room {room} is {params}'


@regop
def o72_setTimer(op, stack, game):
    return BUILD({
        'SO_RESTART': fstack('timer {0} restart', POP),
    })(op, stack)


@regop
def o6_wordVarInc(op, stack, game):
    return fstack('++{0}', SCRIPT_VAR(0))(op, stack)


@regop
def o6_wordVarDec(op, stack, game):
    return fstack('--{0}', SCRIPT_VAR(0))(op, stack)


@regop
def o90_cond(op, stack, game):
    a = stack.pop()
    b = stack.pop()
    c = stack.pop()
    stack.append(f'{c} ? {b} : {a}')


@regop
def o6_wordArrayInc(op, stack, game):
    var = get_var(op.args[0])
    return f'++{var}[{stack.pop()}]'


@regop
def o6_wordArrayDec(op, stack, game):
    var = get_var(op.args[0])
    return f'--{var}[{stack.pop()}]'


@regop
def o6_breakHere(op, stack, game):
    return 'break-here'


@regop
def o72_getTimer(op, stack, game):
    F_PUSH(BUILD({
        'SO_MSECONDS': fstack('timer {0}', POP),
    }))(op, stack)


@regop
def o6_isActorInBox(op, stack, game):
    box = stack.pop()
    actor = stack.pop()
    stack.append(f'{actor} in-box {box}')


@regop
def o6_createBoxMatrix(op, stack, game):
    return 'set-box-path'


@regop
def o6_systemOps(op, stack, game):
    return BUILD({
        'SO_RESTART': fstack('restart'),
        'SO_PAUSE': fstack('pause'),
        'SO_QUIT': fstack('quit'),
    })(op, stack)


@regop
def o8_systemOps(op, stack, game):
    return BUILD({
        'SO_RESTART': fstack('restart'),
        'SO_QUIT': fstack('quit'),
    })(op, stack)


@regop
def o70_systemOps(op, stack, game):
    return BUILD({
        'SO_RESTART': fstack('restart'),
        'SO_QUIT': fstack('quit'),
        'SO_QUIT_QUIT': fstack('quit quit'),
        'SO_RESTART_STRING': fstack('restart {0:msg}', MSG_ARG(0)),
    })(op, stack)


@regop
def o72_systemOps(op, stack, game):
    return BUILD({
        'SO_RESTART': fstack('restart'),
        'SO_QUIT': fstack('quit'),
        'SO_QUIT_QUIT': fstack('quit quit'),
        'SO_RESTART_STRING': fstack('restart {0}', POP_STR),
        'SO_FLUSH_OBJECT_DRAW_QUE': fstack('flush-object-draw-que'),
        'SO_UPDATE_SCREEN': fstack('update-screen'),
    })(op, stack)


@regop
def o6_saveRestoreVerbs(op, stack, game):
    return BUILD({
        # 'SO_SAVE_VERBS': fstack('save-verbs {2} to {1} set {0}', *NPOP(3)),
        'SO_SAVE_VERBS': fstack('verbs-save {2} to {1} set {0}', *NPOP(3)),
        # 'SO_RESTORE_VERBS': fstack('restore-verbs {2} to {1} set {0}', *NPOP(3)),
        'SO_RESTORE_VERBS': fstack('verbs-restore {2} to {1} set {0}', *NPOP(3)),
        # 'SO_DELETE_VERBS': fstack('delete-verbs {2} to {1} set {0}', *NPOP(3)),
        # 'SO_DELETE_VERBS': fstack('verbs-delete {2} to {1} set {0}', *NPOP(3)),
    })(op, stack)


@regop
def o70_setSystemMessage(op, stack, game):
    return BUILD({
        'SO_TITLE_BAR': fstack('title-bar {0:msg}', MSG_ARG(0)),
        'SO_PAUSE_TITLE': fstack('pause-title {0:msg}', MSG_ARG(0)),
    })(op, stack)


@regop
def o72_setSystemMessage(op, stack, game):
    return BUILD({
        'SO_TITLE_BAR': fstack('title-bar {0}', POP_STR),
        'SO_PAUSE_TITLE': fstack('pause-title {0}', POP_STR),
    })(op, stack)


@regop
def o6_resourceRoutines(op, stack, game):
    return BUILD({
        'SO_LOAD_SCRIPT': fstack('load-script {0}', POP),
        'SO_LOAD_SOUND': fstack('load-sound {0}', POP),
        'SO_LOAD_COSTUME': fstack('load-costume {0}', POP),
        'SO_LOAD_ROOM': fstack('load-room {0}', POP),
        'SO_NUKE_SCRIPT': fstack('nuke-script {0}', POP),
        'SO_NUKE_SOUND': fstack('nuke-sound {0}', POP),
        'SO_NUKE_COSTUME': fstack('nuke-costume {0}', POP),
        'SO_NUKE_ROOM': fstack('nuke-room {0}', POP),
        'SO_LOCK_SCRIPT': fstack('lock-script {0}', POP),
        'SO_LOCK_SOUND': fstack('lock-sound {0}', POP),
        'SO_LOCK_COSTUME': fstack('lock-costume {0}', POP),
        'SO_LOCK_ROOM': fstack('lock-room {0}', POP),
        'SO_UNLOCK_SCRIPT': fstack('unlock-script {0}', POP),
        'SO_UNLOCK_SOUND': fstack('unlock-sound {0}', POP),
        'SO_UNLOCK_COSTUME': fstack('unlock-costume {0}', POP),
        'SO_UNLOCK_ROOM': fstack('unlock-room {0}', POP),
        'SO_LOAD_CHARSET': fstack('load-charset {0}', POP),
        'SO_LOAD_OBJECT': (
            fstack('load-object {1} in-room {0}', *NPOP(2))
            if game.version < 7
            else fstack('load-object {0}', POP)
        ),
    })(op, stack)


@regop
def o8_resourceRoutines(op, stack, game):
    return BUILD({
        # 'SO_HEAP_LOAD_CHARSET': fstack('load-charset {0}', POP),
        'SO_HEAP_LOAD_COSTUME': fstack('load-costume {0}', POP),
        'SO_HEAP_LOAD_OBJECT': fstack('load-object {0}', POP),
        'SO_HEAP_LOAD_ROOM': fstack('load-room {0}', POP),
        'SO_HEAP_LOAD_SCRIPT': fstack('load-script {0}', POP),
        'SO_HEAP_LOAD_SOUND': fstack('load-sound {0}', POP),
        'SO_HEAP_LOCK_COSTUME': fstack('lock-costume {0}', POP),
        'SO_HEAP_LOCK_ROOM': fstack('lock-room {0}', POP),
        'SO_HEAP_LOCK_SCRIPT': fstack('lock-script {0}', POP),
        'SO_HEAP_LOCK_SOUND': fstack('lock-sound {0}', POP),
        'SO_HEAP_UNLOCK_COSTUME': fstack('unlock-costume {0}', POP),
        'SO_HEAP_UNLOCK_ROOM': fstack('unlock-room {0}', POP),
        'SO_HEAP_UNLOCK_SCRIPT': fstack('unlock-script {0}', POP),
        'SO_HEAP_UNLOCK_SOUND': fstack('unlock-sound {0}', POP),
        'SO_HEAP_NUKE_COSTUME': fstack('nuke-costume {0}', POP),
        'SO_HEAP_NUKE_ROOM': fstack('nuke-room {0}', POP),
        'SO_HEAP_NUKE_SCRIPT': fstack('nuke-script {0}', POP),
        'SO_HEAP_NUKE_SOUND': fstack('nuke-sound {0}', POP),
    })(op, stack)


@regop
def o72_findObjectWithClassOf(op, stack, game):
    F_PUSH(
        fstack('find-object {2},{1} class [{0:csvargs}]', POP_PARAMS, *NPOP(2)),
    )(op, stack)


@regop
def o70_resourceRoutines(op, stack, game):
    return BUILD({
        'SO_LOAD_SCRIPT': fstack('load-script {0}', POP),
        'SO_LOAD_SOUND': fstack('load-sound {0}', POP),
        'SO_LOAD_COSTUME': fstack('load-costume {0}', POP),
        'SO_LOAD_ROOM': fstack('load-room {0}', POP),
        # 'SO_NUKE_SCRIPT': fstack('nuke-script {0}', POP),
        'SO_NUKE_SOUND': fstack('nuke-sound {0}', POP),
        'SO_NUKE_COSTUME': fstack('nuke-costume {0}', POP),
        'SO_NUKE_ROOM': fstack('nuke-room {0}', POP),
        'SO_LOCK_SCRIPT': fstack('lock-script {0}', POP),
        'SO_LOCK_SOUND': fstack('lock-sound {0}', POP),
        'SO_LOCK_COSTUME': fstack('lock-costume {0}', POP),
        'SO_LOCK_ROOM': fstack('lock-room {0}', POP),
        'SO_UNLOCK_SCRIPT': fstack('unlock-script {0}', POP),
        'SO_UNLOCK_SOUND': fstack('unlock-sound {0}', POP),
        'SO_UNLOCK_COSTUME': fstack('unlock-costume {0}', POP),
        'SO_UNLOCK_ROOM': fstack('unlock-room {0}', POP),
        'SO_CLEAR_HEAP': fstack('clear-heap'),
        'SO_LOAD_CHARSET': fstack('load-charset {0}', POP),
        'SO_LOAD_OBJECT': fstack('load-object {0}', POP),
        'SO_PRELOAD_SCRIPT': fstack('preload-script {0}', POP),
        'SO_PRELOAD_SOUND': fstack('preload-sound {0}', POP),
        'SO_PRELOAD_COSTUME': fstack('preload-costume {0}', POP),
        'SO_PRELOAD_ROOM': fstack('preload-room {0}', POP),
        'SO_UNLOCK_IMAGE': fstack('unlock-image {0}', POP),
        'SO_NUKE_IMAGE': fstack('nuke-image {0}', POP),
        'SO_LOAD_IMAGE': fstack('load-image {0}', POP),
        'SO_LOCK_IMAGE': fstack('lock-image {0}', POP),
        'SO_PRELOAD_IMAGE': fstack('preload-image {0}', POP),
        'SO_LOCK_FLOBJECT': fstack('lock-flobject {0}', POP),
        'SO_UNLOCK_FLOBJECT': fstack('unlock-flobject {0}', POP),
        'SO_PRELOAD_FLUSH': fstack('preload flush'),
        'SO_NUKE_CHARSET': fstack('nuke-charset {0}', POP),
    })(op, stack)


@regop
def o100_resourceRoutines(op, stack, game):
    return BUILD({
        'SO_CHARSET': fstack('charset {0}', POP),
        'SO_COSTUME': fstack('costume {0}', POP),
        'SO_OBJECT': fstack('object {0}', POP),
        'SO_IMAGE': fstack('image {0}', POP),
        'SO_LOAD': fstack('\tload'),
        'SO_ROOM': fstack('room {0}', POP),
        'SO_SCRIPT': fstack('script {0}', POP),
        'SO_SOUND': fstack('sound {0}', POP),
        'SO_CLEAR_HEAP': fstack('clear-heap'),
        'SO_PRELOAD_FLUSH': fstack('preload flush'),
        'SO_LOCK': fstack('\tlock'),
        'SO_NUKE': fstack('\tnuke'),
        'SO_PRELOAD': fstack('\tpreload'),
        'SO_UNLOCK': fstack('\tunlock'),
        'SO_FLOBJECT': fstack('flobject {0}', POP),
        'SO_OFF_HEAP': fstack('off-heap'),
        'SO_ON_HEAP': fstack('on-heap'),
    })(op, stack)


@regop
def o6_loadRoom(op, stack, game):
    return f'current-room {stack.pop()}'


@regop
def o6_getDateTime(op, stack, game):
    stack.append('get-time-date')


@regop
def o6_getRandomNumber(op, stack, game):
    stack.append(f'random {stack.pop()}')


@regop
def o6_getRandomNumberRange(op, stack, game):
    upper = stack.pop()
    lower = stack.pop()
    stack.append(Caster(f'random-between {lower} to {upper}', cast='number'))


@regop
def o70_getStringLen(op, stack, game):
    stack.append(f'string-length {stack.pop()}')


@regop
def o6_wordArrayWrite(op, stack, game):
    return fstack('{0}[{2}] = {1}', SCRIPT_VAR(0), *NPOP(2))(op, stack)


@regop
def o6_pickVarRandom(op, stack, game):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    var = get_var(op.args[0])
    stack.append(f'pick {var} random [ {param_str} ]')


@regop
def o80_pickVarRandom(op, stack, game):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    var = get_var(op.args[0])
    stack.append(f'pick {var} random [ {param_str} ]')


@regop
def o6_pickOneOf(op, stack, game):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    value = stack.pop()
    stack.append(f'pick ({value}) of [ {param_str} ]')


@regop
def o6_pickOneOfDefault(op, stack, game):
    default = stack.pop()
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    value = stack.pop()
    stack.append(f'pick ({value}) of [ {param_str} ] default {default}')


@regop
def o6_shuffle(op, stack, game):
    return fstack('array-shuffle {0}[{2}] to {0}[{1}]', SCRIPT_VAR(0), *NPOP(2))(op, stack)


@regop
def o72_getResourceSize(op, stack, game):
    F_PUSH(
        fstack('sound-size {0}', POP),
    )(op, stack)


@regop
def o73_getResourceSize(op, stack, game):  # o72_getResourceSize
    F_PUSH(
        BUILD({
            'SO_IMAGE_SIZE': fstack('image-size {0}', POP),
            'SO_COSTUME_SIZE': fstack('costume-size {0}', POP),
            'SO_SOUND_SIZE': fstack('sound-size {0}', POP),
        })
    )(op, stack)


@regop
def o100_getResourceSize(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_IMAGE': fstack('image-size {0}', POP),
            'SO_COSTUME': fstack('costume-size {0}', POP),
            'SO_SOUND': fstack('sound-size {0}', POP),
        })
    )(op, stack)


@regop
def o6_setClass(op, stack, game):
    params = get_params(stack)
    obj = stack.pop()
    return f'class-of {obj} is {" ".join(str(param) for param in params)}'


@regop
def o6_ifClassOfIs(op, stack, game):
    params = get_params(stack)
    obj = stack.pop()
    stack.append(f'class-of {obj} is {" ".join(str(param) for param in params)}')


@regop
def o6_stopTalking(op, stack, game):
    return 'stop-talking'


@regop
def o6_getVerbEntrypoint(op, stack, game):
    verb = stack.pop()
    obj = stack.pop()
    stack.append(f'valid-verb {obj} {verb}')


@regop
def o6_getObjectOldDir(op, stack, game):
    obj = stack.pop()
    stack.append(f'actor-facing {obj}')


@regop
def o6_getObjectNewDir(op, stack, game):
    obj = stack.pop()
    stack.append(f'actor-facing {obj}')


@regop
def o70_getActorRoom(op, stack, game):
    stack.append(f'actor-room {stack.pop()}')


@regop
def o8_getActorChore(op, stack, game):
    stack.append(f'actor-chore {stack.pop()}')


@regop
def o8_getActorZPlane(op, stack, game):
    stack.append(f'actor-zplane {stack.pop()}')


@regop
def o6_getPixel(op, stack, game):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'pixel {xpos}, {ypos}')


@regop
def o72_getPixel(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_BACKGROUND_ON': fstack('pixel background {1},{0}', *NPOP(2)),
            'SO_BACKGROUND_OFF': fstack('pixel {1},{0}', *NPOP(2)),
        })
    )(op, stack)


@regop
def o71_polygonHit(op, stack, game):
    F_PUSH(
        fstack('find-polygon {1}, {0}', *NPOP(2)),
    )(op, stack)


@regop
def o60_closeFile(op, stack, game):
    return f'close-file {stack.pop()}'


@regop
def o60_openFile(op, stack, game):
    modes = {
        1: 'read',
        2: 'write',
        6: 'append',
    }
    mode = modes[stack.pop().num]
    string = op.args[0]
    stack.append(f'open-file {msg_val(string)} for {mode}')


@regop
def o72_openFile(op, stack, game):
    modes = {
        1: 'read',
        2: 'write',
        3: '$debug-output',
        6: 'append',
    }
    mode = modes[stack.pop().num]
    string = pop_str(stack)
    stack.append(f'open-file {string} for {mode}')


@regop
def o60_writeFile(op, stack, game):
    size = stack.pop()
    res = stack.pop()
    slot = stack.pop()
    return f'write-file {slot} size {size} value {res}'


@regop
def o72_writeFile(op, stack, game):
    return BUILD({
        'SO_BYTE': fstack('write-file {1} byte {0}', *NPOP(2)),
        'SO_INT': fstack('write-file {1} int {0}', *NPOP(2)),
        'SO_DWORD': fstack('write-file {1} dword {0}', *NPOP(2)),
        'SO_ARRAY': fstack('write-file {1} byte array {0}', *NPOP(2)),
    })(op, stack)


@regop
def o72_readFile(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_BYTE': fstack('read-file {0} byte', POP),
            'SO_INT': fstack('read-file {0} int', POP),
            'SO_DWORD': fstack('read-file {0} dword', POP),
            'SO_ARRAY': fstack('read-file {1} byte array [{0}]', *NPOP(2)),
        })
    )(op, stack)


@regop
def o60_readFile(op, stack, game):
    size = stack.pop()
    slot = stack.pop()
    stack.append(f'read-file {slot} size {size}')


@regop
def o60_seekFilePos(op, stack, game):
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
def o60_readFilePos(op, stack, game):
    slot = stack.pop()
    stack.append(f'read-file {slot} position')


@regop
def o71_appendString(op, stack, game):
    F_PUSH(
        fstack('string-copy {2} from {1} to {0}', *NPOP(3)),
    )(op, stack)


@regop
def o71_copyString(op, stack, game):
    F_PUSH(fstack('string-copy {0}', POP))(op, stack)


@regop
def o71_concatString(op, stack, game):
    F_PUSH(
        fstack('string-copy {1} add {0}', *NPOP(2)),
    )(op, stack)


@regop
def o80_stringToInt(op, stack, game):
    string = stack.pop()
    stack.append(Caster(f'string-number {string}', cast='number'))


@regop
def o6_findAllObjects(op, stack, game):
    stack.append(f'find-all-objects {stack.pop()}')


@regop
def o72_findAllObjects(op, stack, game):
    stack.append(f'find-all-objects {stack.pop()}')


@regop
def o90_findAllObjectsWithClassOf(op, stack, game):
    F_PUSH(
        fstack('find-all-objects {1} class [{0:csvargs}]', POP_PARAMS, POP),
    )(op, stack)


@regop
def o6_putActorAtXY(op, stack, game):
    room = stack.pop()
    ypos = stack.pop()
    xpos = stack.pop()
    act = stack.pop()
    room = '' if room == 0 else f' in-room {room}'
    return f'put-actor {act} at {xpos},{ypos}{room}'


@regop
def o6_putActorAtObject(op, stack, game):
    room = stack.pop() if game.version < 7 else 0  # NOTE: 0 is valid also for <7
    obj = stack.pop()
    act = stack.pop()
    room = '' if room == 0 else f' in-room {room}'
    return f'put-actor {act} at-object {obj}{room}'


@regop
def o71_getCharIndexInString(op, stack, game):
    value = stack.pop()
    value.cast = 'char'
    end = stack.pop()
    pos = stack.pop()
    arr = stack.pop()
    stack.append(f'string-search {arr} from {pos} to {end} for {value}')


@regop
def o6_panCameraTo(op, stack, game):
    # # TODO: v7 uses 2 pops, x y
    # if game.version >= 7:
    #     return fstack('camera-pan-to {1},{0}', *NPOP(2))(op, stack)
    return fstack('camera-pan-to {0}', POP)(op, stack)


@regop
def o6_startObjectQuick(op, stack, game):
    params = get_params(stack)
    param_str = ', '.join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    entry = stack.pop()
    scr = stack.pop()
    stack.append(f'start-object rec {scr} verb {entry}{param_str}')


@regop
def o6_stopSentence(op, stack, game):
    return 'stop-sentence'


@regop
def o72_getArrayDimSize(op, stack, game):
    sub = Value(op.args[0], signed=False)
    arr = get_var(op.args[1])
    if sub.num == 1:
        stack.append(f'dim {arr} [?]')
        return
    if sub.num == 2:
        stack.append(f'dim {arr} [?][]')
        return
    if sub.num == 3:
        stack.append(f'dim {arr} [][?]')
        return
    if sub.num == 4:
        # stack.append(f'dim {arr} [? to]')
        stack.append(f'dim {arr} [][? to]')
        return
    if sub.num == 5:
        # stack.append(f'dim {arr} [to ?]')
        stack.append(f'dim {arr} [][to ?]')
        return
    if sub.num == 6:
        stack.append(f'dim {arr} [? to][]')
        return
    if sub.num == 7:
        stack.append(f'dim {arr} [to ?][]')
        return
    return defop(op, stack, game)


@regop
def o80_getSoundVar(op, stack, game):
    F_PUSH(
        fstack('sound {1} variable {0}', *NPOP(2)),
    )(op, stack)


@regop
def o80_createSound(op, stack, game):
    return BUILD({
        'SO_SOUND_ADD': fstack('\tadd {0}', POP),
        'SO_NEW': fstack('\tnew'),
        'SO_SOUND_START': fstack('create-sound {0}', POP),
        'SO_END': fstack('\t(end-create-sound)'),
        # HE 100
        'SO_INIT': fstack('create-sound {0}', POP),
    })(op, stack)


@regop
def o6_getActorCostume(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-costume {act}')


@regop
def o6_getActorWidth(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-width {act}')


@regop
def o6_getActorElevation(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-elevation {act}')


@regop
def o6_getActorRoom(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-room {act}')


@regop
def o6_getActorAnimCounter(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-chore {act}')


@regop
def o6_getActorScaleX(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-scale {act}')


@regop
def o6_getActorWalkBox(op, stack, game):
    act = stack.pop()
    stack.append(f'actor-box {act}')


@regop
def o90_getActorData(op, stack, game):
    which = stack.pop()
    val = stack.pop()
    act = stack.pop()
    stack.append(f'actor-data {act} {val} {which}')


@regop
def o60_localizeArrayToScript(op, stack, game):
    return f'localize {stack.pop()}'


@regop
def o80_localizeArrayToRoom(op, stack, game):
    return f'room localize {stack.pop()}'


@regop
def o6_freezeUnfreeze(op, stack, game):
    scr = stack.pop()
    if scr.num == 0:
        return 'unfreeze-scripts'
    return f'freeze-scripts {scr}'


@regop
def o8_startVideo(op, stack, game):
    return f'start-video {msg_val(op.args[0])}'


@regop
def o71_polygonOps(op, stack, game):
    return BUILD({
        'SO_SET_POLYGON': fstack('set-polygon {8} at {7},{6} to {5},{4} to {3},{2} to {1},{0}', *NPOP(9)),
        'SO_SET_POLYGON_LOCAL': fstack('set-polygon {8} at {7},{6} to {5},{4} to {3},{2} to {1},{0} local', *NPOP(9)),
        'SO_DELETE_POLYGON': fstack('delete-polygon {1} to {0}', *NPOP(2)),
    })(op, stack)


@regop
def o100_debugInput(op, stack, game):
    return BUILD({
        'SO_INIT': fstack('s_debug = debug-input {0}', POP_STR),
        'SO_COUNT': fstack('\tsize {0}', POP),
        'SO_DEFAULT': fstack('\tdefault', POP_STR),
        'SO_TITLE_BAR': fstack('\ttitle-bar', POP_STR),
        'SO_END': F_PUSH(fstack('s_debug')),
    })(op, stack)


@regop
def o6_drawObject(op, stack, game):
    return fstack('draw-object {1} image {0}', *NPOP(2))(op, stack)


@regop
def o6_drawObjectAt(op, stack, game):
    return fstack('draw-object {2} at {1},{0}', *NPOP(3))(op, stack)


@regop
def o72_drawObject(op, stack, game):
    return BUILD({
        'SO_AT_IMAGE': fstack('draw-object {3} at {2},{1} image {0}', *NPOP(4)),
        'SO_IMAGE': fstack('draw-object {1} image {0}', *NPOP(2)),
        'SO_AT': fstack('draw-object {2} at {1},{0}', *NPOP(3)),
    })(op, stack)


@regop
def o6_setState(op, stack, game):
    state = stack.pop()
    obj = stack.pop()
    return f'state-of {obj} is {state}'


@regop
def o80_setState(op, stack, game):
    state = stack.pop()
    obj = stack.pop()
    return f'state-of {obj} is {state}'


@regop
def o60_setState(op, stack, game):
    state = stack.pop()
    obj = stack.pop()
    return f'state-of {obj} is {state}'


@regop
def o6_getState(op, stack, game):
    obj = stack.pop()
    stack.append(f'state-of {obj}')


@regop
def o72_getSoundPosition(op, stack, game):
    F_PUSH(
        fstack('sound-position {0}', POP),
    )(op, stack)


@regop
def o6_getObjectY(op, stack, game):
    obj = stack.pop()
    stack.append(f'object-y {obj}')


@regop
def o90_sortArray(op, stack, game):
    return BUILD({
        'SO_SORT': PBUILD({
            -1: fstack('array {0} sort < [{4} to {3}] [{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            1: fstack('array {0} sort > [{4} to {3}] [{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        }),
    })(op, stack)


@regop
def o90_getWizData(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_XPOS': fstack('image {1} state {0} object-x', *NPOP(2)),
            'SO_YPOS': fstack('image {1} state {0} object-y', *NPOP(2)),
            'SO_WIDTH': fstack('image {1} state {0} width', *NPOP(2)),
            'SO_HEIGHT': fstack('image {1} state {0} height', *NPOP(2)),
            'SO_COUNT': fstack('image {0} state-count', POP),
            'SO_FIND': fstack('image {3} state {2} pixel {1},{0}', *NPOP(4)),
            'SO_COLOR': fstack('image {3} state {2} color {1},{0}', *NPOP(4)),
            'SO_NEW_GENERAL_PROPERTY': fstack('image {1} property {0}', *NPOP(2)),
            'SO_FONT_START': fstack('image {2} text-extent {1} property {0}', POP, POP_STR, POP),
            'SO_HISTOGRAM': fstack('image {5} state {4} histogram clip {3},{2} to {1},{0}', *NPOP(6)),
        })
    )(op, stack)


@regop
def o90_fontEnum(op, stack, game):
    F_PUSH(
        BUILD({
            'SO_INIT': fstack('font-enumerate enum-start'),
            'SO_PROPERTY': PBUILD({
                1: fstack('font-enumerate get {0}', POP),  # FONT_ENUM_GET
                2: fstack('font-enumerate find {0}', POP_STR),  # FONT_ENUM_FIND
            })
        })
    )(op, stack)


@regop
def o80_drawWizPolygon(op, stack, game):
    return fstack('draw-image {1} polygon {0}', *NPOP(2))(op, stack)


@regop
def o6_walkActorTo(op, stack, game):
    # walk actor-name to x-coord,y-coord
    # walk actor-name to actor-name within number
    # walk actor-name to-object object-name
    ypos = stack.pop()
    xpos = stack.pop()
    act = stack.pop()
    return f'walk {act} to {xpos},{ypos}'


@regop
def o6_walkActorToObj(op, stack, game):
    dist = stack.pop()
    obj = stack.pop()
    act = stack.pop()
    return f'walk {act} to-object {obj} within {dist}'


@regop
def o6_distObjectObject(op, stack, game):
    another = stack.pop()
    obj = stack.pop()
    stack.append(f'proximity {obj} {another}')


@regop
def o6_distPtPt(op, stack, game):
    y2, x2 = stack.pop(), stack.pop()
    y1, x1 = stack.pop(), stack.pop()
    stack.append(f'proximity {x1},{y1} to {x2},{y2}')


@regop
def o6_setCameraAt(op, stack, game):
    # ypos = stack.pop()  # v7+
    xpos = stack.pop()
    return f'camera-at {xpos}'


def get_element_by_path(path: str, root: Iterable[Element]) -> Element | None:
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


def break_lines(asts):
    for _, seq in asts.items():
        stats = iter(list(seq))
        seq.clear()
        last_line = []
        for st in stats:
            if last_line:
                if not (isinstance(st, str) and st.startswith('\t')):
                    if len(last_line) > 1:
                        assert all(isinstance(part, str) for part in last_line), repr(
                            last_line,
                        )
                        term = last_line.pop() + '\n'
                        last_line = [x + ' \\' for x in last_line] + [term]
                    seq.extend(last_line)
                    last_line.clear()
            last_line.append(st)
        if last_line:
            if len(last_line) > 1:
                assert all(isinstance(part, str) for part in last_line), repr(last_line)
                term = last_line.pop() + '\n'
                last_line = [x + ' \\' for x in last_line] + [term]
            seq.extend(last_line)
    return asts


def transform_asts(indent, asts, transform=True):
    asts = break_lines(asts)

    if not transform:
        return asts

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
            deps[label].append(blocks[idx + 1][0])
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
                (ex,) = exits
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
                            # NOTE: Commented these out because it causes problems
                            # when trying to decompile the HE v71 games.
                            # (Unsure if this is needed for Lucas v6 games or not.)
                            # if step == '++' and f'{var} > ' in str(cond.expr):
                            #     asts[label].pop()  # cond
                            #     asts[label].pop()  # adv
                            #     end = str(cond.expr).replace(f'{var} > ', '')
                            # elif step == '--' and f'{var} < ' in str(cond.expr):
                            #     asts[label].pop()  # cond
                            #     asts[label].pop()  # adv
                            #     end = str(cond.expr).replace(f'{var} < ', '')
                            if end and last_label is not None and asts[last_label]:
                                assert last_label == list(deps)[idx - 1]
                                init = str(asts[last_label].pop())
                                if f'{var} = ' in init:
                                    ext, fall = exits
                                    assert ext == ex
                                    asts[last_label].append(
                                        f'for {init} to {end} {step} {{',
                                    )
                                    asts[last_label].extend(
                                        f'\t{st}' for st in asts[label]
                                    )
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
                        if [str(st) for st in asts[label]] == [
                            'break-here',
                        ] and isinstance(ex, ConditionalJump):
                            asts[label].clear()
                            asts[label].append(f'break-until ({ex.expr})')
                        # elif len(asts[label]) == 2 and isinstance(asts[label][0], ConditionalNotJump) and asts[label][1] == 'break-here':
                        #     expr = asts[label][0].expr
                        #     asts[label].clear()
                        #     asts[label].append(f'break-while !({expr})')
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
                        deps[lb] = [
                            f'_{label}' if str(ex) == label else ex for ex in deps[lb]
                        ]
                    asts = {
                        f'_{label}' if label == lbl else lbl: block
                        for lbl, block in asts.items()
                    }
                    deps = {
                        f'_{label}' if label == lbl else lbl: block
                        for lbl, block in deps.items()
                    }

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
            entry = int.from_bytes(stream.read(2), byteorder='little', signed=False)
            yield key, entry - len(meta)


def make_block_context(elem, gid):
    respath_comment = f'; {elem.tag} {elem.attribs["path"]}'
    titles = {
        'LSC2': 'script',
        'LSCR': 'script',
        'SCRP': 'script',
        'ENCD': 'enter',
        'EXCD': 'exit',
        'OBCD': 'object',
    }
    gid_str = '' if gid is None else f' {gid}'
    yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])
    if elem.tag == 'OBCD':
        yield ' '.join(['\tname is', f'"{obj_names[gid]}"'])


def get_elem_info(game, elem):
    obcd = None
    gid = elem.attribs['gid']
    script_map = get_script_map(game)
    if elem.tag == 'OBCD':
        obcd = elem
        elem = sputm.find('VERB', obcd)
    pref, script_data = script_map[elem.tag](elem.data)
    entries = {}
    if elem.tag == 'VERB':
        obj_names[gid] = msg_to_print(
            bytes(sputm.find('OBNA', obcd).data).split(b'\0', maxsplit=1)[0]
        )
        pref = list(parse_verb_meta(pref))
        entries = {off: idx[0] for idx, off in pref}
    else:
        scr_id = (
            int.from_bytes(pref, byteorder='little', signed=False) if pref else None
        )
        assert scr_id is None or scr_id == gid
    return script_data, gid, entries


def decompile_script(elem, game, verbose=False, transform=True):
    script_data, gid, entries = get_elem_info(game, elem)
    yield from make_block_context(elem, gid)
    optable = get_optable(game)
    indent = '\t'
    # print('====================')
    bytecode = descumm_iter(script_data, optable, base_offset=8)
    # from nutcracker.sputm.script.bytecode import print_bytecode
    # bytecode = dict(bytecode)
    # print_bytecode(bytecode)
    # bytecode = iter(bytecode.items())


    hrefs = set()
    srefs = {0}
    stack = deque(
        # ['**ERROR**'] * 3
    )
    asts = deque()
    res = None

    # # clear local variables:
    # for key in g_vars:  # NOTE: dict key is tuple, we iterates on keys only
    #     _, var = key
    #     if str(var).startswith('L.'):
    #         del g_vars[key]
    g_vars.clear()

    while True:
        try:
            off, stat = next(bytecode)
        except StopIteration:
            break
        except BytecodeParseError as exc:
            raise BytecodeError(
                exc,
                elem.attribs['path'],
                dict(realize_refs(srefs, hrefs, asts)),
            )
        hrefs.update(roff.abs for roff in get_argtype(stat.args, RefOffset))
        if elem.tag == 'OBCD' and off + 8 in entries:
            if off + 8 > min(entries.keys()):
                yield from print_locals(indent)
            l_vars.clear()
            yield from print_asts(
                indent,
                transform_asts(
                    indent,
                    dict(realize_refs(srefs, hrefs, asts)),
                    transform=transform,
                ),
            )
            srefs = {off}
            hrefs = {ref for ref in hrefs if ref >= off}
            asts = deque()
            if off + 8 > min(entries.keys()):
                yield '\t}'
                l_vars.clear()
            yield ''  # new line
            yield f'\tverb {entries[off + 8]} {{'
            indent = 2 * '\t'
            stack.clear()
        if verbose:
            yield ' '.join(
                [
                    f'[{stat.offset + 8:08d}]',
                    '\t\t\t\t\t\t\t\t',
                    f'{stat} <{list(stack)}>',
                ],
            )
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            srefs.add(off)
        stack_backup = list(stack)
        try:
            res = ops.get(stat.name, defop)(stat, stack, game)
        except Exception as exc:
            raise ScriptError(
                exc,
                elem.attribs['path'],
                dict(realize_refs(srefs, hrefs, asts)),
                stat,
                stack_backup,
            ) from exc
        if res:
            asts.append((off, res))
            # print(
            #     # f'[{stat.offset + 8:08d}]',
            #     f'{indent}{res}',
            #     # res,
            #     # '\t\t\t\t',
            #     # defop(stat, stack, bytecode),
            # )
    yield from print_locals(indent)
    l_vars.clear()
    yield from print_asts(
        indent,
        transform_asts(
            indent,
            dict(realize_refs(srefs, hrefs, asts)),
            transform=transform,
        ),
    )
    if elem.tag == 'OBCD' and entries:
        yield '\t}'
    yield '}'


obj_names = {}

if __name__ == '__main__':
    import argparse

    from nutcracker.sputm.tree import open_game_resource
    from nutcracker.sputm.windex.scu import dump_script_file

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
            SCHEMA,
            {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map},
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

            decompile = functools.partial(
                decompile_script,
                game=gameres.game,
                verbose=args.verbose,
            )
            with open(fname, 'w') as f:
                dump_script_file(room_no, room, decompile, f)
