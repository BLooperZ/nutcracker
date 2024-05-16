from collections import deque
import io
try:
    # Python 3.10+
    from itertools import pairwise
except:
    # Python 3.9
    from more_itertools import pairwise
from typing import Iterator, Mapping, Union
from nutcracker.sputm.script.bytecode import BytecodeParseError
from nutcracker.sputm.script.opcodes_v5 import SomeOp

from nutcracker.sputm.script.parser import Statement
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
            entry = int.from_bytes(
                stream.read(2), byteorder='little', signed=False
            )
            yield key, entry - len(meta)
        assert stream.read() == b''


def canonical_bytecode(bytecode: Mapping[int, Union[Statement, SomeOp]], base_offset: int = 0) -> Iterator[str]:
    for off, stat in bytecode.items():
        byte_width = 4
        hexdump = ' |\n\t            '.join(
            bytes(x for x in part if x is not None)[::-1]
            .hex(" ")
            .upper()
            .rjust(3 * byte_width - 1)
            for part in reversed(list(grouper(stat.to_bytes()[::-1], byte_width)))
        )
        yield f'[{base_offset + off:08d}]: {hexdump} | {stat}'


class BytecodeError(ValueError):
    def __init__(self, cause: BytecodeParseError, path, asts):
        block = '\n'.join(print_asts('\t', asts))
        bytecode_str = '\n\t'.join(canonical_bytecode(cause.bytecode, cause.base_offset))
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
