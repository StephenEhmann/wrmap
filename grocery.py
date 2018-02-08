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

criterionName = 'grocery'

def find(location, bounds, data, allData, glist, name=None):
    more = True
    token = None
    while (more):
        #print('search...')
        if (not token):
            if (name):
                psn = gmaps.places_nearby(location=location, rank_by='distance', keyword=name)
            else:
                psn = gmaps.places_nearby(location=location, rank_by='distance', type='supermarket')
        else:
            #print('token = ' + token) 
            psn = gmaps.places_nearby(location=location, page_token=token)
        #print('psn:')
        #print(dump(psn, default_flow_style=False, Dumper=Dumper))
        #print('saving token')
        for p in psn['results']:
            if (not utils.isInside(p['geometry']['location'], bounds)):
                # Not in the bounding box
                #print('this one is not inside:')
                #print(dump(p, default_flow_style=False, Dumper=Dumper))
                more = False
                break
            if (data.get(p['place_id'])):
                # Already found this one
                continue

            dist = utils.distance( (p['geometry']['location']['lat'], p['geometry']['location']['lng']),
                                   (location['lat'], location['lng']))
            gRec = {'name': p['name'], 'vicinity': p['vicinity'], 'location': p['geometry']['location'], 'distance': dist}
            data[p['place_id']] = gRec
            glist.append(gRec)

            p['distance'] = dist
            allData.append(p)

        token = psn.get('next_page_token')
        if (not token):
            # finished
            more = False
            break
        time.sleep(2) # next_page_token not immediately ready server-side

def init():
    with open(criterionName + '.yml', 'r') as in_file:
        data = load(in_file, Loader=Loader)
    return data

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
    parser.add_argument('-debug', action='store_true', help='print extra info')
    parser.add_argument('-find', action='store_true', help='find all DB items and write them to ' + criterionName + '.yml')
    parser.add_argument('-name', type=str, help='find only for this name')
    parser.add_argument('-location', type=str, help='location to evaluate (will default to the location given in the config.yml file)')
    parser.add_argument('-evaluate', type=str, help='evaluate the ' + criterionName + ' score for a given coordinate pair (eg. -evaluate 35.936164,-79.040997)')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (args.find and args.evaluate or not args.find and not args.evaluate):
        print('ERROR: exactly one action must be given, choose exactly one of -find or -evaluate')
        sys.exit(1)

    if (not args.find and args.name):
        print('ERROR: -name can only be used with -find')
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

    if (args.location):
        latlong = args.location.split(',')
        location = {'lat': latlong[0], 'lng': latlong[1]}
    else:
        location = locations[config['location']] ['location']
    bounds = locations[config['location']] ['bounds']

    if (args.find):
        # Type - supermarket
        # https://developers.google.com/places/supported_types
        # example: https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=-33.8670522,151.1957362&radius=500&type=restaurant&keyword=cruise&key=YOUR_API_KEY
        data = {}
        allData = []
        glist = []
        find(location, bounds, data, allData, glist, args.name)
        if (args.name == None):
            for i in config[criterionName]['include'].keys():
                find(location, bounds, data, allData, glist, i)

        deletions = []
        for k, v in iter(data.items()):
            if (config[criterionName]['exclude'].get(v['name'])):
                print('excluding ' + v['name'])
                deletions.append(k)

        for d in deletions:
            del data[d]

        if (args.debug):
            print(criterionName + ':')
            print(dump(data, default_flow_style=False, Dumper=Dumper))

            print('glist:')
            print(dump(glist, default_flow_style=False, Dumper=Dumper))

        if (args.name == None):
            modName = ''
        else:
            modName = re.sub(r'\s', r'_', args.name) + '.'

        if (args.location):
            modName = 'location.' + modName

        with open(criterionName + '.' + modName + 'yml', 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        with open(criterionName + '.' + modName + 'all.yml', 'w') as yaml_file:
            dump(allData, yaml_file, default_flow_style=False, Dumper=Dumper)

        if (args.debug):
            with open('glist.' + modName + 'yml', 'w') as yaml_file:
                dump(glist, yaml_file, default_flow_style=False, Dumper=Dumper)

    elif (args.evaluate):
        data = init()
        latlong = args.evaluate.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['threshold'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
# grocery.py -evaluate 35.936164,-79.040997
# grocery.py -evaluate 35.96253900000001,-78.958224
# grocery.py -evaluate 35.916752,-78.963430
