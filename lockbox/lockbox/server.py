from aiohttp import web
from .db import LockboxDB

class LockboxServer:

    def __init__(self, **kwargs):
        self.app = web.Application(**kwargs)
        self.app.router.add_routes([
        ])

        self.db = LockboxDB("db", 27017)
    
    def run(self):
        web.run_app(self.app, host="0.0.0.0", port=80)
