import sys
import heapq
import math
from urllib.request import urlopen, Request
import certifi
import geopy.distance

def isInside(loc, bounds):
    return loc['lng'] > bounds['southwest']['lng'] and loc['lng'] < bounds['northeast']['lng'] and \
           loc['lat'] > bounds['southwest']['lat'] and loc['lat'] < bounds['northeast']['lat']

def distance(loc, ref):
    return geopy.distance.vincenty(loc, ref).miles

def centroid(bounds):
    ## dict in from location.yml, dict out like location in location.yml
    cnt_lat = (bounds['northeast']['lat'] + bounds['southwest']['lat'])/2
    cnt_lng = (bounds['northeast']['lng'] + bounds['southwest']['lng'])/2
    return {'lat':cnt_lat,'lng':cnt_lng}

def ramp(x, mn, mx, pos):
    if (pos):
        return 0.0 if x <= mn else 1.0 if x >= mx else (x - mn) / (mx - mn)
    else:
        return 1.0 if x <= mn else 0.0 if x >= mx else (x - mx) / (mn - mx)

def findNearest(loc, data, n):
    h = []
    for k, v in iter(data.items()):
        heapq.heappush(h, distance(loc, (v['location']['lat'], v['location']['lng'])))
    return [heapq.heappop(h) for i in range(n)]

def evaluate_single_func(funcType, func, x):
    if (funcType == None or func == None):
        raise Exception('ERROR: function data is not given for range for x = ' + str(x))

    if (funcType == 'const'):
        return func
    elif (funcType == 'linear'):
        #print('linear func = ' + str(func))
        x1 = func[0][0]
        y1 = func[0][1]
        x2 = func[1][0]
        y2 = func[1][1]
        return (x-x1) * (y2-y1) / (x2-x1) + y1
    elif (funcType == 'exp'):
        return func[0] * math.exp(func[1] * x)
    else:
        raise Exception('ERROR: unrecognized function type \'' + k + '\'')

def evaluate_function(function, x):
    #print('evaluate_function ' + str(x))
    #print('evaluate_function ' + str(function))
    if (not isinstance(function, list)):
        raise Exception('ERROR: function must be a list')

    # gather the points
    points = [None]
    funcType = None
    func = None
    for f in function:
        if (isinstance(f, dict)):
            if (len(f.keys()) != 1):
                raise Exception('ERROR: function item must be a map with exactly one key')
            for k in f.keys():
                break
            #print('k = ' + k)
            if (k == 'point'):
                points.append(f[k])
                if (funcType == 'linear'):
                    func.append(f[k])
                if (x < f[k][0]):
                    return evaluate_single_func(funcType, func, x)
            elif (k == 'const' or k == 'exp'):
                funcType = k
                func = f[k]
            else:
                raise Exception('ERROR: unrecognized function name \'' + k + '\'')
            
        elif (isinstance(f, list)):
            raise Exception('ERROR: function item cannot be a list: ' + str(f))
        else:
            funcType = f
            func = [points[-1]] # put the last point in there

    return evaluate_single_func(funcType, func, x)

def evaluate_final(function, x):
    if (function == 'average'):
        sum = 0.0
        for i in x: sum += i
        return sum / len(x)
    else:
        raise Exception('ERROR: final function ' + function + ' unimplemented')

def evaluate_require_nearest(loc, data, value):
    #print(str(value))
    selectionType = value['selection']['type']
    if (selectionType != 'nearest'):
        raise Exception('ERROR: can only evaluate for selection type \'nearest\'')

    nearest = findNearest(loc, data, value['selection']['nearest'])
    #print('nearest dists = ' + str(nearest))
    scores = []
    for n in nearest:
        scores.append(evaluate_function(value['function'], n))
    #print('scores = ' + str(scores))

    return evaluate_final(value['selection']['final'], scores)


# Web
def get_webpage(url):
    """ Given a HTTP/HTTPS url and then returns string
    Returns:
        string of HTML source code
    """

    req = Request(url=url)
    with urlopen(req, cafile=certifi.where()) as f:
        return f.read().decode('utf-8')

    #resp = urllib.request.urlopen('https://foo.com/bar/baz.html', cafile=certifi.where())
    req = Request(url, headers={'Accept-Charset': 'utf-8', 'Accept-Language': 'zh-tw,en-us;q=0.5'})
    with urlopen(req, cafile=certifi.where()) as rsq:
        _, _, charset = rsq.headers['Content-Type'].partition('charset=')
        if not charset:
            charset = 'utf-8'
        return rsq.read().decode('utf-8')
        htmlbytes = rsq.read()
    charset = charset.strip()
    try:
        return str(htmlbytes, charset)
    except (UnicodeDecodeError):
        warning('encoding htmlbytes to {} failed'.format(charset))
        with open('UnicodeDecodeError.html', 'wb') as fout:
            fout.write(htmlbytes)
        raise

