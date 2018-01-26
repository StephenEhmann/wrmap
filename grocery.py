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

import utils

sys.path.insert(0, '/home/scratch.sehmann_cad/python')
import googlemaps

gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

criterionName = 'grocery'

# TODO: geocode query
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
    if (better == 'lower'):
        score = 1.0 if minDist <= mn else 0.0 if minDist >= mx else (minDist - mx) / (mn - mx)
    else:
        score = 0.0 if minDist <= mn else 1.0 if minDist >= mx else (minDist - mn) / (mx - mn)
    return score

if (__name__ == "__main__"):
    # main parser
    class MainParser(argparse.ArgumentParser):
        def print_help(self):
            return

        def error(self, message):
            self.print_help()
            sys.stderr.write('error: %s\n' % message)
            sys.exit(2)
    parser = MainParser(add_help=False, allow_abbrev=False)
    parser.add_argument('-name', type=str, help=argparse.SUPPRESS)
    parser.add_argument('-db', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-evaluate', type=str, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if (args.db and args.evaluate or not args.db and not args.evaluate):
        print('ERROR: exactly one action must be given, choose exactly one of -db or -evaluate')
        sys.exit(1)

    # read config
    try:
        stream = open('config.yml', 'r')
        config = load(stream, Loader=Loader)
        stream.close()
    except Exception as e:
        print(str(e))
        raise Exception('ERROR: Failed to load yaml file ' + 'config.yml')

    if (args.db):
        # Type - supermarket
        # https://developers.google.com/places/supported_types
        # example: https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=-33.8670522,151.1957362&radius=500&type=restaurant&keyword=cruise&key=YOUR_API_KEY
        data = {}
        glist = []
        find(config['location'], config['bounds'], data, glist, args.name)
        for i in config[criterionName]['include'].keys():
            find(config['location'], config['bounds'], data, glist, i)

        #with open('grocery.before.yml', 'w') as yaml_file:
        #    dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        deletions = []
        for k, v in iter(data.items()):
            if (config[criterionName]['exclude'].get(v['name'])):
                print('deleting ' + k)
                deletions.append(k)

        for d in deletions:
            del data[d]

        print(criterionName + ':')
        print(dump(data, default_flow_style=False, Dumper=Dumper))

        print('glist:')
        print(dump(glist, default_flow_style=False, Dumper=Dumper))

        if (args.name == None):
            modName = ''
        else:
            modName = re.sub(r'\s', r'_', args.name) + '.'

        with open(criterionName + '.' + modName + 'yml', 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        with open('glist.' + modName + 'yml', 'w') as yaml_file:
            dump(glist, yaml_file, default_flow_style=False, Dumper=Dumper)

    elif (args.evaluate):
        with open(criterionName + '.yml', 'r') as in_file:
            data = load(in_file, Loader=Loader)
        latlong = args.evaluate.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['threshold'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
# grocery.py -evaluate 35.936164,-79.040997
# grocery.py -evaluate 35.96253900000001,-78.958224
# grocery.py -evaluate 35.916752,-78.963430
