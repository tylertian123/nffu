import logging
from .server import LockboxServer

def setup_loggers(level: int):
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(name)s: %(message)s")
    handler.setFormatter(formatter)

    for name in ["scheduler", "task", "server", "db"]:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
    
    # aiohttp access gets separate handler for different format since it already has enough info
    ah_handler = logging.StreamHandler()
    ah_handler.setLevel(level)
    ah_logger = logging.getLogger("aiohttp.access")
    ah_logger.setLevel(level)
    ah_logger.addHandler(ah_handler)

def main():
    print("-------- lockbox started --------")
    setup_loggers(logging.DEBUG)
    print("Initializing lockbox server")
    server = LockboxServer()
    print("Starting lockbox server")
    server.run()
