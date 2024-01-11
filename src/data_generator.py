try:
    from src import config
    from src import geo_utils as gutils
except ModuleNotFoundError:
    import config
    import geo_utils as gutils

import os
import math
import datetime
import random
import uuid
import json
import pandas as pd
from typing import Tuple, List

ors_client = gutils.ors_client

def get_bounding_box(address:str)->List[Tuple]:
    """
    Get bounding box for address
    
    Parameters
    ----------
    address : str
        Address to get bounding box for
    
    Returns
    -------
    List[Tuple]
        Bounding box for address
    """
    geocode_result = ors_client.pelias_search(text=address)
    bounding_box = geocode_result['features'][0]['bbox']
    return bounding_box

def generate_addresses(bbox:List[float], n_addresses:int=5)->List[str]:
    """
    Generate addresses within a bounding box

    Parameters
    ----------
    bbox : List[float]
        Bounding box to generate addresses within
    n_addresses : int, optional
        Number of addresses to generate, by default 5
    
    Returns
    -------
    List[str]
        List of addresses
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    random_coordinates = [
        (random.uniform(min_lon, max_lon), random.uniform(min_lat, max_lat))
        for _ in range(n_addresses)
    ]
    addresses = []
    for coordinate in random_coordinates:
        try:
            geocode_result = ors_client.pelias_reverse(point=coordinate)
            address = geocode_result['features'][0]['properties']['label']
            addresses.append({
                'address': address,
                'coordinate': coordinate,
                'status': 'success',
                'error': ''
            })
        except:
            addresses.append({
                'address': '',
                'coordinate': coordinate,
                'status': 'failure',
                'error': 'Could not generate address'
            })
    return addresses

class VehicleGenerator:
    def __init__(self, n:int, region:str='Lexington, KY'):
        self.n = n
        self.index = 0
        self.addresses = generate_addresses(get_bounding_box(region), n)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.index >= self.n:
            raise StopIteration
        else:
            self.index += 1
            return {
                'vehicle_id': str(uuid.uuid4()),
                'address': self.addresses[self.index-1].get("address"),
                'capacity': random.randint(1, 5)
            }

class RouteGenerator:
    def __init__(self, n_orig:int, n_dest:int, region:str='Lexington, KY', operating_date:datetime.date=datetime.date.today()):
        self.origin = generate_addresses(get_bounding_box(region), n_orig)
        self.destination = generate_addresses(get_bounding_box(region), n_dest)
        self.index = 0
        self.operating_date = operating_date
        self.time_range_start = datetime.datetime.combine(self.operating_date, datetime.time(config.DAY_START_HOUR, 0, 0))
        self.time_range_end = datetime.datetime.combine(self.operating_date, datetime.time(config.DAY_END_HOUR, 0, 0))
    
    def _set_pickup_time(self, granularity:int=5):
        random_time = self.time_range_start + datetime.timedelta(seconds=random.randint(0, int((self.time_range_end - self.time_range_start).total_seconds())))
        minutes = (random_time - self.time_range_start).total_seconds() / 60
        rounded_minutes = math.ceil(minutes / granularity) * granularity
        return self.time_range_start + datetime.timedelta(minutes=rounded_minutes)
        
    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.origin):
            raise StopIteration
        else:
            self.index += 1
            return {
                'route_id': str(uuid.uuid4()),
                'orig_address': self.origin[self.index-1].get("address"),
                'dest_address': random.choice(self.destination).get("address"),
                'num_passengers': random.randint(1, 3),
                'pickup_time': self._set_pickup_time().strftime('%Y-%m-%d %H:%M:%S'),
            }

def generate_data(num_orig:int, num_dest:int, num_vehicles:int, region:str):
    routes = RouteGenerator(num_orig, num_dest, region)
    vehicles = VehicleGenerator(num_vehicles, region)
    _routes = []
    
    for _ in range(num_orig):
        _routes.append(next(routes))
    _vehicles = []
    for _ in range(num_vehicles):
        _vehicles.append(next(vehicles))
    return _routes, _vehicles
if __name__ == '__main__':
    # bbox = get_bounding_box('Lexington, KY')
    # addresses = generate_addresses(bbox, 3)
    from pprint import pprint
    routes, vehicles = generate_data(30, 20, 5, 'Lexington, KY')
    # json.dump(routes, open('routes.json', 'w'))
    # json.dump(vehicles, open('vehicles.json', 'w'))
    # pprint(routes)
    # pprint(vehicles)
    pd.DataFrame(routes).to_csv('data/routes.csv', index=False)
    pd.DataFrame(vehicles).to_csv('data/vehicles.csv', index=False)