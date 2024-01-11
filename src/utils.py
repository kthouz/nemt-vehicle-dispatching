import uuid
import logging

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