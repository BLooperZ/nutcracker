import os
from image import read_image

def from_font_image(args):
    def read_char():
        yoff = 0
        for _ in range(numChars):
            lines = data[yoff:yoff+h]
            yoff += h
            bg = lines[0][-1]
            w = -1
            while lines[0][w] == bg:
                w -= 1
            he = -1
            while lines[he][0] == bg:
                he -= 1
            w = width + w + 1
            he = h + he + 1
            yield w, he, [line[:w] for line in lines[:he]]

    width, height, data = args
    height = len(data)
    width = len(data[0])
    bg = data[0][-1]
    h = 0
    while data[h][-1] == bg:
        h += 1
    numChars = height / h
    return numChars, read_char()

def from_directory(dirname):
    files = os.listdir(dirname)
    for filename in files:
        with open(dirname + '/' + filename, 'rb') as f:
            yield f

def from_char_images(streams):
    return (read_image(im) for im in streams)
