import os
import time
from .server import LockboxServer

def main():
    print("-------- lockbox started --------")
    if os.environ.get("LOCKBOX_DEBUG") != "1":
        print("Sleeping for 20s to wait for mongo initialization...")
        time.sleep(20)
    print("Initializing lockbox server")
    server = LockboxServer()
    print("Starting lockbox server")
    server.run()
