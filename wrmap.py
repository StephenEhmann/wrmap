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
import png

debug = False

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


def initSingle(data, k, v):
    data[k] = {}
    data[k]['module'] = importlib.import_module(k, package=None)
    data[k]['data'] = data[k]['module'].init()

def init(config):
    data = {}
    for k, v in iter(config['evaluation']['value'].items()):
        initSingle(data, k, v)
    return data

def evaluate_variable(loc, data, config, k):
    if (debug): print('eval var for ' + k)
    module = None
    funcRecord = None
    if (k in config['evaluation']['value']):
        funcRecord = config['evaluation']['value'][k]
        module = k
    elif (k in config['evaluation']['otherFunctions']):
        funcRecord = config['evaluation']['otherFunctions'][k]
        module = funcRecord.get('module')
    else:
        raise Exception('ERROR: unregistered variable ' + k)

    if (module):
        v = data[module]
        return v['module'].evaluate(loc, v['data'], funcRecord)
    else:
        return evaluate_internal(loc, data, config, funcRecord)

def evaluate_weighted_sum(loc, data, config, weights):
    score = 0.0
    for k, w in iter(weights.items()):
        dataScore = evaluate_variable(loc, data, config, k)
        if (debug): print('score for ' + k + ' = ' + str(dataScore))
        score += w * dataScore
    return score

def evaluate_mul(loc, data, config, mul):
    score = 1.0
    for v in mul:
        if (isinstance(v, dict)):
            score *= evaluate_internal(loc, data, config, v)
        elif (isinstance(v, list)):
            raise Exception('ERROR: mul operand cannot be a list')
        else:
            # scalar
            dataScore = evaluate_variable(loc, data, config, v)
            if (debug): print('score for ' + v + ' = ' + str(dataScore))
            score *= dataScore
    return score

def evaluate_internal(loc, data, config, function):
    if (debug): print('evalinternal function = ' + str(function))
    count = 0
    for op, v in iter(function.items()):
        if (op == 'mul'):
            if (not isinstance(v, list)):
                raise Exception('ERROR: mul operator requires a list value')
            return evaluate_mul(loc, data, config, v)
        elif (op == 'weighted_sum'):
            if (not isinstance(v, dict)):
                raise Exception('ERROR: weighted_sum operator requires a map value')
            return evaluate_weighted_sum(loc, data, config, v)
        else:
            raise Exception('ERROR: unimplemented op: ' + op)
        count += 1

    if (count > 1):
        raise Exception('ERROR: only one top level op allowed for now')

def evaluate(loc, data, config, funcRecord):
    if (debug): print('top eval funcrecord = ' + str(funcRecord))
    function = funcRecord['function']
    if (isinstance(function, list)):
        raise Exception('ERROR: piecewise functions not implemented for non-module variables')

    return evaluate_internal(loc, data, config, function)


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
    parser.add_argument('-out', type=str, help='optional output name: <name>.<ext>')
    parser.add_argument('-kmz', action='store_true', help='output kmz (by default output png)')
    parser.add_argument('-func', type=str, default='final', help='function to evaluate, default is to evaluate the final function')
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
        data[args.geocode]['centroid'] = utils.centroid(data[args.geocode]['bounds'])
        print('data:')
        print(dump(data, default_flow_style=False, Dumper=Dumper))

    elif (args.eval):
        # initialize
        funcRecord = config['evaluation']['otherFunctions']['final']
        if (args.func):
            funcRecord = config['evaluation']['value'].get(args.func)
            if (not funcRecord):
                funcRecord = config['evaluation']['otherFunctions'].get(args.func)
            else:
                funcRecord['module'] = args.func
            if (not funcRecord):
                print('ERROR: -func does not refer to a valid function in the config file')
                sys.exit(1)

        #print('funcrecord = ' + str(funcRecord))
        data = {}
        if (funcRecord.get('module')):
            # evaluating the metric value of a criterion
            #print('init single data = ' + str(data))
            initSingle(data, funcRecord.get('module'), funcRecord)
            #print('data = ' + str(data))
        else:
            # evaluating some arbitrary function
            data = init(config)

        # evaluate
        if (args.location):
            latlong = args.location.split(',')
            if (funcRecord.get('module')):
                e = evaluate_variable((latlong[0], latlong[1]), data, config, args.func)
            else:
                e = evaluate((latlong[0], latlong[1]), data, config, funcRecord)
            print(str(e))

        elif (args.resolution):
            results = {}
            valResults = {}
            if (args.resolution < 2 or args.resolution > 500):
                print('ERROR: -resolution must be a value in the range [2..500]')
                sys.exit(1)

            lng_steps = args.resolution
            lat_steps = utils.latStepsFromLngSteps(bounds, lng_steps)
            if (0):
                # color gradient testing
                valResults = {
                    (0, 0): 0.0,
                    (1, 0): 0.1,
                    (2, 0): 0.2,
                    (3, 0): 0.3,
                    (4, 0): 0.4,
                    (5, 0): 0.5,
                    (6, 0): 0.6,
                    (7, 0): 0.7,
                    (8, 0): 0.8,
                    (9, 0): 0.9,
                    (10, 0): 1.0,
                }
                png.write(args.out, config, valResults, 11, 1)
                sys.exit(0)
            i = 0
            for loc in utils.grid(bounds, lat_steps, lng_steps):
                yi = i // lng_steps
                xi = i % lng_steps
                #print('xi = ' + str(xi) + ' yi = ' + str(yi))
                y = loc['loc']['lat']
                x = loc['loc']['lng']
                results[(y, x)] = {}
                if (1):
                    if (funcRecord.get('module')):
                        results[(y, x)]['val'] = evaluate_variable((y, x), data, config, args.func)
                    else:
                        results[(y, x)]['val'] = evaluate((y, x), data, config, funcRecord)
                    valResults[(xi,yi)] = results[(y, x)]['val']
                else:
                    # for testing with something like "wrmap.py -resolution 5 -eval"
                    results[(y, x)]['val'] = 'not eval'
                results[(y, x)]['name'] = str(xi) + ',' + str(yi)
                #print('x,y = ' + str(x) + ' , ' + str(y) + ' = ' + str(results[(y, x)]['val']))
                i += 1

            if (args.out):
                if (args.kmz):
                    os.makedirs(args.out, exist_ok=True)
                    kml.write(os.path.join(args.out, 'doc.kml'), config, data, results)
                else:
                    #print('valResults = ' + str(valResults))
                    if (not re.search(r'\.png', args.out)):
                        args.out += '.png'
                    png.write(args.out, config, valResults, lng_steps, lat_steps)

        else:
            print('INTERNAL ERROR')
            sys.exit(1)

    sys.exit(0)

# test:
# wrmap.py -geocode 'Durham NC'
# wrmap.py -eval -location 35.936164,-79.040997
# = 0
# wrmap.py -eval -location 35.96253900000001,-78.958224
# = 1
# wrmap.py -eval -location 35.916752,-78.963430
# = 0.7141783742869423
