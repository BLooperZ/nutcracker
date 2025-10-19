import itertools
import operator
import os
from collections import OrderedDict, defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import parse

from nutcracker.kernel2.element import Element
from nutcracker.sputm.preset import sputm
from nutcracker.sputm.schema import SCHEMA
from nutcracker.sputm.script.parser import CString, WordValue
from nutcracker.sputm.script.shared import (
    BytecodeError,
    ScriptError,
    msg_to_print,
    msg_val,
    parse_verb_meta,
    print_asts,
    realize_refs,
)
from nutcracker.sputm.strings import RAW_ENCODING
from nutcracker.sputm.tree import narrow_schema

from .script.bytecode import BytecodeParseError, descumm_iter, get_argtype, script_map
from .script.opcodes import ByteValue, RefOffset
from .script.opcodes_v5 import OPCODES_v5, SomeOp, VarArgs, Variable
from .script.opcodes_v5 import value as ovalue

USE_SEMANTIC_CONTEXT = False

l_vars = {}
semlog = defaultdict(dict)


def fstat(stat: str, *args: Any, **kwargs: Any) -> str:
    return stat.format(*[PrintArg(arg) for arg in args], **kwargs)


def build_params(mapping, args):
    for subop in args:
        if isinstance(subop, ByteValue) and ord(subop.op) in {0x1F, 0xFF}:
            # 0x1F is used by Monkey Island UTE
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
    return builder(
        {
            'ARG': '{0}',
        },
        sep=sep,
    )(args)


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
        if format_spec == 'psvargs':
            return ' ' + build_varargs(self.arg.args, sep=' ')
        return str(value(self.arg, sem=format_spec))


def print_locals(indent):
    for var in sorted(l_vars.values(), key=operator.attrgetter('num')):
        yield f'{indent[:-1]}local variable {var}'
    if l_vars:
        yield ''  # new line


def get_element_by_path(path: str, root: Iterable[Element]) -> Element | None:
    for elem in root:
        if elem.attribs['path'] == path:
            return elem
        if path.startswith(elem.attribs['path']):
            return get_element_by_path(path, elem)
    return None


def adr(arg):
    return f'&[{arg.abs + 8:08d}]'


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
        return f'({" ".join(resolve_expr(e) for e in exp)})'
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


def regop(name: str):
    def inner(op):
        ops[name] = op
        return op

    return inner


@parse.with_pattern('bak |')
def parse_bak(bak):
    # Parse a string like "bak" into a boolean value
    return bak == 'bak '


@parse.with_pattern('rec |')
def parse_rec(rec):
    # Parse a string like "bak" into a boolean value
    return rec == 'rec '


@parse.with_pattern(r'\s*\S+(\s*,\s*\S+)*|')
def parse_vargs(vargs):
    # Parse a string like "arg1, arg2, arg3" into a list of arguments
    svargs = []
    args = [arg.strip() for arg in vargs.split(',') if arg.strip()]
    for arg in args:
        parg = parse_value(arg)
        if parg is None:
            parg = WordValue(int(arg).to_bytes(2, byteorder='little', signed=False))
            svargs.append(SomeOp('ARG', 0x01, 0, (parg,)))
        else:
            svargs.append(SomeOp('ARG', 0x81, 0, (parg,)))
    svargs.append(ByteValue(bytes([0xFF])))
    return VarArgs(svargs)


@parse.with_pattern(r'\s*\S+(\s+\S+)*|\s*')
def parse_svargs(svargs):
    return svargs.strip()


@parse.with_pattern(r'\s*\S+(\s+\S+)*|\s*')
def parse_build(vargs):
    return vargs.strip()


@parse.with_pattern(r'".*"')
def parse_msg(msg):
    return unescape_message(msg.strip('"'))


@parse.with_pattern(r'\s*(?![!*])\S+\s*')
def parse_var(var):
    return parse_value(var.strip())

def encode_seq(seq: bytes) -> bytes:
    try:
        return bytes([int(b'0x' + seq[:2], 16)]) + seq[2:]
    except:
        return seq


def unescape_message(msg: str) -> bytes:
    bmsg = msg.encode(**RAW_ENCODING)
    controls = {0x04: 'n', 0x05: 'v', 0x06: 'o', 0x07: 's'}
    for control, char in controls.items():
        fmatch = parse.findall(f'%{char}{{num:d}}%', msg)
        for m in fmatch:
            num = m['num']
            bmsg = bmsg.replace(
                f'%{char}{num}%'.encode(**RAW_ENCODING),
                b'\xff' + bytes([control]) + num.to_bytes(2, byteorder='little', signed=False),
            )

    prefix, *parts = bmsg.split(b'\\x')
    bmsg = prefix + b''.join(encode_seq(part) for part in parts)
    bmsg = bmsg.replace(b'\\\\', b'\\')

    return bmsg


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
    },
)


def parse_expr(args):
    for subop in args:
        if isinstance(subop, ByteValue) and ord(subop.op) == 0xFF:
            break
        if subop.name == 'OPERATION':
            stat = subop.args[0]
            res = destr(ops.get(stat.name, str))(stat) or str(stat)
            # if isinstance(res, WindexStatement):
            #     wx = res.windex()
            #     # print(str(wx))
            #     parsed = res.parse(stat.offset, str(wx))
            #     # assert repr(parsed) == repr(res), (repr(parsed), repr(res), stat.to_bytes())
            #     assert parsed.windex() == wx, (repr(parsed), repr(res), stat.to_bytes())

            #     print(f'{wx}')
            #     if parsed.to_bytes() != stat.to_bytes():
            #         print('Warning: parsed statement does not match original bytecode:')
            #         print(f'\t{parsed!r} != {res!r}')
            #         print(f'\t{parsed.to_bytes()} != {stat.to_bytes()}')
            #     res = wx
            yield f'({res})'
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

    def __eq__(self, value):
        return self.expr == value.expr and self.ref.abs == value.ref.abs


@dataclass
class UnconditionalJump:
    ref: RefOffset

    def __str__(self) -> str:
        return f'jump {adr(self.ref)}'

    def __eq__(self, value):
        return self.ref.abs == value.ref.abs


class WindexStatement:
    def __init__(self, opcode, *args):
        self.opcode = opcode
        self.args = args

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} opcode={self.opcode:#04x} args={self.args}>'

    def __str__(self) -> str:
        return f'{self.windex()}'  #  ; {self!r}'

    def to_bytes(self) -> bytes:
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])


@regop('o5_stopObjectCode')
class StopObjectCode(WindexStatement):
    def windex(self) -> str:
        return 'end-object'

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x00
        res = parse.parse('end-object', src)
        if res is None:
            return None
        return cls(opcode)


@regop('o5_stopObjectCodeScript')
class StopObjectCodeScript(WindexStatement):
    def windex(self) -> str:
        return 'end-script'

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0xA0
        res = parse.parse('end-script', src)
        if res is None:
            return None
        return cls(opcode)


@regop('o5_cutscene')
class CutScene(WindexStatement):
    def windex(self) -> str:
        if not self.args:
            return 'cut-scene'
        return fstat('cut-scene {0:svargs}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x40

        res = parse.parse('cut-scene', src)
        if res is not None:
            return cls(opcode)
        res = parse.parse('cut-scene {args:vargs}', src, {'vargs': parse_vargs})
        if res is None:
            return None
        return cls(opcode, res['args'])


@regop('o5_freezeScripts')
class FreezeScripts(WindexStatement):
    def windex(self) -> str:
        scr = self.args[0]
        if ord(scr.op) == 0:
            return 'unfreeze-scripts'
        return fstat('freeze-scripts {0:script}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x60

        res = parse.parse('unfreeze-scripts', src)
        if res is not None:
            return cls(opcode, PBYTE(0))
        res = parse.parse('freeze-scripts {0}', src)
        if res is None:
            return None
        args = iter(res)
        addop, vargs = PARAMS([PBYTE])(args)
        opcode += addop

        return cls(opcode, *vargs)


@regop('o5_breakHere')
class BreakHere2(WindexStatement):
    def windex(self) -> BreakHere:
        return BreakHere()

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x80

        res = parse.parse('break-here', src)
        if res is None:
            return None
        return cls(opcode)


@regop('o5_endCutscene')
class EndCutScene(WindexStatement):
    def windex(self) -> str:
        return 'end-cut-scene'

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0xC0

        res = parse.parse('end-cut-scene', src)
        if res is None:
            return None
        return cls(opcode)


@regop('o5_putActor')
class PutActor(WindexStatement):
    def windex(self) -> str:
        return fstat('put-actor {0:object} at {1},{2}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x01
        res = parse.parse('put-actor {0} at {1},{2}', src)
        if res is None:
            return None
        addop, args = PARAMS([PBYTE, PWORD, PWORD])(iter(res))
        opcode += addop
        return cls(opcode, *args)


@regop('o5_startMusic')
class StartMusic(WindexStatement):
    def windex(self) -> str:
        return fstat('start-music {0:music}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x02

        res = parse.parse('start-music {0}', src)
        if res is None:
            return None
        addop, args = PARAMS([PBYTE])(iter(res))
        opcode += addop

        return cls(opcode, *args)


@regop('o5_chainScript')
class ChainScript(WindexStatement):
    def windex(self) -> str:
        return fstat(
            'chain-script {background}{recursive}{0:script} ({1:cvargs})',
            *self.args,
            background='',  # 'bak ' if op.opcode & 0x20 else ''
            recursive='',  # 'rec ' if op.opcode & 0x40 else ''
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x42

        res = parse.parse(
            'chain-script {bak:bak}{rec:rec}{0} ({vargs:vargs})',
            src,
            {'vargs': parse_vargs, 'bak': parse_bak, 'rec': parse_rec},
        )
        if res is None:
            return None
        assert not res['rec']
        assert not res['bak']
        addop, args = PARAMS([PBYTE])(iter(res))
        opcode += addop

        return cls(opcode, *args, res['vargs'])


@regop('o5_stopScript')
class StopScript(WindexStatement):
    def windex(self) -> str:
        return fstat('stop-script {0:script}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x62

        res = parse.parse('stop-script {0}', src)
        if res is None:
            return None
        addop, args = PARAMS([PBYTE])(iter(res))
        opcode += addop
        return cls(opcode, *args)


@regop('o5_getActorRoom')
class GetActorRoom(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = actor-room {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x03

        res = parse.parse('{0:var} = actor-room {1}', src, {'var': parse_var})
        if res is None:
            return None
        res = iter(res)
        var = next(res)
        addop, args = PARAMS([PBYTE])(res)
        opcode += addop
        return cls(opcode, var, *args)


@regop('o5_getActorY')
class GetActorY(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = actor-y {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x23

        res = parse.parse('{0:var} = actor-y {1}', src, {'var': parse_var})
        if res is None:
            return None
        res = iter(res)
        var = next(res)
        addop, args = PARAMS([PWORD])(res)
        opcode += addop
        return cls(opcode, var, *args)


@regop('o5_getActorX')
class GetActorX(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = actor-x {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x43

        res = parse.parse('{0:var} = actor-x {1}', src, {'var': parse_var})
        if res is None:
            return None
        res = iter(res)
        var = next(res)
        addop, args = PARAMS([PWORD])(res)
        opcode += addop
        return cls(opcode, var, *args)


@regop('o5_getActorFacing')
class GetActorFacing(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = actor-facing {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x63

        res = parse.parse('{0:var} = actor-facing {1}', src, {'var': parse_var})
        if res is None:
            return None
        res = iter(res)
        var = next(res)
        addop, args = PARAMS([PBYTE])(res)
        opcode += addop
        return cls(opcode, var, *args)


@regop('o5_isGreaterEqual')
class IsGreaterEqual(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('{0} <= {1}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x04

        res = parse.parse('if !({0:var} <= {1}) jump &[{jump:d}]', src, {'var': parse_var})
        if res is None:
            return None
        left = res[0]
        right = parse_value(res[1])
        if right is None:
            right = WordValue(int(res[1]).to_bytes(2, byteorder='little', signed=False))
        else:
            opcode += 0x80
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + len(right.to_bytes()) + 2
        return cls(opcode, left, right, RefOffset(target_off - endpos, endpos))


@regop('o5_isLess')
class IsLess(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('{0} > {1}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x44

        res = parse.parse('if !({left:var} > {right}) jump &[{jump:d}]', src, {'var': parse_var})
        if res is None:
            return None
        left = res['left']
        right = parse_value(res['right'])
        if right is None:
            right = WordValue(int(res['right']).to_bytes(2, byteorder='little', signed=False))
        else:
            opcode += 0x80
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + len(right.to_bytes()) + 2
        return cls(opcode, left, right, RefOffset(target_off - endpos, endpos))


@regop('o5_loadRoomWithEgo')
class LoadRoomWithEgo(WindexStatement):
    def windex(self) -> str:
        # windex:   come-out #161 in-room #13 walk-to #202,#202 (actual value #202,#116)
        #           come-out #1035 in-room #76
        # SCUMM refrence: come-out-door object-name in-room room-name [walk x-coord,y-coord]
        return fstat('come-out {0:object} in-room {1:room} walk-to {2},{3}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x24

        res = parse.parse('come-out {0} in-room {1} walk-to {2},{3}', src)
        if res is None:
            return None
        args = iter(res)
        addop, vargs = PARAMS([PWORD, PBYTE])(args)
        opcode += addop
        vargs.append(PWORD(next(args)))
        vargs.append(PWORD(next(args)))

        return cls(opcode, *vargs)


@regop('o5_drawObject')
class DrawObject(WindexStatement):
    def windex(self) -> str:
        obj, *args = self.args
        params = builder(
            {
                'AT': 'at {0},{1}',
                'STATE': 'image {0:state}',
            },
        )
        return fstat('draw-object {0:object} {params}', obj, params=params(args))

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x05

        mapping = {
            0x01: ('AT', 'at {0},{1}', (PARAMS([PWORD, PWORD]),)),
            0x02: ('STATE', 'image {0}', (PARAMS([PWORD]),)),
        }

        res = parse.parse('draw-object {0:S}{params:vargs}', src, {'vargs': parse_build})
        if res is None:
            return None
        obj = parse_value(res[0])
        if obj is None:
            obj = WordValue(int(res[0]).to_bytes(2, byteorder='little', signed=False))
        else:
            opcode += 0x80
        params = []
        if res['params']:
            for op, (name, fmt, arg_types) in mapping.items():
                xres = parse.parse(fmt, res['params'])
                if xres is not None:
                    args = iter(xres)
                    for arg_type in arg_types:
                        addop, addvargs = arg_type(args)
                        op += addop
                        params.append(SomeOp(name, op, 0, tuple(addvargs)))
                    break
        else:
            params.append(ByteValue(bytes([0xFF])))
        return cls(opcode, obj, *params)


@regop('o5_pickupObject')
class PickUpObject(WindexStatement):
    def windex(self) -> str:
        return fstat('pick-up-object {0:object} in-room {1:room}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x25

        res = parse.parse('pick-up-object {0} in-room {1}', src)
        if res is None:
            return None
        addop, args = PARAMS([PWORD, PBYTE])(iter(res))
        opcode += addop
        return cls(opcode, *args)


@regop('o5_getActorElevation')
class GetActorElevation(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = actor-elevation {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x06

        res = parse.parse('{0:var} = actor-elevation {1}', src, {'var': parse_var})
        if res is None:
            return None
        res = iter(res)
        var = next(res)
        addop, args = PARAMS([PBYTE])(res)
        opcode += addop
        return cls(opcode, var, *args)


@regop('o5_setVarRange')
class SetVarRange(WindexStatement):
    def windex(self) -> str:
        target, num, *rest = self.args
        assert len(rest) == num.op[0]
        values = ' '.join(value(val) for val in rest)
        return fstat('{0} = [{values}]', target, values=values)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x26

        res = parse.parse('{0:var} = [{values:svargs}]', src, {'var': parse_var, 'svargs': parse_svargs})
        if res is None:
            return None
        target = res[0]
        svargs = []
        vargs = [int(arg) for arg in res['values'].split()]
        svargs.append(ByteValue(bytes([len(vargs)])))
        if any(arg > 255 for arg in vargs):
            opcode += 0x80
            for val in vargs:
                svargs.append(WordValue(val.to_bytes(2, byteorder='little', signed=False)))
        else:
            for val in vargs:
                svargs.append(ByteValue(bytes([val])))
        return cls(opcode, target, *svargs)


@regop('o5_increment')
class Increment(WindexStatement):
    def windex(self) -> str:
        return fstat('++{0}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x46

        res = parse.parse('++{0}', src)
        if res is None:
            return None
        var = parse_value(res[0])
        return cls(opcode, var)


@regop('o5_decrement')
class Decrement(WindexStatement):
    def windex(self) -> str:
        return fstat('--{0}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0xC6

        res = parse.parse('--{var}', src)
        if res is None:
            return None
        var = parse_value(res['var'])
        return cls(opcode, var)


@regop('o5_setState')
class SetState(WindexStatement):
    def windex(self) -> str:
        return fstat('state-of {0:object} is {1:state}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x07

        res = parse.parse('state-of {0} is {1}', src)
        if res is None:
            return None
        res = iter(res)
        addop, vargs = PARAMS([PWORD, PBYTE])(res)
        opcode += addop

        return cls(opcode, *vargs)


@regop('o5_stringOps')
class StringOps(WindexStatement):
    def windex(self) -> str:
        return builder(
            {
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
            },
        )(self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x27

        mapping = {
            0x01: ('ASSIGN-STRING', '*{0} = {1:msg}', (PARAMS([PBYTE]), PMSG)),
            0x02: ('ASSIGN-STRING-VAR', '*{0} = *{1}', (PARAMS([PBYTE, PBYTE]),)),
            0x03: ('ASSIGN-INDEX', '*{0}[{1}] = {2}', (PARAMS([PBYTE, PBYTE, PBYTE]),)),
            0x04: ('ASSIGN-VAR', '{0} = *{1}[{2}]', (PVAR, PARAMS([PBYTE, PBYTE]))),
            0x05: ('STRING-INDEX', '*{0}[{1}]', (PARAMS([PBYTE, PBYTE]),)),
        }

        for op, (name, fmt, arg_types) in mapping.items():
            res = parse.parse(fmt, src, {'msg': parse_msg})
            if res is not None:
                vargs = []
                args = iter(res)
                for arg_type in arg_types:
                    addop, addvargs = arg_type(args)
                    op += addop
                    vargs.extend(addvargs)

                return cls(opcode, SomeOp(name, op, 0, tuple(vargs)))


def PBYTE(val):
    return ByteValue(bytes([int(val)]))


def PWORD(val):
    return WordValue(int(val).to_bytes(2, byteorder='little', signed=False))


def PMSG(args):
    msg = next(args)
    return 0, [CString(msg)]


def PVAR(args):
    return 0, [parse_value(next(args))]


def PARAMS(types):
    def inner(args):
        vargs = []
        addop = 0
        for atype, mask in zip(types, (0x80, 0x40, 0x20), strict=False):
            arg = next(args)
            parg = parse_value(arg)
            if parg is None:
                parg = atype(arg)
            else:
                addop += mask
            vargs.append(parg)
        return addop, vargs

    return inner


@regop('o5_getStringWidth')
class GetStringWidth(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = string-width {1:msg}', *self.args)


@regop('o5_isNotEqual')
class IsNotEqual(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('{0} is-not {1}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x88

        res = parse.parse('if !({left:var} is-not {right}) jump &[{jump:d}]', src, {'var': parse_var})
        if res is None:
            return None
        left = res['left']
        right = parse_value(res['right'])
        if right is None:
            right = WordValue(int(res['right']).to_bytes(2, byteorder='little', signed=False))
            opcode -= 0x80
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + len(right.to_bytes()) + 2
        return cls(opcode, left, right, RefOffset(target_off - endpos, endpos))


@regop('o5_equalZero')
class EqualZero(WindexStatement):
    def windex(self) -> ConditionalJump:
        var, offset = self.args
        return ConditionalJump(
            fstat('!{0}', var),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x28

        res = parse.parse('if !(!{expr:var}) jump &[{jump:d}]', src, {'var': parse_var})
        if res is None:
            return None
        expr = res['expr']
        assert expr is not None
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(expr.to_bytes()) + 2
        return cls(opcode, expr, RefOffset(target_off - endpos, endpos))


@regop('o5_notEqualZero')
class NotEqualZero(WindexStatement):
    def windex(self) -> ConditionalJump:
        var, offset = self.args
        return ConditionalJump(
            fstat('{0}', var),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0xA8

        res = parse.parse('if !({expr:var}) jump &[{jump:d}]', src, {'var': parse_var})
        if res is None:
            return None
        expr = res['expr']
        assert expr is not None
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(expr.to_bytes()) + 2
        return cls(opcode, expr, RefOffset(target_off - endpos, endpos))


def parse_value(name: str):
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
    from_def = next((k for k, v in defs.items() if v == name), None)
    if from_def is None:
        more = parse.parse('{base}[{num}]', name)
        if more is not None:
            name = more['base']
            more = more['num']
            from_def = next((k for k, v in defs.items() if v == more), None)
            if from_def is None:
                if more.startswith('V.'):
                    more = int(more[2:])
                    more = Variable(more)
                elif more.startswith('L.'):
                    # Local variable
                    more = int(more[2:])
                    more = Variable(more + 0x4000)
                else:
                    more = WordValue(int(more).to_bytes(2, byteorder='little', signed=False))
            else:
                more = Variable(from_def)
        if name.startswith('L.'):
            # Local variable
            num = int(name[2:])
            return Variable(num + 0x4000, more)
        if name.startswith('B.'):
            # Bit variable
            num = int(name[2:])
            return Variable(num + 0x8000, more)
        if name.startswith('V.'):
            # Variable
            num = int(name[2:])
            return Variable(num, more)
        return None
    return Variable(from_def)


@regop('o5_isEqual')
class IsEqual(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('{0} is {1}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        # Parse a string like "if !({0} is {1}) jump &[00000008]"
        # into a ConditionalJump object
        opcode = 0xC8

        res = parse.parse('if !({left:var} is {right}) jump &[{jump:d}]', src, {'var': parse_var})
        if res is None:
            return None
        left = res['left']
        right = parse_value(res['right'])
        if right is None:
            right = WordValue(int(res['right']).to_bytes(2, byteorder='little', signed=False))
            opcode -= 0x80
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + len(right.to_bytes()) + 2
        return cls(opcode, left, right, RefOffset(target_off - endpos, endpos))


@regop('o5_isScriptRunning')
class IsScriptRunning(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = script-running {1:script}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x68

        res = parse.parse('{0:var} = script-running {1}', src, {'var': parse_var})
        if res is None:
            return None
        var = res[0]
        scr = parse_value(res[1])
        if scr is None:
            scr = ByteValue(bytes([int(res[1])]))
        else:
            opcode += 0x80
        return cls(opcode, var, scr)


@regop('o5_faceActor')
class FaceActor(WindexStatement):
    def windex(self) -> str:
        # windex shows actor {} face-towards {}
        # SCUMM reference shows: do-animation actor-name face-towards actor-name
        return fstat('do-animation {0:object} face-towards {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x09

        res = parse.parse('do-animation {0} face-towards {1}', src)
        if res is None:
            return None
        addop, args = PARAMS([PBYTE, PWORD])(iter(res))
        opcode += addop
        return cls(opcode, *args)


@regop('o5_setOwnerOf')
class SetOwnerOf(WindexStatement):
    def windex(self) -> str:
        return fstat('owner-of {0:object} is {1:object}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x29

        res = parse.parse('owner-of {0} is {1}', src)
        if res is None:
            return None
        addop, args = PARAMS([PWORD, PBYTE])(iter(res))
        opcode += addop
        return cls(opcode, *args)


@regop('o5_startScript')
class StartScript(WindexStatement):
    def windex(self) -> str:
        return fstat(
            'start-script {background}{recursive}{0:script} ({1:cvargs})',
            *self.args,
            background='bak ' if self.opcode & 0x20 else '',
            recursive='rec ' if self.opcode & 0x40 else '',
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x0A

        res = parse.parse(
            'start-script {bak:bak}{rec:rec}{0} ({vargs:vargs})',
            src,
            {'vargs': parse_vargs, 'bak': parse_bak, 'rec': parse_rec},
        )
        if res is None:
            return None
        if res['bak']:
            opcode += 0x20
        if res['rec']:
            opcode += 0x40

        addop, args = PARAMS([PBYTE])(iter(res))
        opcode += addop

        return cls(opcode, *args, res['vargs'])


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
    return builder(
        {
            'SO_SAVE_VERBS': 'save-verbs {0} to {1} set {2}',
            'SO_RESTORE_VERBS': 'restore-verbs {0} to {1} set {2}',
        },
    )(op.args)


@regop('o5_resourceRoutines')
def o5_resourceRoutines_wd(op):
    return builder(
        {
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
        },
    )(op.args)


@regop('o5_cursorCommand')
def o5_cursorCommand_wd(op):
    return builder(
        {
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
        },
    )(op.args)


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
    rooms = ' '.join(value(val, sem='room') for val in rooms)
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
    return builder(
        {
            'SO_WAIT_FOR_ACTOR': 'wait-for-actor {0:object}',
            'SO_WAIT_FOR_MESSAGE': 'wait-for-message',
            'SO_WAIT_FOR_CAMERA': 'wait-for-camera',
            'SO_WAIT_FOR_SENTENCE': 'wait-for-sentence',
        },
    )(op.args)


@regop('o5_getObjectState')
def o5_getObjectState_wd(op):
    return fstat('{0} = state-of {1:object}', *op.args)


@regop('o5_getObjectOwner')
def o5_getObjectOwner_wd(op):
    return fstat('{0} = owner-of {1:object}', *op.args)


@regop('o5_matrixOps')
def o5_matrixOps_wd(op):
    return builder(
        {
            'SET-BOX-STATUS': 'set-box {0} to {1:box-status}',
            'SET-BOX-PATH': 'set-box-path',
        },
    )(op.args)


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
    params = builder(
        {
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
        },
    )

    return fstat('actor {0:object} {params}', actor, params=params(args))


@regop('o5_roomOps')
def o5_roomOps_wd(op, version=5):
    return builder(
        {
            'SO_ROOM_SCROLL': 'room-scroll {0} to {1}',
            'SO_ROOM_COLOR': 'room-color {0} in-slot {1}',
            'SO_ROOM_SCREEN': 'set-screen {0} to {1}',
            'SO_ROOM_PALETTE': 'palette {0} in-slot {1}'
            if version < 5
            else 'palette {0} {1} {2} in-slot {4}',
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
                'palette intensity {0} {1} {2} in-slot {4} to {5}'
            ),
            'SO_ROOM_SHADOW': (
                # windex displays empty string here for some reason
                # not found in SCUMM refrence, string is made up
                'room-shadow {0} {1} {2} in-slot {4} to {5}'
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
        },
    )(op.args)


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
            'say-line {0:object} {params}',
        ),
        actor,
        params=string_params(args),
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
    return builder(
        {
            'OFF': 'override off',
            'ON': 'override 1',
        },
    )(op.args)


@regop('o5_systemOps')
def o5_systemOps_wd(op):
    return builder(
        {
            'SO_RESTART': 'restart',
            'SO_PAUSE': 'pause',
            'SO_QUIT': 'quit',
        },
    )(op.args)


@regop('o5_printEgo')
def o5_printEgo_wd(op):
    return fstat('say-line {params}', params=string_params(op.args))


@regop('o5_isLessEqual')
class IsLessEqual(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('{0} >= {1}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x38

        res = parse.parse('if !({left} >= {right}) jump &[{jump:d}]', src)
        if res is None:
            return None
        left = parse_value(res['left'])
        right = parse_value(res['right'])
        if right is None:
            right = WordValue(int(res['right']).to_bytes(2, byteorder='little', signed=False))
        else:
            opcode += 0x80
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + len(right.to_bytes()) + 2
        return cls(opcode, left, right, RefOffset(target_off - endpos, endpos))


@regop('o5_isGreater')
class IsGreater(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('{0} < {1}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x78

        res = parse.parse('if !({left} < {right}) jump &[{jump:d}]', src)
        if res is None:
            return None
        left = parse_value(res['left'])
        right = parse_value(res['right'])
        if right is None:
            right = WordValue(int(res['right']).to_bytes(2, byteorder='little', signed=False))
        else:
            opcode += 0x80
        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + len(right.to_bytes()) + 2
        return cls(opcode, left, right, RefOffset(target_off - endpos, endpos))


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
    params = builder(
        {
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
        },
    )

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
class IfClassOfIs(WindexStatement):
    def windex(self) -> ConditionalJump:
        *args, offset = self.args
        return ConditionalJump(
            fstat('class-of {0:object} is {1:svargs}', *args),
            offset,
        )

    @classmethod
    def parse(cls, base_off: int, src: str):
        # Parse a string like "if !({0} is {1}) jump &[00000008]"
        # into a ConditionalJump object
        opcode = 0x9D

        res = parse.parse('if !(class-of {0} is {1:svargs}) jump &[{jump:d}]', src, {'svargs': parse_svargs})
        if res is None:
            return None
        left = parse_value(res[0])
        if left is None:
            left = WordValue(int(res[0]).to_bytes(2, byteorder='little', signed=False))
            opcode -= 0x80
        svargs = []
        args = [arg.strip() for arg in res[1].split() if arg.strip()]
        for arg in args:
            parg = parse_value(arg)
            if parg is None:
                parg = WordValue(int(arg).to_bytes(2, byteorder='little', signed=False))
                svargs.append(SomeOp('ARG', 0x01, 0, (parg,)))
            else:
                svargs.append(SomeOp('ARG', 0x81, 0, (parg,)))
        svargs.append(ByteValue(bytes([0xFF])))

        target_off = int(res['jump']) - 8
        endpos = base_off + 1 + len(left.to_bytes()) + sum(len(varg.to_bytes()) for varg in svargs) + 2
        return cls(opcode, left, VarArgs(svargs), RefOffset(target_off - endpos, endpos))


@regop('o5_findInventory')
class FindInventory(WindexStatement):
    def windex(self) -> str:
        return fstat('{0} = find-inventory {1},{2}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x3D

        res = parse.parse('{0:var} = find-inventory {1},{2}', src, {'var': parse_var})
        if res is None:
            return None
        args = iter(res)
        var = next(args)
        addop, vargs = PARAMS([PBYTE, PBYTE])(args)
        opcode += addop

        return cls(opcode, var, *vargs)


@regop('o5_setClass')
class SetClass(WindexStatement):
    def windex(self) -> str:
        return fstat('class-of {0:object} is {1:svargs}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0xDD

        res = parse.parse('class-of {0} is {1:svargs}', src, {'svargs': parse_svargs})
        if res is None:
            return None
        left = parse_value(res[0])
        if left is None:
            left = WordValue(int(res[0]).to_bytes(2, byteorder='little', signed=False))
            opcode -= 0x80
        svargs = []
        args = [arg.strip() for arg in res[1].split() if arg.strip()]
        for arg in args:
            parg = parse_value(arg)
            if parg is None:
                parg = WordValue(int(arg).to_bytes(2, byteorder='little', signed=False))
                svargs.append(SomeOp('ARG', 0x01, 0, (parg,)))
            else:
                svargs.append(SomeOp('ARG', 0x81, 0, (parg,)))
        svargs.append(ByteValue(bytes([0xFF])))
        return cls(opcode, left, VarArgs(svargs))


@regop('o5_walkActorTo')
class WalkActorTo(WindexStatement):
    def windex(self) -> str:
        return fstat('walk {0:object} to {1},{2}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x1E

        res = parse.parse('walk {0} to {1},{2}', src)
        if res is None:
            return None
        args = iter(res)
        addop, vargs = PARAMS([PBYTE, PWORD, PWORD])(args)
        opcode += addop

        return cls(opcode, *vargs)


@regop('o5_drawBox')
class DrawBox(WindexStatement):
    def windex(self) -> str:
        return fstat('draw-box {0},{1} to {3},{4} color {5:color}', *self.args)

    @classmethod
    def parse(cls, base_off: int, src: str):
        opcode = 0x3F

        res = parse.parse('draw-box {0},{1} to {2},{3} color {4}', src)
        if res is None:
            return None
        args = iter(res)
        addop, vargs = PARAMS([PWORD, PWORD])(args)
        opcode += addop

        addop, vargs2 = PARAMS([PWORD, PWORD, PBYTE])(args)
        vargs.append(PBYTE(5 + addop))
        vargs.extend(vargs2)

        return cls(opcode, *vargs)


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
                    seq.append(
                        ConditionalJump(
                            st.expr.replace(f'{value(complex_temp)}', complex_value),
                            st.ref,
                        ),
                    )
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
        for label, seq in asts.items():
            for st in seq:
                print('============')
                options = set()
                for op, func in ops.items():
                    if isinstance(func, type) and issubclass(func, WindexStatement):
                        if not getattr(func, 'parse', None):
                            continue
                        x = func.parse(0, str(st))
                        if x is not None:
                            print('WORKS', op, func, repr(st), '->', repr(x))
                            options.add(x)
                options = {x for x in options if x is not None}
                assert len(options) <= 1, options
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
                        assert ext == ex, (ext, ex)
                        if [str(st) for st in asts[label]] == [
                            'break-here',
                        ] and isinstance(ex, ConditionalJump):
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


def semantic_key(name, sem=None):
    if USE_SEMANTIC_CONTEXT and sem:
        return f'{sem}-{name}'
    return str(name)


def make_block_context(elem, gid):
    respath_comment = f'; {elem.tag} {elem.attribs["path"]}'
    titles = {
        'LSCR': 'script',
        'SCRP': 'script',
        'ENCD': 'enter',
        'EXCD': 'exit',
        'OBCD': 'object',
    }
    gid_str = '' if gid is None else f' {semantic_key(gid, titles[elem.tag])}'
    yield ' '.join([f'{titles[elem.tag]}{gid_str}', '{', respath_comment])
    if elem.tag == 'OBCD':
        yield ' '.join(['\tname is', f'"{obj_names[gid]}"'])


def get_elem_info(elem):
    obcd = None
    gid = elem.attribs['gid']
    if elem.tag == 'OBCD':
        obcd = elem
        elem = sputm.find('VERB', obcd)
    pref, script_data = script_map[elem.tag](elem.data)
    entries = {}
    if elem.tag == 'VERB':
        obj_names[gid] = msg_to_print(bytes(sputm.find('OBNA', obcd).data).split(b'\0', maxsplit=1)[0])
        pref = list(parse_verb_meta(pref))
        entries_dict = defaultdict(list)
        for idx, off in pref:
            entries_dict[off].append(idx[0])
        entries = dict(entries_dict)
    else:
        scr_id = int.from_bytes(pref, byteorder='little', signed=False) if pref else None
        assert scr_id is None or scr_id == gid
    return script_data, gid, entries


def destr(func):
    def inner(stat):
        if isinstance(func, type) and issubclass(func, WindexStatement):
            return func(stat.opcode, *stat.args)
        return func(stat)

    return inner


def decompile_script(elem, transform=True):
    script_data, gid, entries = get_elem_info(elem)
    yield from make_block_context(elem, gid)
    indent = '\t'
    bytecode = descumm_iter(script_data, OPCODES_v5, base_offset=8)

    hrefs = set()
    srefs = {0}
    asts = deque()
    res = None
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
            # TODO: in FOA - room 12, object 159, verb 80 jumps to a ref on verb 12
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
            verbs = ' '.join(semantic_key(verb, sem="verb") for verb in entries[off + 8])
            yield f'\tverb {verbs} {{'
            indent = 2 * '\t'
        if isinstance(res, ConditionalJump) or isinstance(res, UnconditionalJump):
            srefs.add(off)
        try:
            res = destr(ops.get(stat.name, str))(stat) or stat
        except Exception as exc:
            raise ScriptError(
                exc,
                elem.attribs['path'],
                dict(realize_refs(srefs, hrefs, asts)),
                stat,
                None,
            ) from exc
        # if isinstance(res, WindexStatement):
        #     wx = res.windex()
        #     # print(str(wx))
        #     parsed = res.parse(stat.offset, str(wx))
        #     # assert repr(parsed) == repr(res), (repr(parsed), repr(res), stat.to_bytes())
        #     assert parsed.windex() == wx, (repr(parsed), repr(res), stat.to_bytes())

        #     print(f'{wx}')
        #     if parsed.to_bytes() != stat.to_bytes():
        #         print('Warning: parsed statement does not match original bytecode:')
        #         print(f'\t{parsed!r} != {res!r}')
        #         print(f'\t{parsed.to_bytes()} != {stat.to_bytes()}')
        #     res = wx
        asts.append((off, res))
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


if __name__ == '__main__':
    import argparse

    from nutcracker.sputm.tree import open_game_resource
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
            SCHEMA,
            {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map},
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
            room_no = rnam.get(room.attribs['gid'], f'room_{room.attribs["gid"]}')
            print(
                '==========================',
                room.attribs['path'],
                room_no,
            )
            fname = f'{script_dir}/{room.attribs["gid"]:04d}_{room_no}.scu'

            with open(fname, 'w') as f:
                dump_script_file(room_no, room, decompile_script, f)

    if USE_SEMANTIC_CONTEXT:
        with open(f'{script_dir}/sem.def', 'w') as f:
            for sem, vals in semlog.items():
                for val in sorted(vals.keys()):
                    semval = semlog[sem][val]
                    if not semval:
                        continue
                    print(f'define {semval} = {val}', file=f)
                print(file=f)
