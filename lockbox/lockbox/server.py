from aiohttp import web
from .db import LockboxDB

class LockboxServer:
    """
    Main server class.
    """

    def __init__(self, **kwargs):
        self.app = web.Application(**kwargs)
        self.app.router.add_routes([
            web.post("/user", self._post_user)
        ])

        self.db = LockboxDB("db", 27017)
    
    async def make_app(self):
        """
        Perform async initialization for the app.
        """
        await self.db.init()
        return self.app
    
    def run(self):
        """
        Run the sever.

        Does not return until the server is killed.
        """
        web.run_app(self.make_app(), host="0.0.0.0", port=80)
    
    async def _post_user(self, request: web.Request):
        """
        Handle a POST to /user.

        JSON should have the following format:
        {
            "login": "...", // TDSB login (student number)
            "password": "...", // TDSB password
            "active": true, // Optional, whether form-filling is active for this user (default true)
        }
        
        Returns the following JSON on success:
        {
            "status": "ok",
            "token": "...", // 256-bit (64 hex chars) access token for this user
        }

        Returns the following JSON on failure:
        {
            "status": "error",
            "reason": "...", // Reason for error, e.g. "missing body", "missing field: field", etc.
        }
        """
        print("Got request: POST to /user")
        if not request.can_read_body:
            return web.json_response({"status": "error", "reason": "missing body"}, status=400)
        if not request.content_type in ("application/json", "text/json"):
            return web.json_response({"status": "error", "reason": "bad content type"}, status=400)
        data = await request.json()
        if "login" not in data:
            return web.json_response({"status": "error", "reason": "missing field: login"}, status=400)
        if "password" not in data:
            return web.json_response({"status": "error", "reason": "missing field: password"}, status=400)
        try:
            token = await self.db.create_user(data["login"], data["password"], data.get("active", True))
        except ValueError as e:
            return web.json_response({"status": "error", "reason": str(e)}, status=400)
        print("Created new user")
        return web.json_response({"status": "ok", "token": token}, status=200)
        
