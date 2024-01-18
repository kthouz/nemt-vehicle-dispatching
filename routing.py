import constants
import helpers

import json
import os
import uuid
import requests
import pandas as pd
import numpy as np
from typing import Tuple, List, Union, Optional, Dict, Any
from pprint import pprint
from datetime import datetime, timedelta


vroom_url = constants.VROOM_BASE_URL
# vroom_url = "http://solver.vroom-project.org"

logger = helpers.init_logger(__name__, level=constants.LOG_LEVEL)

address_cache = helpers.AddressCache()

def get_geocode(address:str, use_cache:bool=True)->dict:
    """
    Get geocode for address's longitude and latitude
    Note: This function uses OpenStreetMap's Nominatim API. So care to optimize for the rate limit or use a different API preferably local

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
        if address_cache.get(address):
            return address_cache.get(address)
        
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "json",
        "q": address
    }
    headers = {
        "User-Agent": "NEMTOptimalRoutePlanner/0.0"
    }
    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        if len(response.json()) > 0:
            geocode = [float(response.json()[0].get('lon')), float(response.json()[0].get('lat'))]
            if use_cache:
                address_cache.update(address, geocode)
            return geocode
        return None
    else:
        logger.error(f"Failed to get geocode for {address}:\n{response.text}")
        return None

def preprocess_jobs(jdf:pd.DataFrame, use_cache:bool=True)->Dict[str, Any]:
    """
    Preprocess jobs dataframe to vroom format
    
    Parameters
    ----------
    jdf : pd.DataFrame
        Job dataframe
    use_cache : bool, optional
        Use cache to get geocode, by default True
    
    Returns
    -------
    Dict[str, Any]
        Dictionary with 'errors' and 'jobs' keys
    """
    errors = {}
    mapper = {}
    jobs = []
    for i, row in jdf.iterrows():
        if 'service_time' not in row:
            row['service_time'] = constants.DEFAULT_SERVICE_TIME
        if 'skills' not in row:
            row['skills'] = ",".join([str(i) for i in range(1, 5)])
        if 'pickup_time' in row:
            row['pickup_time'] = pd.to_datetime(row['pickup_time'])
        if 'nb_passengers' not in row:
            row['nb_passengers'] = 1
        location = get_geocode(row.pickup_address, use_cache)
        if location is None:
            errors[row.job_id] = {
                "vroom_id": i,
                "error": "Failed to convert pickup address to geocode"
            }
            continue
        mapper[i] = row.job_id
        job = {
            "id": i,
            "name": row.job_id,
            "service": row.service_time,
            "delivery": [row.nb_passengers],
            "location": location,
            "skills": helpers.parse_skills(row.skills),
            "time_windows": [
                [helpers.str_to_timestamp(str(row.pickup_time-timedelta(seconds=constants.MAX_WAIT_TIME))), helpers.str_to_timestamp(str(row.pickup_time))]
            ]
        }
        jobs.append(job)
    return {
        "jobs": jobs,
        "errors": errors,
        "vroom_id_mapper": mapper
    }

def preprocess_shipments(sdf:pd.DataFrame, use_cache:bool=True)->Dict[str, Any]:
    """
    Preprocess shipments aka pickup-delivery dataframe to vroom format
    
    Parameters
    ----------
    sdf : pd.DataFrame
        Job dataframe
    use_cache : bool, optional
        Use cache to get geocode, by default True
    
    Returns
    -------
    Dict[str, Any]
        Dictionary with 'errors' and 'shipments' keys
    """
    errors = {}
    mapper = {}
    shipments = []
    for i, row in sdf.iterrows():
        if 'service_time' not in row:
            row['service_time'] = constants.DEFAULT_SERVICE_TIME
        if 'skills' not in row:
            row['skills'] = ",".join([str(i) for i in range(1, 5)])
        if 'pickup_time' in row:
            row['pickup_time'] = pd.to_datetime(row['pickup_time'])
        if 'nb_passengers' not in row:
            row['nb_passengers'] = 1
        pickup_location = get_geocode(row.pickup_address, use_cache)
        delivery_location = get_geocode(row.delivery_address, use_cache)
        if pickup_location is None or delivery_location is None:
            errors[row.job_id] = {
                "vroom_id": i,
                "error": "Failed to convert pickup or delivery address to geocode"
            }
            continue
        mapper[i] = row.job_id
        job = {
            "amount": [row.nb_passengers],
            "skills": helpers.parse_skills(row.skills),
            "pickup": {
                "id": i,
                "service": row.service_time,
                "location": pickup_location,
                "time_windows": [
                    [helpers.str_to_timestamp(str(row.pickup_time-timedelta(seconds=constants.MAX_WAIT_TIME))), helpers.str_to_timestamp(str(row.pickup_time))]
                ]
            },
            "delivery": {
                "id": i,
                "service": row.service_time,
                "location": delivery_location
            }
        }
        shipments.append(job)
    return {
        "shipments": shipments,
        "errors": errors,
        "vroom_id_mapper": mapper
    }

def preprocess_vehicles(vdf:pd.DataFrame, use_cache:bool=True)->Dict[str, Any]:
    """
    Preprocess vehicles dataframe to vroom format

    Parameters
    ----------
    vdf : pd.DataFrame
        Vehicle dataframe
    use_cache : bool, optional
        Use cache to get geocode, by default True
    
    Returns
    -------
    Dict[str, Any]
        Dictionary with 'errors' and 'vehicles' keys
    """
    errors = {}
    mapper = {}
    vehicles = []
    for i, row in vdf.iterrows():
        if 'start_time' not in row:
            row['start_time'] = helpers.digit_to_datetime(constants.DAY_START_HOUR)
        if 'end_time' not in row:
            row['end_time'] = helpers.digit_to_datetime(constants.DAY_END_HOUR)
        start_location = get_geocode(row.address, use_cache)
        end_location = get_geocode(row.address, use_cache)
        if start_location is None or end_location is None:
            errors[row.vehicle_id] = {
                "vroom_id": i,
                "error": "Failed to convert start/end address to geocode"
            }
            continue
        mapper[i] = row.vehicle_id
        vehicle = {
            "id": i,
            "name": row.vehicle_id,
            "start": start_location,
            "end": end_location,
            "capacity": [int(row.capacity)],
            "skills": helpers.parse_skills(row.skills),
            "time_window": [helpers.str_to_timestamp(str(row.start_time)), helpers.str_to_timestamp(str(row.end_time))]
        }
        vehicles.append(vehicle)
    return {
        "vehicles": vehicles,
        "errors": errors,
        "vroom_id_mapper": mapper
    }

def preprocess(vdf:pd.DataFrame, jdf:pd.DataFrame=None, sdf:pd.DataFrame=None, use_cache:bool=True, save:bool=False, session_id:Union[str, None]=None)->List[List[dict]]:
    """
    Optimize route using vroom

    Parameters
    ----------
    vdf : pd.DataFrame
        Vehicle dataframe
    jdf : pd.DataFrame
        Job dataframe
    sdf : pd.DataFrame
        Shipment dataframe
    
    Returns
    -------
    dict
        Optimized route
    """
    veh_processed = preprocess_vehicles(vdf, use_cache)
    if jdf is not None:
        job_processed = preprocess_jobs(jdf, use_cache)
    else:
        job_processed = {"jobs": [], "errors": {}, "vroom_id_mapper": {}}
    if sdf is not None:
        shi_processed = preprocess_shipments(sdf, use_cache)
    else:
        shi_processed = {"shipments": [], "errors": {}, "vroom_id_mapper": {}}
    errors = {
        'vehicle': veh_processed['errors'],
        'job': job_processed['errors'],
        'shipment': shi_processed['errors']
    }
    mapper = {
        'vehicle': veh_processed['vroom_id_mapper'],
        'job': job_processed['vroom_id_mapper'],
        'shipment': shi_processed['vroom_id_mapper']
    }
    if save:
        if session_id is None:
            session_id = str(int(datetime.timestamp(datetime.now())))
        json.dump(veh_processed['vehicles'], open(os.path.join(constants.PREPROCESSED_STORE, f"{session_id}_vehicles.json"), "w"), indent=4)
        json.dump(job_processed['jobs'], open(os.path.join(constants.PREPROCESSED_STORE, f"{session_id}_jobs.json"), "w"), indent=4)
        json.dump(shi_processed['shipments'], open(os.path.join(constants.PREPROCESSED_STORE, f"{session_id}_shipments.json"), "w"), indent=4)
        json.dump(errors, open(os.path.join(constants.PREPROCESSED_STORE, f"{session_id}_errors.json"), "w"), indent=4)
    
    return veh_processed['vehicles'], job_processed['jobs'], shi_processed['shipments'], errors, mapper

def optimize(vehicles:List[dict], jobs:List[dict]=[], shipments:List[dict]=[], save:bool=False, session_id:Union[str, None]=None)->Union[dict, None]:
    """
    Find the optimal route using vroom

    Parameters
    ----------
    vehicles : List[dict]
        List of vehicles and their properties
    jobs : List[dict]
        List of jobs and their properties
    shipments : List[dict]
        List of shipments (pickup-delivery) and their properties

    Returns
    -------
    Dict[str, Any]
        Optimized routes
    NoneType
        If optimization failed
    """
    
    data = {'vehicles': vehicles, 'options': {'g': True, 'geometry': True, 'format': 'json'}}
    if len(jobs) > 0:
        data['jobs'] = jobs
    if len(shipments) > 0:
        data['shipments'] = shipments

    response = requests.post(vroom_url, json=data)
    if response.status_code == 200:
        solution = response.json()
        if save:
            if session_id is None:
                session_id = str(int(datetime.timestamp(datetime.now())))
            json.dump(solution, open(os.path.join(constants.SOLUTION_STORE, f"{session_id}_solution.json"), "w"), indent=4)
            json.dump(data, open(os.path.join(constants.SOLUTION_STORE, f"{session_id}_data.json"), "w"), indent=4)
        return solution
    else:
        logger.error(f"Error: {response.text}")
        return None

if __name__ == "__main__":
    from pprint import pprint
    helpers.initialize_directories()
    vdf = pd.read_csv("data/vehicles.csv").dropna(subset=['skills'])
    jdf = pd.read_csv("data/jobs.csv").head(5)

    vehicles, jobs, shipments, errors, mapper = preprocess(vdf, sdf=jdf, use_cache=True, save=True)   
    solution = optimize(vehicles, jobs=jobs, shipments=shipments, save=True)

