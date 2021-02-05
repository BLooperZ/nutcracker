from collections import deque

from nutcracker.utils.funcutils import flatten
from .script.bytecode import get_scripts, descumm, script_map
from .script.opcodes import OPCODES_v6

ops = {}


def regop(op):
    ops[op.__name__] = op


@regop
def o6_cursorCommand(op, stack, bytecode):
    byte, *rest = op.args
    assert not rest
    sub = ord(byte.op)
    if sub == 0x90:
        print('cursor on')
    elif sub == 0x91:
        print('cursor off')
    elif sub == 0x92:
        print('userput on')
    elif sub == 0x93:
        print('userput off')
    elif sub == 0x94:
        print('cursor soft-on')
    elif sub == 0x95:
        print('cursor soft-off')
    elif sub == 0x96:
        print('userput soft-on')
    elif sub == 0x97:
        print('userput soft-off')
    elif sub == 0x99:
        print(f'set-cursor-image {stack.pop()}')
    elif sub == 0x9A:
        print(f'set-cursor-hotspot {stack.pop()} {stack.pop()}')
    elif sub == 0x9C:
        print(f'init-charset {stack.pop()}')
    elif sub == 0x9D:
        print(f'init-charset {[stack.pop() for i in range(stack.pop())]}')
    elif sub == 0xD6:
        print(f'set-cursor-transparent-color {stack.pop()}')
    else:
        raise NotImplementedError(sub)


@regop
def o6_arrayOps(op, stack, bytecode):
    byte, array, *rest = op.args
    sub = ord(byte.op)
    num = int.from_bytes(array.op, byteorder='little', signed=False)
    if sub == 205:
        msg, *rest = rest
        print(f'string ARRAY_{num} = {msg}')
        # stack.append(f'STR_{num}')


@regop
def o6_setClass(op, stack, bytecode):
    assert not op.args
    print(f'set-class {[stack.pop() for i in range(stack.pop())]} {stack.pop()}')


@regop
def o6_dimArray(op, stack, bytecode):
    byte, array, *_rest = op.args
    sub = ord(byte.op)
    num = int.from_bytes(array.op, byteorder='little', signed=False)
    if sub == 199:
        print(f'word ARRAY_{num}[{stack.pop()}]')
    elif sub == 200:
        print(f'bit ARRAY_{num}[{stack.pop()}]')
    elif sub == 201:
        print(f'nibble ARRAY_{num}[{stack.pop()}]')
    elif sub == 202:
        print(f'byte ARRAY_{num}[{stack.pop()}]')
    elif sub == 203:
        print(f'string ARRAY_{num}[{stack.pop()}]')
    elif sub == 204:
        print(f'nuke ARRAY_{num}[{stack.pop()}]')
    else:
        raise NotImplementedError(sub)


@regop
def o6_pushWordVar(op, stack, bytecode):
    word, *_rest = op.args
    num = int.from_bytes(word.op, byteorder='little', signed=False)
    stack.append(f'VAR_{num}')
    # print('push-word-var VAR_{num}')


@regop
def o6_roomOps(op, stack, bytecode):
    byte, *_rest = op.args
    sub = ord(byte.op)
    if sub == 172:
        print(f'room-scroll {stack.pop()} {stack.pop()}')
    elif sub == 174:
        print(f'set-screen {stack.pop()} {stack.pop()}')
    elif sub == 175:
        print(f'palette {stack.pop()} {stack.pop()} {stack.pop()} {stack.pop()}')
    elif sub == 176:
        print(f'shake-on')
    elif sub == 177:
        print(f'shake-off')
    elif sub == 179:
        print(f'room-intensity {stack.pop()} {stack.pop()} {stack.pop()}')
    elif sub == 180:
        print(f'room-save {stack.pop()} {stack.pop()}')
    elif sub == 181:
        print(f'room-fade {stack.pop()}')
    elif sub == 182:
        print(
            f'room-intensity-rgb {stack.pop()} {stack.pop()} {stack.pop()} {stack.pop()} {stack.pop()}'
        )
    elif sub == 183:
        print(
            f'room-shadow {stack.pop()} {stack.pop()} {stack.pop()} {stack.pop()} {stack.pop()}'
        )
    elif sub == 186:
        print(f'room-transform {stack.pop()} {stack.pop()} {stack.pop()} {stack.pop()}')
    elif sub == 187:
        print(f'room-cycle-speed {stack.pop()} {stack.pop()}')
    elif sub == 213:
        print(f'room-new-palette {stack.pop()}')
    else:
        raise NotImplementedError(sub)


@regop
def o6_kernelSetFunctions(op, stack, bytecode):
    args = [stack.pop() for i in range(stack.pop())]
    print(f'kernel-set {args[0]} {args[1:]}')


@regop
def o6_wordArrayWrite(op, stack, bytecode):
    array, *_rest = op.args
    num = int.from_bytes(array.op, byteorder='little', signed=False)
    value, index = stack.pop(), stack.pop()
    print(f'ARRAY_{num}[{index}] = {value}')


@regop
def o6_pushByte(op, stack, bytecode):
    byte, *rest = op.args
    assert not rest
    stack.append(int.from_bytes(byte.op, byteorder='little', signed=False))


@regop
def o6_pushWord(op, stack, bytecode):
    word, *rest = op.args
    assert not rest
    value = int.from_bytes(word.op, byteorder='little', signed=False)
    stack.append(value)
    # print(f'push-word {value}')


@regop
def o6_stopSound(op, stack, bytecode):
    print(f'stop-sound {stack.pop()}')


@regop
def o6_jump(op, stack, bytecode):
    off, *rest = op.args
    assert not rest
    print(f'goto {off}')


@regop
def o6_beginOverride(op, stack, bytecode):
    print('begin-override')


@regop
def o6_endOverride(op, stack, bytecode):
    print('end-override')


@regop
def o6_writeWordVar(op, stack, bytecode):
    word, *rest = op.args
    num = int.from_bytes(word.op, byteorder='little', signed=False)
    assert not rest
    print(f'VAR_{num} = {stack.pop()}')


@regop
def o6_resourceRoutines(op, stack, bytecode):
    byte, *_rest = op.args
    sub = ord(byte.op)
    cmds = {
        100: 'load-script',
        101: 'load-sound',
        102: 'load-costume',
        103: 'load-room',
        104: 'nuke-script',
        105: 'nuke-sound',
        106: 'nuke-costume',
        107: 'nuke-room',
        108: 'lock-script',
        109: 'lock-sound',
        110: 'lock-costume',
        111: 'lock-room',
        112: 'unlock-script',
        113: 'unlock-sound',
        114: 'unlock-costume',
        115: 'unlock-room',
        117: 'load-charset',
        118: 'kill-charset',
    }
    if sub in cmds:
        print(f'{cmds[sub]} {stack.pop()}')
    elif sub == 119:
        print(f'load-object {stack.pop()}')  # different for >= 7
    else:
        raise NotImplementedError(sub)


@regop
def o6_actorOps(op, stack, bytecode):
    byte, *_rest = op.args
    sub = ord(byte.op)
    if sub == 197:
        print(f'current-actor-is {stack.pop()}')
    elif sub == 76:
        print(f'set-actor-costume {stack.pop()}')
    elif sub == 77:
        print(f'set-actor-speed {stack.pop()} {stack.pop()}')
    elif sub == 78:
        print(f'set-actor-sounds {[stack.pop() for i in range(stack.pop())]}')
    elif sub == 79:
        print(f'set-actor-walk-animation {stack.pop()}')
    elif sub == 80:
        print(f'set-actor-talk-animation {stack.pop()} {stack.pop()}')
    elif sub == 81:
        print(f'set-actor-stand-animation {stack.pop()}')
    elif sub == 82:
        print(f'set-actor-animation {stack.pop()} {stack.pop()} {stack.pop()}')
    elif sub == 83:
        print(f'init-actor')
    elif sub == 84:
        print(f'set-actor-elevation {stack.pop()}')
    elif sub == 85:
        print(f'reset-actor-animation')
    elif sub == 86:
        print(f'set-actor-palette {stack.pop()} {stack.pop()}')
    elif sub == 87:
        print(f'set-actor-talk-color {stack.pop()}')
    elif sub == 88:
        print(f'set-actor-name')
    elif sub == 89:
        print(f'init-animation {stack.pop()}')
    elif sub == 91:
        print(f'set-actor-width {stack.pop()}')
    elif sub == 92:
        print(f'set-actor-scale {stack.pop()}')
    elif sub == 93:
        print(f'clip-off')
    elif sub in {94, 225}:
        print(f'clip-on')
    elif sub == 95:
        print(f'ignore-boxes')
    elif sub == 96:
        print(f'follow-boxes')
    elif sub == 97:
        print(f'set-anim-speed {stack.pop()}')
    elif sub == 98:
        print(f'set-shadow {stack.pop()}')
    elif sub == 99:
        print(f'set-text-position {stack.pop()} {stack.pop()}')
    else:
        raise NotImplementedError(sub)


@regop
def o6_if(op, stack, bytecode):
    stats = list(bytecode)
    off, *rest = op.args
    assert not rest
    print(f'if not {stack.pop()} ({stats.index(off.abs) - stats.index(op.offset)}):')


@regop
def o6_ifNot(op, stack, bytecode):
    stats = list(bytecode)
    off, *rest = op.args
    assert not rest
    print(f'if {stack.pop()} ({stats.index(off.abs) - stats.index(op.offset)}):')


@regop
def o6_eq(op, stack, bytecode):
    stack.append(f'{stack.pop()} == {stack.pop()}')


@regop
def o6_dup(op, stack, bytecode):
    val = stack.pop()
    stack.append(val)
    stack.append(val)


@regop
def o6_neq(op, stack, bytecode):
    stack.append(f'{stack.pop()} != {stack.pop()}')


@regop
def o6_pop(op, stack, bytecode):
    print(f'pop {stack.pop()}')


def defop(op, stack, bytecode):
    print(op)


if __name__ == '__main__':
    import argparse
    import glob

    from .preset import sputm
    from nutcracker.utils.fileio import read_file

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:

        resource = read_file(filename, key=int(args.chiper_key, 16))

        for elem in get_scripts(sputm.map_chunks(resource)):
            _, script_data = script_map[elem.tag](elem.data)
            bytecode = descumm(script_data, OPCODES_v6)
            stack = deque()
            for off, op in bytecode.items():
                ops.get(op.name, defop)(op, stack, bytecode)
            exit(1)
