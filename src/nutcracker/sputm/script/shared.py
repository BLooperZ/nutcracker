import io
from collections import deque
from collections.abc import Iterator, Mapping
from string import printable

from nutcracker.sputm.strings import RAW_ENCODING, EncodingSetting

try:
    # Python 3.10+
    from itertools import pairwise
except:
    # Python 3.9
    from more_itertools import pairwise

from nutcracker.sputm.script.bytecode import BytecodeParseError
from nutcracker.sputm.script.opcodes_v5 import SomeOp
from nutcracker.sputm.script.parser import CString, Statement
from nutcracker.utils.funcutils import grouper


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
            entry = int.from_bytes(stream.read(2), byteorder='little', signed=False)
            yield key, entry - len(meta)
        assert stream.read() == b''


def canonical_bytecode(
    bytecode: Mapping[int, Statement | SomeOp],
    base_offset: int = 0,
) -> Iterator[str]:
    for off, stat in bytecode.items():
        byte_width = 4
        hexdump = ' |\n\t            '.join(
            bytes(x for x in part if x is not None)[::-1]
            .hex(' ')
            .upper()
            .rjust(3 * byte_width - 1)
            for part in reversed(list(grouper(stat.to_bytes()[::-1], byte_width)))
        )
        yield f'[{base_offset + off:08d}]: {hexdump} | {stat}'


class BytecodeError(ValueError):
    def __init__(self, cause: BytecodeParseError, path, asts):
        block = '\n'.join(print_asts('\t', asts))
        bytecode_str = '\n\t'.join(
            canonical_bytecode(cause.bytecode, cause.base_offset),
        )
        msg = (
            '\n'
            f'Script path: {path}\n'
            f'Block:\n{block}\n'
            f'Bytecode:\n\t{bytecode_str}\n'
            f'Next:\n\t[{cause.base_offset + cause.offset:08d}]: {cause.buffer[cause.offset:cause.offset+16].hex(" ").upper()}\n'
            f'Error summary: {cause}'
        )
        super().__init__(
            msg,
        )
        self.cause = cause
        self.path = path
        self.asts = asts


class ScriptError(ValueError):
    def __init__(self, cause, path, asts, stat, stack):
        block = '\n'.join(print_asts('\t', asts))
        msg = (
            '\n'
            f'Script path: {path}\n'
            f'Block:\n{block}\n'
            f'Next statement: {stat} called with stack: {stack}\n'
            f'Error summary: {repr(cause)}'
        )
        super().__init__(
            msg,
        )
        self.cause = cause
        self.path = path
        self.asts = asts
        self.stat = stat
        self.stack = stack


def realize_refs(srefs, hrefs, seq):
    refs = {label: label in hrefs for label in sorted(srefs | hrefs)}
    assert refs
    if len(refs) == 1:
        nref = next(iter(refs))
    else:
        for ref, nref in pairwise(refs):
            label = f'[{ref + 8:08d}]' if refs[ref] else f'_[{ref + 8:08d}]'
            stats = deque(stat for off, stat in seq if off < nref)
            # TODO: investigate what is the meaning of empty ref block
            if stats:
                yield label, stats
            seq = deque((off, stat) for off, stat in seq if off >= nref)
    label = f'[{nref + 8:08d}]' if refs[nref] else f'_[{nref + 8:08d}]'
    stats = deque(stat for _, stat in seq)
    if stats:
        yield label, stats


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
            elif c not in (printable.encode() + bytes(range(ord('\xe0'), ord('\xfa') + 1))):
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
