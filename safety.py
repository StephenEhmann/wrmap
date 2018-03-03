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
import json
from datetime import datetime
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import googlemaps
gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

import utils

criterionName = 'safety'

def find(location, bounds, data, safetyMaps):
    for sm in safetyMaps:
        page = utils.get_webpage(sm)

        # host
        m = re.search(r'var assetHost = "(\S+)"', page)
        if (m):
            host = m.group(1)
        else:
            raise Exception('ERROR: Failed to find "var assetHost" in ' + sm)

        # city id
        m = re.search(r'data-id=\'(\d+)\'', page)
        if (m):
            cityId = m.group(1)
        else:
            raise Exception('ERROR: Failed to find "data-id=" in ' + sm)

        # polygon ids
        polyIdsJson = utils.get_webpage('https:' + host + '/polygons/features/cities/' + str(cityId) + '.json')
        polyIds = json.loads(polyIdsJson)
        #print('polys = ' + str(polys))

        for polyId in polyIds:
            neighborhoodPoly = json.loads(utils.get_webpage('https:' + host + '/polygons/polygon/neighborhoods/' + str(polyId) + '.json'))
            #print('neighborhoodPoly for ' + str(polyId) + ' = ' + str(neighborhoodPoly))
            data[polyId] = neighborhoodPoly

def init():
    with open(criterionName + '.yml', 'r') as in_file:
        data = load(in_file, Loader=Loader)
    return data

def evaluate(loc, data, value):
    # polygons are data[id][geometry]<some list nesting><list of x,y pairs (given as a list)>
    # crime data value (higher is more safe) is given by data[id][properties][c]
    return 0.0


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
    parser.add_argument('-find', action='store_true', help='find all DB items and write them to ' + criterionName + '.yml')
    parser.add_argument('-eval', type=str, help='evaluate the ' + criterionName + ' score for a given coordinate pair (eg. -eval 35.936164,-79.040997)')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (args.find and args.eval or not args.find and not args.eval):
        print('ERROR: exactly one action must be given, choose exactly one of -find or -eval')
        sys.exit(1)

    # read locations
    try:
        stream = open('location.yml', 'r')
        locations = load(stream, Loader=Loader)
        stream.close()
    except Exception as e:
        print(str(e))
        raise Exception('ERROR: Failed to load yaml file ' + 'config.yml')

    # read config
    try:
        stream = open('config.yml', 'r')
        config = load(stream, Loader=Loader)
        stream.close()
    except Exception as e:
        print(str(e))
        raise Exception('ERROR: Failed to load yaml file ' + 'config.yml')

    bounds = locations[config['location']] ['bounds']
    location = utils.centroid(bounds)

    if (args.find):
        data = {}
        find(location, bounds, data, config['find'][criterionName])

        with open(criterionName + '_polys.yml', 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

    elif (args.eval):
        data = init()
        latlong = args.eval.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['value'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
