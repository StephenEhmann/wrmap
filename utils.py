import sys
import geopy.distance

def isInside(loc, bounds):
    return loc['lng'] > bounds['southwest']['lng'] and loc['lng'] < bounds['northeast']['lng'] and \
           loc['lat'] > bounds['southwest']['lat'] and loc['lat'] < bounds['northeast']['lat']

def distance(loc, ref):
    return geopy.distance.vincenty(loc, ref).miles

def ramp(x, mn, mx, pos):
    if (pos):
        return 0.0 if x <= mn else 1.0 if x >= mx else (x - mn) / (mx - mn)
    else:
        return 1.0 if x <= mn else 0.0 if x >= mx else (x - mx) / (mn - mx)
