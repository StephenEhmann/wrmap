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

import googlemaps
gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

import utils
import kml

# TODO: subdivison alg for getting around the 60 query limit

# Geocoding an address
if (0):
    geocode_result = gmaps.geocode('1600 Amphitheatre Parkway, Mountain View, CA')
    print('geocode_result = ' + str(geocode_result))
    print('')

# Look up an address with reverse geocoding
if (0):
    reverse_geocode_result = gmaps.reverse_geocode((40.714224, -73.961452))
    print('reverse_geocode_result = ' + str(reverse_geocode_result))
    print('')

# Request directions via public transit
if (0):
    now = datetime.now()
    directions_result = gmaps.directions("Sydney Town Hall",
                                         "Parramatta, NSW",
                                         mode="transit",
                                         departure_time=now)
    print('directions_result = ' + str(directions_result))


def init(config):
    data = {}
    for k, v in iter(config['evaluation']['enable'].items()):
        if (v):
            # enabled
            data[k] = {}
            data[k]['module'] = importlib.import_module(k, package=None)
            data[k]['data'] = data[k]['module'].init()
            data[k]['threshold'] = config['evaluation']['threshold'][k]
    return data


def evaluate(loc, data, weight):
    score = 0.0
    for k, v in iter(data.items()):
        #print('eval for ' + k)
        kscore = v['module'].evaluate(loc, v['data'], v['threshold'])
        #print('kscore = ' + str(kscore))
        score += weight[k] * kscore
    return score


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
    parser.add_argument('-geocode', type=str, help='get coordinates and other information for a given named (string) location')
    parser.add_argument('-out', type=str, help='optional output kmz name: <name>.kmz')
    parser.add_argument('-location', type=str, help='location to evaluate')
    parser.add_argument('-resolution', type=int, help='evaluate the entire bounds of the location at this resolution (number of steps in the east/west direction, the north/south direction will be auto-scaled)')
    parser.add_argument('-eval', action='store_true', help='evaluate the overall score')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    # error checking
    if (args.geocode and args.eval or not args.geocode and not args.eval):
        print('ERROR: exactly one action must be given, choose exactly one of -geocode or -eval')
        sys.exit(1)

    if (args.geocode):
        if (args.location or args.resolution):
            print('ERROR: -location and -resolution can only be used with -eval')
            sys.exit(1)
    else:
        if (args.location and args.resolution or not args.location and not args.resolution):
            print('ERROR: for -eval, exactly one of -location or -resolution must be given')
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

    location = locations[config['location']] ['location']
    bounds = locations[config['location']] ['bounds']

    if (args.geocode):
        #print('geocode location ' + args.geocode)
        geocode = gmaps.geocode(args.geocode);
        data = {}
        data[args.geocode] = {}
        data[args.geocode]['location'] = geocode[0]['geometry']['location']
        data[args.geocode]['bounds'] = geocode[0]['geometry']['bounds']
        print('data:')
        print(dump(data, default_flow_style=False, Dumper=Dumper))

    elif (args.eval):
        data = init(config)
        if (args.location):
            latlong = args.location.split(',')
            e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['weight'])
            print(str(e))
        elif (args.resolution):
            results = {}
            if (args.resolution < 2 or args.resolution > 100):
                print('ERROR: -resolution must be a value in the range [2..100]')
                sys.exit(1)

            if (1):
                xstart = bounds['southwest']['lng']
                xend = bounds['northeast']['lng']
                ystart = bounds['southwest']['lat']
                yend = bounds['northeast']['lat']

                xdist = utils.distance( (bounds['southwest']['lat'], bounds['southwest']['lng']),
                                        (bounds['southwest']['lat'], bounds['southwest']['lng'] + 0.1))
                ydist = utils.distance( (bounds['southwest']['lat'], bounds['southwest']['lng']),
                                        (bounds['southwest']['lat'] + 0.1, bounds['southwest']['lng']))
                xstep = (xend - xstart) / args.resolution
                ystep = xstep * xdist / ydist
                #print('xstep = ' + str(xstep))
                #print('ystep = ' + str(ystep))

                if (0):
                    # test the two distances
                    xdist = utils.distance( (bounds['southwest']['lat'], bounds['southwest']['lng']),
                                            (bounds['southwest']['lat'], bounds['southwest']['lng'] + xstep))
                    ydist = utils.distance( (bounds['southwest']['lat'], bounds['southwest']['lng']),
                                            (bounds['southwest']['lat'] + ystep, bounds['southwest']['lng']))
                    print('xdist = ' + str(xdist))
                    print('ydist = ' + str(ydist))

                xi = 0
                x = xstart
                while (x < xend):
                    yi = 0
                    y = ystart
                    while (y < yend):
                        results[(y, x)] = {}
                        results[(y, x)]['val'] = evaluate((y, x), data, config['evaluation']['weight'])
                        results[(y, x)]['name'] = str(xi) + ',' + str(yi)
                        print('x,y = ' + str(x) + ' , ' + str(y) + ' = ' + str(results[(y, x)]['val']))
                        yi += 1
                        y += ystep

                    xi += 1
                    x += xstep

            if (args.out):
                os.makedirs(args.out, exist_ok=True)
                kml.write(os.path.join(args.out, 'doc.kml'), config, data, results)

        else:
            print('INTERNAL ERROR')
            sys.exit(1)

    sys.exit(0)

# test:
# wrmap.py -geocode 'Durham NC'
# wrmap.py -eval -location 35.936164,-79.040997
# wrmap.py -eval -location 35.96253900000001,-78.958224
# wrmap.py -eval -location 35.916752,-78.963430
