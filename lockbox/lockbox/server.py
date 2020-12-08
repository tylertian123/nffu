import functools
from aiohttp import web
from umongo import ValidationError
from .db import LockboxDB


def _extract_token(handler):
    """
    Use this decorator on web handlers to require token auth and extract the token.
    """
    @functools.wraps(handler)
    async def _handler(self, request: web.Request):
        if "authorization" not in request.headers:
            return web.json_response({"error": "Missing token"}, status=401)
        auth_parts = request.headers["authorization"].split(" ")
        if len(auth_parts) != 2 or auth_parts[0].lower() != "bearer":
            return web.json_response({"error": "Bearer auth not used"}, status=401)
        token = auth_parts[1]
        return await handler(self, request, token)
    return _handler


class LockboxServer:
    """
    Main server class.
    """

    def __init__(self, **kwargs):
        self.app = web.Application(**kwargs)
        self.app.router.add_routes([
            web.post("/user", self._post_user),
            web.patch("/user", self._patch_user),
            web.get("/user", self._get_user),
            web.delete("/user", self._delete_user),
            web.delete(r"/user/error/{id:[a-f0-9]+}", self._delete_user_error)
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
            "token": "...", // A token consisting of 64 hex digits for this user
        }
        """
        print("Got request: POST to /user")
        try:
            token = await self.db.create_user()
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)
        print("Created new user")
        return web.json_response({"token": token}, status=200)
    
    @_extract_token
    async def _patch_user(self, request: web.Request, token: str):
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
            "error": "...", // Reason for error, e.g. "Missing body", "Bad token", etc.
        }
        """
        print("Got request: PATCH to /user")
        if not request.can_read_body:
            return web.json_response({"error": "Missing body"}, status=400)
        if not request.content_type in ("application/json", "text/json"):
            return web.json_response({"error": "Bad content type"}, status=400)
        data = await request.json()
        try:
            await self.db.modify_user(token, **data)
        except ValueError:
            return web.json_response({"error": "Bad token"}, status=401)
        except ValidationError as e:
            return web.json_response({"error": f"ValidationError: {e}"}, status=400)
        print("User modified")
        return web.Response(status=204)
    
    @_extract_token
    async def _get_user(self, request: web.Request, token): # pylint: disable=unused-argument
        """
        Handle a GET to /user.

        The request should use bearer auth with a token given on user creation.

        Returns the following JSON on success:
        {
            "login": "...", // Optional, TDSB login (student number) (missing if unconfigured)
            "active": true, // Whether form-filling is active for this user
            "errors": [], // An array of LockboxFailures listing the errors
            "credentials_set": true, // Whether credentials are set (both student number and password)
        }

        Returns the following JSON on failure:
        {
            "error": "...", // Reason for error, e.g. "Bad token", etc.
        }
        """
        print("Got request: GET to /user")
        try:
            data = await self.db.get_user(token)
        except ValueError:
            return web.json_response({"error": "Bad token"}, status=401)
        # Modify data
        data["credentials_set"] = "password" in data and "login" in data
        data.pop("id", None)
        data.pop("password", None)
        data.pop("token", None)
        print("User data returned")
        return web.json_response(data, status=200)
    
    @_extract_token
    async def _delete_user(self, request: web.Request, token: str): # pylint: disable=unused-argument
        """
        Handle a DELETE to /user.

        The request should use bearer auth with a token given on user creation.

        204 on success.

        Returns the following JSON on failure:
        {
            "error": "...", // Reason for error, e.g. "Bad token", etc.
        }
        """
        print("Got request: DELETE to /user")
        try:
            await self.db.delete_user(token)
        except ValueError:
            return web.json_response({"error": "Bad token"}, status=401)
        print("User deleted")
        return web.Response(status=204)
    
    @_extract_token
    async def _delete_user_error(self, request: web.Request, token: str):
        """
        Handle a DELETE to /user/error/<id>.

        The request should use bearer auth with a token given on user creation.

        204 on success.

        Returns the following JSON on failure:
        {
            "error": "...", // Reason for error, e.g. "Bad token", etc.
        }
        """
        print("Got request: DELETE to", request.rel_url)
        try:
            await self.db.delete_user_error(token, request.match_info["id"])
        except ValueError as e:
            if str(e) == "Bad token":
                return web.json_response({"error": "Bad token"}, status=401)
            else:
                return web.json_response({"error": str(e)}, status=400)
        print("Error deleted")
        return web.Response(status=204)