#!/home/utils/Python-3.6.1/bin/python3

import os
import sys
import subprocess
import tempfile
import time
import traceback
import argparse
import glob
import re
import time
import importlib
from datetime import datetime
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from PIL import Image

import utils

def write(filename, config, results, width, height):
    im = Image.new("RGB", (width, height))
    data = im.load()
    for (x, y), v in iter(results.items()):
        #print('x,y ' + str((x, y)) + ' = ' + str(v))
        intVal = int(510 * (1.0 - v))
        blue = 0
        if (intVal >= 255):
            red = 255
            green = 255 - (intVal - 255)
        else:
            red = intVal
            green = 255

        val = (red, green, blue)
        #        int(255 * (1.0 - v)),
        #        int(255 * v),
        #        0
        #      )
        data[x,height-y-1] = val
    im.save(filename, "PNG")

    if (0):
        im = Image.new("RGB", (2, 2))
        pix = im.load()
        for x in range(2):
            for y in range(2):
                pix[x,y] = (255,0,0)
        im.save(filename, "PNG")

    if (0):
        data = bytes()
        for i in range( 2**2 ):
            data += bytes(255) + bytes(0) + bytes(0)
        print('data = ' + str(data))
        im = Image.frombytes("RGB", (2,2), data)
        im.save(filename, "PNG")

    if (0):
        print('write ' + str(width) + ' ' + str(height))
        data = [(0, 0, 0) for x in range(width * height)]
        for (x, y), v in iter(results.items()):
            #print('x = ' + str(x))
            #print(str(type(x)))
            #print(str(type(y)))
            #print(str(type(width)))
            #z = x + y*width
            #print(str(type(z)))
            val = (
                    int(255 * (1.0 - v)),
                    int(255 * v),
                    0
                  )
            data[x + y*width] = val
            print(str(x + y*width) + ' = ' + str(val))
        print('data = ' + str(data))
        im = Image.new('L', (width, height))
        im.putdata(data)
        im.save(filename,"PNG")

    if (0):
        data = bytearray([0] * width * height)
        for (x, y), v in iter(results.items()):
            val = (
                    int(255 * (1.0 - v)),
                    int(255 * v),
                    0
                  )
            data[x + y*width] = val
        im = Image.frombytes('L', (width, height), str(data))
        im.save(filename,"PNG")

if (__name__ == "__main__"):
    # main parser
    class MainParser(argparse.ArgumentParser):
        def error(self, message):
            self.print_help()
            sys.stderr.write('error: %s\n' % message)
            sys.exit(2)
    parser = MainParser(add_help=False, allow_abbrev=False)
    parser.add_argument('-h', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--h', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-help', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--help', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-debug', action='store_true', help='print extra info')
    parser.add_argument('-cr', type=str, help='criterion name (eg. bus)')
    parser.add_argument('-input', type=str, help='input filename')
    parser.add_argument('-out', type=str, help='optional output kmz name: <name>.kmz')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (0):
        newImg1 = Image.new('RGB', (512,512))
        pixels1 = newImg1.load()
        for i in range (0,511):
            for j in range (0,511):
                pixels1[i, 511-j]=(0,0,0)
        #newImg1.PIL.save("img1.png")
        newImg1.save("img1.png","PNG")
        sys.exit(0)

    # read config
    try:
        stream = open('config.yml', 'r')
        config = load(stream, Loader=Loader)
        stream.close()
    except Exception as e:
        print(str(e))
        raise Exception('ERROR: Failed to load yaml file ' + 'config.yml')

    if (not args.input):
        raise Exception('ERROR: no -input file given')

    if (not args.cr):
        raise Exception('ERROR: no -cr criterion name given')

    if (not args.out):
        args.out = re.sub(r'\.yml$', r'.kmz', args.input)
    else:
        if (not re.search(r'\.kmz', args.out)):
            args.out += '.kmz'

    try:
        stream = open(args.input, 'r')
        data = load(stream, Loader=Loader)
        stream.close()
    except Exception as e:
        print(str(e))
        raise Exception('ERROR: Failed to load yaml file ' + args.input)

    # TODO
    #write(args.out, config, data, None)

