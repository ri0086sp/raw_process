import rawpy
import numpy as np
import math
import sys
from scipy import signal

""" Process RAW file into a image file.

Example usage:
raw = read("sample.ARW")
rgb = process(raw)
write(rgb, "output.ARW")
"""


def read(filename):
    """
    Read RAW data from specified file. Currently supported formats are
        ARW (Sony RAW format)

    :param filename: path to the target RAW file
    """
    return rawpy.imread(filename)


def process(raw, color_matrix=(1024, 0, 0, 0, 1024, 0, 0, 0, 1024)):
    """
    This processes RAW data that was read by read() method.
    Must be called after read() operation. No error is checked.
    """
    raw_array = get_raw_array(raw)
    blc_raw = black_level_correction(raw, raw_array)
    dms_img = simple_demosaic(raw, blc_raw)
    img_wb = white_balance(raw, dms_img)
    img_ccm = color_correction_matrix(img_wb, color_matrix)
    img_gamma = gamma_correction(img_ccm)
    return img_gamma


def write(rgb_image, output_filename):
    """
    Write the processed RGB image to a specified file as PNG format.
    Thsi must be called after process(). No error is checked.
    :param output_filename: path to the output file. Extension must be png.
    """
    import imageio
    outimg = rgb_image.copy()
    outimg[outimg < 0] = 0
    outimg = outimg / outimg.max() * 255
    imageio.imwrite(output_filename, outimg.astype('uint8'))


def get_raw_array(raw):
    h, w = raw.sizes.raw_height, raw.sizes.raw_width
    raw_array = np.array(raw.raw_image).reshape((h, w)).astype('float')
    return raw_array


def black_level_correction(raw, raw_array):
    blc = raw.black_level_per_channel
    bayer_pattern = raw.raw_pattern
    blc_raw = raw_array.copy()
    blc_raw[0::2, 0::2] -= blc[bayer_pattern[0, 0]]
    blc_raw[0::2, 1::2] -= blc[bayer_pattern[0, 1]]
    blc_raw[1::2, 0::2] -= blc[bayer_pattern[1, 0]]
    blc_raw[1::2, 1::2] -= blc[bayer_pattern[1, 1]]
    return blc_raw


def preview_demosaic(raw, raw_array):
    bayer_pattern = raw.raw_pattern
    h, w = raw.sizes.raw_height, raw.sizes.raw_width
    shuffle = np.zeros((h // 2, w // 2, 4))
    shuffle[:, :, bayer_pattern[0, 0]] = raw_array[0::2, 0::2]
    shuffle[:, :, bayer_pattern[0, 1]] = raw_array[0::2, 1::2]
    shuffle[:, :, bayer_pattern[1, 0]] = raw_array[1::2, 0::2]
    shuffle[:, :, bayer_pattern[1, 1]] = raw_array[1::2, 1::2]
    dms_img = np.zeros((h // 2, w // 2, 3))
    dms_img[:, :, 0] = shuffle[:, :, 0]
    dms_img[:, :, 1] = (shuffle[:, :, 1] + shuffle[:, :, 3]) / 2
    dms_img[:, :, 2] = shuffle[:, :, 2]
    return dms_img

def simple_demosaic(raw, raw_array):
    h, w = raw_array.shape
    dms_img2 = np.zeros((h, w, 3))

    green = raw_array.copy()
    green[(raw.raw_colors == 0) | (raw.raw_colors == 2)] = 0
    g_flt = np.array([[0, 1 / 4, 0], [1 / 4, 1, 1 / 4], [0, 1 / 4, 0]])
    dms_img2[:, :, 1] = signal.convolve2d(green, g_flt, boundary='symm', mode='same')

    red = raw_array.copy()
    red[raw.raw_colors != 0] = 0
    rb_flt = np.array([[1 / 4, 1 / 2, 1 / 4], [1 / 2, 1, 1 / 2], [1 / 4, 1 / 2, 1 / 4]])
    dms_img2[:, :, 0] = signal.convolve2d(red, rb_flt, boundary='symm', mode='same')

    blue = raw_array.copy()
    blue[raw.raw_colors != 2] = 0
    rb_flt = np.array([[1 / 4, 1 / 2, 1 / 4], [1 / 2, 1, 1 / 2], [1 / 4, 1 / 2, 1 / 4]])
    dms_img2[:, :, 2] = signal.convolve2d(blue, rb_flt, boundary='symm', mode='same')
    return dms_img2

def white_balance(raw, rgb_array):
    wb = np.array(raw.camera_whitebalance)
    img_wb = rgb_array.copy()
    img_wb[:, :, 0] *= wb[0] / 1024
    img_wb[:, :, 1] *= wb[1] / 1024
    img_wb[:, :, 2] *= wb[2] / 1024
    return img_wb


def color_correction_matrix(rgb_array, color_matrix):
    img_ccm = np.zeros_like(rgb_array)
    ccm = np.array(color_matrix).reshape((3, 3))
    for c in (0, 1, 2):
        img_ccm[:, :, c] = ccm[c, 0] * rgb_array[:, :, 0] + \
                           ccm[c, 1] * rgb_array[:, :, 1] + \
                           ccm[c, 2] * rgb_array[:, :, 2]
    return img_ccm / 1024


def gamma_correction(rgb_array):
    img_gamma = rgb_array.copy()
    img_gamma[img_gamma < 0] = 0
    img_gamma = img_gamma / img_gamma.max()
    img_gamma = np.power(img_gamma, 1/2.2)
    return img_gamma

def main(argv):
    if (len(argv) < 2):
        print("Usage: {} input_filename [output_filename] [color_matrix]".format(argv[0]))
        print("\tDefault output_filename is output.png")
        print("\tDefault matrix is identity matrix ([1024, 0, 0, 0, 1024, 0, 0, 0, 1024]")
        print("\tExample: python3 {} sample.ARW sample.png \"1141, -205, 88, -52, 1229, -154, 70, -225, 1179\"".format(argv[0]))
        print("\tSupported RAW format is ARW (Sony RAW)")
        return

    filename = argv[1]
    output_filename = "output.png"
    color_matrix = [1024, 0, 0, 0, 1024, 0, 0, 0, 1024]
    if len(argv) > 2:
        output_filename = argv[2]
    if len(argv) > 3:
        color_matrix = [int(value) for value in (argv[3]).split(',')]

    color_matrix = [1024, 0, 0, 0, 1024, 0, 0, 0, 1024]
    raw = read(filename)
    raw_array = get_raw_array(raw)
    blc_raw = black_level_correction(raw, raw_array)
    dms_img = simple_demosaic(raw, blc_raw)
    img_wb = white_balance(raw, dms_img)
    img_ccm = color_correction_matrix(img_wb, color_matrix)
    rgb_image = gamma_correction(img_ccm)
    write(rgb_image, output_filename)


if __name__ == "__main__":
    main(sys.argv)
