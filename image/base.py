from PIL import Image
import numpy as np

def convert_to_pil_image(char, size=None):
    # print('CHAR:', char)
    npp = np.array(list(char), dtype=np.uint8)
    if size:
        width, height = size
        npp.resize(height, width)
    im = Image.fromarray(npp, mode='P')
    return im
