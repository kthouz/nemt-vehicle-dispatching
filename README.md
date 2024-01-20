# nemt-vehicle-dispatching

This project aims at optimizing the matching between ride requests and cars. 

## Problem statement
Consider a city with limited boundaries. We have 
- N number of vehicles located at different locations of the city. Each vehicle can be described by their vehicle ID, size, current location (longitude, latitude) and availability times.
- M number of riders requesting pickups. Each rider can be described by their vehicle ID, number of passengers, pickup address, destination (latitude, longitude) and procedure time.
- City bounding boxes, static and real-time traffic information across the city

Our ask is to match vehicles to as many riders as possible. Some constraints are to be consider
- Load size. Car fitting the right load size are to be considered and priority being given to the smaller size and less expensive vehicle
- Traffic information. Even though the distance between a vehicle and a rider might be short, priority should be given to the vehicle facing less traffic to reach the rider

## Solution
The problem is approached as a Capacitated Pickup-Delivery Problem with Time Windows. [OSRM](https://project-osrm.org/) and [VROOM](http://vroom-project.org/) were used in the backend respectively for distance/duration calculations and routing optimization.

## Caveat
[ ] All rides are considered carpoolable. In the future, we need to respect ride criteria being car-poolable or not
[ ] All vehicles are considered not having any break. Any day they available, they will be ready to work 8AM to 5PM

## Resources
- Generating pdf files: [bbbike.org](https://extract.bbbike.org/) and [geofabrik](https://download.geofabrik.de/north-america/us.html)
- [osrm setup with docker](https://github.com/Project-OSRM/osrm-backend?tab=readme-ov-file#using-docker)
- [vroom-docker](https://github.com/VROOM-Project/vroom-docker)

## How to setup

1. First setup OSRM and VROOM
   1. Ensure you are in the root directory
   2. Run `bash install.sh` and follow instructions
2. Run the app with `gradio app.py`