#!/home/utils/Python-3.6.1/bin/python3

import os
import sys
import subprocess
import tempfile
import time
import traceback
import argparse
import glob
import copy
import heapq
import re
import time
from datetime import datetime
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import googlemaps
gmaps = googlemaps.Client(key='AIzaSyAM8dMF61VMVlcCpDDRcOhhMoudiAixO00')
#gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

import utils

class Client:
    key = None
    db = None
    token = 0
    data = []
    dataIndex = 0
    dataPerPage = 20
    numPages = 3

    def __init__(self, key):
        self.key = key
        with open('fgm.' + key + '.yml', 'r') as in_file:
            self.db = load(in_file, Loader=Loader)
        #print('read DB : ' + str(self.db))

    def findData(self, location, num):
        dataCopy = copy.deepcopy(self.db)
        for k, v in iter(dataCopy.items()):
            v['distance'] = utils.distance( (v['location']['lat'], v['location']['lng']),
                                            (location['lat'], location['lng']) )
            name = v['name'].encode("ascii","ignore").decode("ascii")
            #print(name)
            #print(v['name'])
            #print('type=' + str(type(v['name'])))
            #print('dist for ' + name + ' is ' + str(v['distance']))
            print('dist is ' + str(v['distance']) + ' for ' + name)
        result = []
        for k in heapq.nsmallest(num, dataCopy, key=lambda x: (dataCopy[x]['distance'],x)):
            print('k = ' + k)
            v = dataCopy[k]
            result.append(
                {
                    'geometry': {'location': v['location']},
                    'name': v['name'],
                    'vicinity': v['vicinity'],
                    'place_id': k,
                }
            )
        return result

    def places_nearby(self, location=None, rank_by=None, type=None, keyword=None, page_token=None):
        if (page_token == None):
            if (location == None or rank_by == None or type == None):
                raise Exception('ERROR: fgm.Client.places_nearby: one of the args is not given')
        if (keyword != None):
            raise Exception('ERROR: fgm.Client.places_nearby: keyword functionality is not implemented')

        result = {}
        result['results'] = []
        if (page_token == None):
            self.token = 1
            result['next_page_token'] = self.token
            self.data = self.findData(location, self.dataPerPage * self.numPages)
            #print('self.data = ' + str(self.data))
        else:
            if (page_token != self.token):
                raise Exception('ERROR: invalid use of token, does not match') 
            if (self.token == 0):
                raise Exception('ERROR: invalid use of token, token is 0') 
            if (self.token < self.numPages-1):
                # more pages after this one
                self.token += 1
                result['next_page_token'] = self.token
            elif (self.token == self.numPages-1):
                # last page
                self.token = 0

        for i in range(self.dataPerPage):
            #print('append ' + str(self.data[self.dataIndex + i]))
            result['results'].append(self.data[self.dataIndex + i])

        if (self.token == 0):
            self.dataIndex = 0
        else:
            self.dataIndex += self.dataPerPage

        return result

    def place(self, place_id):
        raise Exception('ERROR: fgm.Client.place is not implemented')

def findOne(location, bounds, type, data, allData):
    print('findone: ')
    print('loc = ' + str(location['lng']) + ' ' + str(location['lat']))
    print('bounds = ' + str(bounds['southwest']['lng']) + ',' + str(bounds['southwest']['lat']) + '  ' + str(bounds['northeast']['lng']) + ',' + str(bounds['northeast']['lat']))

    more = True
    token = None
    while (more):
        #print('search...')
        if (not token):
            psn = gmaps.places_nearby(location=location, rank_by='distance', type=type)
        else:
            #print('token = ' + token) 
            psn = gmaps.places_nearby(location=location, page_token=token)
        #print('psn:')
        #print(dump(psn, default_flow_style=False, Dumper=Dumper))
        #print('saving token')
        for p in psn['results']:
            if (data.get(p['place_id'])):
                # Already found this one
                continue

            dist = utils.distance( (p['geometry']['location']['lat'], p['geometry']['location']['lng']),
                                   (location['lat'], location['lng']))
            gRec = {'name': p['name'], 'vicinity': p['vicinity'], 'location': p['geometry']['location'], 'distance': dist}
            data[p['place_id']] = gRec

            p['distance'] = dist
            allData.append(p)

        time.sleep(2) # next_page_token not immediately ready server-side
        token = psn.get('next_page_token')
        if (not token):
            # finished
            more = False
            break


def find(location, bounds, key, data, allData):
    types = {
        'bus': 'bus_station',
    }
    if (key not in types):
        raise Exception('ERROR: find for ' + key + ' is not implemented, just add the entry into the types dict')

    numDivisions = 10
    ystep = (bounds['northeast']['lat'] - bounds['southwest']['lat']) / float(numDivisions)
    y = bounds['southwest']['lat']
    xstep = (bounds['northeast']['lng'] - bounds['southwest']['lng']) / float(numDivisions)
    x = bounds['southwest']['lng']
    for yi in range(numDivisions):
        x = bounds['southwest']['lng']
        for xi in range(numDivisions):
            oneLocation = {'lat': y + 0.5 * ystep, 'lng': x + 0.5 * xstep}
            oneBounds = {'southwest': {'lat': y, 'lng': x}, 'northeast': {'lat': y + ystep, 'lng': x + xstep}}
            findOne(oneLocation, oneBounds, types[key], data, allData)
            x += xstep
        y += ystep

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
    parser.add_argument('-find', type=str, help='find all DB items and write them to fgm.find.<>.yml')
    parser.add_argument('-location', type=str, help='find all DB items that are found from this location')
    args = parser.parse_args()

    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (not args.find and not args.location):
        raise Exception('ERROR: -find or -location required')

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
    location = utils.centroid(bounds)

    if (args.find):
        raise Exception('------------------- PROTECTION AGAINST RUNNING THIS --------------------')

        data = {}
        allData = []
        find(location, bounds, args.find, data, allData)

        with open('fgm.find.' + args.find + '.yml', 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        with open('fgm.find.' + args.find + '.all.yml', 'w') as yaml_file:
            dump(allData, yaml_file, default_flow_style=False, Dumper=Dumper)

    elif (args.location):
        latlong = args.location.split(',')
        location = {'lat': latlong[0], 'lng': latlong[1]}
        testClient = Client(key='bus')

        data = {}
        allData = []
        more = True
        token = None
        while (more):
            #print('search...')
            if (not token):
                psn = testClient.places_nearby(location=location, rank_by='distance', type='bus')
            else:
                #print('token = ' + token)
                psn = testClient.places_nearby(location=location, page_token=token)
            #print('psn:')
            #print(dump(psn, default_flow_style=False, Dumper=Dumper))
            #print('saving token')
            for p in psn['results']:
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


        with open('fgm.test.yml', 'w') as yaml_file:
            dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)

        with open('fgm.test.all.yml', 'w') as yaml_file:
            dump(allData, yaml_file, default_flow_style=False, Dumper=Dumper)

        if (0):
            psn = testClient.places_nearby(location=location, rank_by='distance', type='bus_station')
            with open('fgm.psn.yml', 'w') as yaml_file:
                dump(psn, yaml_file, default_flow_style=False, Dumper=Dumper)

    sys.exit(0)

# test:
#fgm.py -location 35.9875919,-78.9050688
