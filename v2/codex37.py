import struct

def to_matrix(w, h, data):
    return [data[i*w:(i+1)*w] for i in range(h)]

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

def read_le_uint32(f):
    return struct.unpack('<I', f[:4])[0]

def maketable(pitch, index):
    maketable_bytes = [
        0,   0,   1,   0,   2,   0,   3,   0,   5,   0,
        8,   0,  13,   0,  21,   0,  -1,   0,  -2,   0,
        -3,   0,  -5,   0,  -8,   0, -13,   0, -17,   0,
        -21,   0,   0,   1,   1,   1,   2,   1,   3,   1,
        5,   1,   8,   1,  13,   1,  21,   1,  -1,   1,
        -2,   1,  -3,   1,  -5,   1,  -8,   1, -13,   1,
        -17,   1, -21,   1,   0,   2,   1,   2,   2,   2,
        3,   2,   5,   2,   8,   2,  13,   2,  21,   2,
        -1,   2,  -2,   2,  -3,   2,  -5,   2,  -8,   2,
        -13,   2, -17,   2, -21,   2,   0,   3,   1,   3,
        2,   3,   3,   3,   5,   3,   8,   3,  13,   3,
        21,   3,  -1,   3,  -2,   3,  -3,   3,  -5,   3,
        -8,   3, -13,   3, -17,   3, -21,   3,   0,   5,
        1,   5,   2,   5,   3,   5,   5,   5,   8,   5,
        13,   5,  21,   5,  -1,   5,  -2,   5,  -3,   5,
        -5,   5,  -8,   5, -13,   5, -17,   5, -21,   5,
        0,   8,   1,   8,   2,   8,   3,   8,   5,   8,
        8,   8,  13,   8,  21,   8,  -1,   8,  -2,   8,
        -3,   8,  -5,   8,  -8,   8, -13,   8, -17,   8,
        -21,   8,   0,  13,   1,  13,   2,  13,   3,  13,
        5,  13,   8,  13,  13,  13,  21,  13,  -1,  13,
        -2,  13,  -3,  13,  -5,  13,  -8,  13, -13,  13,
        -17,  13, -21,  13,   0,  21,   1,  21,   2,  21,
        3,  21,   5,  21,   8,  21,  13,  21,  21,  21,
        -1,  21,  -2,  21,  -3,  21,  -5,  21,  -8,  21,
        -13,  21, -17,  21, -21,  21,   0,  -1,   1,  -1,
        2,  -1,   3,  -1,   5,  -1,   8,  -1,  13,  -1,
        21,  -1,  -1,  -1,  -2,  -1,  -3,  -1,  -5,  -1,
        -8,  -1, -13,  -1, -17,  -1, -21,  -1,   0,  -2,
        1,  -2,   2,  -2,   3,  -2,   5,  -2,   8,  -2,
        13,  -2,  21,  -2,  -1,  -2,  -2,  -2,  -3,  -2,
        -5,  -2,  -8,  -2, -13,  -2, -17,  -2, -21,  -2,
        0,  -3,   1,  -3,   2,  -3,   3,  -3,   5,  -3,
        8,  -3,  13,  -3,  21,  -3,  -1,  -3,  -2,  -3,
        -3,  -3,  -5,  -3,  -8,  -3, -13,  -3, -17,  -3,
        -21,  -3,   0,  -5,   1,  -5,   2,  -5,   3,  -5,
        5,  -5,   8,  -5,  13,  -5,  21,  -5,  -1,  -5,
        -2,  -5,  -3,  -5,  -5,  -5,  -8,  -5, -13,  -5,
        -17,  -5, -21,  -5,   0,  -8,   1,  -8,   2,  -8,
        3,  -8,   5,  -8,   8,  -8,  13,  -8,  21,  -8,
        -1,  -8,  -2,  -8,  -3,  -8,  -5,  -8,  -8,  -8,
        -13,  -8, -17,  -8, -21,  -8,   0, -13,   1, -13,
        2, -13,   3, -13,   5, -13,   8, -13,  13, -13,
        21, -13,  -1, -13,  -2, -13,  -3, -13,  -5, -13,
        -8, -13, -13, -13, -17, -13, -21, -13,   0, -17,
        1, -17,   2, -17,   3, -17,   5, -17,   8, -17,
        13, -17,  21, -17,  -1, -17,  -2, -17,  -3, -17,
        -5, -17,  -8, -17, -13, -17, -17, -17, -21, -17,
        0, -21,   1, -21,   2, -21,   3, -21,   5, -21,
        8, -21,  13, -21,  21, -21,  -1, -21,  -2, -21,
        -3, -21,  -5, -21,  -8, -21, -13, -21, -17, -21,
        0,   0,  -8, -29,   8, -29, -18, -25,  17, -25,
        0, -23,  -6, -22,   6, -22, -13, -19,  12, -19,
        0, -18,  25, -18, -25, -17,  -5, -17,   5, -17,
        -10, -15,  10, -15,   0, -14,  -4, -13,   4, -13,
        19, -13, -19, -12,  -8, -11,  -2, -11,   0, -11,
        2, -11,   8, -11, -15, -10,  -4, -10,   4, -10,
        15, -10,  -6,  -9,  -1,  -9,   1,  -9,   6,  -9,
        -29,  -8, -11,  -8,  -8,  -8,  -3,  -8,   3,  -8,
        8,  -8,  11,  -8,  29,  -8,  -5,  -7,  -2,  -7,
        0,  -7,   2,  -7,   5,  -7, -22,  -6,  -9,  -6,
        -6,  -6,  -3,  -6,  -1,  -6,   1,  -6,   3,  -6,
        6,  -6,   9,  -6,  22,  -6, -17,  -5,  -7,  -5,
        -4,  -5,  -2,  -5,   0,  -5,   2,  -5,   4,  -5,
        7,  -5,  17,  -5, -13,  -4, -10,  -4,  -5,  -4,
        -3,  -4,  -1,  -4,   0,  -4,   1,  -4,   3,  -4,
        5,  -4,  10,  -4,  13,  -4,  -8,  -3,  -6,  -3,
        -4,  -3,  -3,  -3,  -2,  -3,  -1,  -3,   0,  -3,
        1,  -3,   2,  -3,   4,  -3,   6,  -3,   8,  -3,
        -11,  -2,  -7,  -2,  -5,  -2,  -3,  -2,  -2,  -2,
        -1,  -2,   0,  -2,   1,  -2,   2,  -2,   3,  -2,
        5,  -2,   7,  -2,  11,  -2,  -9,  -1,  -6,  -1,
        -4,  -1,  -3,  -1,  -2,  -1,  -1,  -1,   0,  -1,
        1,  -1,   2,  -1,   3,  -1,   4,  -1,   6,  -1,
        9,  -1, -31,   0, -23,   0, -18,   0, -14,   0,
        -11,   0,  -7,   0,  -5,   0,  -4,   0,  -3,   0,
        -2,   0,  -1,   0,   0, -31,   1,   0,   2,   0,
        3,   0,   4,   0,   5,   0,   7,   0,  11,   0,
        14,   0,  18,   0,  23,   0,  31,   0,  -9,   1,
        -6,   1,  -4,   1,  -3,   1,  -2,   1,  -1,   1,
        0,   1,   1,   1,   2,   1,   3,   1,   4,   1,
        6,   1,   9,   1, -11,   2,  -7,   2,  -5,   2,
        -3,   2,  -2,   2,  -1,   2,   0,   2,   1,   2,
        2,   2,   3,   2,   5,   2,   7,   2,  11,   2,
        -8,   3,  -6,   3,  -4,   3,  -2,   3,  -1,   3,
        0,   3,   1,   3,   2,   3,   3,   3,   4,   3,
        6,   3,   8,   3, -13,   4, -10,   4,  -5,   4,
        -3,   4,  -1,   4,   0,   4,   1,   4,   3,   4,
        5,   4,  10,   4,  13,   4, -17,   5,  -7,   5,
        -4,   5,  -2,   5,   0,   5,   2,   5,   4,   5,
        7,   5,  17,   5, -22,   6,  -9,   6,  -6,   6,
        -3,   6,  -1,   6,   1,   6,   3,   6,   6,   6,
        9,   6,  22,   6,  -5,   7,  -2,   7,   0,   7,
        2,   7,   5,   7, -29,   8, -11,   8,  -8,   8,
        -3,   8,   3,   8,   8,   8,  11,   8,  29,   8,
        -6,   9,  -1,   9,   1,   9,   6,   9, -15,  10,
        -4,  10,   4,  10,  15,  10,  -8,  11,  -2,  11,
        0,  11,   2,  11,   8,  11,  19,  12, -19,  13,
        -4,  13,   4,  13,   0,  14, -10,  15,  10,  15,
        -5,  17,   5,  17,  25,  17, -25,  18,   0,  18,
        -12,  19,  13,  19,  -6,  22,   6,  22,   0,  23,
        -17,  25,  18,  25,  -8,  29,   8,  29,   0,  31,
        0,   0,  -6, -22,   6, -22, -13, -19,  12, -19,
        0, -18,  -5, -17,   5, -17, -10, -15,  10, -15,
        0, -14,  -4, -13,   4, -13,  19, -13, -19, -12,
        -8, -11,  -2, -11,   0, -11,   2, -11,   8, -11,
        -15, -10,  -4, -10,   4, -10,  15, -10,  -6,  -9,
        -1,  -9,   1,  -9,   6,  -9, -11,  -8,  -8,  -8,
        -3,  -8,   0,  -8,   3,  -8,   8,  -8,  11,  -8,
        -5,  -7,  -2,  -7,   0,  -7,   2,  -7,   5,  -7,
        -22,  -6,  -9,  -6,  -6,  -6,  -3,  -6,  -1,  -6,
        1,  -6,   3,  -6,   6,  -6,   9,  -6,  22,  -6,
        -17,  -5,  -7,  -5,  -4,  -5,  -2,  -5,  -1,  -5,
        0,  -5,   1,  -5,   2,  -5,   4,  -5,   7,  -5,
        17,  -5, -13,  -4, -10,  -4,  -5,  -4,  -3,  -4,
        -2,  -4,  -1,  -4,   0,  -4,   1,  -4,   2,  -4,
        3,  -4,   5,  -4,  10,  -4,  13,  -4,  -8,  -3,
        -6,  -3,  -4,  -3,  -3,  -3,  -2,  -3,  -1,  -3,
        0,  -3,   1,  -3,   2,  -3,   3,  -3,   4,  -3,
        6,  -3,   8,  -3, -11,  -2,  -7,  -2,  -5,  -2,
        -4,  -2,  -3,  -2,  -2,  -2,  -1,  -2,   0,  -2,
        1,  -2,   2,  -2,   3,  -2,   4,  -2,   5,  -2,
        7,  -2,  11,  -2,  -9,  -1,  -6,  -1,  -5,  -1,
        -4,  -1,  -3,  -1,  -2,  -1,  -1,  -1,   0,  -1,
        1,  -1,   2,  -1,   3,  -1,   4,  -1,   5,  -1,
        6,  -1,   9,  -1, -23,   0, -18,   0, -14,   0,
        -11,   0,  -7,   0,  -5,   0,  -4,   0,  -3,   0,
        -2,   0,  -1,   0,   0, -23,   1,   0,   2,   0,
        3,   0,   4,   0,   5,   0,   7,   0,  11,   0,
        14,   0,  18,   0,  23,   0,  -9,   1,  -6,   1,
        -5,   1,  -4,   1,  -3,   1,  -2,   1,  -1,   1,
        0,   1,   1,   1,   2,   1,   3,   1,   4,   1,
        5,   1,   6,   1,   9,   1, -11,   2,  -7,   2,
        -5,   2,  -4,   2,  -3,   2,  -2,   2,  -1,   2,
        0,   2,   1,   2,   2,   2,   3,   2,   4,   2,
        5,   2,   7,   2,  11,   2,  -8,   3,  -6,   3,
        -4,   3,  -3,   3,  -2,   3,  -1,   3,   0,   3,
        1,   3,   2,   3,   3,   3,   4,   3,   6,   3,
        8,   3, -13,   4, -10,   4,  -5,   4,  -3,   4,
        -2,   4,  -1,   4,   0,   4,   1,   4,   2,   4,
        3,   4,   5,   4,  10,   4,  13,   4, -17,   5,
        -7,   5,  -4,   5,  -2,   5,  -1,   5,   0,   5,
        1,   5,   2,   5,   4,   5,   7,   5,  17,   5,
        -22,   6,  -9,   6,  -6,   6,  -3,   6,  -1,   6,
        1,   6,   3,   6,   6,   6,   9,   6,  22,   6,
        -5,   7,  -2,   7,   0,   7,   2,   7,   5,   7,
        -11,   8,  -8,   8,  -3,   8,   0,   8,   3,   8,
        8,   8,  11,   8,  -6,   9,  -1,   9,   1,   9,
        6,   9, -15,  10,  -4,  10,   4,  10,  15,  10,
        -8,  11,  -2,  11,   0,  11,   2,  11,   8,  11,
        19,  12, -19,  13,  -4,  13,   4,  13,   0,  14,
        -10,  15,  10,  15,  -5,  17,   5,  17,   0,  18,
        -12,  19,  13,  19,  -6,  22,   6,  22,   0,  23
    ]
    index *= 255
    assert index + 254 < (len(maketable_bytes) / 2)

    for i in range(255):
        j = (i + index) * 2
        yield maketable_bytes[j + 1] * pitch + maketable_bytes[j]

def print_nothing(code):
    def func(*args):
        print(f'nothing {code}')
        return None
    return func

curtable = 0

def bomp_decode_line(src, decoded_size):
    assert decoded_size > 0

    ln = decoded_size

    # int num
    # byte code, color
    sidx = 0
    didx = 0

    out = [0 for _ in range(decoded_size)]

    while ln > 0:
        code = src[sidx]
        sidx += 1
        num = (code // 2) + 1
        if num > ln:
            num = ln
        ln -= num
        if code & 1:
            color = src[sidx]
            sidx += 1
            out[didx:didx+num] = [color] * num
        else:
            out[didx:didx+num] = src[sidx:sidx+num]
            sidx += num
        didx += num
    
    return out

def action2(delta_bufs, decoded_size, src, seq_nb, mask_flags, bw, bh, pitch, offset_table, delta_size):
    global delta_buf
    global scene_num

    print(f'SCENE {scene_num}')
    scene_num += 1

    dst = delta_bufs[curtable]
    delta_buf[dst:dst+decoded_size] = bomp_decode_line(src, decoded_size)

    if dst > 0:
        # print(f'{frme_num}-DST')
        delta_buf[:dst] = [0] * dst

    tmp = delta_size - dst - decoded_size
    if tmp > 0:
        # print(f'{frme_num}-TMP')
        delta_buf[dst + decoded_size:dst + decoded_size + tmp] = [0] * tmp

def proc3_with_FDFE(out, dst, src, decoded_size, next_offs, bw, bh, pitch, offset_table):

    sidx = 0
    didx = dst

    # had_fdfe = False

    for i in range(bh):
        for j in range(bw):
            code = src[sidx]
            sidx += 1
            if code == 0xFD:
                t = src[sidx]
                sidx += 1
                tmax = 2 ** 32
                t += ((t << 8) % tmax) + ((t << 16) % tmax) + ((t << 24) % tmax)
                for x in range(4):
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = struct.pack('<I', t)
                # had_fdfe = True
            elif code == 0xFE:
                for x in range(4):
                    t = src[sidx]
                    sidx += 1
                    tmax = 2 ** 32
                    t += ((t << 8) % tmax) + ((t << 16) % tmax) + ((t << 24) % tmax)
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = struct.pack('<I', t)
                # had_fdfe = True
            elif code == 0xFF:
                for x in range(4):
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = src[sidx:sidx + 4]
                    sidx += 4
            else:
                didx2 = didx + offset_table[code] + next_offs
                for x in range(4):
                    dpp = didx + pitch * x
                    spp = didx2 + pitch * x
                    out[dpp:dpp + 4] = out[spp:spp + 4]
            didx += 4
        didx += pitch * 3
    # if not had_fdfe:
    #     print(f'flag raised: no FDFE found in proc3_with_FDFE')
    return out[dst:]

def proc3_without_FDFE(out, dst, src, decoded_size, next_offs, bw, bh, pitch, offset_table):

    sidx = 0
    didx = dst

    for i in range(bh):
        for j in range(bw):
            code = src[sidx]
            # if code in [0xFD, 0xFE]:
            #     print(f'flag raised: code {code} in proc3_without_FDFE')
            sidx += 1
            if code == 0xFF:
                for x in range(4):
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = src[sidx:sidx + 4]
                    sidx += 4
            else:
                didx2 = didx + offset_table[code] + next_offs
                for x in range(4):
                    dpp = didx + pitch * x
                    spp = didx2 + pitch * x
                    out[dpp:dpp + 4] = out[spp:spp + 4]
            didx += 4
        didx += pitch * 3
    return out[dst:]

def action3(delta_bufs, decoded_size, src, seq_nb, mask_flags, bw, bh, pitch, offset_table, delta_size):
    global delta_buf
    global curtable

    if (seq_nb & 1) or not (mask_flags & 1):
	    curtable ^= 1

    dst = delta_bufs[curtable]

    proc3 = proc3_with_FDFE if (mask_flags & 4) != 0 else proc3_without_FDFE
    delta_buf[dst:] = proc3(
        delta_buf, dst,
        src, decoded_size,
        delta_bufs[curtable ^ 1] - delta_bufs[curtable], bw, bh,
        pitch, offset_table
    )

def proc4_without_FDFE(out, dst, src, decoded_size, next_offs, bw, bh, pitch, offset_table):

    sidx = 0
    didx = dst
    l = 0

    for i in range(bh):
        for j in range(bw):
            if not l:
                code = src[sidx]
                # if code in [0xFD, 0xFE]:
                #     print(f'flag raised: code {code} in proc4_without_FDFE')
                sidx += 1
            if l == 0 and code == 0xFF:
                for x in range(4):
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = src[sidx:sidx + 4]
                    sidx += 4
            else:
                if l == 0 and code == 0x00:
                    l = src[sidx]
                    sidx += 1
                elif l != 0:
                    l -= 1
                didx2 = didx + offset_table[code] + next_offs
                for x in range(4):
                    dpp = didx + pitch * x
                    spp = didx2 + pitch * x
                    out[dpp:dpp + 4] = out[spp:spp + 4]
            didx += 4
        didx += pitch * 3
    return out[dst:]


def proc4_with_FDFE(out, dst, src, decoded_size, next_offs, bw, bh, pitch, offset_table):

    sidx = 0
    didx = dst
    l = 0

    # had_fdfe = False

    for i in range(bh):
        for j in range(bw):
            if not l:
                code = src[sidx]
                sidx += 1
            if l == 0 and code == 0xFD:
                t = src[sidx]
                sidx += 1
                tmax = 2 ** 32
                t += ((t << 8) % tmax) + ((t << 16) % tmax) + ((t << 24) % tmax)
                for x in range(4):
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = struct.pack('<I', t)
                # had_fdfe = True
            elif l == 0 and code == 0xFE:
                for x in range(4):
                    t = src[sidx]
                    sidx += 1
                    tmax = 2 ** 32
                    t += ((t << 8) % tmax) + ((t << 16) % tmax) + ((t << 24) % tmax)
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = struct.pack('<I', t)
                # had_fdfe = True
            elif l == 0 and code == 0xFF:
                for x in range(4):
                    dpp = didx + pitch * x
                    out[dpp:dpp + 4] = src[sidx:sidx + 4]
                    sidx += 4
            else:
                if l == 0 and code == 0x00:
                    l = src[sidx]
                    sidx += 1
                elif l != 0:
                    l -= 1
                didx2 = didx + offset_table[code] + next_offs
                for x in range(4):
                    dpp = didx + pitch * x
                    spp = didx2 + pitch * x
                    out[dpp:dpp + 4] = out[spp:spp + 4]
            didx += 4
        didx += pitch * 3
    
    # if not had_fdfe:
    #     print(f'flag raised: no FDFE found in proc4_with_FDFE')
    return out[dst:]

def action4(delta_bufs, decoded_size, src, seq_nb, mask_flags, bw, bh, pitch, offset_table, delta_size):
    global delta_buf
    global curtable

    if (seq_nb & 1) or not (mask_flags & 1):
	    curtable ^= 1

    dst = delta_bufs[curtable]

    proc4 = proc4_with_FDFE if (mask_flags & 4) != 0 else proc4_without_FDFE
    delta_buf[dst:] = proc4(
        delta_buf, dst,
        src, decoded_size,
        delta_bufs[curtable ^ 1] - delta_bufs[curtable], bw, bh,
        pitch, offset_table
    )

action_switch = [
    print_nothing(0),
    print_nothing(1),
    action2,
    action3,
    action4
]

delta_buf = None
delta_bufs = None
frme_num = 0
scene_num = 0

def decode37(width, height, f):

    global delta_buf
    global delta_bufs
    global last_frame
    global frme_num

    width = 320
    height = 200

    # with open('FIRST_FOBJ.DAT', 'wb') as aside:
    #     aside.write(f)

    frame_size = width * height

    delta_size = frame_size * 3 + 0x13600

    if not delta_buf:
        # print('HERE1')
        delta_buf = [0 for _ in range(delta_size)]
        delta_bufs = [0x4D80, 0xE880 + frame_size]
    # else:
    #     print('HERE2')
        # print(delta_buf[delta_bufs[curtable]:delta_bufs[curtable]+frame_size])


    # print(delta_bufs)
    # _prevSeqNb = 0;
    # _tableLastPitch = -1;
    # _tableLastIndex = -1;


    bw = (width + 3) // 4
    bh = (height + 3) // 4
    pitch = bw * 4

    seq_nb = read_le_uint16(f[2:])
    decoded_size = read_le_uint32(f[4:])
    mask_flags = f[12]
    offset_table = list(maketable(pitch, f[1]))

    print(f'DECODING FRAME {frme_num} USING {f[0]}, with FDFE: {mask_flags & 4}')
    # print(offset_table)

    # changes globals :/
    action_switch[f[0]](delta_bufs, decoded_size, f[16:], seq_nb, mask_flags, bw, bh, pitch, offset_table, delta_size)

    dst = delta_bufs[curtable]
    out = delta_buf[dst:dst+frame_size]
    frme_num += 1

    return to_matrix(width, height, out)
