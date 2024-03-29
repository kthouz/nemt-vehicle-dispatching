import os
from dotenv import load_dotenv
load_dotenv(".env")

OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY')
OPENROUTESERVICE_BASE_URL = os.getenv('OPENROUTESERVICE_API_URL')

VROOM_BASE_URL = os.getenv('VROOM_SERVER_URL','http://solver.vroom-project.org')
OSRM_BASE_URL = os.getenv('OSRM_SERVER_URL','https://router.project-osrm.org')

ALLOW_POOLING = False
DEFAULT_VEHICLE_SIZE = 4
DAY_START_HOUR = 8 # HOUR
DAY_END_HOUR = 17 # HOUR
MAX_WAIT_TIME = 60*5 #seconds
DEFAULT_SERVICE_TIME = 60*5 #seconds

ADDRESS_STORE = "data/addresses.json"
PREPROCESSED_STORE = "data/preprocessed"
SOLUTION_STORE = "data/solution"
LOGS_STORE = "data/logs"
LOG_LEVEL = os.getenv('LOG_LEVEL','INFO')

VEHICLE_KEYS = ['id', 'start', 'end', 'capacity', 'skills', 'time_window']
JOB_KEYS = ['id', 'service', 'delivery', 'location', 'skills', 'time_windows']

START_STOP_ICON_URL = "images/start_stop-noun-12703.svg"

VEHICLES_DF_FIELDS = ["available", "vehicle_id", "address", "capacity", "skills", "working_hours", "breaks"]
JOBS_DF_FIELDS = ["job_id", "pickup_address", "delivery_address", "nb_passengers", "earliest_pickup", "latest_delivery", "service_time"]


