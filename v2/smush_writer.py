#!/usr/bin/env python3

import struct

def mktag(tag, data):
    new_data = data
    if len(data) % 2 != 0:
        new_data += b'\x00'
    return tag.encode() + struct.pack('>I', len(data)) + new_data
