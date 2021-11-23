import io
import json
from collections import deque
from string import printable
from typing import Iterable, Optional
from nutcracker.kernel.element import Element
from nutcracker.sputm.script.parser import CString, DWordValue

from nutcracker.sputm.tree import narrow_schema
from nutcracker.sputm.schema import SCHEMA

from nutcracker.sputm.script.bytecode import get_scripts, script_map, descumm
from nutcracker.sputm.script.opcodes import ByteValue, RefOffset, WordValue


class Value:

    suffix = {
        ByteValue: 'B',
        WordValue: 'W',
        DWordValue: 'D',
    }

    def __init__(self, orig):
        self.orig = orig
        self.num = int.from_bytes(orig.op, byteorder='little', signed=False)
        self.cast = None

    def __repr__(self):
        if self.cast == 'char':
            return f"'{chr(self.num)}'"
        suffix = self.suffix[type(self.orig)]
        return f'{self.num}'

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
def get_var(orig):
    while isinstance(orig, Dup):
        orig = orig.orig
    key = (type(orig), Value(orig).num)
    if not key in g_vars:
        g_vars[key] = Variable(orig)
    # print(g_vars)
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
    return json.dumps(msg_to_print(arg.msg))


def adr(arg):
    return f"&[{arg.abs + 8:08d}]"


ops = {'_strings': deque()}


def regop(op):
    ops[op.__name__] = op


def defop(op, stack, bytecode):
    raise NotImplementedError(f'{op} <{stack}>')
    return f'{op} <{stack}>'



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
    return f'if !( {stack.pop()} ) jump {adr(off)}'


@regop
def o6_if(op, stack, bytecode):
    off, *rest = op.args
    assert not rest
    return f'if ( {stack.pop()} ) jump {adr(off)}'

@regop
def o6_jump(op, stack, bytecode):
    off, *rest = op.args
    assert not rest
    return f'jump {adr(off)}'


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
    return f'start-script [{flags}] {scr}{param_str}'


@regop
def o72_startScript(op, stack, bytecode):
    assert len(op.args) == 1 and isinstance(op.args[0], ByteValue), op.args
    params = get_params(stack)
    param_str = ", ".join(str(param) for param in params)
    if param_str:
        param_str = f' ( {param_str} )'
    return f'start-script [{Value(op.args[0])}] {stack.pop()}{param_str}'


@regop
def o6_stopScript(op, stack, bytecode):
    return f'stop-script {stack.pop()}'


@regop
def o72_arrayOps(op, stack, bytecode):
    sub = Value(op.args[0])
    arr = get_var(op.args[1])
    if sub.num == 7:
        string = ops['_strings'].pop() if (arrs := stack.pop()).num == (2 ** 16) - 1 else arrs
        arr.cast = 'string'
        return f'{arr} = {string}'
    if sub.num == 194: # Formatted string
        num_params = stack.pop().num + 1
        params = [stack.pop() for _ in range(num_params)]
        string = ops['_strings'].pop() if (arrs := stack.pop()).num == (2 ** 16) - 1 else arrs
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
    defop(op, stack, bytecode)


@regop
def o6_isAnyOf(op, stack, bytecode):
    params = get_params(stack)
    var = stack.pop()
    cast = getattr(var, 'cast', None)
    if cast:
        for param in params:
            param.cast = cast
    stack.append(f'{var} in [{", ".join(str(param) for param in params)}]')


@regop
def o72_isAnyOf(op, stack, bytecode):
    params = get_params(stack)
    var = stack.pop()
    cast = getattr(var, 'cast', None)
    if cast:
        for param in params:
            param.cast = cast
    stack.append(f'$ {var} in [{", ".join(str(param) for param in params)}]')


@regop
def o6_stopObjectCode(op, stack, bytecode):
    return '; end-object-code'


@regop
def o72_getScriptString(op, stack, bytecode):
    ops['_strings'].append(KeyString(op.args[0]))


@regop
def o72_readINI(op, stack, bytecode):
    sub = Value(op.args[0])
    arr = stack.pop()
    string = ops['_strings'].pop() if arr.num == (2 ** 16) - 1 else arr
    if sub.num == 6:
        stack.append(Caster(f'read-ini number {string}', cast='number'))
    elif sub.num == 7:
        stack.append(Caster(f'read-ini string {string}', cast='string'))
    # raise NotImplementedError(op.args)


@regop
def o72_writeINI(op, stack, bytecode):
    sub = Value(op.args[0])
    if sub.num == 6:
        value = stack.pop()
        option = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
        return f'write-ini {option} {value}'
    if sub.num == 7:
        value = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
        option = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
        return f'write-ini {option} {value}'
    defop(op, stack, bytecode)


@regop
def o72_rename(op, stack, bytecode):
    target = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    source = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    return f'$ rename-file {source} to {target}'


@regop
def o72_debugInput(op, stack, bytecode):
    string = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    return f'$ debug-input {string}'


@regop
def o72_traceStatus(op, stack, bytecode):
    string = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    return f'$ trace-status {string} {stack.pop()}'


def printer(action, op, stack):
    cmd = Value(op.args[0])
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
    if cmd.num == 249:
        return f'\tcolors {get_params(stack)} \\'
    if cmd.num == 254:
        return f'{action} \\'
    if cmd.num == 255:
        return f'\tdefault'
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
    return f'$ talk {act} {msg_val(op.args[0])}'


@regop
def o72_talkEgo(op, stack, bytecode):
    return f'$ talk {msg_val(op.args[0])}'


@regop
def o6_talkActor(op, stack, bytecode):
    act = stack.pop()
    return f'$ talk {act} {msg_val(op.args[0])}'


@regop
def o6_talkEgo(op, stack, bytecode):
    # with io.BytesIO(b'\x09\x00') as stream:
    #     stack.append(get_var(WordValue(stream)))
    return f'$ talk {msg_val(op.args[0])}'


@regop
def o71_getStringWidth(op, stack, bytecode):
    ln = stack.pop()
    pos = stack.pop()
    array = stack.pop()
    stack.append(f'$ string-width {array} {pos} {ln}')


@regop
def o6_beginOverride(op, stack, bytecode):
    return f'override'


@regop
def o72_createDirectory(op, stack, bytecode):
    string = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    return f'$ mkdir {string}'


@regop
def o72_deleteFile(op, stack, bytecode):
    string = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    return f'$ delete-file {string}'

@regop
def o72_dimArray(op, stack, bytecode):
    cmd = Value(op.args[0])
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
def o70_isResourceLoaded(op, stack, bytecode):
    types = {
        18: 'image',
        226: 'room',
        227: 'costume',
        228: 'sound',
        229: 'script'
    }
    sub = Value(op.args[0])
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
    return f'$ sound-kludge {param_str}'


@regop
def o6_cutscene(op, stack, bytecode):
    params = get_params(stack)
    param_str = " ".join(str(param) for param in params)
    return f'$ start-cut-scene ({param_str})'


@regop
def o6_endCutscene(op, stack, bytecode):
    return '; end-cut-scene'


@regop
def o6_startSound(op, stack, bytecode):
    return f'start-sound {stack.pop()}'


@regop
def o70_soundOps(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 9:
        return f'$ sfx soft-on'
    if cmd.num == 232:
        return f'$ start-sfx {stack.pop()}'
    if cmd.num == 230:
        return f'$ sfx-channel {stack.pop()}'
    if cmd.num == 231:
        return f'$ sfx-offset {stack.pop()}'
    if cmd.num == 245:
        return f'$ loop-sfx'
    if cmd.num == 255:
        return f'$ stop-sfx'
    defop(op, stack, bytecode)


@regop
def o71_kernelSetFunctions(op, stack, bytecode):
    params = get_params(stack)
    if params[0].num == 1:
        return f'$ restore-background {" ".join(params[1:])}'
    if params[0].num == 23:
        return f'$ clear-charset-mask'
    raise ValueError(params)

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
def o6_roomOps(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 172:
        x2 = stack.pop()
        x1 = stack.pop()
        return f'room-scroll is {x1} {x2}'
    if cmd.num == 174:
        h = stack.pop()
        b = stack.pop()
        return f'$ room-screens {b} {h}'
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
    if cmd.num == 181:
        return f'fades {stack.pop()}'
    if cmd.num == 213:
        return f'$ room-color is {stack.pop()}'
    defop(op, stack, bytecode)


@regop
def o72_roomOps(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 172:
        x2 = stack.pop()
        x1 = stack.pop()
        return f'room-scroll is {x1} {x2}'
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
        savegame = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
        action = options[stack.pop().num]
        return f'$ {action}-game {savegame}'
    if cmd.num == 234:
        a = stack.pop()
        b = stack.pop()
        return f'$ palette {b} in-slot {a}'
    defop(op, stack, bytecode)


@regop
def o6_actorFollowCamera(op, stack, bytecode):
    return f'camera-follow {stack.pop()}'


@regop
def o70_pickupObject(op, stack, bytecode):
    room = stack.pop()
    obj = stack.pop()
    return f'pick-up-object {obj} in {room}'



@regop
def o6_getActorMoving(op, stack, bytecode):
    stack.append(f'actor-moving {stack.pop()}')


@regop
def o6_getOwner(op, stack, bytecode):
    stack.append(f'owner-of {stack.pop()}')


@regop
def o6_setOwner(op, stack, bytecode):
    act = stack.pop()
    obj = stack.pop()
    return f'owner-of {obj} is {act}'


@regop
def o80_cursorCommand(op, stack, bytecode):
    cmd = Value(op.args[0])
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
        return f'set-cursor-image {stack.pop()}'
    elif cmd.num == 0x9A:
        return f'set-cursor-hotspot {stack.pop()} {stack.pop()}'
    elif cmd.num == 0x9C:
        return f'init-charset {stack.pop()}'
    elif cmd.num == 0x9D:
        params = get_params(stack)
        return f'charset-color {params}'
    defop(op, stack, bytecode)


@regop
def o72_printWizImage(op, stack, bytecode):
    return f'$ print-wiz-image {stack.pop()}'


@regop
def o6_cursorCommand(op, stack, bytecode):
    cmd = Value(op.args[0])
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
        return f'set-cursor-image {stack.pop()}'
    elif cmd.num == 0x9A:
        return f'set-cursor-hotspot {stack.pop()} {stack.pop()}'
    elif cmd.num == 0x9C:
        return f'init-charset {stack.pop()}'
    elif cmd.num == 0x9D:
        params = get_params(stack)
        return f'charset-color {params}'
    elif cmd.num == 0xD6:
        return f'set-cursor-transparent-color {stack.pop()}'
    defop(op, stack, bytecode)


def to_signed(arg):
    if isinstance(arg, Value):
        if isinstance(arg.orig, WordValue):
            n = arg.num
            n = n & 0xffff
            return (n ^ 0x8000) - 0x8000
        if isinstance(arg.orig, ByteValue):
            n = arg.num
            n = n & 0xff
            return (n ^ 0x80) - 0x80
    return arg


@regop
def o6_actorOps(op, stack, bytecode):
    cmd = Value(op.args[0])
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
        return f'\televation {to_signed(stack.pop())}'
    # TODO: 85 animation default - no pops
    if cmd.num == 86:
        new_color = stack.pop()
        old_color = stack.pop()
        return f'\tcolor {old_color} is {new_color}'
    if cmd.num == 87:
        color = stack.pop()
        return f'\ttalk-color {color} \\'
    if cmd.num == 88:
        return f'\tname {msg_val(op.args[1])}'
    # TODO: 89 - init-animation - 1 pop
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
    defop(op, stack, bytecode)

@regop
def o72_actorOps(op, stack, bytecode):
    cmd = Value(op.args[0])
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
        arr = stack.pop()
        string = ops['_strings'].pop() if arr.num == (2 ** 16) - 1 else arr
        slot = stack.pop()
        return f'\tsay {slot} {string}\\'
    return o6_actorOps(op, stack, bytecode)


@regop
def o72_resetCutscene(op, stack, bytecode):
    return '$ reset-cut-scene'


@regop
def o90_setSpriteInfo(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 37:
        return f'\tgroup {stack.pop()}'
    if cmd.num == 43:
        return f'\tpriority {stack.pop()}'
    if cmd.num == 44:
        ypos = stack.pop()
        xpos = stack.pop()
        return f'\tmove {to_signed(xpos)},{to_signed(ypos)}'
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
    defop(op, stack, bytecode)


@regop
def o90_setSpriteGroupInfo(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 44:
        dy = stack.pop()
        dx = stack.pop()
        return f'\tmove {to_signed(dx)},{to_signed(dy)}'
    if cmd.num == 57:
        return f'$ sprite-group {stack.pop()} \\'
    if cmd.num == 67:
        bottom = stack.pop()
        right = stack.pop()
        top = stack.pop()
        left = stack.pop()
        return f'\tbox {left},{top} to {right},{bottom}'
    defop(op, stack, bytecode)


@regop
def o90_getSpriteInfo(op, stack, bytecode):
    sub = Value(op.args[0])
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
    defop(op, stack, bytecode)


@regop
def o80_drawLine(op, stack, bytecode):
    step = stack.pop()
    id = stack.pop()
    y = stack.pop()
    x = stack.pop()
    y1 = stack.pop()
    x1 = stack.pop()
    sub = Value(op.args[0])
    return f'$ draw-line {sub} {x1},{y1} to {x},{y} {id} {step}'


@regop
def o90_floodFill(op, stack, bytecode):
    sub = Value(op.args[0])
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
    defop(op, stack, bytecode)


@regop
def o6_getAnimateVariable(op, stack, barcode):
    var = stack.pop()
    act = stack.pop()
    stack.append(f'$ actor-animation-var {act} {var}')


@regop
def o6_animateActor(op, stack, barcode):
    chore = stack.pop()
    act = stack.pop()
    return f'do-animation {act} {chore}'


@regop
def o80_readConfigFile(op, stack, bytecode):
    cmd = Value(op.args[0])
    option = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    section = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    filename = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    if cmd.num == 6:
        stack.append(Caster(f'read-ini [number] {filename} {section} {option}', cast='number'))
        return
    defop(op, stack, bytecode)


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
    scale = stack.pop()
    ypos = stack.pop()
    xpos = stack.pop()
    obj = stack.pop()
    return f'stamp-object {obj} at {xpos},{ypos} scale {scale}'




@regop
def o72_redimArray(op, stack, bytecode):
    cmd = Value(op.args[0])
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
    cmd = Value(op.args[0])
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
    defop(op, stack, bytecode)


@regop
def o72_drawWizImage(op, stack, bytecode):
    flags = stack.pop()
    x1 = stack.pop()
    y1 = stack.pop()
    res = stack.pop()
    return f'$ draw-wiz-image {res} at {x1},{y1} flags {flags}'


@regop
def o90_wizImageOps(op, stack, bytecode):
    cmd = Value(op.args[0])
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
        return f'\tdraw'
    defop(op, stack, bytecode)


@regop
def o6_delayFrames(op, stack, bytecode):
    return f'$ sleep-for {stack.pop()} frames'


@regop
def o6_delayMinutes(op, stack, bytecode):
    return f'$ sleep-for {stack.pop()} minutes'


@regop
def o6_delay(op, stack, bytecode):
    return f'$ sleep-for {stack.pop()} jiffies'


@regop
def o6_delaySeconds(op, stack, bytecode):
    return f'$ sleep-for {stack.pop()} seconds'


@regop
def o6_wait(op, stack, bytecode):
    sub = Value(op.args[0])
    if sub.num == 168:
        return f'wait-for-actor {stack.pop()} [ref {adr(op.args[1])}]'
    if sub.num == 169:
        return 'wait-for-message'
    if sub.num == 170:
        return 'wait-for-camera'
    defop(op, stack, bytecode)


@regop
def o72_setTimer(op, stack, bytecode):
    cmd = Value(op.args[0])
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
    cmd = Value(op.args[0])
    stack.append(f'$ get-timer {stack.pop()} {cmd}')


@regop
def o72_systemOps(op, stack, bytecode):
    cmd = Value(op.args[0])
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
    defop(op, stack, bytecode)


@regop
def o72_setSystemMessage(op, stack, bytecode):
    sub = Value(op.args[0])
    arr = stack.pop()
    string = ops['_strings'].pop() if arr.num == (2 ** 16) - 1 else arr
    if sub.num == 243:
        return f'$ window-title {string}'
    # raise NotImplementedError(op.args)


@regop
def o6_resourceRoutines(op, stack, bytecode):
    cmd = Value(op.args[0])
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
    defop(op, stack, bytecode) 


@regop
def o70_resourceRoutines(op, stack, bytecode):
    cmd = Value(op.args[0])
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
    defop(op, stack, bytecode)


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
def o80_pickVarRandom(op, stack, bytecode):
    params = get_params(stack)
    value = Value(op.args[0])
    stack.append(f'$ pick-random {value} of {params}')



@regop
def o6_pickOneOf(op, stack, bytecode):
    params = get_params(stack)
    value = stack.pop()
    stack.append(f'pick ({value}) of {params}')


@regop
def o6_pickOneOfDefault(op, stack, bytecode):
    default = stack.pop()
    params = get_params(stack)
    value = stack.pop()
    stack.append(f'pick ({value}) of {params} default {default}')


@regop
def o6_shuffle(op, stack, bytecode):
    end = stack.pop()
    start = stack.pop()
    arr = get_var(op.args[0])
    return f'array-shuffle {arr}[{start}] to {arr}[{end}]'


@regop
def o72_getResourceSize(op, stack, bytecode):
    res = stack.pop()
    cmd = Value(op.args[0])
    if cmd.num == 13:
        stack.append(f'$ size-of sfx {res}')
        return
    defop(op, stack, bytecode)


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
    return 'stop-sentence'


@regop
def o6_getVerbEntrypoint(op, stack, bytecode):
    verb = stack.pop()
    obj = stack.pop()
    stack.append(f'$ valid-verb {obj}, {verb}')


@regop
def o6_getObjectOldDir(op, stack, bytecode):
    obj = stack.pop()
    stack.append(f'$ object-direction-old {obj}')

@regop
def o70_getActorRoom(op, stack, bytecode):
    stack.append(f'actor-room {stack.pop()}')


@regop
def o71_polygonHit(op, stack, bytecode):
    ypos = stack.pop()
    xpos = stack.pop()
    stack.append(f'$ polygon-hit {xpos} {ypos}')


@regop
def o72_jumpToScript(op, stack, bytecode):
    params = get_params(stack)
    flags = Value(op.args[0])
    return f'$ call-script [{flags}] {params}'


@regop
def o60_closeFile(op, stack, bytecode):
    return f'$ close-file {stack.pop()}'


@regop
def o72_openFile(op, stack, bytecode):
    modes = {
        1: 'read',
        2: 'write',
        6: 'append',
    }
    mode = modes[stack.pop().num]
    string = ops['_strings'].pop() if (arr := stack.pop()).num == (2 ** 16) - 1 else arr
    stack.append(f'$ open-file {mode} {string}')


@regop
def o72_writeFile(op, stack, bytecode):
    res = stack.pop()
    slot = stack.pop()
    sub = Value(op.args[0])
    if sub.num == 8:
        return f'$ write-file {Value(op.args[1])} {slot} {res}'


@regop
def o72_readFile(op, stack, bytecode):
    sub = Value(op.args[0])
    if sub.num == 8:
        size = stack.pop()
        slot = stack.pop()
        stack.append(f'$ read-file {Value(op.args[1])} {slot} ( {size} )')
        return
    defop(op, stack, bytecode)


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
    return f'$ seek-file {slot} {offset} {mode}'


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
def o72_findAllObjects(op, stack, bytecode):
    stack.append(f'find-all-objects {stack.pop()}')


@regop
def o6_putActorAtXY(op, stack, bytecode):
    room = stack.pop()
    ypos = stack.pop()
    xpos = stack.pop()
    act = stack.pop()
    room = '' if room == 0 else f' in room {room}'
    return f'$ put-actor {act} at {xpos},{ypos}{room}'

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
    stack.append(f'start-script rec {scr}{param_str}')


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
    sub = Value(op.args[0])
    arr = get_var(op.args[1])
    if sub.num == 1:
        stack.append(f'$ array-dimension-base {arr}')
        return
    defop(op, stack, bytecode)


@regop
def o80_getSoundVar(op, stack, bytecode):
    var = stack.pop()
    sound = stack.pop()
    stack.append(f'$ sfx-var {sound} {var}')


@regop
def o6_getActorCostume(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-costume {act}')

@regop
def o6_getActorElevation(op, stack, bytecode):
    act = stack.pop()
    stack.append(f'actor-elevation {act}')


@regop
def o60_localizeArrayToScript(op, stack, bytecode):
    return f'$ localize-array {stack.pop()}'

@regop
def o71_polygonOps(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 247:
        to = stack.pop()
        src = stack.pop()
        return f'$ erase-polygon from {src} to {to}'
    if cmd.num == 248:
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
    defop(op, stack, bytecode)


@regop
def o72_drawObject(op, stack, bytecode):
    cmd = Value(op.args[0])
    if cmd.num == 62:
        state = stack.pop()
        y = stack.pop()
        x = stack.pop()
        return f'$ draw-object state at {x},{y} state {stack.pop()}'
    if cmd.num == 63:
        return f'$ draw-object state {stack.pop()}'
    defop(op, stack, bytecode)

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
    cmd = Value(op.args[0])
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
    defop(op, stack, bytecode)


@regop
def o6_walkActorTo(op, stack, bytecode):
    # walk actor-name to x-coord,y-coord
    # walk actor-name to actor-name within number
    # walk actor-name to-object object-name
    dist = stack.pop()
    obj = stack.pop()
    act = stack.pop()
    return f'walk {act} to-object {obj} within {dist}'


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


obj_names = {}

if __name__ == '__main__':
    import argparse
    import os

    from nutcracker.utils.fileio import read_file
    from nutcracker.utils.libio import suppress_stdout

    from nutcracker.sputm.tree import open_game_resource, narrow_schema
    from nutcracker.sputm.schema import SCHEMA
    from nutcracker.sputm.preset import sputm
    from nutcracker.sputm.strings import get_optable

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('-v', '--verbose', action='count', help='output every opcode')
    args = parser.parse_args()

    filename = args.filename

    with suppress_stdout():
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

            with open(fname, 'w') as f:
                for elem in get_scripts(room):
                    # if elem.attribs['path'] != 'LECF_0001\\LFLF_0001\\RMDA_0001\\LSCR_0202':
                    #     continue
                    pref, script_data = script_map[elem.tag](elem.data)
                    obj_id = None
                    indent = '\t'
                    if elem.tag == 'VERB':
                        pref = list(parse_verb_meta(pref))
                        obcd = get_element_by_path(os.path.dirname(elem.attribs['path']), room)
                        obj_id = obcd.attribs['gid']
                        obj_names[obj_id] = sputm.find('OBNA', obcd).data.split(b'\0')[0].decode()
                    print(';', elem.tag, elem.attribs['path'], file=f)
                    titles = {
                        'LSC2': 'script',
                        'LSCR': 'script',
                        'SCRP': 'script',
                        'ENCD': 'enter',
                        'EXCD': 'exit',
                        'VERB': 'verb',
                    }
                    if elem.tag == 'VERB':
                        print(f'object', obj_id, '{', file=f)
                        print(f'\tname is', f'"{obj_names[obj_id]}"', file=f)
                    else:
                        print(titles[elem.tag], list(pref), '{', file=f)
                    bytecode = descumm(script_data, get_optable(gameres.game))
                    # print_bytecode(bytecode)

                    refs = [off.abs for stat in bytecode.values() for off in stat.args if isinstance(off, RefOffset)]

                    stack = deque(
                        # ['**ERROR**'] * 3
                    )
                    if elem.tag == 'VERB':
                        entries = {off: idx[0] for idx, off in pref}
                    for off, stat in bytecode.items():
                        if elem.tag == 'VERB' and off + 8 in entries:
                            if off + 8 > min(entries.keys()):
                                print('\t}', file=f)
                            print('\n\tverb', entries[off + 8], '{', file=f)
                            indent = 2 * '\t'
                            stack.clear()
                        if args.verbose:
                            print(
                                f'[{stat.offset + 8:08d}]',
                                '\t\t\t\t\t\t\t\t',
                                f'{stat} <{list(stack)}>',
                                file=f,
                            )
                        res = ops.get(stat.name, defop)(stat, stack, bytecode)
                        if off in refs:
                            print(
                                f'[{stat.offset + 8:08d}]:',
                                file=f
                            )
                        if res:
                            print(
                                # f'[{stat.offset + 8:08d}]',
                                f'{indent}{res}',
                                # res,
                                # '\t\t\t\t',
                                # defop(stat, stack, bytecode),
                                file=f,
                            )
                    if elem.tag == 'VERB' and entries:
                        print('\t}', file=f)
                    print('}\n', file=f)
