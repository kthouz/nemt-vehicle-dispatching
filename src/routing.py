try:
    from src import config
    from src import utils
except ModuleNotFoundError:
    import config
    import utils

import json
import requests
import openrouteservice
from pydantic import BaseModel, model_validator, validator
from typing import Tuple, List, Union, Optional, Dict, Any
from pprint import pprint

logger = utils.init_logger(__name__, level=config.LOG_LEVEL)
client = openrouteservice.Client(key=config.OPENROUTESERVICE_API_KEY, base_url=config.OPENROUTESERVICE_BASE_URL)

class Location(BaseModel):
    address: Optional[Union[str, None]] = None
    coordinates: Optional[Union[Tuple[float, float], None]] = None

    @model_validator(mode='after')
    def validate_location(cls, values):
        """
        Validate that either address or coordinates is provided
        """
        if values.address is None and values.coordinates is None:
            raise ValueError("Either address or coordinates must be provided")
        return values


def get_geocode(address:str, use_cache:bool=True)->dict:
    """
    Get geocode for address's longitude and latitude
    Note: This function uses OpenStreetMap's Nominatim API instead of OpenRouteService's Pelias API because the latter is not free and the local endpoint is not working.

    Parameters
    ----------
    address : str
        Address to get geocode for
    
    Returns
    -------
    dict
        Geocode for address
    """
    if use_cache:
        if address in utils.ADDRESS_CACHE:
            return utils.ADDRESS_CACHE[address]
        
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "json",
        "q": address
    }
    headers = {
        "User-Agent": "NEMTOptimalRoutePlanner/0.1"
    }
    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        if len(response.json()) > 0:
            geocode = [float(response.json()[0].get('lon')), float(response.json()[0].get('lat'))]
            if use_cache:
                utils.cache_address({address: geocode}, save=True)
            return geocode
        return None
    else:
        logger.error(f"Failed to get geocode for {address}:\n{response.text}")
        return None
    

def get_distance_duration(source:Union[str, Tuple[float, float]], destination:Union[str, Tuple[float, float]])->Tuple[float, float]:
    """
    Get distance and duration between two locations. Distance is measured in miles while duration is measured in seconds.
    
    Parameters
    ----------
    source : Union[str, Tuple[float, float]]
        Source location
    destination : Union[str, Tuple[float, float]]
        Destination location
    
    Returns
    -------
    Tuple[float, float]
        Distance and duration between source and destination
    """
    if isinstance(source, str):
        source = get_geocode(source)
    if isinstance(destination, str):
        destination = get_geocode(destination)
    logger.debug(f"Getting distance and duration for {source} and {destination}")
    directions = client.directions([source, destination], profile='driving-car', units='mi', validate=True)
    distance = directions['routes'][0]['summary']['distance']
    duration = directions['routes'][0]['summary']['duration']
    return distance, duration

def get_distance_matrix(locations:Dict[Union[int, str], Location], sources:List[Union[str, int]]=None, destinations:List[Union[str, int]]=None)->dict:
    """
    Get distance matrix for locations. Distance is measured in miles while duration is measured in seconds.
    
    Parameters
    ----------
    locations : Dict[Union[int, str], Location]
        Dictionary of locations to get distance matrix for
    sources : List[Union[str, int]], optional
        List of indices that refer to locations to be considered as sources. Defaults to None.
    destinations : List[Union[str, int]], optional
        List of indices that refer to locations to be considered as destinations. Defaults to None.
    
    Returns
    -------
    dict
        Distance and duration matrix for locations
    """
    _loc_coordinates = []
    for loc_index, location in locations.items():
        if location.coordinates is None:
            location.coordinates = get_geocode(location.address)
            logger.info(f"Location {loc_index}:{location.address} coordinates found as {location.coordinates}")
        if location.address is None:
            location.address = "NoMention"
        _loc_coordinates.append(location.coordinates)
    
    matrix = client.distance_matrix(
        locations=_loc_coordinates,
        metrics=["distance", "duration"],
        units="mi",
        optimized=True,
        validate=True,
        sources=sources,
        destinations=destinations
    )
    return {
        "distance": matrix["distances"],
        "duration": matrix["durations"],
        "locations": {index: x.model_dump() for index, x in locations.items()},
        "address_to_index": {location.address: index for index, location in locations.items()},
    }
if __name__=='__main__':
    pprint(utils.ADDRESS_CACHE)
    addresses = ["1740 Nicholasville Rd, Lexington, KY", "2397 Paynes Depot Road, Georgetown, KY, USA", "1000 South Limestone, Lexington, KY, USA", "2101 Patchen Lake Ln, Lexington, KY 40505", "3489 Lansdowne Dr, Lexington, KY 40517", "601 E Main St, Lexington, KY 40508", "4701 Hartland Pkwy, Lexington, KY 40515", "900 Richmond Rd, Lexington, KY 40502", "1600 Leestown Rd, Lexington, KY 40511", "2173 Nicholasville Rd, Lexington, KY 40503", "4001 Kennesaw Dr, Lexington, KY 40515", "1648 McGrathiana Pkwy #300, Lexington, KY 40511", "333 W Vine St, Lexington, KY 40507"]
    locations = dict()
    for i, address in enumerate(addresses):
        geocode = get_geocode(address)
        if geocode is None:
            continue
        locations[i] = Location(address=address, coordinates=geocode)
        print(f"Getting geocode for {address} as {geocode}")
    
    source = [-84.50481,38.04296]
    destination = [-84.4893,38.05042]
    distance, duration = get_distance_duration(source, destination)
    logger.info(f"Distance between {source} and {destination} is {distance} miles and takes {duration} seconds")

    matrix = get_distance_matrix(locations)
    pprint(matrix)