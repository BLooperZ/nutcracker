import struct
import io
from codex import encode, decode

meta_struct = ('codec', 'xoff', 'yoff', 'width', 'height', 'zero1', 'zero2')

def mktag(tag, data):
    return tag + struct.pack('>I', len(data)) + data

def mkobj(width, height, data, codec, force=None):
    xoff = 0
    yoff = 0
    meta = codec, xoff, yoff, width, height, 0, 0
    res = b''.join(struct.pack('<H', item) for item in meta)
    # res = struct.pack('<H', codec)
    # res += struct.pack('<H', xoff)
    # res += struct.pack('<H', yoff)
    # res += struct.pack('<H', width)
    # res += struct.pack('<H', height)
    # res += struct.pack('<H', 0)
    # res += struct.pack('<H', 0)
    res += encode(width, height, data, codec if not force else force)
    if len(res) % 2 == 1:
        res += '\x00'
    return mktag('FOBJ', res)

def untag(stream, force=None):
    tag = stream.read(4)
    if force and force != tag:
        raise ValueError
    size = struct.unpack('>I', stream.read(4))[0]
    return io.BytesIO(stream.read(size))

def unobj(data):
    stream = io.BytesIO(data)
    stream = untag(stream, force='FOBJ')
    meta = (struct.unpack('<H', stream.read(2))[0] for _ in meta_struct)
    codec, _, _, width, height, _, _ = meta
    # codec = struct.unpack('<H', stream.read(2))[0]
    # stream.seek(4 ,1) # xoff + yoff
    # width = struct.unpack('<H', stream.read(2))[0]
    # height = struct.unpack('<H', stream.read(2))[0]
    # stream.seek(4, 1) # zeros
    data = stream.read()
    return width, height, decode(width, height, data), codec

def read_nut_file(filename):
    def read_chunk():
        for _ in range(numChars):
            yield untag(stream, force='FRME').read()

    with open (filename, 'rb') as fontFile:
        stream = untag(fontFile, force='ANIM')
    header = mktag('AHDR', untag(stream, force='AHDR').read())
    numChars = struct.unpack('<H', header[10:12])[0]
    return header, numChars, read_chunk()

def write_nut_file(header, numChars, chars, filename):
    chars = (mktag('FRME', char) for char in chars)

    header = untag(io.BytesIO(header), force='AHDR').read()
    header = struct.pack('<H', 2) + struct.pack('<H', numChars) + header[4:]
    header = mktag('AHDR', header)

    nutFile = mktag('ANIM', header + b''.join(chars))

    with open(filename, 'wb') as fontFile:
        fontFile.write(nutFile)

def decode_frames(chars):
    return (unobj(char)[:-1] for char in chars)

def encode_frames(chars, codec, force=None):
    return (mkobj(w, he, lines, codec, force=force) for w, he, lines in chars)