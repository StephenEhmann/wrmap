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
import colorsys
from datetime import datetime
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from PIL import Image

import utils

# https://en.wikipedia.org/wiki/Hue
# TODO: feature to add: variable range lengths like this:
#    'red_green': { 'ranges': 10, 'ranges': [(0.0, 255,0,0), (0.3, 255,255,0), (1.0, 0,255,0)] },
quant = {
    #RETIRED because red_green_hue does the same thing... 'red_yellow_green': { 'mode': 'rgb', 'numValues': 10, 'ranges': [ [(255,0,0), (255,255,0)], [(255,255,0), (0,255,0)] ] },
    'red_white_green': { 'mode': 'hsv', 'blend': 's', 'numValues': 10, 'ranges': [ [(0.0,1.0,1.0), (0.0,0.0,1.0)], [(120.0/360.0,0.0,1.0), (120.0/360.0,1.0,1.0)] ] },
    'red_white_blue': { 'mode': 'hsv', 'blend': 's', 'numValues': 10, 'ranges': [ [(0.0,1.0,1.0), (0.0,0.0,1.0)], [(240.0/360.0,0.0,1.0), (240.0/360.0,1.0,1.0)] ] },
    'red_green_hue': { 'mode': 'hsv', 'blend': 'h', 'numValues': 10, 'ranges': [ [(0.0,1.0,1.0), (120.0/360.0,1.0,1.0)] ] },
}

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
        data[x,height-y-1] = val
    im.save(filename, "PNG")

def transform(i, o):
    img = Image.open(i)
    rgb_im = img.convert('RGB')
    pix = rgb_im.load()
    if (0):
        #rgb_im[1,1] = (0,0,255)
        pix[10,1] = (0,0,255)
        if (1):
            r, g, b = rgb_im.getpixel((1, 1))
            r2, g2, b2 = pix[1,1]
        else:
            r, g, b = img.getpixel((1, 1))
        print(r, g, b)
        print(r2, g2, b2)

    width, height = img.size
    fi = [[0 for x in range(width)] for y in range(height)]
    for y in range(height):
        for x in range(width):
            r, g, b = pix[x,y]
            if (r == 255):
                i = 510 - g
            elif (g == 255):
                i = r
            else:
                raise Exception('bad color')
            f = 1.0 - i / 510.0
            #print('x,y,f = ' + str((x, y, f)))
            fi[y][x] = f
            intVal = int(510 * (1.0 - f))
            blue = 0
            if (intVal >= 255):
                red = 255
                green = 255 - (intVal - 255)
            else:
                red = intVal
                green = 255
            if (0 and (red, green, blue) != (r, g, b)):
                print('diff: ' + str((x, y, f)) + ' ' + str((red, green, blue)) + ' ' + str((r, g, b)))
            pix[x,y] = (red, green, blue)

    rgb_im.save(o, "PNG")

def interpolate(r, t):
    return r[0] * (1.0-t) + r[1] * t

def interpolate_rgb(r, t):
    return ( int(r[0][0] * (1.0-t) + r[1][0] * t + 0.5), int(r[0][1] * (1.0-t) + r[1][1] * t + 0.5), int(r[0][2] * (1.0-t) + r[1][2] * t + 0.5) )

def my_hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255.0), int(g * 255.0), int(b * 255.0))

def qtestImage(n, q):
    img = Image.new('RGB', (q['numValues'], 1))
    pix = img.load()
    if (0):
        ranges = []
        pprev = None
        for p in q['p']:
            if (pprev):
                ranges.append([pprev, p])
            pprev = p
        print('ranges = ' + str(ranges))

    for i in range(1, 2 * q['numValues'], 2):  # sample midpoints of each quantized range
        rangeLen = q['numValues'] / len(q['ranges'])
        colorRange = int((i-1) // 2 / rangeLen)
        #print('cr = ' + str(colorRange))
        #colorRange = int(i * len(q['ranges']) / (2 * q['numValues']))
        a = int(colorRange * rangeLen)
        b = int((colorRange+1) * rangeLen)
        t = ((i-1)//2 - a) / (b - a)
        print('a,b,t = ' + str((a, b, t)))
        if (q['mode'] == 'rgb'):
            pix[(i-1) // 2, 0] = interpolate_rgb(q['ranges'][colorRange], t)
            print('color at ' + str((i-1) // 2) + ' = ' + str(pix[(i-1) // 2, 0]))
        elif (q['mode'] == 'hsv'):
            if ('h' in q['blend']):
                h = interpolate( (q['ranges'][colorRange][0][0], q['ranges'][colorRange][1][0]), t)
            else:
                h = q['ranges'][colorRange][0][0]
            if ('s' in q['blend']):
                s = interpolate( (q['ranges'][colorRange][0][1], q['ranges'][colorRange][1][1]), t)
            else:
                s = q['ranges'][colorRange][0][1]
            if ('v' in q['blend']):
                v = interpolate( (q['ranges'][colorRange][0][2], q['ranges'][colorRange][1][2]), t)
            else:
                v = q['ranges'][colorRange][0][2]
            print('hsv = ' + str((h, s, v)))
            pix[(i-1) // 2, 0] = my_hsv_to_rgb(h, s, v)
        else:
            raise Exception('unrecognized color mode')
    img.save(n + '.png', 'PNG')

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
    parser.add_argument('-input', type=str, help='input filename')
    parser.add_argument('-out', type=str, help='optional output png name: <name>.png')
    parser.add_argument('-q', type=str, help='choose the qunatized color scheme, default red_gree')
    parser.add_argument('-qtest', action='store_true', help='output quantized color scheme gradient images')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (args.qtest):
        for n, q in iter(quant.items()):
            qtestImage(n, q)
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
    if (not re.search(r'\.png', args.input)):
        args.input += '.png'

    if (not args.out):
        args.out = re.sub(r'\.png$', r'_out.png', args.input)
    if (not re.search(r'\.png', args.out)):
        args.out += '.png'

    transform(args.input, args.out)

