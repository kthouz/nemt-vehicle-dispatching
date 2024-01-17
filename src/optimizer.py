try:
    from src import config
    from src import utils
except ModuleNotFoundError:
    import config
    import utils

import requests
import json
logger = utils.init_logger(__name__, level=config.LOG_LEVEL)

vroom_url = config.VROOM_BASE_URL
# vroom_url = "http://solver.vroom-project.org"

def optimize(vehicles, jobs):
    data = {'vehicles': vehicles, 'jobs': jobs, 'options': {'g': True, 'geometry': True, 'format': 'json'}}

    response = requests.post(vroom_url, json=data)
    if response.status_code == 200:
        solution = response.json()
        print(json.dumps(solution, indent=4))
    else:
        print("Error:", response.text)


if __name__ == "__main__":
    logger.info("Initializing optimizer")
    vehicles = [
      {
        "id": 1,
        "start": [-84.51235422426745, 38.01869995],
        "end": [-84.51235422426745, 38.01869995],
        "capacity": [4],
        "skills": list(range(1, 15)), 
        "time_window": [1600416000, 1600430400]
      }
    ]
    jobs = [
      {
        "id": 1,
        "service": 300,
        "delivery": [1],
        "location": [-84.581628, 38.204014],
        "skills": [1],
        "time_windows": [
          [1600419600, 1600423200]
        ]
      },
      {
        "id": 2,
        "service": 300,
        "pickup": [1],
        "location": [-84.5093899, 38.0310772],
        "skills": [1]
      }
    ]
    optimize(vehicles, jobs)