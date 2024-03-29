import constants

import os
import json
import logging
import polyline
import folium
import webcolors
import requests
import leafmap.foliumap as leafmap
import numpy as np
import pandas as pd
import colorcet as cc
from typing import Tuple, List, Union, Optional, Dict, Any
from datetime import datetime
from pprint import pprint

if not os.path.exists(constants.ADDRESS_STORE):
    os.makedirs(os.path.dirname(constants.ADDRESS_STORE), exist_ok=True)
    with open(constants.ADDRESS_STORE, "w") as f:
        json.dump({}, f)

class AddressCache:
    def __init__(self, filename:str=constants.ADDRESS_STORE):
        self.filename = filename
        self.address_cache = json.load(open(filename, "r"))
    
    def get(self, address:str)->Tuple[float, float]:
        return self.address_cache.get(address)
    
    def update(self, address:str, geocode:Tuple[float, float], mode:str='hard')->None:
        assert mode in ['soft', 'hard'], f"Invalid mode {mode}. Valid modes are 'soft' and 'hard'"
        self.address_cache[address] = geocode
        if mode=='hard':
            self.save()
    
    def save(self)->None:
        with open(constants.ADDRESS_STORE, "w") as f:
            json.dump(self.address_cache, f)
    
    def reset(self, mode:str='soft')->None:
        assert mode in ['soft', 'hard'], f"Invalid mode {mode}. Valid modes are 'soft' and 'hard'"
        self.address_cache = dict()
        if mode=='hard':
            self.save()

address_cache = AddressCache()
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
    print(f"looking up a new address: {address}")
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
        address_cache.update(address, None)
        return None
    
def initialize_directories(directories:List[str]=[constants.PREPROCESSED_STORE, constants.SOLUTION_STORE, constants.LOGS_STORE])->None:
    print("Initializing directories")
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory {directory}")

def str_to_timestamp(dt:str)->int:
    """
    Convert datetime to timestamp

    Parameters
    ----------
    dt : str
        str datetime to convert

    Returns
    -------
    int
        Timestamp
    """
    return int(datetime.strptime(dt, "%Y-%m-%d %H:%M:%S").timestamp())

def str_to_seconds_past_midnight(dt:datetime)->int:
    """
    Convert datetime to seconds past midnight

    Parameters
    ----------
    dt : datetime
        str datetime to convert

    Returns
    -------
    int
        Seconds past midnight
    """
    dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    return dt.hour*3600 + dt.minute*60 + dt.second

def digit_to_datetime(digit:int)->datetime:
    """
    Convert digit to datetime

    Parameters
    ----------
    digit : int
        Digit to convert

    Returns
    -------
    datetime
        Datetime
    """
    assert digit>=0 and digit<24, f"Invalid digit {digit}. Digit must be between 0 and 24"
    today = datetime.today()
    dt = datetime(today.year, today.month, today.day, digit, 0, 0)
    return dt

def timestamp_to_datetime(ts:int)->datetime:
    """
    Convert timestamp to datetime

    Parameters
    ----------
    ts : int
        Timestamp to convert

    Returns
    -------
    datetime
        Datetime
    """
    return datetime.fromtimestamp(ts)

def get_timestamp_interval(date:datetime.date, interval:str)->List[int]:
    """
    Get timestamp interval from date and interval

    Parameters
    ----------
    date : datetime.date
        Date
    interval : str
        Interval

    Returns
    -------
    List[int]
        Timestamp interval
    """
    start_time, end_time = interval.split("-")
    start_time = datetime.strptime(start_time, "%H:%M")
    end_time = datetime.strptime(end_time, "%H:%M")
    start_datetime = datetime.combine(date, start_time.time())
    end_datetime = datetime.combine(date, end_time.time())
    return [start_datetime.timestamp(), end_datetime.timestamp()]

def parse_skills(skills:str)->List[int]:
    """
    Parse skills from string

    Parameters
    ----------
    skills : str
        Skills string

    Returns
    -------
    List[int]
        List of skills
    """
    return list(map(lambda x: int(x.strip()), str(skills).split(",") if skills else []))

def init_logger(name:str, level:int=logging.INFO)->logging.Logger:
    """
    Initialize logger

    Parameters
    ----------
    name : str
        Name of logger
    level : int, optional
        Logging level, by default logging.INFO

    Returns
    -------
    logging.Logger
        Logger object
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

def compute_center_coordinates(coords:List[Tuple[float,float]])->Tuple[float, float]:
    """
    Compute center coordinates from list of coordinates

    Parameters
    ----------
    coords : List[Tuple[float,float]]
        List of coordinates

    Returns
    -------
    Tuple[float, float]
        Center coordinates
    """
    coords = np.array(coords)
    return coords.mean(axis=0).tolist()

def build_osrm_path(coords:List[Tuple[float,float]], base_url:str=constants.OSRM_BASE_URL)->str:
    """
    Build OSRM path from list of coordinates

    Parameters
    ----------
    coords : List[Tuple[float,float]]
        List of coordinates
    base_url : str, optional
        OSRM server URL, by default constants.OSRM_BASE_URL

    Returns
    -------
    str
        OSRM path
    """
    coord_string = ';'.join([f"{coord[1]},{coord[0]}" for coord in coords])
    url = f"{base_url}/route/v1/driving/{coord_string}?overview=full&geometries=polyline"
    response = requests.get(url)
    if response.ok:
        return response.json()['routes'][0]['geometry']
    else:
        return ""

def geojson_unassigned(unassigned_data:pd.DataFrame)->Dict[str, Any]:
    """
    Create GeoJSON from data
    
    Parameters
    ----------
    unassigned_data : pd.DataFrame
        Data to create GeoJSON from
        
    Returns
    -------
    Dict[str, Any]
        GeoJSON
    """
    points = []
    for i, row in unassigned_data.iterrows():
        points.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": get_geocode(row["pickup_address"], use_cache=True)
            },
            "properties": {
                "type": "pickup",
                "job_id": row["job_id"],
                "address": row["pickup_address"],
                "load": row["nb_passengers"],
                "arrival": row["earliest_pickup"],
            },
            "route": None,
        })
        points.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": get_geocode(row["delivery_address"], use_cache=True)
            },
            "properties": {
                "type": "delivery",
                "job_id": row["job_id"],
                "address": row["delivery_address"],
                "load": row["nb_passengers"],
                "arrival": row["latest_delivery"],
            },
            "route": None,
        })
    geojson = {
        "type": "FeatureCollection",
        "features": points,
    }

    return geojson

def get_job_address(veh_id:str, job_id:str, _type:str, jobs:pd.DataFrame, vehicles, id_mapper:Dict[str, Any])->str:

    if _type.lower() in ('start', 'end', 'start/end'):
        vdf = vehicles[vehicles['vehicle_id']==veh_id]['address']
        if vdf.shape[0]==0:
            return f"Start/End::{veh_id}"
        else:
            return vdf.values[0]

    job_id = id_mapper.get(job_id)
    if job_id:
        if _type=="pickup":
            return jobs[jobs.job_id==job_id].pickup_address.values[0]
        elif _type=="delivery":
            return jobs[jobs.job_id==job_id].delivery_address.values[0]
        else:
            return f"No Address Provided"
    raise Exception(f"Job ID {job_id} not found in id_mapper")

def geojson_assigned(steps_data:Dict[str, Any], id_mapper:Dict[str, Any], jobs:pd.DataFrame, vehicles:pd.DataFrame)->Dict[str, Any]:
    """
    Create GeoJSON from data
    
    Parameters
    ----------
    steps_data : Dict[str, Any]
        Data to create GeoJSON from
        
    Returns
    -------
    Dict[str, Any]
        GeoJSON
    """
    points = []
    linestring = dict()
    for i, step in enumerate(steps_data["steps"]):
        _type = step["type"]
        if _type in ('start', 'end'):
            _type = "Start/End"
        address = get_job_address(steps_data['vehicle_id'], step.get("id"), _type, jobs, vehicles, id_mapper)
        
        points.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": step["location"]
            },
            "properties": {
                "step": i,
                "type": _type,
                "address": address,
                "arrival": datetime.fromtimestamp(step["arrival"]).strftime("%Y-%m-%d %H:%M:%S"),
                "duration": int(np.ceil(step["duration"]/60)),
                "distance": int(np.ceil(step["distance"]*0.000621371)),
                "waiting_time": int(np.ceil(step["waiting_time"]/60)),
                "service": int(np.ceil(step["service"]/60)),
                "load": step["load"][0],
            },
            "route": None,
        })
    coords = [step["location"][::-1] for step in steps_data["steps"]]
    linestring = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords
        },
        "properties": {
            "vehicle_id": steps_data["vehicle_id"],
            "total_distance": int(np.ceil(steps_data["distance"]*0.000621371)),
            "total_duration": int(np.ceil(steps_data["duration"]/60)),
            "total_waiting_time": int(np.ceil(steps_data["waiting_time"]/60)),
        },
        "route": build_osrm_path(coords)
    }

    geojson = {
        "type": "FeatureCollection",
        "features": points + [linestring],
        "vehicle_id": steps_data["vehicle_id"]
    }

    return geojson

def format_step_popup(step, properties:Dict[str, Any])->str:
    html = f"""
    <p><b>Step:</b> {step}</p>
    <p><b>Address:</b> {properties['address']}</p>
    <p><b>Type:</b> {properties['type']}</p>
    <p><b>Service:</b> {properties['service']} minutes</p>
    <p><b>Arrival:</b> {properties['arrival']}</p>
    <p><b>Waiting time:</b> {properties['waiting_time']} minutes</p>
    <p><b>Duration:</b> {properties['duration']} minutes</p>
    <p><b>Distance:</b> {properties['distance']} miles</p>
    """
    return html

def format_route_popup(properties:Dict[str, Any])->str:
    html = f"""
    <p><b>Vehicle:</b> {properties['vehicle_id']}</p>
    <p><b>Total distance:</b> {properties['total_distance']} miles</p>
    <p><b>Total duration:</b> {properties['total_duration']} minutes</p>
    <p><b>Total waiting time:</b> {properties['total_waiting_time']} minutes</p>
    """
    return html

def format_unassigned_popup(properties:Dict[str, Any])->str:
    if properties['type'].lower()=='pickup':
        html = f"""
        <p><b>Job:</b> {properties['job_id']}</p>
        <p><b>Type:</b> {properties['type']}</p>
        <p><b>Address:</b> {properties['address']}</p>
        <p><b>Requested Pickup:</b> {properties['arrival']}</p>
        <p><b>Load:</b> {properties['load']}</p>
        """
    elif properties['type'].lower()=='delivery':
        html = f"""
        <p><b>Job:</b> {properties['job_id']}</p>
        <p><b>Type:</b> {properties['type']}</p>
        <p><b>Address:</b> {properties['address']}</p>
        <p><b>Requested Delivery:</b> {properties['arrival']}</p>
        <p><b>Load:</b> {properties['load']}</p>
        """
    else:
        raise Exception(f"Invalid type {properties['type']}. Valid types are 'pickup' and 'delivery'")
    return html

def plot_vehicle_depots(m:leafmap.Map)->leafmap.Map:
    pass

def plot_vehicle_routes(m:leafmap.Map)->leafmap.Map:
    pass

def plot_unassigned_jobs(m:leafmap.Map)->leafmap.Map:
    pass


def generate_leafmap(routes:List[Dict[str, Any]], id_mapper:Dict[str, Any], jobs:pd.DataFrame, vehicles:pd.DataFrame, unassigned:List[Dict[str, Any]]=[], recipe:str='cpdptw', zoom=8, height="500px", width="500px"):
    assert recipe in ['cpdptw', 'cvrp'], f"Invalid recipe {recipe}. Valid recipes are 'cpdptw' and 'cvrp'"
    colors = cc.palette['glasbey_bw']
    m = leafmap.Map(zoom_start=zoom, height=height, width=width, tiles="OpenStreetMap")
    coordinates = []
    assigned_geojsons = list(map(lambda x: geojson_assigned(x, id_mapper, jobs, vehicles), routes))
    unassigned_geojson = geojson_unassigned(unassigned)
    feature_groups = []
    layer_control = folium.LayerControl(collapsed=False)

    fg = folium.FeatureGroup(name=f"Unassigned Jobs")
    for point in unassigned_geojson['features']:
        coordinates.append(point['geometry']['coordinates'][::-1])
        popup = folium.Popup(format_unassigned_popup(point['properties']), max_width=300)
        if point['properties']['type'].lower()=='delivery':
            folium.RegularPolygonMarker(location=point['geometry']['coordinates'][::-1], popup=popup, color=colors[0], fill=True, fill_color=colors[0], fill_opacity=1, number_of_sides=3, radius=5).add_to(fg)
        elif point['properties']['type'].lower()=='pickup':
            folium.RegularPolygonMarker(location=point['geometry']['coordinates'][::-1], popup=popup, color=colors[1], fill=True, fill_color=colors[1], fill_opacity=1, number_of_sides=5, radius=5).add_to(fg)
        else:
            raise Exception(f"Invalid type {point['properties']['type']}. Valid types are 'pickup' and 'delivery'")
    fg.add_to(m)
    feature_groups.append(fg)
    if len(routes)==0:
        layer_control.add_to(m)
        center = compute_center_coordinates(coordinates)
        m.set_center(center[1], center[0], zoom)
        return m.to_gradio()

    for i, geojson in enumerate(assigned_geojsons):
        fg = folium.FeatureGroup(name=f"Vehicle {geojson['vehicle_id']}")
        _color = colors[(i+2)%len(colors)]
        nb_steps = len(geojson['features'])-1
        step_counter = 0
        for feature in geojson['features']:
            if feature['geometry']['type'] == 'LineString':
                popup = folium.Popup(format_route_popup(feature['properties']), max_width=300)
                if 'route' in feature:
                    folium.PolyLine(locations=polyline.decode(feature['route']), color=_color, weight=2, popup=popup).add_to(fg)
                else:
                    folium.PolyLine(locations=feature['geometry']['coordinates'], color=_color, weight=2).add_to(fg)
            elif feature['geometry']['type'] == 'Point':
                if step_counter==nb_steps:
                    step_counter = f"0,{step_counter}"
                coordinates.append(feature['geometry']['coordinates'][::-1])
                properties = feature['properties']
                popup = folium.Popup(format_step_popup(step_counter, properties), max_width=300)
                step_counter += 1
                if properties['type'].lower() in ('start', 'end', 'start/end'):
                    icon = folium.Icon(icon='home', color='lightgray')
                    folium.Marker(location=feature['geometry']['coordinates'][::-1], popup=popup, icon=icon).add_to(fg)
                else:

                    folium.CircleMarker(location=feature['geometry']['coordinates'][::-1], popup=popup, color=_color, fill=True, fill_color=_color, fill_opacity=1, radius=5).add_to(fg)
            else:
                raise Exception(f"Invalid geometry type {feature['geometry']['type']}. Supported: 'Point' or 'LineString'")
        fg.add_to(m)
        feature_groups.append(fg)
    layer_control.add_to(m)
    center = compute_center_coordinates(coordinates)
    m.set_center(center[1], center[0], zoom)
    return m.to_gradio()
    

def generate_generic_leafmap(center:Tuple[float, float]=[44.58, -103.46], zoom:int=4, height:str="500px", width:str="500px"):
    """
    Generate generic leafmap with center at given center coordinates and zoom level

    """
    m = leafmap.Map(center=center, zoom_start=zoom, height=height, width=width, tiles="OpenStreetMap")
    return m.to_gradio()

