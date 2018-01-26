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
from datetime import datetime
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import googlemaps
gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

import utils

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

def find(location, bounds, data, glist, name=None):
    if (0):
        geocode = gmaps.geocode('Durham NC');
        print('location = ' + str(geocode[0]['geometry']['location']))
        print('bounds = ' + str(geocode[0]['geometry']['bounds']))
        if (0):
            print('geocode:')
            print(dump(geocode, default_flow_style=False, Dumper=Dumper))

    more = True
    token = None
    while (more):
        print('search...')
        if (not token):
            if (name):
                psn = gmaps.places_nearby(location=location, rank_by='distance', keyword=name)
            else:
                psn = gmaps.places_nearby(location=location, rank_by='distance', type='grocery_or_supermarket')
        else:
            #print('token = ' + token) 
            psn = gmaps.places_nearby(location=location, page_token=token)
        #print('psn:')
        #print(dump(psn, default_flow_style=False, Dumper=Dumper))
        with open('psn.yml', 'w') as yaml_file:
            dump(psn, yaml_file, default_flow_style=False, Dumper=Dumper)
        print('saving token')
        for p in psn['results']:
            if (not utils.isInside(p['geometry']['location'], bounds)):
                #print('this one is not inside:')
                #print(dump(p, default_flow_style=False, Dumper=Dumper))
                more = False
                break
            if (not data.get(p['place_id'])):
                gRec = {'name': p['name'], 'vicinity': p['vicinity'], 'location': p['geometry']['location'], 'distance': utils.distance(p['geometry']['location'], location)}
                data[p['place_id']] = gRec
                glist.append(gRec)
        token = psn.get('next_page_token')
        if (not token):
            # finished
            more = False
            break
        time.sleep(2)

def evaluate(loc, data, threshold):
    metric = threshold['metric']
    better = threshold['better']
    mn = threshold['min']
    mx = threshold['max']
    if (metric != 'distance_to_nearest'):
        raise Exception('ERROR: can only evaluate for metric distance_to_nearest')

    minDist = 100
    minK = ''
    for k, v in iter(data.items()):
        dist = utils.distance(loc, (v['location']['lat'], v['location']['lng']))
        if (dist < minDist):
            minDist = dist
            minK = k
    return utils.ramp(minDist, mn, mx, (better != 'lower'))

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
    parser.add_argument('-location', type=str, help='location to evaluate')
    # TODO: what are the units of -resolution?
    parser.add_argument('-resolution', type=str, help='evaluate the entire bounds of the location at this resolution')
    parser.add_argument('-eval', type=str, help='evaluate the overall score')
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
        print('geocode location ' + args.geocode)
        geocode = gmaps.geocode(args.geocode);
        data = {}
        data[args.geocode] = {}
        data[args.geocode]['location'] = geocode[0]['geometry']['location']
        data[args.geocode]['bounds'] = geocode[0]['geometry']['bounds']
        print('data:')
        print(dump(data, default_flow_style=False, Dumper=Dumper))

    elif (args.eval):
        with open(criterionName + '.yml', 'r') as in_file:
            data = load(in_file, Loader=Loader)
        if (args.location):
            latlong = args.location.split(',')
            e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['threshold'][criterionName])
            print(str(e))
        elif (args.resolution):
            pass
        else:
            print('INTERNAL ERROR')
            sys.exit(1)

    sys.exit(0)

# test:
# wrmap.py -geocode 'Durham NC'
# wrmap.py -eval -location 35.936164,-79.040997
# wrmap.py -eval -location 35.96253900000001,-78.958224
# wrmap.py -eval -location 35.916752,-78.963430
