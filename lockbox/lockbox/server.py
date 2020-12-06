from aiohttp import web
from umongo import ValidationError
from .db import LockboxDB

class LockboxServer:
    """
    Main server class.
    """

    def __init__(self, **kwargs):
        self.app = web.Application(**kwargs)
        self.app.router.add_routes([
            web.post("/user", self._post_user),
            web.patch("/user", self._patch_user)
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
    
    async def _post_user(self, request: web.Request): # pylint: disable=unused-argument
        """
        Handle a POST to /user.

        The request should have no payload. This will create a new user and give back a token.

        Returns the following JSON on success:
        {
            "status": "ok",
            "token": "...", // A token consisting of 64 hex digits for this user
        }
        """
        print("Got request: POST to /user")
        try:
            token = await self.db.create_user()
        except ValueError as e:
            return web.json_response({"status": "error", "reason": str(e)}, status=400)
        print("Created new user")
        return web.json_response({"status": "ok", "token": token}, status=200)
    
    async def _patch_user(self, request: web.Request):
        """
        Handle a PATCH to /user.

        The request should use bearer auth with a token given on user creation.

        JSON payload should have the following format:
        {
            "login": "...", // Optional, TDSB login (student number)
            "password": "...", // Optional, TDSB password
            "active": true, // Optional, whether form-filling is active for this user (default true)
        }
        
        204 on success.

        Returns the following JSON on failure:
        {
            "status": "error",
            "reason": "...", // Reason for error, e.g. "Missing body", "Bad token", etc.
        }
        """
        print("Got request: POST to /user")
        if "authorization" not in request.headers:
            return web.json_response({"status": "error", "reason": "Missing token"}, status=401)
        auth_parts = request.headers["authorization"].split(" ")
        if len(auth_parts) != 2 or auth_parts[0].lower() != "bearer":
            return web.json_response({"status": "error", "reason": "Bearer auth not used"}, status=401)
        token = auth_parts[1]
        if not request.can_read_body:
            return web.json_response({"status": "error", "reason": "Missing body"}, status=400)
        if not request.content_type in ("application/json", "text/json"):
            return web.json_response({"status": "error", "reason": "Bad content type"}, status=400)
        data = await request.json()
        try:
            await self.db.modify_user(token, **data)
        except ValueError:
            return web.json_response({"status": "error", "reason": "Bad token"}, status=401)
        except ValidationError as e:
            return web.json_response({"status": "error", "reason": f"ValidationError: {e}"}, status=400)
        return web.Response(status=204)
