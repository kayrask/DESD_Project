import math, re

POSTCODE_CENTROIDS = {
    "BS1": (51.4545, -2.5960), "BS2": (51.4600, -2.5727), "BS3": (51.4403, -2.5969),
    "BS4": (51.4324, -2.5519), "BS5": (51.4643, -2.5479), "BS6": (51.4726, -2.5970),
    "BS7": (51.4841, -2.5842), "BS8": (51.4554, -2.6163), "BS9": (51.4886, -2.6283),
    "BS10": (51.5046, -2.6006), "BS11": (51.4958, -2.6682), "BS13": (51.4120, -2.6018),
    "BS14": (51.4052, -2.5498), "BS15": (51.4536, -2.5050), "BS16": (51.4892, -2.5167),
    "BS20": (51.4878, -2.7424), "BS23": (51.3429, -2.9772), "BS24": (51.3271, -2.9416),
    "BA1": (51.3813, -2.3590), "BA2": (51.3670, -2.3491), "BA3": (51.2836, -2.4606),
    "GL1": (51.8642, -2.2382), "GL2": (51.8363, -2.2707), "GL50": (51.9000, -2.0743),
    "SN1": (51.5600, -1.7833), "SN2": (51.5724, -1.7812), "SN3": (51.5649, -1.7507),
    "TA1": (51.0142, -3.0999), "TA2": (51.0303, -3.0729), "TA3": (51.0001, -2.9922),
    "NP18": (51.5960, -2.9400), "NP19": (51.5793, -2.9719), "NP20": (51.5842, -2.9977),
}

DEFAULT_BRISTOL = (51.4545, -2.5879)


def _get_area(postcode: str):
    pc = postcode.upper().strip()
    m = re.match(r'^([A-Z]{1,2}\d{1,2}[A-Z]?)', pc)
    if m:
        area = m.group(1)
        if area in POSTCODE_CENTROIDS:
            return POSTCODE_CENTROIDS[area]
        short = re.match(r'^([A-Z]{1,2}\d{1,2})', area)
        if short and short.group(1) in POSTCODE_CENTROIDS:
            return POSTCODE_CENTROIDS[short.group(1)]
    return None


def calculate_food_miles(postcode1: str, postcode2: str):
    c1 = _get_area(postcode1) if postcode1 else None
    c2 = _get_area(postcode2) if postcode2 else None
    if not c1:
        c1 = DEFAULT_BRISTOL
    if not c2:
        c2 = DEFAULT_BRISTOL
    R = 3958.8
    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)
