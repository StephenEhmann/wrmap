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

import googlemaps
gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

import utils
import kml

criterionName = 'bus'

def find(location, bounds, data, allData, name=None):
    more = True
    token = None
    while (more):
        #print('search...')
        if (not token):
            if (name):
                psn = gmaps.places_nearby(location=location, rank_by='distance', keyword=name)
            else:
                psn = gmaps.places_nearby(location=location, rank_by='distance', type='bus_station')
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

                p['details'] = details

            allData.append(p)
            #break

        #break
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
    parser.add_argument('-out', type=str, help='along with -find, optional output kmz name: <name>.kmz')

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

    bounds = locations[config['location']] ['bounds']
    if (args.location):
        latlong = args.location.split(',')
        location = {'lat': latlong[0], 'lng': latlong[1]}
    else:
        # location = locations[config['location']] ['location']
        location = utils.centroid(bounds)
    
    if (args.find):
        if (not config[criterionName].get('include')):
            config[criterionName]['include'] = {}
        if (not config[criterionName].get('exclude')):
            config[criterionName]['exclude'] = {}

        data = {}
        allData = []
        find(location, bounds, data, allData, args.name)
        if (args.name == None and config[criterionName].get('include')):
            for i in config[criterionName]['include'].keys():
                find(location, bounds, data, allData, i)

        deletions = []
        for k, v in iter(data.items()):
            if (config[criterionName]['exclude'].get(v['name'])):
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

        if (args.out):
            # package the data so that kml understands it
            kmlData = {'bus': {'data': data} }
            if (os.path.dirname(args.out)):
                os.makedirs(os.path.dirname(args.out), exist_ok=True)
            kml.write(args.out, config, kmlData, None)
            #kml.write(os.path.join(args.out, 'doc.kml'), config, data, results)

    elif (args.evaluate):
        data = init()
        latlong = args.evaluate.split(',')
        e = evaluate((latlong[0], latlong[1]), data, config['evaluation']['value'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
