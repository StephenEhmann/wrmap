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
import kml

criterionName = 'grocery'

# TODO: update with Levi's alg
def find(location, bounds, data, allData, name=None):
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

def evaluate(loc, data, value):
    return utils.evaluate_require_nearest(loc, data, value)


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
    parser.add_argument('-kml', type=str, help='along with -find, optional output kmz name: <name>.kmz')
    parser.add_argument('-name', type=str, help='find only for this name')
    parser.add_argument('-location', type=str, help='location to evaluate (will default to the location given in the config.yml file)')
    parser.add_argument('-eval', type=str, help='evaluate the ' + criterionName + ' score for a given coordinate pair (eg. -eval 35.936164,-79.040997)')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (args.find and args.eval or not args.find and not args.eval):
        print('ERROR: exactly one action must be given, choose exactly one of -find or -eval')
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

        if (not config['find'][criterionName].get('include')):
            config['find'][criterionName]['include'] = {}
        if (not config['find'][criterionName].get('exclude')):
            config['find'][criterionName]['exclude'] = {}

        data = {}
        allData = []
        if (args.name == None):
            find(location, bounds, data, allData)
            for i in config['find'][criterionName]['include'].keys():
                find(location, bounds, data, allData, i)
        else:
            find(location, bounds, data, allData, args.name)

        deletions = []
        for k, v in iter(data.items()):
            if (config['find'][criterionName]['exclude'].get(v['name'])):
                print('excluding ' + v['name'])
                deletions.append(k)

        for d in deletions:
            del data[d]

        if (args.debug):
            print(criterionName + ':')
            print(dump(data, default_flow_style=False, Dumper=Dumper))

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

        if (args.kml):
            # package the data so that kml understands it
            kmlData = {criterionName: {'data': data} }
            if (os.path.dirname(args.kml)):
                os.makedirs(os.path.dirname(args.kml), exist_ok=True)
            kml.write(args.kml, config, kmlData, None)
            #kml.write(os.path.join(args.kml, 'doc.kml'), config, data, results)

    elif (args.eval):
        data = init()
        latlong = args.eval.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['value'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
# grocery.py -eval 35.936164,-79.040997
#0.0038027166005736783
# grocery.py -eval 35.96253900000001,-78.958224
#0.9517840481226215
# grocery.py -eval 35.916752,-78.963430
#0.4059346506450308
