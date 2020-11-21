#!/usr/bin/env python3
from nutcracker.utils.funcutils import grouper, flatten

def read_message(stream, escape=None, var_size=2):
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

class CString:
    def __init__(self, stream, var_size=2):
        self.msg = b''.join(read_message(stream, escape=b'\xff', var_size=var_size))
    def __repr__(self):
        return f'MSG {self.msg!r}'
    def to_bytes(self):
        msg = self.msg if self.msg is not None else b''
        return msg + b'\0'

class ByteValue:
    def __init__(self, stream):
        self.op = stream.read(1)
    def __repr__(self):
        return f'BYTE hex=0x{ord(self.op):02x} dec={ord(self.op)}'
    def to_bytes(self):
        return self.op

class WordValue:
    def __init__(self, stream):
        self.op = stream.read(2)
    def __repr__(self):
        val = int.from_bytes(self.op, byteorder='little', signed=True)
        return f'WORD hex=0x{val:04x} dec={val}'
    def to_bytes(self):
        return self.op

class DWordValue:
    def __init__(self, stream):
        self.op = stream.read(4)
    def __repr__(self):
        val = int.from_bytes(self.op, byteorder='little', signed=True)
        return f'DWORD hex=0x{val:04x} dec={val}'
    def to_bytes(self):
        return self.op

class RefOffset:
    def __init__(self, stream, word_size=2):
        rel = int.from_bytes(stream.read(word_size), byteorder='little', signed=True)
        self.endpos = stream.tell()
        self.size = word_size
        self.abs = rel + self.endpos

    @property
    def rel(self):
        return self.abs - self.endpos

    def __repr__(self):
        if self.size == 2:
            return f'REF rel=0x{self.rel:04x} abs=0x{(self.abs):04x}'
        return f'REF rel=0x{self.rel:08x} abs=0x{(self.abs):08x}'

    def to_bytes(self):
        return self.rel.to_bytes(self.size, byteorder='little', signed=True)

class Statement:
    def __init__(self, name, op, opcode, stream):
        self.name = name
        self.opcode = opcode
        self.offset = stream.tell() - 1
        self.args = tuple(op(stream))

    def __repr__(self):
        return ' '.join([f'0x{self.opcode:02x}', self.name, '{', *(str(x) for x in self.args), '}'])

    def to_bytes(self):
        return b''.join([bytes([self.opcode]), *(x.to_bytes() for x in self.args)])
