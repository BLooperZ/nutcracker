import functools
import io
import operator
import os
from collections import OrderedDict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nutcracker.kernel2.element import Element
from nutcracker.sputm.preset import sputm
from nutcracker.sputm.schema import SCHEMA
from nutcracker.sputm.script.bytecode import (
    BytecodeParseError,
    descumm_iter,
    get_argtype,
)
from nutcracker.sputm.script.opcodes import ByteValue, RefOffset, WordValue
from nutcracker.sputm.script.parser import CString, DWordValue, ScriptArg, Statement
from nutcracker.sputm.script.shared import BytecodeError, ScriptError, msg_to_print, msg_val, realize_refs
from nutcracker.sputm.strings import (
    RAW_ENCODING,
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
        assert b'\xff' not in self.orig.msg, self.orig.msg
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


def get_var(orig: 'ScriptArg | Dup') -> Variable:
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
        if isinstance(self.orig, Value):
            self.orig.cast = self.cast
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
            or (isinstance(left, BinExpr) and left.pre >= self.pre and left.op != self.op)
        ):
            left = f'({left})'
        right = self.right
        if (
            isinstance(right, str)
            or isinstance(right, Negate)
            or (isinstance(right, BinExpr) and right.pre >= self.pre and right.op != self.op)
        ):
            right = f'({right})'
        return f'{left} {self.op} {right}'


class Negate:
    def __init__(self, op):
        self.op = op

    def __repr__(self):
        return f'!{PrintArg(self.op)}'


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


def push_str(stack, msg):
    ops['_strings'].append(msg)


def pop_str(stack) -> Any:
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


def fstack(pattern: str, *args: Any, **kwargs: Any) -> 'Callable[[Statement, deque[Any]], str]':
    def inner(op: 'Statement', stack: deque[Any]) -> str:
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
        if format_spec == 'inline':
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


def POP(op: Statement, stack: deque[Any]) -> Any:
    return stack.pop()


def NPOP(num: int) -> Sequence[Callable[[Statement, deque[Any]], Any]]:
    return num * [POP]


def POP_STR(op: Statement, stack: deque[Any]) -> Any:
    return pop_str(stack)


def MSG_ARG(num: int) -> Callable[[Statement, deque[Any]], CString]:
    def inner(op: Statement, stack: deque[Any]) -> CString:
        cstr = op.args[num]
        assert isinstance(cstr, CString), op.args
        return cstr

    return inner


def BYTE_ARG(num: int) -> Callable[[Statement, deque[Any]], Value]:
    def inner(op: Statement, stack: deque[Any]) -> Value:
        assert isinstance(op.args[num], ByteValue), op.args
        return Value(op.args[num], signed=False)

    return inner


def WORD_ARG(num: int) -> Callable[[Statement, deque[Any]], Value]:
    def inner(op: Statement, stack: deque[Any]) -> Value:
        assert isinstance(op.args[num], (WordValue, DWordValue)), op.args
        return Value(op.args[num])

    return inner


def DWORD_ARG(num: int) -> Callable[[Statement, deque[Any]], Value]:
    def inner(op: Statement, stack: deque[Any]) -> Value:
        assert isinstance(op.args[num], DWordValue), op.args
        return Value(op.args[num])

    return inner


def BYTE_VAR(num: int) -> Callable[[Statement, deque[Any]], Variable]:
    def inner(op: Statement, stack: deque[Any]) -> Variable:
        assert isinstance(op.args[num], ByteValue), op.args
        return get_var(op.args[num])

    return inner


def SCRIPT_VAR(num: int) -> Callable[[Statement, deque[Any]], Variable]:
    def inner(op: Statement, stack: deque[Any]) -> Variable:
        assert isinstance(op.args[num], (WordValue, DWordValue)), op.args
        return get_var(op.args[num])

    return inner


def REF_ARG(num: int) -> Callable[[Statement, deque[Any]], str]:
    def inner(op: Statement, stack: deque[Any]) -> str:
        off = op.args[num]
        assert isinstance(off, RefOffset), op.args
        return adr(off)

    return inner


def POP_PARAMS(op, stack):
    return get_params(stack)


def BUILD(
    mapping: 'Mapping[str, Callable[[Statement, deque[Any]], Any]]',
) -> 'Callable[[Statement, deque[Any]], Any]':
    def inner(op: 'Statement', stack: deque[Any]) -> Any:
        assert len(op.args), op.args
        subop, *rest = op.args
        assert not rest, rest
        assert isinstance(subop, Statement), subop
        return mapping[subop.name](subop, stack)

    return inner


def F_PUSH(
    func: 'Callable[[Statement, deque[Any]], Any]',
) -> 'Callable[[Statement, deque[Any]], None]':
    def inner(op: 'Statement', stack: deque[Any]) -> None:
        stack.append(func(op, stack))

    return inner


def PBUILD(
    getter: Callable[[Statement, deque[Any]], Any],
) -> 'Callable[..., Callable[[Statement, deque[Any]], Any]]':
    def inner(
        mapping: 'Mapping[int, Callable[[Statement, deque[Any]], Any]]',
        fallback: Callable[[Statement, deque[Any]], Any] | None = None,
    ) -> 'Callable[[Statement, deque[Any]], Any]':
        def inner2(op: 'Statement', stack: deque[Any]) -> Any:
            sub = getter(op, stack)
            res = mapping.get(sub.num)
            if res is not None:
                return res(op, stack)
            if fallback is None:
                raise KeyError(sub.num)
            stack.append(sub)
            return fallback(op, stack)

        return inner2

    return inner


def GUARD(condtion: bool) -> Callable[..., Any]:
    def inner(option: Any, fallback: Any = None) -> Any:
        if condtion:
            return option
        return fallback or {}

    return inner


## OPCODES


def CAST(
    cast: str, func: 'Callable[[Statement, deque[Any]], Any]'
) -> 'Callable[[Statement, deque[Any]], Caster]':
    def inner(op: Statement, stack: deque[Any]) -> Caster:
        return Caster(func(op, stack), cast=cast)

    return inner


@dataclass(frozen=True)
class GameVersion:
    version: int
    he_version: int


def PRINTER(action: str, *args: Any, game: GameVersion) -> 'Callable[[Statement, deque[Any]], Any]':
    return BUILD({
        'SO_BASEOP': fstack(action, *args),
        'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
        'SO_CLIPPED': fstack('\tclipped {0}', POP),
        'SO_CENTER': fstack('\tcenter'),
        'SO_LEFT': fstack('\tleft'),
        'SO_OVERHEAD': fstack('\toverhead'),
        'SO_MUMBLE': fstack('\tmumble'),
        'SO_TEXTSTRING': fstack('\t{0:msg}', MSG_ARG(0)),
        'SO_FORMATTED_STRING': fstack('\t{0:msg} {2}{1:psvargs}', MSG_ARG(0), POP_PARAMS, POP),
        'SO_TALKIE': fstack('\ttalkie {0}', POP),
        **GUARD(game.he_version < 72)(
            {
                'SO_COLOR': fstack('\tcolor {0}', POP),
                'SO_COLOR_LIST': fstack('\tcolors {0:csvargs}', POP_PARAMS)
            },
            {'SO_COLOR_LIST': fstack('\tcolor {0:csvargs}', POP_PARAMS)},
        ),
        'SO_END': fstack('\tend'),
        **GUARD(game.version >= 8)({
            'SO_PRINT_CHARSET': fstack('\tcharset {0}', POP),
            'SO_PRINT_WRAP': fstack('\twrap'),
        }),
    })


@functools.cache
def get_ops(
    game: GameVersion,
) -> 'Mapping[str, Callable[[Statement, deque[Any]], str | None]]':
    fallback_ops = {
        key: functools.partial(opf, game=game) for key, opf in ops.items() if not key.startswith('_')
    }
    lec_ops = {
        'o6_pushByte': F_PUSH(BYTE_ARG(0)),
        'o6_pushWord': F_PUSH(WORD_ARG(0)),
        'o72_pushDWord': F_PUSH(DWORD_ARG(0)),
        # 'o6_pushByteVar': F_PUSH(BYTE_VAR(0)),
        'o6_pushWordVar': F_PUSH(SCRIPT_VAR(0)),
        'o6_wordVarInc': fstack('++{0}', SCRIPT_VAR(0)),
        'o6_wordVarDec': fstack('--{0}', SCRIPT_VAR(0)),
        'o6_wordArrayInc': fstack('++{1}[{0}]', POP, WORD_ARG(0)),
        'o6_wordArrayDec': fstack('--{1}[{0}]', POP, WORD_ARG(0)),
        'o6_wordArrayWrite': fstack('{0}[{2}] = {1}', SCRIPT_VAR(0), *NPOP(2)),
        'o6_wordArrayIndexedWrite': fstack('{0}[{3}][{2}] = {1}', SCRIPT_VAR(0), *NPOP(3)),
        'o6_drawBox': fstack('draw-box {4},{3} to {2},{1} color {0}', *NPOP(5)),
        'o6_setBoxFlags': fstack('set-box {1:svargs} to {0}', POP, POP_PARAMS),
        'o6_setBoxSet': fstack('set-box-set {0}', POP),
        'o6_loadRoomWithEgo': GUARD(game.version < 7)(
            fstack('come-out-door {3} in-room {2} walk {1},{0}', *NPOP(4)),
            fstack('come-out-door {2} walk {1},{0}', *NPOP(3)),
        ),
        'startObject': GUARD(game.he_version < 72)(
            fstack('start-object {3:sflags} {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(3)),
            # # o72_startObject
            BUILD({
                'SO_NONE': fstack('start-object {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
                # 'SO_BAK': fstack('start-object bak {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
                'SO_REC': fstack('start-object rec {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
                # 'SO_BAK_REC': fstack('start-object bak rec {2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            }),
        ),
        'startScript': GUARD(game.he_version < 72)(
            fstack('start-script {2:sflags}{1:script}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # # o72_startScript
            BUILD({
                'SO_NONE': fstack('start-script {1}{0:pvargs}', POP_PARAMS, POP),
                'SO_BAK': fstack('start-script bak {1}{0:pvargs}', POP_PARAMS, POP),
                'SO_REC': fstack('start-script rec {1}{0:pvargs}', POP_PARAMS, POP),
                # 'SO_BAK_REC': fstack('start-script bak rec {1}{0:pvargs}', POP_PARAMS, POP),
            }),
        ),
        'o6_startObjectQuick': F_PUSH(fstack('@{2} verb {1}{0:pvargs}', POP_PARAMS, *NPOP(2))),
        'o6_startScriptQuick': fstack('@{1}{0:pvargs}', POP_PARAMS, POP),
        'o6_startScriptQuick2': F_PUSH(fstack('@{1}{0:pvargs}', POP_PARAMS, POP)),
        'jumpToScript': GUARD(game.he_version < 72)(
            fstack('chain-script {2:sflags} {1:script}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # # o72_jumpToScript
            BUILD({
                'SO_NONE': fstack('chain-script {1}{0:pvargs}', POP_PARAMS, POP),
                # 'SO_BAK': fstack('chain-script bak {1}{0:pvargs}', POP_PARAMS, POP),
                'SO_REC': fstack('chain-script rec {1}{0:pvargs}', POP_PARAMS, POP),
                # 'SO_BAK_REC': fstack('chain-script bak rec {1}{0:pvargs}', POP_PARAMS, POP),
            }),
        ),
        'o6_stopObjectScript': fstack('stop-object {0}', POP),
        'o6_stopScript': fstack('stop-script {0}', POP),
        'arrayOps': BUILD({
            'SO_ASSIGN_INT_LIST': fstack('{0}[{1:hzero}] = [{2:csvargs}]', SCRIPT_VAR(0), POP, POP_PARAMS),
            **GUARD(game.he_version < 72)(
                {
                    'SO_ASSIGN_STRING': fstack('{2}[{1:hzero}] = {0:msg}', MSG_ARG(1), POP, SCRIPT_VAR(0)),
                    'SO_ASSIGN_2DIM_LIST': fstack(
                        '{0}[{3}][{1:hzero}] = [{2:csvargs}]', SCRIPT_VAR(0), POP, POP_PARAMS, POP
                    ),
                },
                {
                    'SO_STRING': fstack('{1}[] = {0}', POP_STR, SCRIPT_VAR(0)),
                    'SO_ASSIGN_2DIM_LIST': fstack(
                        '{0}[{2}][] = [{1:csvargs}]', SCRIPT_VAR(0), POP_PARAMS, POP
                    ),
                    'SO_COMPLEX_ARRAY_ASSIGNMENT': fstack(
                        '{0}[{5} to {4}][{3} to {2}] = [{1:csvargs}]', SCRIPT_VAR(0), POP_PARAMS, *NPOP(4)
                    ),
                    'SO_COMPLEX_ARRAY_COPY_OPERATION': fstack(
                        '{0}[{9} to {8}][{7} to {6}] = {1}[{5} to {4}][{3} to {2}]',
                        SCRIPT_VAR(0),
                        SCRIPT_VAR(1),
                        *NPOP(8),
                    ),
                    'SO_RANGE_ARRAY_ASSIGNMENT': fstack(
                        '{0}[{6} to {5}][{4} to {3}] = ({2} to {1})', SCRIPT_VAR(0), *NPOP(6)
                    ),
                    'SO_COMPLEX_ARRAY_MATH_OPERATION': fstack(
                        '{0}[{15} to {14}][{13} to {12}] := ({1}[{11} to {10}][{9} to {8}] {3:operation} {2}[{7} to {6}][{5} to {4}])',
                        SCRIPT_VAR(0),
                        SCRIPT_VAR(1),
                        SCRIPT_VAR(2),
                        *NPOP(13),
                    ),
                    'SO_FORMATTED_STRING': fstack(
                        '{0} = {3} {2}{1:psvargs}', SCRIPT_VAR(0), POP_PARAMS, POP, POP_STR
                    ),
                },
            ),
        }),
        'o6_stopObjectCodeReturn': fstack('return {0}', POP),
        'o6_stopObjectCodeObject': fstack('end-object'),
        'o6_stopObjectCodeScript': fstack('end-script'),
        'o6_printDebug': PRINTER('print-debug', game=game),
        'o6_printText': PRINTER('print-text', game=game),
        'o6_printLine': PRINTER('print-line', game=game),
        'o6_printSystem': PRINTER('print-system', game=game),
        'o6_printEgo': PRINTER('say-line', game=game),
        'o6_printActor': PRINTER('say-line {0}', POP, game=game),
        'o6_talkEgo': fstack('say-line {0:msg}', MSG_ARG(0)),
        'o6_talkActor': fstack('say-line {1} {0:msg}', MSG_ARG(0), POP),
        'o6_setBlastObjectWindow': fstack('set-blastport {3},{2} to {1},{0}', *NPOP(4)),
        **GUARD(game.version < 8)(
            {'o6_doSentence': fstack('do-sentence {3} {2} {1} {0}', *NPOP(4))},
            {'o8_doSentence': fstack('do-sentence {2} {1} with {0}', *NPOP(3))},
        ),
        'kernelSetFunctions': fstack('kludge {0:svargs}', POP_PARAMS),
        'kernelGetFunctions': F_PUSH(fstack('kludge {0:svargs}', POP_PARAMS)),
        'o6_breakHere': fstack('break-here'),
        'o6_delayFrames': fstack('break-here {0} times', POP),
        'o6_delay': fstack('sleep-for {0} jiffies', POP),
        'o6_delaySeconds': fstack('sleep-for {0} seconds', POP),
        'o6_delayMinutes': fstack('sleep-for {0} minutes', POP),
        'o6_wait': BUILD({
            'SO_WAIT_FOR_ACTOR': fstack('wait-for-actor {0} ; [ref {1}]', POP, REF_ARG(0)),
            'SO_WAIT_FOR_MESSAGE': fstack('wait-for-message'),
            'SO_WAIT_FOR_CAMERA': fstack('wait-for-camera'),
            'SO_WAIT_FOR_SENTENCE': fstack('wait-for-sentence'),
            **GUARD(game.version >= 7)({
                'SO_WAIT_FOR_ANIMATION': fstack('wait-for-animation {0} ; [ref {1}]', POP, REF_ARG(0)),
                'SO_WAIT_FOR_TURN': fstack('wait-for-turn {0} ; [ref {1}]', POP, REF_ARG(0)),
            }),
        }),
        **GUARD(game.he_version < 72)(
            {
                'o6_drawObject': fstack('draw-object {1} image {0}', *NPOP(2)),
                'o6_drawObjectAt': fstack('draw-object {2} at {1},{0}', *NPOP(3)),
            },
            {
                'o72_drawObject': BUILD({
                    'SO_AT_IMAGE': fstack('draw-object {3} at {2},{1} image {0}', *NPOP(4)),
                    'SO_IMAGE': fstack('draw-object {1} image {0}', *NPOP(2)),
                    'SO_AT': fstack('draw-object {2} at {1},{0}', *NPOP(3)),
                }),
            },
        ),
        'o6_getActorLayer': F_PUSH(fstack('actor-zplane {0}', POP)),
        'o6_distPtPt': F_PUSH(fstack('proximity {3},{2} to {1},{0}', *NPOP(4))),
        'o6_cutscene': fstack('cut-scene ({0:svargs})', POP_PARAMS),
        'o6_endCutscene': fstack('end-cut-scene'),
        'o6_beginOverride': fstack('override'),
        'o6_endOverride': fstack('override off'),
        'dimArray': BUILD({
            'SO_UNDIM_ARRAY': fstack('undim {0}', SCRIPT_VAR(0)),
            'SO_INT': fstack('dim int array {0}[{1}]', SCRIPT_VAR(0), POP),
            'SO_BIT': fstack('dim bit array {0}[{1}]', SCRIPT_VAR(0), POP),
            'SO_NIBBLE': fstack('dim nibble array {0}[{1}]', SCRIPT_VAR(0), POP),
            'SO_BYTE': fstack('dim byte array {0}[{1}]', SCRIPT_VAR(0), POP),
            'SO_DWORD': fstack('dim dword array {0}[{1}]', SCRIPT_VAR(0), POP),
            'SO_STRING': fstack('dim string array {0}[{1}]', SCRIPT_VAR(0), POP),
        }),
        'dim2dimArray': BUILD({
            'SO_INT': fstack('dim int array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            'SO_BIT': fstack('dim bit array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            'SO_NIBBLE': fstack('dim nibble array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            'SO_BYTE': fstack('dim byte array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            'SO_DWORD': fstack('dim dword array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            'SO_STRING': fstack('dim string array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
        }),
        'o6_soundKludge': fstack('sound {0:svargs}', POP_PARAMS),
        'o6_startSound': GUARD(game.he_version >= 70)(
            fstack('start-sound {1} offset {0}', *NPOP(2)),
            fstack('start-sound {0}', POP),
        ),
        'o6_getActorFromXY': F_PUSH(fstack('find-actor {1},{0}', *NPOP(2))),
        'o6_findObject': F_PUSH(fstack('find-object {1},{0}', *NPOP(2))),
        'o6_findAllObjects': F_PUSH(fstack('find-all-objects {0}', POP)),
        'o6_findInventory': F_PUSH(fstack('find-inventory {1},{0}', *NPOP(2))),
        'o6_stopSound': fstack('stop-sound {0}', POP),
        'o6_isSoundRunning': F_PUSH(fstack('sound-running {0}', POP)),
        'o6_isScriptRunning': F_PUSH(fstack('script-running {0}', POP)),
        'o6_isRoomScriptRunning': F_PUSH(fstack('object-running {0}', POP)),
        'o6_roomOps': BUILD({
            'SO_ROOM_SCROLL': fstack('room-scroll is {1} {0}', *NPOP(2)),
            'SO_ROOM_SCREEN': fstack('set-screen {1} to {0}', *NPOP(2)),
            'SO_ROOM_PALETTE': fstack('palette {3} {2} {1} in-slot {0}', *NPOP(4)),
            'SO_ROOM_SHAKE_ON': fstack('shake on'),
            'SO_ROOM_SHAKE_OFF': fstack('shake off'),
            'SO_ROOM_INTENSITY': fstack('palette intensity {2} in-slot {1} to {0}', *NPOP(3)),
            **GUARD(game.version < 8)(
                {'SO_ROOM_SAVEGAME': fstack('saveload-game {1} in-slot {0}', *NPOP(2))},
                {
                    'SO_ROOM_SAVE_GAME': fstack('save-game'),
                    'SO_ROOM_LOAD_GAME': fstack('load-game'),
                },
            ),
            'SO_ROOM_FADE': fstack('fades {0}', POP),
            'SO_RGB_ROOM_INTENSITY': fstack('palette intensity {4} {3} {2} in-slot {1} to {0}', *NPOP(5)),
            'SO_ROOM_TRANSFORM': fstack('palette transform {3} in-slot {2} to {1} steps {0}', *NPOP(4)),
            'SO_CYCLE_SPEED': fstack('palette cycle-speed {1} is {0}', *NPOP(2)),
            'SO_ROOM_NEW_PALETTE': (
                # windex show empty string here
                fstack('palette {0}', POP)
            ),
            **GUARD(game.he_version >= 60)({
                'SO_ROOM_SAVEGAME_BY_NAME': GUARD(game.he_version < 72)(
                    fstack('saveload-game {0:msg} name {1}', MSG_ARG(0), POP),
                    fstack('saveload-game {1} name {0}', POP_STR, POP),
                ),
                'SO_ROOM_PALETTE_IN_ROOM': fstack('palette {1} in-room {0}', *NPOP(2)),
                'SO_OBJECT_ORDER': fstack('object-order {1} {0}', *NPOP(2)),
                'SO_ROOM_COPY_PALETTE': fstack('palette {1} in-slot {0}', *NPOP(2)),
            }),
        }),
        'o6_getVerbEntrypoint': F_PUSH(fstack('valid-verb {1} {0}', *NPOP(2))),
        **GUARD(game.he_version < 80)({
            'verbOps': BUILD({
                'SO_VERB_INIT': fstack('verb {0}', POP),
                'SO_VERB_IMAGE': fstack('\timage {0}', POP),
                'SO_VERB_NAME': GUARD(game.he_version < 72)(
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
                **GUARD(game.version >= 8)({
                    'SO_VERB_LINE_SPACING': fstack('\tspacing {0}', POP),
                }),
            }),
            'o6_getVerbFromXY': F_PUSH(fstack('find-verb {1},{0}', *NPOP(2))),
            'o6_saveRestoreVerbs': BUILD({
                # 'SO_SAVE_VERBS': fstack('save-verbs {2} to {1} set {0}', *NPOP(3)),
                'SO_SAVE_VERBS': fstack('verbs-save {2} to {1} set {0}', *NPOP(3)),
                # 'SO_RESTORE_VERBS': fstack('restore-verbs {2} to {1} set {0}', *NPOP(3)),
                'SO_RESTORE_VERBS': fstack('verbs-restore {2} to {1} set {0}', *NPOP(3)),
                #     # 'SO_DELETE_VERBS': fstack('delete-verbs {2} to {1} set {0}', *NPOP(3)),
                #     # 'SO_DELETE_VERBS': fstack('verbs-delete {2} to {1} set {0}', *NPOP(3)),
            }),
        }),
        'o6_actorFollowCamera': fstack('camera-follow {0}', POP),
        'o6_pickupObject': GUARD(game.version < 7 or game.he_version >= 70)(
            fstack('pick-up-object {1} in-room {0}', *NPOP(2)),
            fstack('pick-up-object {0}', POP),
        ),
        'o6_getActorMoving': F_PUSH(fstack('actor-moving {0}', POP)),
        'o6_getInventoryCount': F_PUSH(fstack('inventory-size {0}', POP)),
        'o6_getOwner': F_PUSH(fstack('owner-of {0}', POP)),
        'o6_setOwner': fstack('owner-of {1} is {0}', *NPOP(2)),
        'o6_faceActor': fstack('do-animation {1} face-towards {0}', *NPOP(2)),
        'o6_setObjectName': fstack('new-name-of {1} is {0:msg}', MSG_ARG(0), POP),
        'cursorCommand': BUILD({
            'SO_CURSOR_ON': fstack('cursor on'),
            'SO_CURSOR_OFF': fstack('cursor off'),
            'SO_USERPUT_ON': fstack('userput on'),
            'SO_USERPUT_OFF': fstack('userput off'),
            'SO_CURSOR_SOFT_ON': fstack('cursor soft-on'),
            'SO_CURSOR_SOFT_OFF': fstack('cursor soft-off'),
            'SO_USERPUT_SOFT_ON': fstack('userput soft-on'),
            'SO_USERPUT_SOFT_OFF': fstack('userput soft-off'),
            'SO_CURSOR_IMAGE': GUARD(game.he_version >= 70 or 7 <= game.version < 8)(
                fstack('cursor image {0}', POP),
                fstack('cursor {1} image {0}', *NPOP(2)),
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
            **GUARD(game.version >= 8)({
                'SO_CURSOR_PUT': fstack('put-cursor {1},{0}', *NPOP(2)),
            }),
            **GUARD(game.he_version >= 80)({
                'SO_CURSOR_COLOR_IMAGE': fstack('cursor color image {0}', POP),
                'SO_BUTTON': fstack('button {1} image {0}', *NPOP(2)),
                'SO_CURSOR_COLOR_PAL_IMAGE': fstack('cursor color image {1} palette {0}', *NPOP(2)),
                'SO_CHARSET': fstack('charset {0}', POP),
            }),
        }),
        'actorOps': BUILD({
            'SO_ACTOR_INIT': fstack('actor {0}', POP),
            'SO_PALETTE': fstack('\tcolor {1} is {0}', *NPOP(2)),
            'SO_DEFAULT': fstack('\tdefault'),
            'SO_COSTUME': fstack('\tcostume {0}', POP),
            'SO_IGNORE_BOXES': fstack('\tignore-boxes'),
            'SO_FOLLOW_BOXES': fstack('\tfollow-boxes'),
            'SO_NEVER_ZCLIP': fstack('\tnever-zclip'),
            'SO_ALWAYS_ZCLIP': fstack('\talways-zclip {0}', POP),
            'SO_SCALE': fstack('\tscale {0}', POP),
            'SO_STEP_DIST': fstack('\tstep-dist {1},{0}', *NPOP(2)),
            'SO_TALK_COLOR': fstack('\ttalk-color {0}', POP),
            'SO_ACTOR_NAME': fstack('\tname {0:msg}', MSG_ARG(0)),
            'SO_TEXT_OFFSET': fstack('\ttext-offset {1},{0}', *NPOP(2)),
            'SO_ACTOR_WIDTH': fstack('\twidth {0}', POP),
            'SO_ELEVATION': fstack('\televation {0}', POP),
            'SO_TALK_ANIMATION': fstack('\ttalk-animation {1} {0}', *NPOP(2)),
            'SO_STAND_ANIMATION': fstack('\tstand-animation {0}', POP),
            'SO_WALK_ANIMATION': fstack('\twalk-animation {0}', POP),
            'SO_INIT_ANIMATION': fstack('\tinit-animation {0}', POP),
            'SO_ANIMATION_SPEED': fstack('\tanimation-speed {0}', POP),
            'SO_ANIMATION_DEFAULT': fstack('\tanimation default'),
            'SO_SHADOW': GUARD(game.version < 8)(
                fstack('\tshadow {0}', POP),
                fstack('\tspecial-draw {0}', POP),
            ),
            # 'SO_ANIMATION': fstack('\tanimation {2} {1} {0}', *NPOP(3)),
            'SO_NEW': fstack('\tnew'),
            'SO_SOUND': fstack('\tsound {0:csvargs}', POP_PARAMS),
            'SO_ACTOR_IGNORE_TURNS_ON': fstack('\tignore-turns on'),
            'SO_ACTOR_IGNORE_TURNS_OFF': fstack('\tignore-turns off'),
            **GUARD(game.version >= 7)({
                'SO_ACTOR_TALK_SCRIPT': fstack('\ttalk-script {0}', POP),
                'SO_ACTOR_WALK_SCRIPT': fstack('\twalk-script {0}', POP),
                'SO_ACTOR_DEPTH': fstack('\tto-zplane {0}', POP),
                'SO_ACTOR_FACE': fstack('\tdirection {0}', POP),
                'SO_ACTOR_TURN': fstack('\tturn-to {0}', POP),
                'SO_ACTOR_WALK_PAUSE': fstack('\tstop-walk'),
                'SO_ACTOR_WALK_RESUME': fstack('\tresume-walk'),
                **GUARD(game.version < 8)({
                    'SO_ALWAYS_ZCLIP_FT_DEMO': fstack('\tzclip {0}', POP),
                }),
                'SO_ACTOR_STOP': fstack('\tstop'),  # Actually only used in COMI
            }),
            **GUARD(game.version >= 8)({
                'SO_ACTOR_FREQUENCY': fstack('\tfrequency {0}', POP),
                'SO_ACTOR_VOLUME': fstack('\tvolume {0}', POP),
                'SO_ACTOR_PAN': fstack('\tpan {0}', POP),
            }),
            **GUARD(game.he_version >= 60)({
                'SO_ACTOR_DEFAULT_CLIPPED': fstack('\tdefault-box {3},{2} to {1},{0}', *NPOP(4)),
                'SO_BACKGROUND_ON': fstack('\tbak on'),
                # 'SO_BACKGROUND_OFF': fstack('\tbak off'),
                'SO_TALKIE': GUARD(game.he_version >= 72)(
                    fstack('\ttalkie {1} {0}', POP_STR, POP),
                    fstack('\ttalkie {1} {0}', MSG_ARG(0), POP),
                ),
            }),
            **GUARD(game.he_version >= 72)({
                'SO_CONDITION': fstack('\tcondition {0:csvargs}', POP_PARAMS),
                'SO_TALK_CONDITION': fstack('\ttalk-condition {0}', POP),
                'SO_PRIORITY': fstack('\torder {0}', POP),
                'SO_CHARSET_SET': fstack('\tcharset {0}', POP),
                'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
                'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
                'SO_ERASE': fstack('\terase {0}', POP),
            }),
            **GUARD(game.he_version >= 90)({
                'SO_NEW_GENERAL_PROPERTY': fstack('\tproperty {1} is {0}', *NPOP(2)),
            }),
            **GUARD(game.he_version >= 99)({
                'SO_ROOM_PALETTE': fstack('\tpalette {0}', POP),
            }),
            **GUARD(game.he_version >= 100)(
                {
                    'SO_ACTOR_SOUNDS': fstack('\tsound {0:csvargs}', POP_PARAMS),
                    'SO_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
                },
                GUARD(game.version >= 7 or game.he_version >= 60)({
                    'SO_ACTOR_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2)),
                }),
            ),
        }),
        'o6_pseudoRoom': fstack('pseudo-room {1} is {0:csvargs}', POP_PARAMS, POP),
        'o6_getObjectX': F_PUSH(fstack('object-x {0}', POP)),
        'o6_getObjectY': F_PUSH(fstack('object-y {0}', POP)),
        'o6_stampObject': fstack('stamp-object {3} at {2},{1} image {0}', *NPOP(4)),
        'o6_isActorInBox': F_PUSH(fstack('{1} in-box {0}', *NPOP(2))),
        'o6_createBoxMatrix': fstack('set-box-path'),
        'o6_systemOps': BUILD({
            'SO_RESTART': fstack('restart'),
            'SO_QUIT': fstack('quit'),
            # **GUARD(game.version < 8 and game.he_version < 60)({
            #     'SO_PAUSE': fstack('pause'),
            # }),
            **GUARD(game.he_version >= 70)({
                'SO_QUIT_QUIT': fstack('quit quit'),
                'SO_RESTART_STRING': GUARD(game.he_version < 72)(
                    fstack('restart {0:msg}', MSG_ARG(0)),
                    fstack('restart {0}', POP_STR),
                ),
            }),
            **GUARD(game.he_version >= 72)({
                'SO_FLUSH_OBJECT_DRAW_QUE': fstack('flush-object-draw-que'),
                'SO_UPDATE_SCREEN': fstack('update-screen'),
            }),
        }),
        'o6_getAnimateVariable': F_PUSH(fstack('actor {1} variable {0}', *NPOP(2))),
        'o6_animateActor': fstack('do-animation {1} {0}', *NPOP(2)),
        'resourceRoutines': GUARD(game.he_version < 100)(
            BUILD({
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
                'SO_LOAD_OBJECT': GUARD(game.version < 7 and game.he_version < 70)(
                    fstack('load-object {1} in-room {0}', *NPOP(2)),
                    fstack('load-object {0}', POP),
                ),
                **GUARD(game.he_version >= 70)({
                    'SO_CLEAR_HEAP': fstack('clear-heap'),
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
                }),
            }),
            # o100_resourceRoutines
            BUILD({
                'SO_CHARSET': fstack('charset {0}', POP),
                'SO_SCRIPT': fstack('script {0}', POP),
                'SO_SOUND': fstack('sound {0}', POP),
                'SO_COSTUME': fstack('costume {0}', POP),
                'SO_ROOM': fstack('room {0}', POP),
                'SO_IMAGE': fstack('image {0}', POP),
                # 'SO_OBJECT': fstack('object {0}', POP),
                'SO_FLOBJECT': fstack('flobject {0}', POP),
                'SO_LOAD': fstack('\tload'),
                # 'SO_CLEAR_HEAP': fstack('clear-heap'),
                'SO_PRELOAD_FLUSH': fstack('preload flush'),
                'SO_LOCK': fstack('\tlock'),
                'SO_NUKE': fstack('\tnuke'),
                'SO_PRELOAD': fstack('\tpreload'),
                'SO_UNLOCK': fstack('\tunlock'),
                'SO_OFF_HEAP': fstack('\toff-heap'),
                'SO_ON_HEAP': fstack('\ton-heap'),
            }),
        ),
        'o6_loadRoom': fstack('current-room {0}', POP),
        'o6_getRandomNumber': F_PUSH(fstack('random {0}', POP)),
        'o6_getRandomNumberRange': F_PUSH(CAST('number', fstack('random-between {1} to {0}', *NPOP(2)))),
        'o6_pickVarRandom': F_PUSH(fstack('pick {1} random [ {0:csvargs} ]', POP_PARAMS, SCRIPT_VAR(0))),
        'o6_pickOneOf': F_PUSH(fstack('pick {1} of [ {0:csvargs} ]', POP_PARAMS, POP)),
        'o6_pickOneOfDefault': F_PUSH(
            fstack('pick {2} of [ {1:csvargs} ] default {0}', POP, POP_PARAMS, POP)
        ),
        'o6_shuffle': fstack('array-shuffle {0}[{2}] to {0}[{1}]', SCRIPT_VAR(0), *NPOP(2)),
        'o6_getDateTime': F_PUSH(fstack('get-time-date')),
        'o6_setClass': fstack('class-of {1} is {0:svargs}', POP_PARAMS, POP),
        'o6_ifClassOfIs': F_PUSH(fstack('class-of {1} is {0:svargs}', POP_PARAMS, POP)),
        'o6_stopTalking': fstack('stop-talking'),
        'o6_getObjectOldDir': F_PUSH(fstack('actor-facing {0}', POP)),
        **GUARD(game.version >= 7)({
            'o6_getObjectNewDir': F_PUSH(fstack('facing {0}', POP)),
        }),
        'o6_getPixel': GUARD(game.he_version < 72)(
            F_PUSH(fstack('pixel {1},{0}', *NPOP(2))),
            F_PUSH(  # o72_getPixel
                BUILD({
                    'SO_BACKGROUND_ON': fstack('pixel background {1},{0}', *NPOP(2)),
                    'SO_BACKGROUND_OFF': fstack('pixel {1},{0}', *NPOP(2)),
                })
            ),
        ),
        'o6_putActorAtXY': fstack('put-actor {3} at {2},{1} in-room {0}', *NPOP(4)),
        'o6_putActorAtObject': GUARD(game.version < 7)(
            fstack('put-actor {2} at-object {1} in-room {0}', *NPOP(3)),
            fstack('put-actor {1} at-object {0}', *NPOP(2)),
        ),
        'o6_panCameraTo': GUARD(game.version < 7)(
            fstack('camera-pan-to {0}', POP),
            fstack('camera-pan-to {1},{0}', *NPOP(2)),
        ),
        'o6_setCameraAt': GUARD(game.version < 7)(
            fstack('camera-at {0}', POP),
            fstack('camera-at {1},{0}', *NPOP(2)),
        ),
        'o6_stopSentence': fstack('stop-sentence'),
        'o6_getActorCostume': F_PUSH(fstack('actor-costume {0}', POP)),
        'o6_getActorWidth': F_PUSH(fstack('actor-width {0}', POP)),
        'o6_getActorElevation': F_PUSH(fstack('actor-elevation {0}', POP)),
        'o6_getActorRoom': F_PUSH(fstack('actor-room {0}', POP)),
        'o6_getActorAnimCounter': F_PUSH(fstack('actor-chore {0}', POP)),
        'o6_getActorScaleX': F_PUSH(fstack('actor-scale {0}', POP)),
        'o6_getActorWalkBox': F_PUSH(fstack('actor-box {0}', POP)),
        'o6_setState': fstack('state-of {1} is {0}', *NPOP(2)),
        'o6_getState': F_PUSH(fstack('state-of {0}', POP)),
        'o6_walkActorTo': fstack('walk {2} to {1},{0}', *NPOP(3)),
        'o6_walkActorToObj': fstack('walk {2} to-object {1} within {0}', *NPOP(3)),
        'o6_distObjectObject': F_PUSH(fstack('proximity {1} to {0}', *NPOP(2))),
        'o6_freezeUnfreeze': PBUILD(POP)(
            {0: fstack('unfreeze-scripts')},
            fstack('freeze-scripts {0}', POP),
        ),
        **GUARD(game.version >= 8)({
            'o8_blastText': PRINTER('blast-text', game=game),
            'o8_getStringWidth': F_PUSH(fstack('string-width charset {1} {0:msg}', MSG_ARG(0), POP)),
            'o8_cameraOps': BUILD({
                'SO_CAMERA_PAUSE': fstack('camera pause'),
                'SO_CAMERA_RESUME': fstack('camera resume'),
            }),
            'o8_getActorChore': F_PUSH(fstack('actor-chore {0}', POP)),
            'o8_startVideo': fstack('start-video {0:msg}', MSG_ARG(0)),
            'o8_getObjectImageX': F_PUSH(fstack('object-image-x {0}', POP)),
            'o8_getObjectImageY': F_PUSH(fstack('object-image-y {0}', POP)),
            'o8_getObjectImageHeight': F_PUSH(fstack('object-image-height {0}', POP)),
            'o8_getObjectImageWidth': F_PUSH(fstack('object-image-width {0}', POP)),
            'o8_getActorZPlane': F_PUSH(fstack('actor-zplane {0}', POP)),
            'o8_debug': fstack('debug {0}', POP),
        }),
    }
    he60_ops = {
        'o60_redimArray': BUILD({
            'SO_BYTE': fstack('redim byte array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            'SO_INT': fstack('redim int array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            **GUARD(game.he_version >= 72)({
                'SO_DWORD': fstack('redim dword array {0}[{2}][{1}]', SCRIPT_VAR(0), *NPOP(2)),
            }),
        }),
        'o60_localizeArrayToScript': fstack('localize {0}', POP),
        'o60_closeFile': fstack('close-file {0}', POP),
        'o60_seekFilePos': (
            # fstack('seek-file {2} {1} type {0}', *NPOP(3)),
            PBUILD(POP)({
                1: fstack('seek-file {1} to {0}', *NPOP(2)),
                2: fstack('seek-file {1} to add {0}', *NPOP(2)),
            })
        ),
        'o60_readFilePos': F_PUSH(fstack('read-file {0} position', POP)),
        **GUARD(game.he_version < 70)(
            {
                'o60_soundOps': BUILD({
                    'SO_SOUND_START_VOLUME': (
                        # windex shows empty string
                        fstack('sound volume {0}', POP)
                    ),
                    'SO_SOUND_VOLUME_RAMP': fstack('sound volume-ramp {0}', POP),
                    'SO_SOUND_FREQUENCY': (
                        # windex shows empty string
                        fstack('sound frequency {0}', POP)
                    ),
                }),
            },
            {
                'o70_soundOps': BUILD({
                    'SO_SOUND_START': fstack('start-sound {0}', POP),
                    'SO_AT': fstack('\tat {0}', POP),
                    'SO_SOFT': fstack('\tsoft'),
                    'SO_SOUND_START_VOLUME': (fstack('\tvolume {0}', POP)),
                    'SO_NOW': fstack('\tnow'),
                    'SO_SOUND_CHANNEL': fstack('\tchannel {0}', POP),
                    'SO_SOUND_LOOPING': fstack('\tloop'),
                    'SO_SOUND_MODIFY': fstack('sound {0}', POP),
                    'SO_VARIABLE': fstack('sound {2} variable {1} is {0}', *NPOP(3)),
                    # 'SO_SOUND_SOFT': fstack('\tsoft'),
                    **GUARD(game.he_version < 99)(
                        {'SO_SOUND_VOLUME': fstack('sound {1} volume {0}', *NPOP(2))},
                        {'SO_SOUND_VOLUME': fstack('\tvolume {0}', POP)},
                    ),
                    'SO_SOUND_PAN': fstack('\tpan {0}', POP),
                    'SO_SOUND_FREQUENCY': fstack('\tfrequency {0}', POP),
                    'SO_END': fstack('\t(end-sound)'),
                }),
            },
        ),
        **GUARD(game.he_version < 72)(
            {
                'o60_openFile': F_PUSH(fstack('open-file {1:msg} for {0}', POP, MSG_ARG(0))),
                'o60_deleteFile': fstack('delete-file {0:msg}', MSG_ARG(0)),
                'o60_writeFile': fstack('write-file {2} size {1} value {0}', *NPOP(3)),
                'o60_readFile': F_PUSH(fstack('read-file {1} size {0}', *NPOP(2))),
                'o60_rename': fstack('rename-file {1:msg} to {0:msg}', MSG_ARG(1), MSG_ARG(0)),
            },
            {
                'o72_openFile': F_PUSH(fstack('open-file {1} for {0}', POP, POP_STR)),
                'o72_deleteFile': fstack('delete-file {0}', POP_STR),
                'o72_writeFile': BUILD({
                    'SO_BYTE': fstack('write-file {1} byte {0}', *NPOP(2)),
                    'SO_INT': fstack('write-file {1} int {0}', *NPOP(2)),
                    'SO_DWORD': fstack('write-file {1} dword {0}', *NPOP(2)),
                    'SO_ARRAY': fstack('write-file {1} byte array {0}', *NPOP(2)),
                }),
                'o72_readFile': F_PUSH(
                    BUILD({
                        'SO_BYTE': fstack('read-file {0} byte', POP),
                        'SO_INT': fstack('read-file {0} int', POP),
                        'SO_DWORD': fstack('read-file {0} dword', POP),
                        'SO_ARRAY': fstack('read-file {1} byte array [{0}]', *NPOP(2)),
                    })
                ),
                'o72_rename': fstack('rename-file {1} to {0}', POP_STR, POP_STR),
            },
        ),
        'debugInput': GUARD(100 <= game.he_version < 101)(
            BUILD({  # o100_debugInput
                'SO_INIT': fstack('s_debug = debug-input {0}', POP_STR),
                'SO_COUNT': fstack('\tsize {0}', POP),
                'SO_DEFAULT': fstack('\tdefault', POP_STR),
                'SO_TITLE_BAR': fstack('\ttitle-bar', POP_STR),
                'SO_END': F_PUSH(fstack('s_debug')),
            }),
            # o72_debugInput
            F_PUSH(fstack('debug-input {0}', POP_STR)),
        ),
    }
    he70_ops = {
        'o70_setSystemMessage': GUARD(game.he_version < 72)(
            BUILD({
                'SO_TITLE_BAR': fstack('title-bar {0:msg}', MSG_ARG(0)),
                'SO_PAUSE_TITLE': fstack('pause-title {0:msg}', MSG_ARG(0)),
            }),
            BUILD({
                'SO_TITLE_BAR': fstack('title-bar {0}', POP_STR),
                'SO_PAUSE_TITLE': fstack('pause-title {0}', POP_STR),
            }),
        ),
        'isResourceLoaded': GUARD(game.he_version < 100)(
            F_PUSH(  # o70_isResourceLoaded
                BUILD({
                    'SO_IMAGE_LOADED': fstack('image-loaded {0}', POP),
                    'SO_ROOM_LOADED': fstack('room-loaded {0}', POP),
                    'SO_COSTUME_LOADED': fstack('costume-loaded {0}', POP),
                    'SO_SOUND_LOADED': fstack('sound-loaded {0}', POP),
                    'SO_SCRIPT_LOADED': fstack('script-loaded {0}', POP),
                }),
            ),
            F_PUSH(  # o100_isResourceLoaded
                BUILD({
                    'SO_IMAGE': fstack('image-loaded {0}', POP),
                    # 'SO_ROOM': fstack('room-loaded {0}', POP),
                    'SO_COSTUME': fstack('costume-loaded {0}', POP),
                    'SO_SOUND': fstack('sound-loaded {0}', POP),
                    # 'SO_SCRIPT': fstack('script-loaded {0}', POP),
                })
            ),
        ),
        'o70_getStringLen': F_PUSH(fstack('string-length {0}', POP)),
        **GUARD(game.he_version < 72)(
            {
                'o70_readINI': F_PUSH(
                    PBUILD(POP)({
                        1: CAST('number', fstack('read-ini {0:msg}', MSG_ARG(0))),
                        2: CAST('string', fstack('read-ini string {0:msg}', MSG_ARG(0))),
                    })
                ),
                'o70_writeINI': PBUILD(POP)({
                    1: fstack('write-ini {1:msg} = {0}', POP, MSG_ARG(0)),
                    2: fstack('write-ini string {1:msg} = {0:msg}', MSG_ARG(1), MSG_ARG(0)),
                }),
                'o70_createDirectory': fstack('create-directory {0:msg}', MSG_ARG(0)),
            },
            {
                'o72_readINI': F_PUSH(
                    BUILD({
                        'SO_DWORD': CAST('number', fstack('read-ini {0}', POP_STR)),
                        'SO_STRING': CAST('string', fstack('read-ini string {0}', POP_STR)),
                    }),
                ),
                'o72_writeINI': BUILD({
                    'SO_DWORD': fstack('write-ini {1} = {0}', POP, POP_STR),
                    'SO_STRING': fstack('write-ini string {1} = {0}', POP_STR, POP_STR),
                }),
                'o72_createDirectory': fstack('create-directory {0}', POP_STR),
            },
        ),
    }
    he71_ops = {
        'o71_findBox': F_PUSH(fstack('find-box {1},{0}', *NPOP(2))),
        'o71_polygonHit': F_PUSH(fstack('find-polygon {1}, {0}', *NPOP(2))),
        'o71_polygonOps': BUILD({
            'SO_SET_POLYGON': fstack('set-polygon {8} at {7},{6} to {5},{4} to {3},{2} to {1},{0}', *NPOP(9)),
            'SO_SET_POLYGON_LOCAL': fstack(
                'set-polygon {8} at {7},{6} to {5},{4} to {3},{2} to {1},{0} local', *NPOP(9)
            ),
            'SO_DELETE_POLYGON': fstack('delete-polygon {1} to {0}', *NPOP(2)),
        }),
        'o71_getStringWidth': F_PUSH(fstack('string-width {2} from {1} to {0}', *NPOP(3))),
        'o71_appendString': F_PUSH(fstack('string-copy {2} from {1} to {0}', *NPOP(3))),
        'o71_concatString': F_PUSH(fstack('string-copy {1} add {0}', *NPOP(2))),
        'o71_getStringLenForWidth': F_PUSH(fstack('string-margin {2} from {1} margin {0}', *NPOP(3))),
        'o71_compareString': F_PUSH(fstack('string-compare {1} {0}', *NPOP(2))),
        'o71_copyString': F_PUSH(fstack('string-copy {0}', POP)),
        'o71_getCharIndexInString': F_PUSH(
            fstack('string-search {3} from {2} to {1} for {0}', CAST('char', POP), *NPOP(3))
        ),
    }
    he72_ops = {
        'o72_captureWizImage': fstack('capture-image {4} at {3},{2} to {1},{0}', *NPOP(5)),
        'o72_traceStatus': fstack('debug {1} {0}', POP, POP_STR),
        'o72_resetCutscene': fstack('override off off'),
        **GUARD(game.he_version < 90)({
            'o72_drawWizImage': F_PUSH(fstack('draw-image {3} at {2},{1} {0}', *NPOP(4))),
        }),
        'o72_printWizImage': fstack('print-image {0}', POP),
        'o72_setTimer': BUILD({'SO_RESTART': fstack('timer {0} restart', POP)}),
        'o72_getTimer': F_PUSH(BUILD({'SO_MSECONDS': fstack('timer {0}', POP)})),
        'o72_getSoundPosition': F_PUSH(fstack('sound-position {0}', POP)),
        'o72_getArrayDimSize': F_PUSH(
            PBUILD(BYTE_ARG(0))({
                1: fstack('dim {0} [?]', SCRIPT_VAR(1)),
                2: fstack('dim {0} [?][]', SCRIPT_VAR(1)),
                3: fstack('dim {0} [][?]', SCRIPT_VAR(1)),
                4: (
                    # fstack('dim {0} [? to]', SCRIPT_VAR(1)),
                    fstack('dim {0} [][? to]', SCRIPT_VAR(1))
                ),
                5: (
                    # fstack('dim {0} [to ?]', SCRIPT_VAR(1))
                    fstack('dim {0} [][to ?]', SCRIPT_VAR(1))
                ),
                6: fstack('dim {0} [? to][]', SCRIPT_VAR(1)),
                7: fstack('dim {0} [to ?][]', SCRIPT_VAR(1)),
            })
        ),
        'o72_getHeap': F_PUSH(
            BUILD({
                # 'SO_HEAP_FREE': fstack('heap-free'),
                'SO_HEAP_LARGEST_FREE': fstack('heap-largest-free'),
            }),
        ),
        'o72_getNumFreeArrays': F_PUSH(fstack('free-arrays')),
        'o72_getObjectImageX': F_PUSH(fstack('object-image-x {0}', POP)),
        'o72_getObjectImageY': F_PUSH(fstack('object-image-y {0}', POP)),
        'o72_findObjectWithClassOf': F_PUSH(
            fstack('find-object {2},{1} class [{0:csvargs}]', POP_PARAMS, *NPOP(2)),
        ),
        **GUARD(game.he_version < 100)(
            GUARD(game.he_version < 73)(
                {'o72_getResourceSize': F_PUSH(fstack('sound-size {0}', POP))},
                {
                    'o73_getResourceSize': F_PUSH(
                        BUILD({
                            'SO_IMAGE_SIZE': fstack('image-size {0}', POP),
                            'SO_COSTUME_SIZE': fstack('costume-size {0}', POP),
                            'SO_SOUND_SIZE': fstack('sound-size {0}', POP),
                        })
                    ),
                },
            ),
            {
                'o100_getResourceSize': F_PUSH(
                    BUILD({
                        # 'SO_IMAGE': fstack('image-size {0}', POP),
                        # 'SO_COSTUME': fstack('costume-size {0}', POP),
                        'SO_SOUND': fstack('sound-size {0}', POP),
                    })
                ),
            },
        ),
    }
    he80_ops = {
        'o80_drawWizPolygon': fstack('draw-image {1} polygon {0}', *NPOP(2)),
        'o80_getFileSize': F_PUSH(fstack('file-size {0}', POP_STR)),
        'o80_sourceDebug': fstack('source-debug {1} {0}', DWORD_ARG(0), DWORD_ARG(1)),
        'o80_stringToInt': F_PUSH(CAST('number', fstack('string-number {0}', POP))),
        'o80_drawLine': BUILD({
            'SO_ACTOR': fstack('draw-line {5},{4} to {3},{2} actor {1} step-dist {0}', *NPOP(6)),
            # 'SO_IMAGE': fstack('draw-line {5},{4} to {3},{2} image {1} step-dist {0}', *NPOP(6)),
            'SO_COLOR': fstack('draw-line {5},{4} to {3},{2} color {1} step-dist {0}', *NPOP(6)),
        }),
        'o80_readConfigFile': F_PUSH(
            BUILD({
                'SO_DWORD': CAST('number', fstack('(read-ini {2} {1} {0})', POP_STR, POP_STR, POP_STR)),
                'SO_STRING': CAST(
                    'string', fstack('(read-ini string {2} {1} {0})', POP_STR, POP_STR, POP_STR)
                ),
            })
        ),
        'o80_writeConfigFile': BUILD({
            'SO_DWORD': fstack('write-ini {3} {2} {1} is {0}', POP, POP_STR, POP_STR, POP_STR),
            'SO_STRING': fstack('write-ini string {3} {2} {1} is {0}', POP_STR, POP_STR, POP_STR, POP_STR),
        }),
        'o80_localizeArrayToRoom': fstack('room localize {0}', POP),
        'o80_getSoundVar': F_PUSH(fstack('sound {1} variable {0}', *NPOP(2))),
        'o80_createSound': BUILD({
            **GUARD(game.he_version < 100)(
                {'SO_SOUND_START': fstack('create-sound {0}', POP)},
                {'SO_INIT': fstack('create-sound {0}', POP)},
            ),
            'SO_SOUND_ADD': fstack('\tadd {0}', POP),
            'SO_NEW': fstack('\tnew'),
            'SO_END': fstack('\t(end-create-sound)'),
        }),
    }
    he90_ops = {
        'o90_priorityChainScript': BUILD({
            'SO_NONE': fstack('chain-script {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # 'SO_BAK': fstack('chain-script bak {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # 'SO_REC': fstack('chain-script rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # 'SO_BAK_REC': fstack('chain-script bak rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        }),
        'o90_priorityStartScript': BUILD({
            'SO_NONE': fstack('start-script {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # 'SO_BAK': fstack('start-script bak {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            'SO_REC': fstack('start-script rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
            # 'SO_BAK_REC': fstack('start-script bak rec {2} order {1}{0:pvargs}', POP_PARAMS, *NPOP(2)),
        }),
        'o90_min': F_PUSH(fstack('min {1} {0}', *NPOP(2))),
        'o90_max': F_PUSH(fstack('max {1} {0}', *NPOP(2))),
        'o90_atan2': F_PUSH(fstack('angle-from-delta {1},{0}', *NPOP(2))),
        'o90_getSegmentAngle': F_PUSH(fstack('angle-from-line {3},{2} to {1},{0}', *NPOP(4))),
        'o90_sin': F_PUSH(fstack('sin {0}', POP)),
        'o90_cos': F_PUSH(fstack('cos {0}', POP)),
        'o90_shl': F_PUSH(fstack('{1} << {0}', *NPOP(2))),
        'o90_shr': F_PUSH(fstack('{1} >> {0}', *NPOP(2))),
        'o90_sqrt': F_PUSH(fstack('sqrt {0}', POP)),
        'o90_xor': F_PUSH(fstack('{1} bxor {0}', *NPOP(2))),
        'o90_disabled_windowOps': BUILD({
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
        }),
        'o90_dim2dim2Array': BUILD({
            'SO_INT': fstack('dim int array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
            'SO_BIT': fstack('dim bit array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)),
            # 'SO_NIBBLE': fstack(
            #     'dim nibble array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)
            # ),
            'SO_BYTE': fstack(
                'dim byte array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)
            ),
            'SO_DWORD': fstack(
                'dim dword array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)
            ),
            # 'SO_STRING': fstack(
            #     'dim string array {0}[{5} to {4}][{3} to {2}] order {1}', SCRIPT_VAR(0), *NPOP(5)
            # ),
        }),
        'o90_redim2dimArray': BUILD({
            'SO_INT': fstack('redim int array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            # 'SO_BIT': fstack('redim bit array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            # 'SO_NIBBLE': fstack('redim nibble array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            'SO_BYTE': fstack('redim byte array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            'SO_DWORD': fstack('redim dword array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            # 'SO_STRING': fstack('redim string array {0}[{4} to {3}][{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
        }),
        'o90_getLinesIntersectionPoint': F_PUSH(
            fstack(
                'find-segment-intersection {9},{8} ({7},{6} to {5},{4}), ({3},{2} to {1},{0})',
                *NPOP(8),
                SCRIPT_VAR(1),
                SCRIPT_VAR(0),
            )
        ),
        'o90_setSpriteInfo': BUILD({
            'SO_INIT': GUARD(game.version > 98)(
                fstack('sprite {0} to {1}', *NPOP(2)),
                fstack('sprite {0}', POP),
            ),
            'SO_IMAGE': fstack('\timage {0}', POP),
            'SO_STEP_DIST_X': fstack('\tstep-dist-x {0}', POP),
            'SO_STEP_DIST_Y': fstack('\tstep-dist-y {0}', POP),
            'SO_GROUP': fstack('\tgroup {0}', POP),
            'SO_ANGLE': fstack('\tangle {0}', POP),
            'SO_ANIMATION': fstack('\tanimation {0}', POP),
            'SO_ANIMATION_SPEED': fstack('\tanimation-speed {0}', POP),
            'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
            'SO_AT_IMAGE': fstack('\tsource image {0}', POP),
            'SO_CLASS': fstack('\tclass [{0:csvargs}]', POP_PARAMS),
            'SO_ERASE': fstack('\terase {0}', POP),
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
            **GUARD(game.he_version < 100)(
                {'SO_ACTOR_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2))},
                {'SO_VARIABLE': fstack('\tvariable {1} is {0}', *NPOP(2))},
            ),
        }),
        'o90_getSpriteInfo': F_PUSH(
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
                'SO_FIND': GUARD(game.he_version >= 99)(
                    fstack(
                        '{1:inline} {4},{3} group {2} class [{0:csvargs}]',
                        POP_PARAMS,
                        PBUILD(POP)({
                            0: fstack('find-sprite'),
                            1: fstack('find-sprite rectangle'),
                        }),
                        *NPOP(3),
                    ),
                    GUARD(game.he_version >= 98)(
                        PBUILD(POP)({
                            0: fstack('find-sprite {2},{1} group {0}', *NPOP(3)),
                            1: fstack('find-sprite rectangle {2},{1} group {0}', *NPOP(3)),
                        }),
                        fstack('find-sprite {2},{1} group {0}', *NPOP(3)),
                    ),
                ),
                'SO_IMAGE': fstack('sprite {0} image', POP),
                'SO_STATE': fstack('sprite {0} state', POP),
                'SO_ANIMATION': fstack('sprite {0} animation-type', POP),
                'SO_PALETTE': fstack('sprite {0} palette', POP),
                'SO_UPDATE': fstack('sprite {0} update-type', POP),
                'SO_SCALE': fstack('sprite {0} scale', POP),
                'SO_CLASS': fstack('sprite {1} class [{0:csvargs}]', POP_PARAMS, POP),
                **GUARD(game.he_version < 100)(
                    {'SO_ACTOR_VARIABLE': fstack('sprite {1} variable {0}', *NPOP(2))},
                    {'SO_VARIABLE': fstack('sprite {1} variable {0}', *NPOP(2))},
                ),
                'SO_MASK': fstack('sprite {0} mask image', POP),
                'SO_AT_IMAGE': fstack('sprite {0} source image', POP),
                'SO_NEW_GENERAL_PROPERTY': fstack('sprite {1} property {0}', *NPOP(2)),
                'SO_PROPERTY': PBUILD(POP)({
                    0: fstack('sprite {0} hflip', POP),
                    1: fstack('sprite {0} vflip', POP),
                    # 2: fstack('sprite {0} show', POP),
                    4: fstack('sprite {0} image remap', POP),
                }),
            })
        ),
        'o90_setSpriteGroupInfo': BUILD({
            'SO_INIT': fstack('sprite group {0}', POP),
            'SO_GROUP': PBUILD(POP)({
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
        }),
        'o90_getDistanceBetweenPoints': F_PUSH(
            BUILD({
                'SO_COORD_2D': fstack('line-length {3},{2} to {1},{0}', *NPOP(4)),
                'SO_COORD_3D': fstack('line-length {5},{4},{3} to {2},{1},{0}', *NPOP(6)),
            })
        ),
        'o90_getPolygonOverlap': F_PUSH(
            fstack('overlap {2} ([{1:csvargs}],[{0:csvargs}])', POP_PARAMS, POP_PARAMS, POP)
        ),
        'o90_getSpriteGroupInfo': F_PUSH(
            BUILD({
                'SO_ARRAY': fstack('sprite group {0} sprite []', POP),
                'SO_PRIORITY': fstack('sprite group {0} order', POP),
                'SO_XPOS': fstack('sprite group {0} object-x', POP),
                'SO_YPOS': fstack('sprite group {0} object-y', POP),
            })
        ),
        'o90_floodFill': BUILD({
            'SO_INIT': fstack('flood-fill'),
            'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
            'SO_COLOR': fstack('\tcolor {0}', POP),
            'SO_END': fstack('\t(end)'),
            'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
        }),
        'o90_getObjectData': F_PUSH(
            BUILD({
                'SO_INIT': fstack('object {0}', POP),
                'SO_DRAW_YPOS': fstack('{0:inline} object-draw-y', POP),
                'SO_DRAW_XPOS': fstack('{0:inline} object-draw-x', POP),
                'SO_STATE': fstack('{0:inline} state', POP),
                'SO_WIDTH': fstack('{0:inline} width', POP),
                'SO_HEIGHT': fstack('{0:inline} height', POP),
                # 'SO_STATE_COUNT': fstack('{0:inline} state-count', POP),
                # 'SO_NEW_GENERAL_PROPERTY': fstack('{1:inline} property {0}', *NPOP(2)),  # TODO: verify order is correct
            })
        ),
        'o90_wizImageOps': BUILD({
            'SO_INIT': fstack('image {0}', POP),
            'SO_WIDTH': fstack('\twidth {0}', POP),
            'SO_HEIGHT': fstack('\theight {0}', POP),
            'SO_DRAW': fstack('\tdraw'),
            'SO_SAVE': fstack('\tsave {1} {0}', POP_STR, POP),
            'SO_LOAD': fstack('\tload {0}', POP_STR),
            'SO_CAPTURE': fstack('\tcapture {4} at {3},{2} to {1},{0}', *NPOP(5)),
            'SO_STATE': fstack('\tstate {0}', POP),
            'SO_SET_FLAGS': fstack('\tset-flags {0}', POP),
            'SO_NOW': fstack('draw-image {4} at {3},{2} state {1} {0}', *NPOP(5)),
            'SO_AT': fstack('\tat {1},{0}', *NPOP(2)),
            'SO_AT_IMAGE': fstack('\tsource image {0}', POP),
            'SO_CLIPPED': fstack('\tclip {3},{2} to {1},{0}', *NPOP(4)),
            **GUARD(game.he_version < 99)(
                {'SO_COLOR': fstack('\tcolor {1} to {0}', *NPOP(2))},
                {'SO_COLOR_LIST': fstack('\tcolor {1} to {0}', *NPOP(2))},
            ),
            'SO_NEW': fstack('\tnew'),
            'SO_PALETTE': fstack('\tpalette {0}', POP),
            'SO_POLY_TO_POLY': fstack('\tcapture {2} from polygon {1} to polygon {0}', *NPOP(3)),
            'SO_SCALE': fstack('\tscale {0}', POP),
            'SO_END': fstack('\t(end-wiz)'),
            'SO_FONT_CREATE': fstack(
                '\tfont-create font {4} style {3} size {2} foreground {1} background {0}',
                *NPOP(4),
                POP_STR,
            ),
            'SO_FONT_END': fstack('\tfont-end'),
            'SO_FONT_RENDER': fstack('\tfont-render {2} at {1},{0}', *NPOP(2), POP_STR),
            'SO_FONT_START': fstack('\tfont-start'),
            'SO_RENDER_FLOOD_FILL': fstack('\tflood-fill {2},{1} color {0}', *NPOP(3)),
            'SO_RENDER_INTO_IMAGE': fstack('\timage {0}', POP),
            'SO_RENDER_RECTANGLE': fstack('\tdraw-box {4},{3} to {2},{1} color {0}', *NPOP(5)),
            **GUARD(game.he_version < 100)(
                {'SO_CURSOR_HOTSPOT': fstack('\thotspot {1},{0}', *NPOP(2))},
                {'SO_HISTOGRAM': fstack('\thotspot {1},{0}', *NPOP(2))},  # SO_CURSOR_HOTSPOT
            ),
            'SO_RENDER_LINE': fstack('\tdraw-line {4},{3} to {2},{1} color {0}', *NPOP(5)),
            'SO_SET_POLYGON': fstack('\tpolygon {0}', POP),
            'SO_SHADOW': fstack('\tshadow {0}', POP),
            'SO_ANGLE': fstack('\tangle {0}', POP),
            'SO_NEW_GENERAL_PROPERTY': fstack('\tproperty {1} is {0}', *NPOP(2)),
            'SO_RENDER_ELLIPSE': fstack(
                '\tdraw-ellipse {7},{6} to {5},{4} at {3},{2} steps {1} color {0}', *NPOP(8)
            ),
        }),
        'o90_getPaletteData': F_PUSH(
            BUILD({
                'SO_COLOR': fstack('palette {1} slot {0} color', *NPOP(2)),
                'SO_NEW': fstack('rgb {2},{1},{0}', *NPOP(3)),
                'SO_STATE': fstack('palette {2} slot {1} channel {0}', *NPOP(3)),
                **GUARD(game.he_version >= 100)({
                    'SO_CHANNEL': fstack('rgb {1} channel {0}', *NPOP(2)),
                }),
            }),
        ),
        'o90_paletteOps': BUILD({
            'SO_INIT': fstack('new palette {0}', POP),
            'SO_TO': fstack('\tslot {2} to {1} color {0}', *NPOP(3)),
            'SO_COSTUME': fstack('\tfrom costume {0}', POP),
            'SO_COLOR': fstack('\tslot {4} to {3} rgb {2},{1},{0}', *NPOP(5)),
            'SO_PALETTE': fstack('\tfrom palette {0}', POP),
            'SO_IMAGE': fstack('\tfrom image {1} state {0}', *NPOP(2)),
            'SO_NEW': fstack('\tnew'),
            'SO_END': fstack('\t(end)'),
        }),
        'o90_sortArray': BUILD({
            'SO_SORT': PBUILD(POP)({
                -1: fstack('array {0} sort < [{4} to {3}] [{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
                1: fstack('array {0} sort > [{4} to {3}] [{2} to {1}]', SCRIPT_VAR(0), *NPOP(4)),
            }),
        }),
        'o90_getWizData': F_PUSH(
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
        ),
        'o90_fontEnum': F_PUSH(
            BUILD({
                'SO_INIT': fstack('font-enumerate enum-start'),
                'SO_PROPERTY': PBUILD(POP)({
                    1: fstack('font-enumerate get {0}', POP),  # FONT_ENUM_GET
                    2: fstack('font-enumerate find {0}', POP_STR),  # FONT_ENUM_FIND
                }),
            })
        ),
        'o90_getActorData': F_PUSH(
            PBUILD(POP)({
                1: fstack('actor {1} condition {0}', *NPOP(2)),
                2: fstack('actor {1} animation {0}', *NPOP(2)),
                3: fstack('actor {1} animation-speed{0:hzero}', *NPOP(2)),
                # 4: fstack('actor {1} shadow{0:hzero}', *NPOP(2)),
                5: fstack('actor {1} order{0:hzero}', *NPOP(2)),
                6: fstack('actor {1} palette{0:hzero}', *NPOP(2)),
            })
        ),
        'o90_cond': F_PUSH(fstack('{2} ? {1} : {0}', *NPOP(3))),
        'o90_findAllObjectsWithClassOf': F_PUSH(
            fstack('find-all-objects {1} class [{0:csvargs}]', POP_PARAMS, POP),
        ),
        'videoOps': BUILD({
            'SO_INIT': fstack('video {0}', POP),
            'SO_CLOSE': fstack('\tclose-file'),
            'SO_IMAGE': fstack('\timage {0}', POP),
            'SO_LOAD': fstack('\topen-file {0}', POP_STR),
            'SO_SET_FLAGS': PBUILD(POP)(
                {
                    1: fstack('\tbackground'),
                    4: fstack('\tforeground'),
                    # 8: fstack('\tlooping'),
                },
                fstack('\tset-flags {0}', POP),
            ),
            'SO_END': fstack('\t(end)'),
        }),
        'getVideoData': F_PUSH(
            BUILD({
                'SO_COUNT': fstack('video {0} state-count', POP),
                # 'SO_HEIGHT': fstack('video {0} height', POP),
                # 'SO_IMAGE': fstack('video {0} image', POP),
                # 'SO_NEW_GENERAL_PROPERTY': fstack('video {1} propery {0}', *NPOP(2)),
                'SO_STATE': fstack('video {0} state', POP),
                # 'SO_WIDTH': fstack('video {0} width', POP),
            })
        ),
    }
    return {
        **fallback_ops,
        **lec_ops,
        **GUARD(game.he_version >= 60)(he60_ops),
        **GUARD(game.he_version >= 70)(he70_ops),
        **GUARD(game.he_version >= 71)(he71_ops),
        **GUARD(game.he_version >= 72)(he72_ops),
        **GUARD(game.he_version >= 80)(he80_ops),
        **GUARD(game.he_version >= 90)(he90_ops),
    }


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
    stack.extend(params * 2)


@regop
def o6_not(op, stack, game):
    arg = stack.pop()
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
def o72_getScriptString(op, stack, game):
    push_str(stack, KeyString(op.args[0]))


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
        obj_names[gid] = msg_to_print(bytes(sputm.find('OBNA', obcd).data).split(b'\0', maxsplit=1)[0])
        pref = list(parse_verb_meta(pref))
        entries = {off: idx[0] for idx, off in pref}
    else:
        scr_id = int.from_bytes(pref, byteorder='little', signed=False) if pref else None
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

        fops = get_ops(GameVersion(game.version, game.he_version))
        try:
            res = fops.get(stat.name, functools.partial(defop, game=game))(stat, stack)
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
            room_no = rnam.get(room.attribs['gid'], f'room_{room.attribs["gid"]}')
            print(
                '==========================',
                room.attribs['path'],
                room_no,
            )
            fname = f'{script_dir}/{room.attribs["gid"]:04d}_{room_no}.scu'

            decompile = functools.partial(
                decompile_script,
                game=gameres.game,
                verbose=args.verbose,
            )
            with open(fname, 'w') as f:
                dump_script_file(room_no, room, decompile, f)
