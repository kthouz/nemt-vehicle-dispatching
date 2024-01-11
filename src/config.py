import os
from dotenv import load_dotenv
load_dotenv()

LOG_LEVEL = os.getenv('LOG_LEVEL','INFO')
OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY')

ALLOW_POOLING = False
DEFAULT_VEHICLE_SIZE = 4
DAY_START_HOUR = 8
DAY_END_HOUR = 17

