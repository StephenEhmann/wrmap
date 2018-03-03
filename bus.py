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

criterionName = 'bus'

if (1):
    import googlemaps
    #gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU') # Stephen's key
    #gmaps = googlemaps.Client(key='AIzaSyAM8dMF61VMVlcCpDDRcOhhMoudiAixO00') # Eric's key
    gmaps = googlemaps.Client(key='AIzaSyDpKsGiSCE6MH_KlGTSW8eza6u6dVa8kIE') # Levi's key
else:
    import fgm
    gmaps = fgm.Client(key=criterionName)

#server_queries = 0

# TODO: how to make bus webpage scraping robust?
def findDetails(origAllData, keywords):
    debug = True
    startAt = 0
    limit = 0

    if (0):
        # the first 600
        startAt = 0
        limit = 600
    if (0):
        # the rest
        startAt = 600
        limit = 0
    count = 0
    allData = []
    for d in origAllData:
        if (count >= startAt):
            if ('url' not in d):
                if (debug):
                    print('query: ' + d['place_id'])
                details = gmaps.place(d['place_id'])
                d['url'] = details['result']['url']
            if (d.get('found_keyword') == None):
                print('url = ' + d['url'])
                failed = False
                try:
                    buspage = utils.get_webpage(d['url'])
                except Exception as e:
                    failed = True
                else:
                    for k in keywords:
                        if (re.search(k, buspage)):
                            d['found_keyword'] = 1
                    if (d.get('found_keyword') == None):
                        d['found_keyword'] = 0

                if (failed):
                    print('failed at ' + str(count))
                    allFilename = criterionName + '.all.' + str(startAt) + '_' + str(count-1) + '.new.yml'
                    with open(allFilename, 'w') as yaml_file:
                        dump(allData, yaml_file, default_flow_style=False, Dumper=Dumper)
                    break

            allData.append(d)

        count += 1
        if (limit > 0 and count >= limit):
            break

    return allData

def filterData(data, allData):
    for d in allData:
        if ('found_keyword' not in d):
            print('ERROR: cannot finish filtering because there is missing found_keyword data in the ' + d['name'] + ' record')
            break
        if (d['found_keyword']):
            gRec = {'name': d['name'], 'vicinity': d['vicinity'], 'location': d['geometry']['location']}
            data[d['place_id']] = gRec

def init():
    with open(criterionName + '.yml', 'r') as in_file:
        data = load(in_file, Loader=Loader)
    return data

def evaluate(loc, data, value, extraData=None):
    return utils.evaluate_require_nearest(loc, data, value, extraData=extraData)


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
    parser.add_argument('-extraData', action='store_true', help='print extra data for evals')
    parser.add_argument('-find', action='store_true', help='find all DB items and write them to ' + criterionName + '.yml')
    parser.add_argument('-name', type=str, help='find only for this name')
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
        if (args.cached):
            try:
                stream = open(criterionName + '.all.yml', 'r')
                origAllData = load(stream, Loader=Loader)
                stream.close()
            except Exception as e:
                print(str(e))
                raise Exception('ERROR: Failed to load yaml file ' + placeType + '.all.yml')

            allData = findDetails(origAllData, config['find'][criterionName]['include'].keys())
            filterData(data, allData)

        else:
            if (args.name):
                utils.find(location, bounds, data, allData, name=args.name)
            else:
                utils.find(location, bounds, data, allData, placeType='bus_station')
                if (args.name == None and config['find'][criterionName].get('include')):
                    for i in config['find'][criterionName]['include'].keys():
                        utils.find(location, bounds, data, allData, name=i)

        deletions = []
        for k, v in iter(data.items()):
            if (config['find'][criterionName]['exclude'].get(v['name'])):
                print('excluding ' + v['name'])
                deletions.append(k)

        if (args.debug):
            print(criterionName + ':')
            print(dump(data, default_flow_style=False, Dumper=Dumper))

        for d in deletions:
            del data[d]

        if (args.name == None):
            modName = ''
        else:
            modName = re.sub(r'\s', r'_', args.name) + '.'

        if (args.location):
            modName = 'location.' + modName

        filename = criterionName + '.' + modName + 'yml'
        allFilename = criterionName + '.' + modName + 'all.yml'
        if (args.cached):
            filename = criterionName + '.' + modName + 'new.yml'
            allFilename = criterionName + '.' + modName + 'all.new.yml'

        with open(filename, 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        with open(allFilename, 'w') as yaml_file:
            dump(allData, yaml_file, default_flow_style=False, Dumper=Dumper)

    elif (args.eval):
        data = init()
        latlong = args.eval.split(',')
        extraData = None
        if (args.extraData):
            extraData = {}
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['value'][criterionName], extraData=extraData)
        print(str(e))
        if (args.extraData):
            print('extraData = ' + str(extraData))

    #print('server queries:',server_queries)

    sys.exit(0)

# test:
