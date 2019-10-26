from typing import IO, Optional

CHIPER_KEY = 0x69

def read(stream: IO[bytes], size: Optional[int] = None, key = CHIPER_KEY):
    return bytes(b ^ key for b in stream.read(size))  # type: ignore  # None reads until EOF

if __name__ == '__main__':
    import argparse
    from functools import partial

    from nutcracker.utils import copyio

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('output', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename,'rb') as infile, open(args.output,'wb') as outfile:
        for buffer in copyio.buffered(partial(read, infile, key=CHIPER_KEY)):
            outfile.write(buffer)
