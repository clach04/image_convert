#!/usr/bin/env python
# -*- coding: us-ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""Convert (bitmap) image into 7 color BMP, suitable for e-ink color display
"""

import argparse
import os.path
import sys

from PIL import Image, ImagePalette, ImageOps


def convert_one(input_filename, display_direction=None, display_mode='scale', display_dither=Image.FLOYDSTEINBERG):
    # Read input image
    input_image = Image.open(input_filename)

    # Get the original image size
    width, height = input_image.size

    # Specified target size
    if display_direction:
        if display_direction == 'landscape':
            target_width, target_height = 800, 480
        else:  # portrait
            target_width, target_height = 480, 800
    else:
        if  width > height:  # landscape
            target_width, target_height = 800, 480
        else:  # portrait
            target_width, target_height = 480, 800
        
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
    pal_image.putpalette( (0,0,0,  255,255,255,  0,255,0,   0,0,255,  255,0,0,  255,255,0, 255,128,0) + (0,0,0)*249)
      
    # The color quantization and dithering algorithms are performed, and the results are converted to RGB mode
    quantized_image = resized_image.quantize(dither=display_dither, palette=pal_image).convert('RGB')

    # Save output image
    output_filename = os.path.splitext(input_filename)[0] + '_' + display_mode + '_output.bmp'
    quantized_image.save(output_filename)
    return output_filename


def main(argv=None):
    if argv is None:
        argv = sys.argv

    print('Python %s on %s' % (sys.version.replace('\n', ' '), sys.platform.replace('\n', ' ')))

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

    # Check whether the input file exists
    if not os.path.isfile(input_filename):
        print(f'Error: file {input_filename} does not exist')
        sys.exit(1)

    output_filename = convert_one(input_filename, display_direction, display_mode, display_dither)

    print(f'Successfully converted {input_filename} to {output_filename}')

    return 0


if __name__ == "__main__":
    sys.exit(main())
