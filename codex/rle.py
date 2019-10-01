from typing import Sequence

def encode_lined_rle(bmap: Sequence[Sequence[int]]) -> bytes:
    print('======================')
    for line in bmap:
        print(line)
    return b''

def decode_lined_rle(data, width, height):
    datlen = len(data)

    output = [[0 for _ in range(width)] for _ in range(height)]

    pos = 0
    next_pos = pos
    for curry in range(height):
    # while pos < datlen and curry < height:
        currx = 0
        bytecount = int.from_bytes(data[next_pos:next_pos + 2], byteorder='little', signed=False)
        pos = next_pos + 2
        next_pos += bytecount + 2
        while pos < datlen and pos < next_pos:
            code = data[pos]
            pos += 1
            print(code)
            if code & 1:  # skip count
                print('skip')
                currx += (code >> 1)
            else:
                count = (code >> 2) + 1
                if code & 2:  # encoded run
                    print('encoded')
                    output[curry][currx:currx+count] = [data[pos]] * count
                    pos += 1
                else:  # absolute run
                    print('absolute')
                    output[curry][currx:currx+count] = data[pos:pos+count]
                    pos += count
                currx += count
            assert not currx > width
    return output
