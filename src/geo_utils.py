try:
    from src import config
except ModuleNotFoundError:
    import config

import os
import random
import uuid
import openrouteservice
from pydantic import BaseModel
from typing import Tuple

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