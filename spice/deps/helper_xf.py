#!/usr/bin/python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.

import logging
import argparse
import time

from dogtail import tree
from dogtail.rawinput import press, release, absoluteMotion, keyCombo

from PIL import Image, ImageDraw

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
    description='Helper to operate on file transfer.')

parser.add_argument("file_n", nargs='?', metavar='FILE', default="test.png",
                    help="Specify file name.")

group = parser.add_mutually_exclusive_group()
group.add_argument("-g", "--genimg", metavar='INT', nargs='?', type=int,
                   help="Generate an image of side size INT pixels.")

args = parser.parse_args()

if args.genimg:
    size_img = args.genimg
    img = Image.new('RGB', size=(size_img, size_img), color='yellow')
    draw = ImageDraw.Draw(img)
    for i in range(0, size_img, 3):
        draw.line([(i, 0), (size_img, size_img)], fill='green')
        draw.line([(0, i), (size_img, size_img)], fill='red')
        draw.line([(size_img, 0), (0, i)], fill='blue')
    draw.ellipse((0.6*size_img, 0.15*size_img, 0.8*size_img, 0.3*size_img),
                 fill='red')
    with open(args.file_n, 'w') as fd:
        img.save(fd, args.file_n.split(".")[-1])
else:
    app_nau = tree.root.application('nautilus')[0]
    app_rv = tree.root.application('remote-viewer')[0]
    time.sleep(0.6)
    keyCombo('<Super_L>Left')
    time.sleep(0.6)
    srcf = app_nau.findChildren(lambda x: x.name == args.file_n)[0]
    src_position = (srcf.position[0] + srcf.size[0] / 2,
                    srcf.position[1] + srcf.size[1] / 2)
    press(*src_position)
    trgt = app_rv.findChildren(lambda x: x.roleName == "drawing area")[0]
    dest_position = (trgt.position[0] + (3 * trgt.size[0]) / 4,
                     trgt.position[1] + trgt.size[1] / 2)
    absoluteMotion(*dest_position)
    # magic in dogtail
    absoluteMotion(*dest_position)
    release(*dest_position)
