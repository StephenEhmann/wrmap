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
# TODO: add this to README and notify others
#import html5lib
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import utils

criterionName = 'bus'

if (1):
    import googlemaps
    gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU') # Stephen's key
    #gmaps = googlemaps.Client(key='AIzaSyAM8dMF61VMVlcCpDDRcOhhMoudiAixO00') # Eric's key
    #gmaps = googlemaps.Client(key='AIzaSyDpKsGiSCE6MH_KlGTSW8eza6u6dVa8kIE') # Levi's key
else:
    import fgm
    gmaps = fgm.Client(key=criterionName)

#server_queries = 0

def findDetails(location, bounds, data, allData, name=None):
    if (0):
        # https://github.com/MikimotoH/gisTools/blob/master/google_place.py
        details = gmaps.place(p['place_id'])
        url = details['result']['url']
        print('url = ' + url)
        buspage = utils.get_webpage(url)
        print('webpage = ' + buspage)
        # Scrape this from the cached results section:
        """
        [["Buses",[[3,"bus2.png",null,"Bus",[["https://maps.gstatic.com/mapfiles/transit/iw2/b/bus2.png",0,[15,15],null,0]]]],[[null,null,null,null,"0x89ace4dfacb0eac1:0x2afeb462d543b31c",[[5,["2",1,"#0033cc","#ffffff"]]]],[null,null,null,null,"0x89ace40fe82c61e9:0x4b96e38b28ffccd4",[[5,["BCC",1,"#0033cc","#ffffff"]]]]],null,1,"5",2]]
        """
        #tree = html.fromstring(buspage)
        #tree = html5lib.parse(buspage)
        #bus_elm = tree.find("./html/body/div[1]/div/div[4]/div[4]/div/div/div[2]/div/div[2]/div[1]/div[2]/div/div/div[2]/div/table/tr/td")
        #bus_elm = tree.xpath("/html/body/div[1]/div/div[4]/div[4]/div/div/div[2]/div/div[2]/div[1]/div[2]/div/div/div[2]/div/table/tr/td")
        if (not bus_elm):
            print('ERROR: xpath get bus failed for ' + p['place_id'])
        else:
            print('bus_elm: ' + str(bus_elm))
            bus_elm = bus_elm[0]
            buses = list(filter(lambda s: len(s.strip()) > 0,
                                bus_elm.text_content().strip().split()))
            details['buses'] = buses
            #yield (station, float(loc['lat']), float(loc['lng']), buses)

def init():
    with open(criterionName + '.yml', 'r') as in_file:
        data = load(in_file, Loader=Loader)
    return data

def evaluate(loc, data, value):
    #print(str(value))
    selection = value['selection']
    if (selection != 'nearest'):
        raise Exception('ERROR: can only evaluate for selection \'nearest\'')

    minDist = 100
    minK = ''
    for k, v in iter(data.items()):
        dist = utils.distance(loc, (v['location']['lat'], v['location']['lng']))
        if (dist < minDist):
            minDist = dist
            minK = k
    # distance to nearest grocery store is x
    return utils.evaluate_function(value['function'], minDist)


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

        with open(criterionName + '.' + modName + 'yml', 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        with open(criterionName + '.' + modName + 'all.yml', 'w') as yaml_file:
            dump(allData, yaml_file, default_flow_style=False, Dumper=Dumper)

    elif (args.eval):
        data = init()
        latlong = args.eval.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['value'][criterionName])
        print(str(e))

    #print('server queries:',server_queries)

    sys.exit(0)

# test:
