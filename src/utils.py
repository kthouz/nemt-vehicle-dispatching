import sys
sys.path.append("..")

try:
    from src import config
except ModuleNotFoundError:
    import config

import json
import os
import uuid
import logging
from typing import Dict, Any, List, Tuple

if not os.path.exists(config.ADDRESS_STORE):
    os.makedirs(os.path.dirname(config.ADDRESS_STORE), exist_ok=True)
    with open(config.ADDRESS_STORE, "w") as f:
        json.dump({}, f)

ADDRESS_CACHE = json.load(open(config.ADDRESS_STORE, "r"))

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

def generate_id()->str:
    return str(uuid.uuid4())

def cache_address(addresses:Dict[str, Tuple[float, float]], store:Dict[str, Any]=dict(), save:bool=False)->dict:
    """
    Cache address to file

    Parameters
    ----------
    addresses : Dict[str, Tuple[float, float]]
        Addresses to cache
    store : Dict[str, Any], optional
        Address store, by default dict()
    save : bool, optional
        Whether to save to file, by default False

    Returns
    -------
    str
        Cached address
    """
    store.update(addresses)
    if save:
        with open(config.ADDRESS_STORE, "w") as f:
            json.dump(store, f)
