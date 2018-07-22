import struct

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]


def to_matrix(w, h, data):
    return [data[i*w:(i+1)*w] for i in range(h)]

# TO DO: try to get correct pallete from header
pallete = {
    # SCUMMFNT: [2,1]
    # TITLFNT: [240,241,242]
    # FONT0: [225]
    # FONT1,FONT2: [0,1]
    # FONT3: [1]
    # FONT4: [224, 225]

    0: 0, 1: 180, 2: 40,
    224: 190, 225: 30,
    240: 240, 241: 110, 242: 70,
}

BG = 128

def decode(width, height, f):
    def getColor(num):
        c_pallete = pallete
        if num in c_pallete:
            return c_pallete[num]
        return num
    decoded = unidecoder(width, height, f, getColor)
    return to_matrix(width, height, decoded)

def unidecoder(width, height, f, getColor):
    out = [BG for _ in range(width * height)]
    dst = 0
    src = 0
    for _ in range(height):
        dstPtrNext = dst + width
    	srcPtrNext = src + 2 + read_le_uint16(f[src:])
        src += 2
        lens = width
        while lens > 0:
            offs = read_le_uint16(f[src:])
            src += 2
            dst += offs
            lens -= offs
            w = read_le_uint16(f[src:]) + 1
            src += 2
            lens -= w
            if lens < 0:
                w += lens
            wr = []
            for i in range(w):
                wr.append(struct.unpack('<B', f[src + i])[0])
                out[dst+i] = getColor(struct.unpack('<B', f[src + i])[0])
            dst += w
            src += w
        dst = dstPtrNext
        src = srcPtrNext
    return out

def encode(width, height, out, codec):
    def getColor(num):
        c_pallete = {v: k for k, v in pallete.iteritems()}
        if num in c_pallete:
            return c_pallete[num]
        return num

    if codec == 44:
        return codec44(width, height, out, getColor)
    if codec == 21:
        return codec21(width, height, out, getColor)
    return NotImplemented

def codec44(width, height, out, getColor):
    f = ''
    for line in out:
        l = ''
        done = 0
        while done < width:
            i = 0
            while done + i < width and line[done+i] == BG:
                i += 1
            off = i
            while done + i < width and line[done+i] != BG:
                i += 1
            lst = line[done+off:done+i]
            l += struct.pack('<H', off)
            r = 1 if (done + i < width) else 0
            if lst:
                l += struct.pack('<H', len(lst) - r)
                for it in lst:
                    l += struct.pack('<B', getColor(it))
            else:
                l += struct.pack('<H', 0)
            done += i
        f += struct.pack('<H', len(l) + 1) + l + struct.pack('<B', 0)
    f += struct.pack('<H', width + 5) + '\x00\x00' + struct.pack('<H', width)
    for i in range(width):
        f += '\x00'
    if len(f) % 2 == 0:
        f += '\x00\x00'
    return f

def codec21(width, height, out, getColor):
    f = ''
    for line in (out + [[BG for _ in range(width)]]):
        l = ''
        done = 0
        while done <= width:
            i = 0
            while done + i < width and line[done+i] == BG:
                i += 1
            off = i
            r = i + 1
            if done + r > width:
                l += (struct.pack('<H', r))
                break
            while done + i < width and line[done+i] != BG:
                i += 1
            lst = line[done+off:done+i]
            l += struct.pack('<H', off)
            if lst:
                l += struct.pack('<H', len(lst) - 1)
                for it in lst:
                    l += struct.pack('<B', getColor(it))
            done += i
        f += struct.pack('<H', len(l)) + l
    return f
