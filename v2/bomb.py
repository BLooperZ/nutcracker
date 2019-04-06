
def decode_line(src, decoded_size):
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
        if code % 2 == 0:
            out[didx:didx+num] = src[sidx:sidx+num]
            sidx += num
        else:
            color = src[sidx]
            sidx += 1
            out[didx:didx+num] = [color] * num
        didx += num
    
    return out
