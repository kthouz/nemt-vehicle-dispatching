try:
    from src import config
    from src import utils
    from src import schema
except ModuleNotFoundError:
    import config
    import utils
    import schema

logger = utils.init_logger(__name__, level=config.LOG_LEVEL)

if __name__ == "__main__":
    logger.info("Initializing optimizer")