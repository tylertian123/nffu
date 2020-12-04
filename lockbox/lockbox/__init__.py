from .server import LockboxServer

def main():
    server = LockboxServer()
    server.run()
