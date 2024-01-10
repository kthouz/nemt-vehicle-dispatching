import os
from dotenv import load_dotenv
load_dotenv()

OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY')

ALLOW_POOLING = False

