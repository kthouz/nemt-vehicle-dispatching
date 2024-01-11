try:
    from src import config
    from src import utils
except ModuleNotFoundError:
    import config
    import utils

import os
import random
import uuid
import openrouteservice
from pydantic import BaseModel
from typing import Tuple, List, Union

logger = utils.init_logger(__name__, level=config.LOG_LEVEL)
ors_client = openrouteservice.Client(key=config.OPENROUTESERVICE_API_KEY)

def address_to_coordinates(address:str)->Tuple[float, float]:
    """
    Convert address to coordinates
    
    Parameters
    ----------
    address : str
        Address to convert to coordinates
    
    Returns
    -------
    Tuple[float, float]
        Coordinates of address
    """
    geocode_result = ors_client.pelias_search(text=address)
    coordinates = geocode_result['features'][0]['geometry']['coordinates']
    return coordinates

def get_distance_matrix(addresses:List[str]=[], coordinates:List[Tuple[float, float]]=[])->dict:
    """
    Get distance matrix for addresses/coordinates. Distance is measured in miles while duration is measured in seconds.
    
    Parameters
    ----------
    addresses : List[str], optional
        List of addresses to get distance matrix for. Defaults to [].
    coordinates : List[Tuple[float, float]], optional
        List of coordinates to get distance matrix for. Defaults to [].
    
    Returns
    -------
    dict
        Distance and duration matrix for addresses and coordinates. 
    """
    assert addresses or coordinates, "Either addresses or coordinates must be provided"

    if addresses:
        coordinates = [address_to_coordinates(address) for address in addresses] + coordinates
    distance_matrix = ors_client.distance_matrix(
        locations=coordinates,
        metrics=["distance", "duration"],
        units="mi",
        optimized=False,
        validate=False
    )
    addresses = {
        address: tuple(coordinates[i]) for i, address in enumerate(addresses)
    }
    locations = [tuple(x) for x in distance_matrix["metadata"]["query"]["locations"]]
    lookup = dict()
    for i in range(len(distance_matrix['durations'])):
        for j in range(i, len(distance_matrix["durations"][0])):
            lookup[(tuple(locations[i]), tuple(locations[j]))] = {
                "distance": distance_matrix["distances"][i][j],
                "duration": distance_matrix["durations"][i][j]
            }
    
    result = {
        "distance": distance_matrix["distances"],
        "duration": distance_matrix["durations"],
        "locations": locations,
        "addresses": addresses,
        "lookup": lookup
    }
    return result

def get_trip_duration(origin:Union[str, Tuple[float, float]], destination:Union[str, Tuple[float, float]])->float:
    """
    Get trip duration between origin and destination
    
    Parameters
    ----------
    origin : Union[str, Tuple[float, float]]
        Origin coordinates
    destination : Union[str, Tuple[float, float]]
        Destination coordinates
    
    Returns
    -------
    float
        Trip duration in seconds
    """
    addresses = []
    coordinates = []
    for x in [origin, destination]:
        if isinstance(x, str):
            addresses.append(x)
        else:
            coordinates.append(x)
    matrix = get_distance_matrix(addresses=addresses, coordinates=coordinates)
    if isinstance(origin, str):
        origin = matrix["addresses"][origin]
    if isinstance(destination, str):
        destination = matrix["addresses"][destination]
    duration_seconds = matrix["lookup"][(tuple(origin), tuple(destination))]["duration"]
    return duration_seconds