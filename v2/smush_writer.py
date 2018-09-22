#!/usr/bin/env python3

import struct

def mktag(tag, data):
    if len(data) % 2 != 0:
        data += b'\x00'
    return tag.encode() + struct.pack('>I', len(data)) + data
