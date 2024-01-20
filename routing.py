import constants
import helpers

import json
import os
import uuid
import traceback
import requests
import pandas as pd
import numpy as np
from typing import Tuple, List, Union, Optional, Dict, Any
from pprint import pprint
from datetime import datetime, timedelta


vroom_url = constants.VROOM_BASE_URL
# vroom_url = "http://solver.vroom-project.org"

logger = helpers.init_logger(__name__, level=constants.LOG_LEVEL)


class LocationsMatrix:
    """
    Class to store distance/duration location matrices

    Attributes
    ----------
    locations : List[str]
        List of locations
    distances : List[List[float]]
        Distance matrix in meters
    durations : List[List[float]]
        Duration matrix in seconds
    lookup : Dict[str, int]
        Lookup dictionary for locations (address to index)
    use_cache : bool
        Use cache to get geocode
    """
    def __init__(self, locations:List[str], use_case:bool=True) -> None:
        self.locations = locations
        self.distances = None
        self.durations = None
        self.lookup = None
        self.use_cache = use_case
        self.compute_matrices()

    def compute_matrices(self)->np.ndarray:
        """
        Compute and set duration and distance matrices for locations
        """
        coords = []
        lookup = {}
        locations = set(self.locations)
        i = 0
        for location in locations:
            lookup[location] = i
            geocode = helpers.get_geocode(location, self.use_cache)
            if geocode is not None:
                coords.append(geocode)
                i += 1
        
        coords = ";".join([f"{coord[0]},{coord[1]}" for coord in coords])
        url = f"{constants.OSRM_BASE_URL}/table/v1/driving/{coords}?annotations=distance,duration"
        response = requests.get(url)

        if response.status_code == 200:
            self.durations = response.json()['durations']
            self.distances= response.json()['distances']
            self.lookup = lookup
        else:
            raise Exception(f"Failed to get duration matrix for {locations}:\n{response.text}")

    def get_duration(self, source:str, destination:str)->Union[float, None]:
        """
        Get duration between source and destination
        
        Parameters
        ----------
        source : str
            Source location
        destination : str
            Destination location
        
        Returns
        -------
        Union[int, None]
            Duration between source and destination
        """
        try:
            return self.durations[self.lookup[source]][self.lookup[destination]]
        except KeyError:
            logger.error(f"Failed to get duration for {source} and {destination}")
            logger.error(traceback.format_exc())
            return None
    
    def get_distance(self, source:str, destination:str)->Union[float, None]:
        """
        Get distance between source and destination
        
        Parameters
        ----------
        source : str
            Source location
        destination : str
            Destination location
        
        Returns
        -------
        Union[int, None]
            Distance between source and destination
        """
        try:
            return self.distances[self.lookup[source]][self.lookup[destination]]
        except KeyError:
            logger.error(f"Failed to get distance for {source} and {destination}")
            logger.error(traceback.format_exc())
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
        if 'earliest_pickup' in row:
            row['earliest_pickup'] = pd.to_datetime(row['earliest_pickup'])
        if 'latest_delivery' in row:
            row['latest_delivery'] = pd.to_datetime(row['latest_delivery'])
        if 'nb_passengers' not in row:
            row['nb_passengers'] = 1
        location = helpers.get_geocode(row.pickup_address, use_cache)
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
                [helpers.str_to_timestamp(str(row.earliest_pickup-timedelta(seconds=constants.MAX_WAIT_TIME))), helpers.str_to_timestamp(str(row.earliest_pickup))]
            ]
        }
        jobs.append(job)
    return {
        "jobs": jobs,
        "errors": errors,
        "vroom_id_mapper": mapper
    }

def preprocess_shipments(sdf:pd.DataFrame, use_cache:bool=True, matrix:List[List[float]]=None)->Dict[str, Any]:
    """
    Preprocess shipments aka pickup-delivery dataframe to vroom format
    
    Parameters
    ----------
    sdf : pd.DataFrame
        Job dataframe
    use_cache : bool, optional
        Use cache to get geocode, by default True
    matrix : List[List[float]], optional
        Duration matrix between locations, by default None
    
    Returns
    -------
    Dict[str, Any]
        Dictionary with 'errors' and 'shipments' keys
    """
    errors = {}
    mapper = {}
    shipments = []
    if matrix is None:
        addresses = list(set(sdf['pickup_address'].unique().tolist() + sdf['delivery_address'].unique().tolist()))
        matrix = LocationsMatrix(addresses, use_cache)
    for i, row in sdf.iterrows():
        if 'service_time' not in row:
            row['service_time'] = constants.DEFAULT_SERVICE_TIME
        if 'skills' not in row:
            row['skills'] = ",".join([str(i) for i in range(1, 5)])
        if 'earliest_pickup' in row:
            row['earliest_pickup'] = pd.to_datetime(row['earliest_pickup'])
        if 'latest_delivery' in row:
            row['latest_delivery'] = pd.to_datetime(row['latest_delivery'])
        if 'nb_passengers' not in row:
            row['nb_passengers'] = 1
        pickup_location = helpers.get_geocode(row.pickup_address, use_cache)
        delivery_location = helpers.get_geocode(row.delivery_address, use_cache)
        duration = matrix.get_duration(row.pickup_address, row.delivery_address)
        estimated_pickup_time = row.latest_delivery - timedelta(seconds=int(duration))
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
                    [helpers.str_to_timestamp(str(row.earliest_pickup-timedelta(seconds=constants.MAX_WAIT_TIME))), helpers.str_to_timestamp(str(max(row.earliest_pickup, estimated_pickup_time)))]
                ]
            },
            "delivery": {
                "id": i,
                "service": row.service_time,
                "location": delivery_location,
                "time_windows": [
                    [helpers.str_to_timestamp(str(row.latest_delivery-timedelta(seconds=constants.MAX_WAIT_TIME))), helpers.str_to_timestamp(str(row.latest_delivery))]
                ]
            }
        }

        shipments.append(job)
    return {
        "shipments": shipments,
        "errors": errors,
        "vroom_id_mapper": mapper
    }

def preprocess_vehicles(vdf:pd.DataFrame, use_cache:bool=True, date:datetime.date=datetime.today().date())->Dict[str, Any]:
    """
    Preprocess vehicles dataframe to vroom format

    Parameters
    ----------
    vdf : pd.DataFrame
        Vehicle dataframe
    use_cache : bool, optional
        Use cache to get geocode, by default True
    date : datetime.date, optional
        Date to use for start and end time, by default datetime.today().date
    
    Returns
    -------
    Dict[str, Any]
        Dictionary with 'errors' and 'vehicles' keys
    """
    errors = {}
    mapper = {}
    vehicles = []
    for i, row in vdf.iterrows():
        time_window = helpers.get_timestamp_interval(date, row.working_hours)
        start_location = helpers.get_geocode(row.address, use_cache)
        end_location = helpers.get_geocode(row.address, use_cache)
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
            "time_window": time_window
        }
        vehicles.append(vehicle)
    return {
        "vehicles": vehicles,
        "errors": errors,
        "vroom_id_mapper": mapper
    }

def preprocess(vdf:pd.DataFrame, tasks:pd.DataFrame=None, task_type:str='shipment', use_cache:bool=True, save:bool=False, session_id:Union[str, None]=None)->List[List[dict]]:
    """
    Optimize route using vroom

    Parameters
    ----------
    vdf : pd.DataFrame
        Vehicle dataframe
    tasks : pd.DataFrame
        Job/Shipment dataframe
    task_type : str, optional
        Type of task, by default 'shipment'. Can be either 'job' or 'shipment'
    
    Returns
    -------
    dict
        Optimized route
    """
    assert task_type in ('job', 'shipment'), "task_type must be either 'job' or 'shipment'"
    if task_type == 'job':
        raise NotImplementedError("Job optimization is not implemented yet. Only pickup-delivery (aka shipment) optimization is supported")
    else:
        print("-- Processing shipments --")
        job_processed = {"jobs": [], "errors": {}, "vroom_id_mapper": {}}
        shi_processed = preprocess_shipments(tasks, use_cache)
        date = pd.to_datetime(tasks['earliest_pickup']).min().date()
    
    print("-- Processing vehicles --")
    veh_processed = preprocess_vehicles(vdf, use_cache, date)

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
    jdf = pd.read_csv("data/jobs.csv")

    vehicles, jobs, shipments, errors, mapper = preprocess(vdf, sdf=jdf, use_cache=True, save=True)   
    # solution = optimize(vehicles, jobs=jobs, shipments=shipments, save=True)

    # addresses = list(json.load(open("data/addresses.json", "r")).keys())
    addresses = jdf['pickup_address'].unique().tolist() + jdf['delivery_address'].unique().tolist()
    addresses = list(set(addresses))
    matrix = LocationsMatrix(addresses)
    # pprint(matrix.durations)
    # pprint(matrix.distances)
    # pprint(matrix.lookup)
    # pprint(matrix.get_duration(addresses[0], addresses[1]))
    # pprint(matrix.get_distance(addresses[0], addresses[1]))
    # pprint(matrix.get_duration("1307 Cane Run Road, Georgetown, KY, USA", "Chandamere Way, Jessamine County, KY, USA"))

