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
import xml
from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.dom import minidom

import utils

def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = xml.etree.ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def SubElementWithText(parent, tag, text, attrib={}):
    element = SubElement(parent, tag, attrib=attrib)
    if (text != None):
        element.text = text
    return element

icons = {
    'balloon': '1899',
    'house': '1603',
    'shopping cart': '1685',
    'bus': '1532',
}

def addFolder(doc, name):
    folder = SubElement(doc, 'Folder')
    name = SubElementWithText(folder, 'name', name)
    return folder

def addStyle(doc, color, icon):
    color = str(color)
    color = color.upper()

    if (icon not in icons):
        raise Exception('ERROR: invalid icon given, allowed icons are ' + icons.keys())
    icon = icons[icon]

    style = SubElement(doc, 'Style', {'id': 'icon-' + icon + '-' + color + '-nodesc-normal'})
    iconStyle = SubElement(style, 'IconStyle')
    iconElem = SubElement(iconStyle, 'Icon')
    href = SubElementWithText(iconElem, 'href', 'http://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png')

    style = SubElement(doc, 'Style', {'id': 'icon-' + icon + '-' + color + '-nodesc-highlight'})
    iconStyle = SubElement(style, 'IconStyle')
    iconElem = SubElement(iconStyle, 'Icon')
    href = SubElementWithText(iconElem, 'href', 'http://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png')

    styleMap = SubElement(doc, 'StyleMap', {'id': 'icon-' + icon + '-' + color + '-nodesc'})
    pair = SubElement(styleMap, 'Pair')
    key = SubElementWithText(pair, 'key', 'normal')
    styleUrl = SubElementWithText(pair, 'styleUrl', '#icon-' + icon + '-' + color + '-nodesc-normal')
    pair = SubElement(styleMap, 'Pair')
    key = SubElementWithText(pair, 'key', 'highlight')
    styleUrl = SubElementWithText(pair, 'styleUrl', '#icon-' + icon + '-' + color + '-nodesc-highlight')

    return '#icon-' + icon + '-' + color + '-nodesc'

def addPoint(folder, style, name, coords):
    pm = SubElement(folder, 'Placemark')
    name = SubElementWithText(pm, 'name', name)
    #desc = SubElementWithText(pm, 'description', 'desc of point')
    styleUrl = SubElementWithText(pm, 'styleUrl', style)
    point = SubElement(pm, 'Point')
    coords = SubElementWithText(point, 'coordinates', str(coords[0]) + ',' + str(coords[1]) + ',0')

def write(filename, config, data, results):
    root = Element('kml')
    root.set('xmlns', 'http://www.opengis.net/kml/2.2')

    doc = SubElement(root, 'Document')
    name = SubElement(doc, 'name')
    name.text = 'evaluation'

    # create the style map
    valueStyles = []
    total = 255 + 255
    steps = 6
    stepSize = round((255 + 255) / (steps - 1))
    while (total >= 0):
        if (total >= 255):
            red = 255
            green = 255 - (total - 255)
        else:
            red = total
            green = 255
        hexRed = '%02X' % red
        hexGreen = '%02X' % green
        #print(hexRed)
        #hexRed = '{num:2X}'.format(num=red)
        #print(hexRed)
        #hexRed = format(red, '02d')
        #print(hexRed)
        #hexGreen = format(green, 'X')
        #valueIndex = round((255 + 255 - total) / (255 + 255) * (steps-1))
        valueStyles.append(addStyle(doc, hexRed + hexGreen + '00', 'balloon'))
        print('color[' + str((255 + 255 - total) / (255 + 255)) + '] = ' + str(red) + ' '  + str(green) + '  ' + hexRed + hexGreen + '00')
        total -= stepSize

    folder = addFolder(doc, 'values')
    for l, v in iter(results.items()):
        valueIndex = round(v['val'] * (steps-1))
        addPoint(folder, valueStyles[valueIndex], v['name'], (l[1], l[0]))

    for k, c in iter(data.items()):
        style = addStyle(doc, config[k]['style']['color'], config[k]['style']['icon'])
        folder = addFolder(doc, k)
        for i, v in iter(c['data'].items()):
            addPoint(folder, style, v['name'], (v['location']['lng'], v['location']['lat']))

    with open(filename, 'w') as kml_file:
        kml_file.write(prettify(root))

