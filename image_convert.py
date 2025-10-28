#!/usr/bin/env python
# -*- coding: us-ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""Convert (bitmap) image into 7 color BMP, suitable for e-ink color display
"""

import argparse
import glob
import os.path
import sys

from PIL import Image, ImagePalette, ImageOps


is_py3 = sys.version_info >= (3,)

def open_parse_gimp_palette_gpl_file(filename):
    f = open(filename)

    color_names = {}
    color_names_list = []  # ordered as found in GIMP Palette gpl file
    found_colors = False
    color_entry_style = 'UNKNOWN'
    for line in f:
        line = line.strip()
        if not line:
            continue
        #print('*LINE: %r' % line)  # DEBUG
        if line == '#':
            found_colors = True
            continue
        if not found_colors and line.startswith('#Colors:'):
            color_entry_style = 'DECIMAL_RBG+HEX'
            found_colors = True
            continue
        if not found_colors and line.startswith('Name:'):
            continue
        if not found_colors and line.startswith('Columns:'):
            expected_column_count = int(line.split(':')[1])  # expecting 3....
            if expected_column_count == 1:
                color_entry_style = 'DECIMAL_RBG+HEX'  # appears to be similar to named but tabs instead of spaces and names not hex?
            elif expected_column_count in (3, 16):
                color_entry_style = 'NAMED'  # 3 for RGB and + 1 for name
            else:
                raise NotImplementedError('%d columns for colors' % expected_column_count)
            continue
        if found_colors:
            #print('LINE: %r' % line)
            #print('LINE: %r' % line.split())
            if color_entry_style == 'NAMED':
                colors, color_name = line.split('\t')
                r, g, b = map(int, colors.split())
                #print(color_name, r, g, b)
                if color_name in color_names:
                    color_name += '_%02x%02x%02x' % (r, g, b)
                color_names[color_name] = (r, g, b)
            elif color_entry_style == 'DECIMAL_RBG+HEX':
                color_name = 'blank'
                r, g, b, hex_rgb = line.split('\t')
                color_name = hex_rgb
                colors = (r, g, b)
                r, g, b = map(int, colors)
                #print(color_name, r, g, b)
                if color_name in color_names:
                    color_name += '_%02x%02x%02x' % (r, g, b)
                color_names[color_name] = (r, g, b)
            else:
                raise NotImplementedError('Entry style %s' % color_entry_style)
            color_names_list.append(color_name)

    f.close()
    return color_names, color_names_list

def gpl2pil_256palette(filename):
    color_palette, color_names_ordered = open_parse_gimp_palette_gpl_file(filename)
    rgb_list = []
    for color_name in color_names_ordered:
        rgb_tuple = color_palette[color_name]
        rgb_list.append(rgb_tuple[0])  # dumb but seems to work...
        rgb_list.append(rgb_tuple[1])
        rgb_list.append(rgb_tuple[2])
    if len(color_names_ordered) < 256:
        rgb_list += [0] * (3 * (256 - len(color_names_ordered)))
    print(len(rgb_list))
    print(len(rgb_list) / 3)
    return rgb_list

# this function quantizetopalette() is from https://stackoverflow.com/questions/29433243/convert-image-to-specific-palette-using-pil-without-dithering
def quantizetopalette(silf, palette, dither=False):
    """Convert an RGB or L mode image to use a given P image's palette."""

    silf.load()

    # use palette from reference image
    palette.load()
    if palette.mode != "P":
        raise ValueError("bad mode for palette image")
    if silf.mode != "RGB" and silf.mode != "L":
        raise ValueError(
            "only RGB or L mode images can be quantized to a palette"
            )
    im = silf.im.convert("P", 1 if dither else 0, palette.im)
    # the 0 above means turn OFF dithering

    # Really old versions of Pillow (before 4.x) have _new
    # under a different name
    try:
        return silf._new(im)
    except AttributeError:
        return silf._makeself(im)

def mygetpalette(pal_type, orig_image_palette):
    # return palette list of tuples in RGB order
    palette = []
    if pal_type != "RGB":
        return palette
    image_palette = orig_image_palette[:]
    while image_palette != []:
        r = image_palette.pop(0)
        g = image_palette.pop(0)
        b = image_palette.pop(0)
        palette.append( (r, g, b) )
    return palette

def save_4bit_index_nano_raw(im):
    """im is a PIL.Image
    """
    out_filename = 'test_4bit.bin'  # DEBUG FIXME
    width, height = im.size
    # Sanity checks on assumptions
    if 'getdata' not in dir(im.palette):
        raise NotImplementedError('image must be indexed, try a PNG or GIF')
    pal_type, pal_data = im.palette.getdata()
    if pal_type != "RGB":
        raise NotImplementedError('Need RGB palette, try a PNG file (instead of BMP)')

    print(pal_data)
    if is_py3:
        pal_data = list(pal_data)
    else:
        pal_data = list(map(ord, pal_data))  # py2 bytes to ints

    indexed_palette = mygetpalette(pal_type,pal_data) ## must contain accurate palette

    print('save_4bit_index_nano_raw() palette')
    print(indexed_palette)
    p_count = 0
    for entry in indexed_palette:
        print(p_count, entry)
        p_count += 1

    pixels = list(im.getdata())
    fo = open(out_filename, 'wb')

    fo.write(b"".join((height.to_bytes(2, "big"), width.to_bytes(2, "big"))))

    pixel_counter = 0
    nibbles = [0, 0]
    while pixel_counter < len(pixels):
        for n in range(2):
            c = pixels[pixel_counter]
            nibbles[n] = c
            pixel_counter += 1
        #print('DEBUG: %d, %d' % (nibbles[0], nibbles[1]))
        fo.write(int.to_bytes((nibbles[0] << 4) | nibbles[1], 1, "big"))

    fo.close()
    print('wrote: %r' % (out_filename,))

def convert_one(input_filename, display_direction=None, display_mode='scale', display_dither=Image.FLOYDSTEINBERG, pil_256_color_palette=None, resolution=None):
    # If missing, default to 7-color eink palette.    Black, White,       Green,   Blue,    Red,     Yellow,    Orange     # unused-black for remaining
    pil_256_color_palette = pil_256_color_palette or (0,0,0, 255,255,255, 0,255,0, 0,0,255, 255,0,0, 255,255,0, 255,128,0) + (0,0,0)*249
    resolution = resolution or (800, 480)
    # Read input image
    input_image = Image.open(input_filename)

    # Get the original image size
    width, height = input_image.size

    # Specified target size
    if display_direction:
        if display_direction == 'landscape':
            target_width, target_height = resolution
        else:  # portrait
            target_width, target_height = resolution[1], resolution[0]
    else:
        if  width > height:  # landscape
            target_width, target_height = resolution
        else:  # portrait
            target_width, target_height = resolution[1], resolution[0]
        
    if display_mode == 'scale':
        # Computed scaling
        scale_ratio = max(target_width / width, target_height / height)

        # Calculate the size after scaling
        resized_width = int(width * scale_ratio)
        resized_height = int(height * scale_ratio)

        # Resize image
        output_image = input_image.resize((resized_width, resized_height))

        # Create the target image and center the resized image
        resized_image = Image.new('RGB', (target_width, target_height), (255, 255, 255))
        left = (target_width - resized_width) // 2
        top = (target_height - resized_height) // 2
        resized_image.paste(output_image, (left, top))
    elif display_mode == 'cut':
        # Calculate the fill size to add or the area to crop
        if width / height >= target_width / target_height:
            # The image aspect ratio is larger than the target aspect ratio, and padding needs to be added on the left and right
            delta_width = int(height * target_width / target_height - width)
            padding = (delta_width // 2, 0, delta_width - delta_width // 2, 0)
            box = (0, 0, width, height)
        else:
            # The image aspect ratio is smaller than the target aspect ratio and needs to be filled up and down
            delta_height = int(width * target_height / target_width - height)
            padding = (0, delta_height // 2, 0, delta_height - delta_height // 2)
            box = (0, 0, width, height)

        resized_image = ImageOps.pad(input_image.crop(box), size=(target_width, target_height), color=(255, 255, 255), centering=(0.5, 0.5))


    # Create a palette object
    pal_image = Image.new("P", (1,1))
    #                       Black, White,           Green,  Blue,       Red,    Yellow,     Orange  # unused-black for remaining
    pal_image.putpalette(pil_256_color_palette)
      
    # The color quantization and dithering algorithms are performed, and the results are converted to RGB mode
    quantized_image = resized_image.quantize(dither=display_dither, palette=pal_image).convert('RGB')
    print('quantized_image.mode: %r' % (quantized_image.mode,))
    """
    palette_image = quantized_image.convert("P", palette=Image.ADAPTIVE, colors=16)  # FIXME / DEBUG
    #palette_image = quantized_image.convert("P", palette=pal_image, colors=16)  # FIXME / DEBUG - too many colors
    #palette_image = quantized_image.convert("P", palette=pal_image, colors=16)  # FIXME / DEBUG - this does not preserve the palette location/indexes :-( turns out palette param is a boolean, not palette content :-(
    palette_image = quantizetopalette(quantized_image, pal_image, dither=False)  # This works, but palette information appears to be missing, which is wierd but seems to work as bin convertor ignores it :-)
    print('palette_image.mode: %r' % (palette_image.mode,))
    save_4bit_index_nano_raw(palette_image)  # FIXME / TODO
    """

    # Save output image
    # for 7-color eink, need 24-bit BMP
    output_filename = os.path.splitext(input_filename)[0] + '_' + display_mode + '_output.bmp'
    quantized_image.save(output_filename)
    return output_filename


def main(argv=None):
    if argv is None:
        argv = sys.argv

    print('Python %s on %s' % (sys.version.replace('\n', ' '), sys.platform.replace('\n', ' ')))
    """
    # DEBUG
    #filename = argv[1]
    filename = os.path.join('palettes', 'nano_4-bit_colors.gpl')  # FIXME
    color_palette, color_names_ordered = open_parse_gimp_palette_gpl_file(filename)
    pil_256_color_palette = gpl2pil_256palette(filename)
    print(color_palette)
    print(color_names_ordered)
    print(pil_256_color_palette)
    resolution = (320, 240)
    #return
    """

    filename = os.path.join(os.path.dirname(__file__), 'palettes', 'eink_7-color.gpl')  # default palette
    pil_256_color_palette = gpl2pil_256palette(filename)
    resolution = None
    #resolution = (800, 480)

    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description='Process some images.')

    # Add orientation parameter
    parser.add_argument('image_file', type=str, help='Input image file')  # TODO multiple arguments AND wildcard
    parser.add_argument('--dir', choices=['landscape', 'portrait'], help='Image direction (landscape or portrait)')
    parser.add_argument('--mode', choices=['scale', 'cut'], default='scale', help='Image conversion mode (scale or cut)')
    parser.add_argument('--dither', type=int, choices=[Image.NONE, Image.FLOYDSTEINBERG], default=Image.FLOYDSTEINBERG, help='Image dithering algorithm (NONE(0) or FLOYDSTEINBERG(3))')

    # Parse command line arguments
    args = parser.parse_args()

    # Get input parameter
    input_filename = args.image_file
    display_direction = args.dir
    display_mode = args.mode
    display_dither = Image.Dither(args.dither)


    if '*' in input_filename:
        # wildcard, probably Windows...
        filenames = glob.glob(input_filename)
    else:
        filenames = [input_filename]  # for now, assume a single parameter

    for filename in filenames:
        print('Processing %s' % (filename,))
        # TODO revisit below
        # Check whether the input file exists
        if not os.path.isfile(filename):
            print(f'Error: file {filename} does not exist')
            sys.exit(1)
        # TODO revisit above
        output_filename = convert_one(filename, display_direction, display_mode, display_dither, pil_256_color_palette=pil_256_color_palette, resolution=resolution)
        print(f'\tSuccessfully converted {filename} to {output_filename}')

    return 0


if __name__ == "__main__":
    sys.exit(main())
