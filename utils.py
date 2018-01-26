import sys
#from math import sin, cos, sqrt, atan2, radians

sys.path.insert(0, '/home/scratch.sehmann_cad/python')
import geopy.distance

def isInside(loc, bounds):
    return loc['lng'] > bounds['southwest']['lng'] and loc['lng'] < bounds['northeast']['lng'] and \
           loc['lat'] > bounds['southwest']['lat'] and loc['lat'] < bounds['northeast']['lat']

def distance(loc, ref):
    #return (loc['lng'] - ref['lng']) ** 2 + (loc['lat'] - ref['lat']) ** 2
    #coords_1 = (loc['lat'], loc['lng'])
    #coords_2 = (ref['lat'], ref['lng'])

    return geopy.distance.vincenty(loc, ref).miles
