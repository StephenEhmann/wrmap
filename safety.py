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
import json
from datetime import datetime
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import googlemaps
gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU')

import utils

criterionName = 'safety'
resolution = 500
safety_default = 9 # for points outside all polygons, default score to most safe

tol = 10**-16 ## tolerance for testing lat/lng differences

###### Polygon Function ######
def find(location, bounds, data, safetyMaps):
    for sm in safetyMaps:
        page = utils.get_webpage(sm)

        # host
        m = re.search(r'var assetHost = "(\S+)"', page)
        if (m):
            host = m.group(1)
        else:
            raise Exception('ERROR: Failed to find "var assetHost" in ' + sm)

        # city id
        m = re.search(r'data-id=\'(\d+)\'', page)
        if (m):
            cityId = m.group(1)
        else:
            raise Exception('ERROR: Failed to find "data-id=" in ' + sm)

        # polygon ids
        polyIdsJson = utils.get_webpage('https:' + host + '/polygons/features/cities/' + str(cityId) + '.json')
        polyIds = json.loads(polyIdsJson)
        #print('polys = ' + str(polys))

        for polyId in polyIds:
            neighborhoodPoly = json.loads(utils.get_webpage('https:' + host + '/polygons/polygon/neighborhoods/' + str(polyId) + '.json'))
            #print('neighborhoodPoly for ' + str(polyId) + ' = ' + str(neighborhoodPoly))
            data[polyId] = neighborhoodPoly

###### Grid Functions ######
def horz_intersect(lng1, lng2, lat, seg):
    ## lng1 < lng2 define longitude end points of horizontal line at latitude lat
    ## seg is nested list of [lng,lat]  of endpoints of a line segment
    ## return 1 if they intersect, 0 otherwise
    ## edge cases: (http://geomalgorithms.com/a03-_inclusion.html) upward edge excludes ne point, downward edge excludes nw point, don't test horizontal, intersection must be strictly to right of lng1
    slng1 = seg[0][0]
    slng2 = seg[1][0]
    slat1 = seg[0][1]
    slat2 = seg[1][1]
    if abs(slat1 - slat2) < tol:
        raise Exception('do not pass horizontal line segment (seg) to horz_intersect')
    if lng1 >= lng2:
        raise Exception('horz_intersect requires lng1 < lng2')
    if (min(slat1,slat2) <= lat) and (lat < max(slat1,slat2)):
        ## seg crosses lat at some longitude
        if (lng1 < min(slng1,slng2)) and (max(slng1,slng2) <= lng2):
            ## seg crosses lat between lng1 and lng2
            return 1
        else:
            ## check longitude intersection point
            lng_intsect = (lat*(slng2 - slng1) + (slat2*slng1 - slat1*slng2) ) / (slat2 - slat1)
            if (lng1 < lng_intsect) and (lng_intsect <= lng2):
                return 1
            else:
                return 0
    else:
        return 0

def horz_intersect_poly(lng1, lng2, lat, polygon):
    ## lng1 < lng2 define longitude end points of horizontal line at latitude lat
    ## polygon is ordered list of vertices [[lng,lat],...]
    ## return number of times horizontal line intersects polygon
    int_cnt = 0
    for i in range(len(polygon)-1):
        seg = [polygon[i], polygon[i+1] ]
        if abs(seg[0][1] - seg[1][1]) < tol:
            ## skip horizontal edges
            pass
        else:
            int_cnt += horz_intersect(lng1, lng2, lat, seg)
    return int_cnt

def add_poly_bound(safe_poly,outer_bound):
    ## add bounding box to each polygon as [[min_lng,max_lng],[min_lat,max_lat]]
    ## also calculate one outermost bounding box around all polygons
    min_lngs = []
    max_lngs = []
    min_lats = []
    max_lats = []
    for nbhd in safe_poly:
        poly = safe_poly[nbhd]['geometry']['coordinates'][0][0]
        poly_lngs = [vert[0] for vert in poly]
        poly_lats = [vert[1] for vert in poly]
        
        min_lng_p = min(poly_lngs)
        max_lng_p = max(poly_lngs)
        min_lat_p = min(poly_lats)
        max_lat_p = max(poly_lats)
        
        min_lngs.append(min_lng_p)
        max_lngs.append(max_lng_p)
        min_lats.append(min_lat_p)
        max_lats.append(max_lat_p)
        
        safe_poly[nbhd]['geometry']['bound'] = [[min_lng_p ,max_lng_p], [min_lat_p ,max_lat_p] ]

    outer_bound.append([min(min_lngs) ,max(max_lngs)] )
    outer_bound.append([min(min_lats) ,max(max_lats)] )
    #print(outer_bound)

def is_even(x):
    if (x%2):
        return False
    else:
        return True
    
def poly_to_grid(safe_poly, bounds, resolution, debug=None):
    #print(bounds)

    result = {}
    grid = []
    lng_steps = resolution
    lat_steps = utils.latStepsFromLngSteps(bounds, lng_steps)
    ystep = (bounds['northeast']['lat'] - bounds['southwest']['lat']) / float(lat_steps)
    xstep = (bounds['northeast']['lng'] - bounds['southwest']['lng']) / float(lng_steps)
    
    result['bounds'] = bounds
    result['numsteps'] = {'lng': lng_steps, 'lat': lat_steps}
    result['lenstep'] = {'x': xstep, 'y': ystep}
    result['startgrid'] = bounds['southwest']

    if (debug):
        debug_out = []
    
    max_lng = max(outer_bound[0][1],bounds['northeast']['lng']) + 10*tol #longitude that is definitely outside all bounding boxes
    for yi in range(lat_steps):
        y = result['startgrid']['lat'] + (float(yi) + 0.5) * ystep
        poly_prev = None
        row_grid = []
        for xi in range(lng_steps):
            x = result['startgrid']['lng'] + (float(xi) + 0.5) * xstep
            poly_curr = None
            if (poly_prev) and is_even(horz_intersect_poly(x - xstep, x, y, safe_poly[poly_prev]['geometry']['coordinates'][0][0]) ):
                ## test intersections with polygon for line from previous point, if intersections are even, then it's in the same polygon
                poly_curr = poly_prev
                row_grid.append(safe_poly[poly_curr]['properties']['c'] )
                poly_prev = poly_curr
                if (debug):
                    debug_out.append({'x_y': [x,y], 'poly': poly_curr, 'score': row_grid[xi], 'how_found': 'prev'})
            else:
                for nbhd in safe_poly:
                    min_x = safe_poly[nbhd]['geometry']['bound'][0][0]
                    max_x = safe_poly[nbhd]['geometry']['bound'][0][1]
                    min_y = safe_poly[nbhd]['geometry']['bound'][1][0]
                    max_y = safe_poly[nbhd]['geometry']['bound'][1][1]
                    if (min_x <= x and x < max_x) and (min_y <= y and y < max_y):
                        ## if in bounding box, then check against polygon
                        if not is_even(horz_intersect_poly(x, max_lng, y, safe_poly[nbhd]['geometry']['coordinates'][0][0]) ):
                            ## test intersections with polygon for line to point definitely outside polygon, if intersections are odd, then it's in this polygon
                            poly_curr = nbhd
                            row_grid.append(safe_poly[poly_curr]['properties']['c'])
                            poly_prev = poly_curr
                            if (debug):
                                debug_out.append({'x_y': [x,y], 'poly': poly_curr, 'score': row_grid[xi], 'how_found': 'search'})
                            break #can only be in one polygon, so if we found one, stop looking
            if (not poly_curr):
                ## this point outside all polygons, use default
                row_grid.append(safety_default)
                poly_prev = poly_curr
                if (debug):
                    debug_out.append({'x_y': [x,y], 'poly': 'none', 'score': row_grid[xi], 'how_found': 'none'})
        grid.append(row_grid)
    result['grid'] = grid
    if (debug):
        with open(criterionName + '_debug.yml', 'w') as yaml_file:
            dump(debug_out, yaml_file, default_flow_style=False, Dumper=Dumper)    
    return result

## some tests of functions
#print(outer_bound)
#print('2 is even',is_even(2))
#print('3 is even',is_even(3))
#print('4.0 is even',is_even(4.0))
#print('4.00001 is even',is_even(4.00001))
#test_poly = safe_poly[48420]['geometry']['coordinates'][0][0] #need to remove extra list levels
#print(horz_intersect(0,5,0,[[0,0],[5,2]]) )
#print(horz_intersect_poly(-78.89, -78.8, 36.02, test_poly))
#print(safe_poly['outer_bound'])
#print(safe_poly[48420])

def init():
    with open(criterionName + '.yml', 'r') as in_file:
        data = load(in_file, Loader=Loader)
    return data

def evaluate(loc, data, value):
    if (not utils.isInside({'lat': loc[0], 'lng': loc[1]}, data['bounds']) ):
        print('ERROR: evaluation point outside of safety grid bounds')
        sys.exit(1)    
    y_dist_start = float(loc[0]) - data['startgrid']['lat']
    x_dist_start = float(loc[1]) - data['startgrid']['lng']
    row = int(y_dist_start//data['lenstep']['y'])
    col = int(x_dist_start//data['lenstep']['x'])
    score = data['grid'][row][col]
    return utils.evaluate_function(value['function'], score)


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
    parser.add_argument('-find', type=str, help='polys: find safety polygons and write them to ' + criterionName + '_polys.yml \n' + 'grid: map polygons to grid and write it to ' + criterionName + '.yml')
    parser.add_argument('-eval', type=str, help='evaluate the ' + criterionName + ' score for a given coordinate pair (eg. -eval 35.936164,-79.040997)')
    args = parser.parse_args()
    
    if (args.h or args.help):
        parser.print_help()
        sys.exit(0)

    if (args.find and args.eval or not args.find and not args.eval):
        print('ERROR: exactly one action must be given, choose exactly one of -find or -eval')
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
    
    if (args.find):
        if (args.find == 'polys'):
            location = utils.centroid(bounds)
            data = {}
            find(location, bounds, data, config['find'][criterionName])

            with open(criterionName + '_polys.yml', 'w') as yaml_file:
                dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)
                
        elif (args.find == 'grid'):
            #read safety polygons
            try:
                stream = open(criterionName + '_polys.yml', 'r')
                safe_poly = load(stream, Loader=Loader)
                stream.close()
            except Exception as e:
                print(str(e))
                raise Exception('ERROR: Failed to load yaml file ' + criterionName + '.yml')

            outer_bound = []
            add_poly_bound(safe_poly,outer_bound)

            if (args.debug):
                poly_to_grid(safe_poly, bounds, resolution, debug = True)
            else:
                data = poly_to_grid(safe_poly, bounds, resolution)
                with open(criterionName + '.yml', 'w') as yaml_file:
                    dump(data, yaml_file, default_flow_style=False, Dumper=Dumper)
        else:
            raise Exception('ERROR: -find needs argument either polys or grid')

    elif (args.eval):
        data = init()
        latlong = args.eval.split(',')
        e = evaluate((float(latlong[0]), float(latlong[1])), data, config['evaluation']['value'][criterionName])
        print(str(e))

    sys.exit(0)

# test:
