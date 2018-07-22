import png

def read_image(stream):
    w = png.Reader(stream)
    r = w.read()
    lines = list(r[2])
    size = r[3]['size']

    width, height = size
    data = []
    for line in lines:
        row = list(line)
        if row[-1] == 255:
            row = [a for idx, a in enumerate(row) if idx % 2 == 0]
        data.append(row)
    return width, height, data

def save_image(filename, data):
    width, height, lines = data
    with open(filename, 'wb') as outFile:
        wr = png.Writer(width, height, greyscale=True)
        wr.write(outFile, lines)