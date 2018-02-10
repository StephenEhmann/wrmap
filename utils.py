import sys
import math
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
