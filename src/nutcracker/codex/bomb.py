import io


def decode_line(src, decoded_size):
    with io.BytesIO(src) as stream:
        return decode_line_stream(stream, decoded_size)


def decode_line_stream(stream, decoded_size):
    assert decoded_size > 0
    with io.BytesIO() as out:
        while out.tell() < decoded_size:
            code = ord(stream.read(1))
            run_len = (code // 2) + 1
            line = stream.read(1) * run_len if code & 1 else stream.read(run_len)
            out.write(line)
        if out.tell() > decoded_size:
            raise ValueError('out of bounds')
        return list(out.getvalue())
