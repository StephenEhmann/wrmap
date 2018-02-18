import sys
import heapq
import math
from urllib.request import urlopen, Request
import certifi
import geopy.distance

if (1):
    import googlemaps
    gmaps = googlemaps.Client(key='AIzaSyDNyA5ZDP1JClw9sTnVXuFJP_1FvZk30zU') # Stephen's key
    #gmaps = googlemaps.Client(key='AIzaSyAM8dMF61VMVlcCpDDRcOhhMoudiAixO00') # Eric's key
    #gmaps = googlemaps.Client(key='AIzaSyDpKsGiSCE6MH_KlGTSW8eza6u6dVa8kIE') # Levi's key
else:
    import fgm
    gmaps = fgm.Client(key=criterionName)

def isInside(loc, bounds):
    return loc['lng'] > bounds['southwest']['lng'] and loc['lng'] < bounds['northeast']['lng'] and \
           loc['lat'] > bounds['southwest']['lat'] and loc['lat'] < bounds['northeast']['lat']

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

# Find
def find(location, bounds, data, allData, placeType=None, name=None, doSplit=True):
    if (placeType == None and name == None or placeType != None and name != None):
        raise Exception('ERROR: exactly one of placeType and name must be given')

    #global server_queries
    cont_srch = True
    bound_list = [bounds] #initialize stack of subdivided bounding boxes
    split_count = 0
    split_limit = 100 #terminate if split too many times
    while(cont_srch):
        box = bound_list.pop() #pop one subdivided bounding box
        center = centroid(box)
        #print('start outer loop, current center is', center)
        split = False #default is don't split, change to True below if distance to results are less than radius
        radius = max( distance( (box['northeast']['lat'], box['northeast']['lng']), (center['lat'], center['lng']) ),
                      distance( (box['southwest']['lat'], box['southwest']['lng']), (center['lat'], center['lng']) ) )
        #print('box=' + str(box))
        #print('center=' + str(center))
        #print('radius=' + str(radius))
        more = True
        token = None
        while (more):
            if (not token):
                if (name):
                    psn = gmaps.places_nearby(location=center, rank_by='distance', keyword=name)
                    #server_queries += 1
                else:
                    psn = gmaps.places_nearby(location=center, rank_by='distance', type=placeType)
                    #server_queries += 1
            else:
                #print('token = ' + token)
                psn = gmaps.places_nearby(location=center, page_token=token)
                #server_queries += 1
            psn_result_count = 0
            for p in psn['results']:
                dist_center = distance( (p['geometry']['location']['lat'], p['geometry']['location']['lng']),
                                        (center['lat'], center['lng']))
                if (dist_center < radius):
                    if (psn_result_count == 0):
                        #print('splitting')
                        split = doSplit
                else:
                    #print('        exceeded radius')
                    more = False
                    split = False
                    break
                psn_result_count = psn_result_count + 1

                if (not isInside(p['geometry']['location'], bounds)):
                    # Not in the original, outermost bounding box
                    #print('this one is not inside:')
                    #print(dump(p, default_flow_style=False, Dumper=Dumper))
                    continue
                if (data.get(p['place_id'])):
                    # Already found this one
                    continue

                dist = distance( (p['geometry']['location']['lat'], p['geometry']['location']['lng']),
                                       (location['lat'], location['lng'])) #still calculate dist to original location for recording
                gRec = {'name': p['name'], 'vicinity': p['vicinity'], 'location': p['geometry']['location'], 'distance': dist}

                if (0):
                    details = gmaps.place(p['place_id'])
                    url = details['result']['url']
                    gRec['url'] = details['result']['url']

                data[p['place_id']] = gRec

                p['distance'] = dist

                allData.append(p)

                if (0):
                    # Debug: just do one iteration
                    more = False
                    split = False
                    cont_srch = False
                    break

            if (more):
                token = psn.get('next_page_token')

            if (not token):
                # finished
                more = False
                break
            time.sleep(2) # next_page_token not immediately ready server-side

        if (split):
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
            elif (k == 'const' or k == 'exp' or k == 'exp2'):
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

    nearest = getNearest(loc, data, value['selection']['nearest'])
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

