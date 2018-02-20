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

criterionName = 'employment'

def findType(location, bounds, data, allData, placeType, writeYmls=False, useCached=False):
    print('findType ' + str(placeType) + ' cached=' + str(useCached))
    typeData = {}
    allTypeData = []
    if (useCached):
        try:
            stream = open(criterionName + '.' + placeType + '.all.yml', 'r')
            cachedData = load(stream, Loader=Loader)
            stream.close()
        except Exception as e:
            print(str(e))
            raise Exception('ERROR: Failed to load yaml file ' + placeType + '.all.yml')

        allTypeData = cachedData
        for p in cachedData:
            gRec = {'name': p['name'], 'vicinity': p['vicinity'], 'location': p['geometry']['location']}
            typeData[p['place_id']] = gRec
    else:
        utils.find(location, bounds, typeData, allTypeData, placeType=placeType, doSplit=True)
    data.update(typeData)
    allData += allTypeData

    if (writeYmls):
        with open(criterionName + '.' + placeType + '.yml', 'w') as yaml_file:
            dump(typeData, yaml_file, default_flow_style=False, Dumper=Dumper)

        if (not useCached):
            with open(criterionName + '.' + placeType + '.all.yml', 'w') as yaml_file:
                dump(allTypeData, yaml_file, default_flow_style=False, Dumper=Dumper)

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
    parser.add_argument('-name', type=str, help='find only for this name')
    parser.add_argument('-type', type=str, help='find only for this type')
    parser.add_argument('-cached', action='store_true', help='use cached search results in <type>.all.yml')
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

    bounds = locations[config['location']] ['bounds']
    if (args.location):
        latlong = args.location.split(',')
        location = {'lat': latlong[0], 'lng': latlong[1]}
    else:
        location = utils.centroid(bounds)

    if (args.find):
        if (not config['find'][criterionName].get('include')):
            config['find'][criterionName]['include'] = {}
        if (not config['find'][criterionName].get('exclude')):
            config['find'][criterionName]['exclude'] = {}

        data = {}
        allData = []
        if (args.name):
            utils.find(location, bounds, data, allData, name=args.name)
        else:
            # What about these place types: bakery, bar, cafe, supermarket?
            if (args.type):
                findType(location, bounds, data, allData, args.type, writeYmls=True, useCached=args.cached)
            else:
                findType(location, bounds, data, allData, 'lodging', writeYmls=True, useCached=args.cached)
                findType(location, bounds, data, allData, 'restaurant', writeYmls=True, useCached=args.cached)
                findType(location, bounds, data, allData, 'bakery', writeYmls=True, useCached=args.cached)
                findType(location, bounds, data, allData, 'cafe', writeYmls=True, useCached=args.cached)
                #findType(location, bounds, data, allData, 'bar', writeYmls=True, useCached=args.cached)
                findType(location, bounds, data, allData, 'supermarket', writeYmls=True, useCached=args.cached)

                for i in config['find'][criterionName]['include'].keys():
                    utils.find(location, bounds, data, allData, name=i)

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

    elif (args.eval):
        data = init()
        latlong = args.eval.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['value'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
