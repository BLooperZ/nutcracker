import itertools
from collections.abc import Callable, Iterable, Iterator
from typing import IO, Protocol, Self


def read_message(
    stream: IO[bytes],
    escape: bytes | None = None,
    var_size: int = 2,
) -> Iterator[bytes]:
    while True:
        c = stream.read(1)
        if c in {b'', b'\0'}:
            break
        assert c is not None
        if c == escape:
            t = stream.read(1)
            c += t
            if ord(t) not in {1, 2, 3, 8}:
                c += stream.read(var_size)
        yield c


class ScriptArg(Protocol):
    def to_bytes(self) -> bytes: ...


class CString(ScriptArg):
    def __init__(self, msg: bytes, var_size: int = 2) -> None:
        self.msg = msg

    @classmethod
    def parse(cls, stream: IO[bytes], var_size: int = 2) -> 'Self':
        msg = b''.join(read_message(stream, escape=b'\xff', var_size=var_size))
        return cls(msg)

    def __repr__(self) -> str:
        return f'<MSG {self.msg!r}>'

    def to_bytes(self) -> bytes:
        msg = self.msg if self.msg is not None else b''
        return msg + b'\0'


class ByteValue(ScriptArg):
    def __init__(self, op: bytes) -> None:
        self.op = op

    @classmethod
    def parse(cls, stream: IO[bytes]) -> 'Self':
        op = stream.read(1)
        return cls(op)

    def __repr__(self) -> str:
        return f'<BYTE hex=0x{ord(self.op):02x} dec={ord(self.op)}>'

    def to_bytes(self) -> bytes:
        return self.op


class WordValue(ScriptArg):
    def __init__(self, op: bytes) -> None:
        self.op = op

    @classmethod
    def parse(cls, stream: IO[bytes]) -> 'Self':
        op = stream.read(2)
        return cls(op)

    def __repr__(self) -> str:
        val = int.from_bytes(self.op, byteorder='little', signed=True)
        return f'<WORD hex=0x{val:04x} dec={val}>'

    def to_bytes(self) -> bytes:
        return self.op


class DWordValue(ScriptArg):
    def __init__(self, op: bytes) -> None:
        self.op = op

    @classmethod
    def parse(cls, stream: IO[bytes]) -> 'Self':
        op = stream.read(4)
        return cls(op)

    def __repr__(self) -> str:
        val = int.from_bytes(self.op, byteorder='little', signed=True)
        return f'<DWORD hex=0x{val:04x} dec={val}>'

    def to_bytes(self) -> bytes:
        return self.op


class RefOffset(ScriptArg):
    def __init__(self, rel: int, endpos: int, word_size: int = 2) -> None:
        self.endpos = endpos
        self.size = word_size
        self.abs = rel + self.endpos

    @classmethod
    def parse(
        cls,
        stream: IO[bytes],
        word_size: int = 2,
    ) -> 'Self':
        rel = int.from_bytes(stream.read(word_size), byteorder='little', signed=True)
        endpos = stream.tell()
        return cls(rel, endpos, word_size)

    @property
    def rel(self) -> int:
        return self.abs - self.endpos

    def __repr__(self) -> str:
        if self.size == 2:
            return f'<REF rel=0x{self.rel:04x} abs=0x{(self.abs):04x}>'
        return f'<REF rel=0x{self.rel:08x} abs=0x{(self.abs):08x}>'

    def to_bytes(self) -> bytes:
        return self.rel.to_bytes(self.size, byteorder='little', signed=True)


class Statement:
    def __init__(
        self,
        name: str,
        opcode: int,
        offset: int,
        args: Iterable[ScriptArg],
    ) -> None:
        self.name = name
        self.opcode = opcode
        self.offset = offset
        self.args = tuple(args)


    @classmethod
    def parse(
        cls,
        name: str,
        ops: Iterable[Callable[[IO[bytes]], Iterable[ScriptArg]]],
        opcode: int,
        stream: IO[bytes],
    ) -> 'Self':
        return cls(
            name,
            opcode,
            stream.tell() -1,
            tuple(
                itertools.chain.from_iterable(
                    op(stream)
                    for op in ops
                ),
            ),
        )

    def __repr__(self) -> str:
        return ' '.join(
            [f'0x{self.opcode:02x}', self.name, '{', *(str(x) for x in self.args), '}'],
        )

    def to_bytes(self) -> bytes:
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])
