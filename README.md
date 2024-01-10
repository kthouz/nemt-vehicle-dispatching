# nemt-vehicle-dispatching

This project aims at optimizing the matching between ride requests and cars. 

## Problem statement
Consider a city with limited boundaries. We have 
- N number of vehicles located at different locations of the city. Each vehicle can be described by their vehicle ID, size, current location (longitude, latitude) and availability times.
- M number of patients requesting pickups. Each patient can be described by their vehicle ID, number of passengers, pickup address, destination (latitude, longitude) and procedure time.
- City bounding boxes, static and real-time traffic information across the city

Our ask is to match vehicles to as many patients as possible. Some constraints are to be consider
- Load size. Car fitting the right load size are to be considered and priority being given to the smaller size and less expensive vehicle
- Traffic information. Even though the distance between a vehicle and a patient might be short, priority should be given to the vehicle facing less traffic to reach the patient

## Running [OpenRouteService](https://giscience.github.io/openrouteservice/installation/Installation-and-Usage) locally

## Resources
- [Routing Map](https://graphhopper.com/maps/)
- [Routing APIs](https://docs.graphhopper.com/)
- [Graphhoper Pricing Info](https://www.graphhopper.com/pricing/)
- [OpenTraffic real time traffic data](https://github.com/opentraffic)
- [OpenRouteService](https://giscience.github.io/openrouteservice/)