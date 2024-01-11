try:
    from src import config
    from src import utils
    from src import geo_utils as gutils
except ModuleNotFoundError:
    import config
    import utils
    import geo_utils as gutils

from pydantic import BaseModel, Field, validator, root_validator
from typing import Tuple, List, Optional, Dict, Any, Union
from enum import Enum
import datetime
import logging
import uuid
import random

logger = utils.init_logger(__name__, level=config.LOG_LEVEL)

class RideStatus(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    ENROUTE = "en-route"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    INFEASIBLE = "infeasible"
    DELAYED = "delayed"

class VehicleStatus(Enum):
    BUSY = "busy"
    AVAILABLE = "available"
    OFFLINE = "offline"

class Ride(BaseModel):
    ride_id: Optional[str] = Field(default_factory=utils.generate_id, alias="rideId")
    pickup_address: str = Field(..., alias="pickupAddress")
    pickup_location: Optional[Union[Tuple[float, float], None]] = Field(None, alias="pickupLocation")
    pickup_time: datetime.datetime = Field(default_factory=datetime.datetime.now, alias="pickupTime")
    dropoff_address: str = Field(..., alias="dropoffAddress")
    dropoff_location: Optional[Union[Tuple[float, float], None]] = Field(None, alias="dropoffLocation")
    dropoff_time: Optional[Union[datetime.datetime, None]] = Field(None, alias="dropoffTime")
    load: int = Field(1, gt=0, alias="load")
    status: Optional[RideStatus] = RideStatus.PENDING

    @root_validator(pre=False, skip_on_failure=True)
    def set_default_values(cls, values):
        """
        auto set location geo coordinates if None was set and also dropoff time
        """
        if values["pickup_location"] and values["dropoff_location"] and values["dropoff_time"]:
            return values
        if values["pickup_location"] is None:
            values["pickup_location"] = gutils.address_to_coordinates(values["pickup_address"])
            logger.info(f"Ride {values['ride_id']}.pickup_location defaulted to {values['pickup_location']}")
        if values["dropoff_location"] is None:
            values["dropoff_location"] = gutils.address_to_coordinates(values["dropoff_address"])
            logger.info(f"Ride {values['ride_id']}.dropoff_location defaulted to {values['dropoff_location']}")
        duration_seconds = int(gutils.get_trip_duration(values["pickup_location"], values["dropoff_location"]))
        values["dropoff_time"] = values["pickup_time"] + datetime.timedelta(seconds=duration_seconds)
        logger.info(f"Ride {values['ride_id']}.dropoff_time defaulted to {values['dropoff_time']}")
        return values
    
    def update_dropoff_time(self, time:Union[datetime.datetime, None]=None):
        if time is not None:
            self.dropoff_time = time
            return
        duration_seconds = int(utils.get_trip_duration(self.pickup_location, self.dropoff_location))
        self.dropoff_time = self.pickup_time + datetime.timedelta(seconds=duration_seconds)
        return
    
    def update_status(self, status:Union[RideStatus, None]=None):
        """
        update the status of the ride taking into account the current status and time
        """
        if status is not None:
            self.status = status
        if self.status == RideStatus.SCHEDULED and datetime.datetime.now() >= self.pickup_time:
            self.status = RideStatus.DELAYED
        if self.status == RideStatus.PENDING and datetime.datetime.now() >= self.pickup_time:
            self.status = RideStatus.SKIPPED
        logger.debug(f"Ride {self.ride_id} is {self.status.value}")
    
    def get_status(self):
        return self.status.value


class Vehicle(BaseModel):
    vehicle_id: Optional[str] = Field(default_factory=utils.generate_id, alias="vehicleId")
    operating_date: datetime.date = Field(default_factory=datetime.date.today, alias="operatingDate")
    size: int = Field(config.DEFAULT_VEHICLE_SIZE, gt=0, alias="size")
    next_available_time: Optional[Union[datetime.datetime, None]] = Field(None, alias="nextAvailableTime")
    available_seats: Optional[Union[int, None]] = Field(None, gt=0, alias="availableSeats")
    status: Optional[VehicleStatus] = VehicleStatus.AVAILABLE
    rides: Optional[List[Ride]] = Field(default_factory=list, alias="rides")

    @validator("available_seats")
    def validate_available_seats(cls, v, values):
        if v > values["size"]:
            raise ValueError("availableSeats must be less than or equal to size")
        return v
    
    @root_validator(pre=False, skip_on_failure=True)
    def set_default_values(cls, values):
        """
        auto set available seats if None was set
        """
        if values["available_seats"] is None and len(values["rides"]) == 0:
            values["available_seats"] = values["size"]
            logger.info(f"Vehicle {values['vehicle_id']}.available_seats defaulted to {values['available_seats']}")
        
        if values["next_available_time"] is None and values["status"] == VehicleStatus.AVAILABLE:
            values["next_available_time"] = datetime.datetime.combine(values["operating_date"], datetime.time(config.DAY_START_TIME))
            logger.info(f"Vehicle {values['vehicle_id']}.next_available_time estimated to {values['next_available_time']}")

        return values
    
    def update_status(self, status:Union[VehicleStatus, None]=None):
        if status is not None:
            self.status = status
            return
        
        if self.status == VehicleStatus.OFFLINE:
            logger.warning(f"Vehicle {self.vehicle_id} is already offline")
            return
        
        if self.available_seats == 0:
            self.status = VehicleStatus.BUSY
        elif self.available_seats == self.size:
            self.status = VehicleStatus.AVAILABLE
        else:
            if not config.ALLOW_POOLING:
                self.status = VehicleStatus.BUSY
            else:
                self.status = VehicleStatus.AVAILABLE
        logger.debug(f"Vehicle {self.vehicle_id} is {self.status.value}")
        return
    
    def assign_ride(self, ride:Ride):
        """
        assign a ride to the vehicle and update the status
        """
        self.rides.append(ride)
        self.available_seats -= ride.load
        self.update_status()
        logger.debug(f"Vehicle {self.vehicle_id} assigned ride {ride.ride_id}. Total rides: {len(self.rides)}")
        return

    def update_next_available_time(self, time:Union[datetime.datetime, None]=None):
        if time is not None:
            self.next_available_time = time
            logger.debug(f"Vehicle {self.vehicle_id} next available time set to {self.next_available_time}")
            return
        # compute the next available time based on the list of rides or status
        if self.status == VehicleStatus.OFFLINE:
            self.next_available_time = datetime.datetime.max
            logger.debug(f"Vehicle {self.vehicle_id} next available time set to {self.next_available_time}")
            return
        
        if len(self.rides) == 0 or self.status == VehicleStatus.AVAILABLE:
            self.next_available_time = datetime.datetime.combine(self.operating_date, datetime.time(config.DAY_START_TIME))
            logger.debug(f"Vehicle {self.vehicle_id} next available time set to {self.next_available_time}")
            return
        
        last_ride = self.rides[-1]
        self.next_available_time = last_ride.dropoff_time
        logger.debug(f"Vehicle {self.vehicle_id} next available time set to {self.next_available_time}")
        return

if __name__=='__main__':
    ride = Ride(
        pickupAddress="1097 Gentry Road, Lexington, KY, USA",
        dropoffAddress="Grace Lane, Jessamine County, KY, USA",
        pickupTime=datetime.datetime.now(),
        load=2
    )