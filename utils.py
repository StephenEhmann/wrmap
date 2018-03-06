import sys
import time
import heapq
import math
import urllib
from urllib.request import urlopen, Request
import certifi
import contextlib
import geopy.distance

if (1):
    import googlemaps
    #gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU') # Stephen's key
    #gmaps = googlemaps.Client(key='AIzaSyAM8dMF61VMVlcCpDDRcOhhMoudiAixO00') # Eric's key
    gmaps = googlemaps.Client(key='AIzaSyDpKsGiSCE6MH_KlGTSW8eza6u6dVa8kIE') # Levi's key
else:
    import fgm
    gmaps = fgm.Client(key=criterionName)

def isInside(loc, bounds):
    return float(loc['lng']) > bounds['southwest']['lng'] and float(loc['lng']) < bounds['northeast']['lng'] and \
           float(loc['lat']) > bounds['southwest']['lat'] and float(loc['lat']) < bounds['northeast']['lat']

def distance(loc, ref):
    return geopy.distance.vincenty(loc, ref).miles

def centroid(bounds):
    ## dict in from location.yml, dict out like location in location.yml
    cnt_lat = (bounds['northeast']['lat'] + bounds['southwest']['lat']) / 2.0
    cnt_lng = (bounds['northeast']['lng'] + bounds['southwest']['lng']) / 2.0
    return {'lat': cnt_lat, 'lng': cnt_lng}

def ramp(x, mn, mx, pos):
    if (pos):
        return 0.0 if x <= mn else 1.0 if x >= mx else (x - mn) / (mx - mn)
    else:
        return 1.0 if x <= mn else 0.0 if x >= mx else (x - mx) / (mn - mx)

# calculate lng steps based on lat steps so that x-step-distance = y-step-distance
def latStepsFromLngSteps(bounds, lng_steps):
    xstart = bounds['southwest']['lng']
    xend = bounds['northeast']['lng']
    ystart = bounds['southwest']['lat']
    yend = bounds['northeast']['lat']

    xdist = distance((ystart, xstart), (ystart, xend))
    ydist = distance((ystart, xstart), (yend, xstart))
    lat_steps = int((ydist / xdist) * lng_steps)

    #print('lng_steps = ' + str(lng_steps))
    #print('lat_steps = ' + str(lat_steps))
    #print('aspect ratio = ' + str(ydist / xdist))
    #print('xdist = ' + str(xdist))
    #print('xincr = ' + str(xdist / lng_steps))
    #print('ydist = ' + str(ydist))
    #print('yincr = ' + str(ydist / lat_steps))

    #xstep = (xend - xstart) / lng_steps
    #ystep = xstep * xdist / ydist

    return lat_steps

# produces points at the centers of "pixels"
def grid(bounds, lat_steps, lng_steps):
    ystep = (bounds['northeast']['lat'] - bounds['southwest']['lat']) / float(lat_steps)
    xstep = (bounds['northeast']['lng'] - bounds['southwest']['lng']) / float(lng_steps)
    for yi in range(lat_steps):
        for xi in range(lng_steps):
            y = bounds['southwest']['lat'] + (float(yi) + 0.5) * ystep
            x = bounds['southwest']['lng'] + (float(xi) + 0.5) * xstep
            oneLocation = {'lat': y, 'lng': x}
            oneBounds = {'southwest': {'lat': y-0.5*ystep, 'lng': x-0.5*xstep}, 'northeast': {'lat': y+0.5*ystep, 'lng': x+0.5*xstep}}
            yield {'loc': oneLocation, 'bounds': oneBounds}

# Find
def find(location, bounds, data, allData, placeType=None, name=None, dataName=None, doSplit=True, lat_steps=None, lng_steps=None):
    debug = True
    print('find ' + str(placeType) + ' ' + str(name))
    if (placeType == None and name == None or placeType != None and name != None):
        raise Exception('ERROR: exactly one of placeType and name must be given')

    #global server_queries
    cont_srch = True
    if (lat_steps and lng_steps):
        raise Exception('This code needs to be updated now that grid is a generator')
        doSplit = False
        g = grid(bounds, lat_steps, lng_steps)
        bounds_list = []
        for i in g:
            print('bounds = ' + str(i['bounds']))
            bounds_list.append(i['bounds'])
        sys.exit(0)
    else:
        bound_list = [bounds] #initialize stack of subdivided bounding boxes
    split_count = 0
    split_limit = 200 #terminate if split too many times
    while (cont_srch):
        box = bound_list.pop() #pop one subdivided bounding box
        center = centroid(box)
        if (debug): print('start outer loop, current center is', center)
        radius = max( distance( (box['northeast']['lat'], box['northeast']['lng']), (center['lat'], center['lng']) ),
                      distance( (box['southwest']['lat'], box['southwest']['lng']), (center['lat'], center['lng']) ) )
        if (not name and radius <= 4.4):
            if (debug): print('box=' + str(box))
            if (debug): print('center=' + str(center))
            if (debug): print('radius=' + str(radius))
            if (name):
                psn = gmaps.places_nearby(location=center, rank_by='distance', keyword=name)
                #server_queries += 1
            else:
                psn = gmaps.places_nearby(location=center, rank_by='distance', type=placeType)
                #server_queries += 1

            if (debug): print('results count = ' + str(len(psn['results'])))
            exceededRadius = False
            newOne = False
            for p in psn['results']:
                dist_center = distance( (p['geometry']['location']['lat'], p['geometry']['location']['lng']),
                                        (center['lat'], center['lng']))
                if (debug): print('dist center = ' + str(dist_center))
                if (dist_center >= radius):
                    if (debug): print('exceeded radius')
                    exceededRadius = True
                    break

                if (not isInside(p['geometry']['location'], bounds)):
                    # Not in the original, outermost bounding box
                    #print('this one is not inside:')
                    #print(dump(p, default_flow_style=False, Dumper=Dumper))
                    continue

                if (data.get(p['place_id'])):
                    # Already found this one
                    continue
                newOne = True
                if (len(psn['results']) < 20):
                    if (debug): print('  new one')
                    pass

                gRec = {'name': p['name'] if dataName == None else dataName, 'vicinity': p['vicinity'], 'location': p['geometry']['location']}

                if (0):
                    details = gmaps.place(p['place_id'])
                    url = details['result']['url']
                    gRec['url'] = details['result']['url']

                data[p['place_id']] = gRec
                p['distance'] = distance( (p['geometry']['location']['lat'], p['geometry']['location']['lng']),
                                          (location['lat'], location['lng'])) #still calculate dist to original location for recording
                allData.append(p)

                if (0):
                    # Debug: only iterate one result
                    cont_srch = False
                    break

        # Observed API behavior:
        # - different lat/long even slightly can yield different numbers of results
        # -- there appears to be some choice google is making about how many results to return for a specific location
        # - splitting (which samples new center locations) can yield results not previously seen
        # - searching by name and searching by type have different behaviors
        # - there can be 0 results
        # - the search seems to be capped to 4.4 miles
        # Examples:
        # - 1: 20 results, split into 1.1 and 1.2, 1.1: 12 results (1 new one), 1.2: 6 results (1 new one):
        #   so we didn't get the original 20 results, some are not being given

        # TODO: how do we decide to search at a finer granularity?
        # Inputs available: newOne, exceededRadius, len(psn['results'])
        split = False
        if (radius > 4.4):
            split = True
        elif (exceededRadius):
            # This does not mean that there aren't new results to be had (they pop into existence) as we split
            split = False
        else:
            if (not name and len(psn['results']) == 0):
                split = False
            elif (name and len(psn['results']) == 1):
                split = False
            elif (len(psn['results']) == 20):
                # results are full there are almost for sure more so always split
                split = True
            else:
                # there could be more results at a finer resolution, how do we know?
                split = True

        # split if splitting is enabled and there were results and none of the exceeded the radius
        if (doSplit and split):
            #subdivide current bounding box in 2 and append to bound_list
            split_count = split_count + 1
            print('split #: ', split_count)
            if ( abs(box['northeast']['lat'] - box['southwest']['lat']) > abs(box['northeast']['lng'] - box['southwest']['lng']) ):
                lat_mid = (box['northeast']['lat'] + box['southwest']['lat']) / 2.0
                new_box1 = { 'northeast': {'lat': box['northeast']['lat'], 'lng': box['northeast']['lng']},
                             'southwest': {'lat': lat_mid, 'lng': box['southwest']['lng']} }
                new_box2 = { 'northeast': {'lat': lat_mid, 'lng': box['northeast']['lng']},
                             'southwest': {'lat': box['southwest']['lat'], 'lng': box['southwest']['lng']} }
            else:
                lng_mid = (box['northeast']['lng'] + box['southwest']['lng']) / 2.0
                new_box1 = { 'northeast': {'lat': box['northeast']['lat'], 'lng': box['northeast']['lng']},
                             'southwest': {'lat': box['southwest']['lat'], 'lng': lng_mid} }
                new_box2 = { 'northeast': {'lat': box['northeast']['lat'], 'lng': lng_mid},
                             'southwest': {'lat': box['southwest']['lat'], 'lng': box['southwest']['lng']} }
            bound_list.append(new_box1)
            bound_list.append(new_box2)

        if (0):
            # Debug: only iterate one box
            cont_srch = False

        if (not bound_list or split_count > split_limit):
            cont_srch = False #terminate search if there is no bounding box in bound_list or excede split limit
            if (split_count > split_limit):
                print('---------------------------------- split limit of', split_limit,'reached --------------- why this happened should be investigated')



# Evaluation
def getNearest(loc, data, n):
    if (n == 'all'):
        result = []
        for k, v in iter(data.items()):
            result.append(distance(loc, (v['location']['lat'], v['location']['lng'])))
        #print('Returning ' + str(result))
        return result

    h = []
    if (0):
        #print('dists')
        #startTime = time.time()
        dists = []
        for k, v in iter(data.items()):
            dists.append(distance(loc, (v['location']['lat'], v['location']['lng'])))
        #print('elapsedTime = ' + str(time.time() - startTime))

        #print('heap')
        #startTime = time.time()
        for d in dists:
            #heapq.heappush(h, distance(loc, (v['location']['lat'], v['location']['lng'])))
            heapq.heappush(h, d)
        #print('elapsedTime = ' + str(time.time() - startTime))
    else:
        for k, v in iter(data.items()):
            heapq.heappush(h, distance(loc, (v['location']['lat'], v['location']['lng'])))

    return [heapq.heappop(h) for i in range(n)]

def evaluate_single_func(funcType, func, x):
    if (funcType == None or func == None):
        raise Exception('ERROR: function data is not given for range for x = ' + str(x))

    if (funcType == 'linear'):
        #print('linear func = ' + str(func))
        x1 = func[0][0]
        y1 = func[0][1]
        x2 = func[1][0]
        y2 = func[1][1]
        return (x-x1) * (y2-y1) / (x2-x1) + y1
    elif (funcType == 'exp'):
        return func[0] * math.exp(func[1] * x)
    elif (funcType == 'exp2'):
        return func[0] * math.exp(func[1] * x * x)
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
            elif (k == 'exp' or k == 'exp2'):
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

def evaluate_require_nearest(loc, data, value, extraData=None):
    #print(str(value))
    selectionType = value['selection']['type']
    if (selectionType != 'nearest'):
        raise Exception('ERROR: can only evaluate for selection type \'nearest\'')

    nearest = getNearest(loc, data, value['selection']['nearest'])
    if (extraData != None):
        extraData['nearest'] = nearest
        print('nearest dists = ' + str(nearest))
    scores = []
    for n in nearest:
        scores.append(evaluate_function(value['function'], n))
    #print('scores = ' + str(scores))

    return evaluate_final(value['selection']['final'], scores)


# Web
# o-xterm-34  216.228.112.21
# sc-xterm-06 216.228.112.21
# sc-xterm-01 216.228.112.22
# sc-xterm-17 216.228.112.22
# sc-xterm-02 216.228.112.21
def get_webpage(url):
    """ Given a HTTP/HTTPS url and then returns string
    Returns:
        string of HTML source code
    """

    try:
        req = Request(url=url)
        #with urlopen(req, cafile=certifi.where()) as f:
        result = ''
        with contextlib.closing(urlopen(req, cafile=certifi.where())) as f:
            result = f.read().decode('utf-8')
        return result
    except urllib.error.HTTPError as httperr:
        #print(httperr.headers)  # Dump the headers to see if there's more information
        #print(httperr.read())
        raise

    #resp = urllib.request.urlopen('https://foo.com/bar/baz.html', cafile=certifi.where())
    req = Request(url, headers={'Accept-Charset': 'utf-8', 'Accept-Language': 'zh-tw,en-us;q=0.5'})
    #with urlopen(req, cafile=certifi.where()) as rsq:
    with contextlib.closing(urlopen(req, cafile=certifi.where())) as rsq:
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

