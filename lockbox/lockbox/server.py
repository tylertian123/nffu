"""
Main server implementation.
"""

import functools
import json
import logging
from aiohttp import web
from .db import LockboxDB, LockboxDBError


def _extract_token(handler):
    """
    Use this decorator on web handlers to require token auth and extract the token.
    """
    @functools.wraps(handler)
    async def _handler(self, request: web.Request, *args, **kwargs):
        if "authorization" not in request.headers:
            return web.json_response({"error": "Missing token"}, status=401)
        auth_parts = request.headers["authorization"].split(" ")
        if len(auth_parts) != 2 or auth_parts[0].lower() != "bearer":
            return web.json_response({"error": "Bearer auth not used"}, status=401)
        token = auth_parts[1]
        return await handler(self, request, token=token, *args, **kwargs)
    return _handler


def _handle_db_errors(handler):
    """
    Use this decorator to handle LockboxDBErrors and return an http response.
    """
    @functools.wraps(handler)
    async def _handler(*args, **kwargs):
        try:
            return await handler(*args, **kwargs)
        except LockboxDBError as e:
            code = {
                LockboxDBError.BAD_TOKEN: 401,              # Unauthorized
                LockboxDBError.INVALID_FIELD: 400,          # Bad Request
                LockboxDBError.INTERNAL_ERROR: 500,         # Internal Server Error
                LockboxDBError.STATE_CONFLICT: 409,         # Conflict
                LockboxDBError.RATE_LIMIT_EXCEEDED: 429,    # Too Many Requests
                LockboxDBError.OTHER: 400,                  # Bad Request
            }[e.code]
            print(f"Error {code}: {str(e)}")
            return web.json_response({"error": str(e)}, status=code)
    return _handler


def _json_payload(handler):
    """
    Use this decorator to verify that the payload is JSON and download it.
    """
    @functools.wraps(handler)
    async def _handler(self, request: web.Request, *args, **kwargs):
        if not request.can_read_body:
            return web.json_response({"error": "Missing body"}, status=400)
        if not request.content_type in ("application/json", "text/json"):
            return web.json_response({"error": "Bad content type"}, status=400)
        try:
            data = await request.json()
        except json.JSONDecodeError as e:
            return web.json_response({"error": f"Invalid json: {e}"}, status=400)
        return await handler(self, request, payload=data, *args, **kwargs)
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
            web.delete(r"/user/error/{id:[a-f0-9]+}", self._delete_user_error),
            web.get("/user/courses", self._get_user_courses),
            web.post("/user/courses/update", self._post_user_courses_update),
            web.post("/form_geometry", self._post_form_geometry),
            web.get("/debug/tasks", self._get_debug_tasks),
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

        # Setup access logging
        stdio_handler = logging.StreamHandler()
        stdio_handler.setLevel(logging.INFO)
        logger = logging.getLogger('aiohttp.access')
        logger.addHandler(stdio_handler)
        logger.setLevel(logging.DEBUG)

        web.run_app(self.make_app(), host="0.0.0.0", port=80)
    
    @_handle_db_errors
    async def _post_user(self, request: web.Request): # pylint: disable=unused-argument
        """
        Handle a POST to /user.

        The request should have no payload. This will create a new user and give back a token.

        Returns the following JSON on success:
        {
            "token": "...", // A token consisting of 64 hex digits for this user
        }
        """
        token = await self.db.create_user()
        return web.json_response({"token": token}, status=200)
    
    @_handle_db_errors
    @_json_payload
    @_extract_token
    async def _patch_user(self, request: web.Request, token: str, payload: dict): # pylint: disable=unused-argument
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

        Possible error response codes:
        - 400: Invalid format, token, or field value (including TDSB credentials)
        """
        await self.db.modify_user(token, **payload)
        return web.Response(status=204)
    
    @_handle_db_errors
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

        Possible error response codes:
        - 401: Invalid token
        """
        data = await self.db.get_user(token)
        # Modify data
        data["credentials_set"] = "password" in data and "login" in data
        data.pop("id", None)
        data.pop("password", None)
        data.pop("token", None)
        return web.json_response(data, status=200)
    
    @_handle_db_errors
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

        Possible error response codes:
        - 401: Invalid token
        """
        await self.db.delete_user(token)
        print("User deleted")
        return web.Response(status=204)
    
    @_handle_db_errors
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

        Possible error response codes:
        - 400: Invalid error id
        - 401: Invalid token
        """
        await self.db.delete_user_error(token, request.match_info["id"])
        print("Error deleted")
        return web.Response(status=204)
    
    @_handle_db_errors
    @_extract_token
    async def _get_user_courses(self, request: web.Request, token: str): # pylint: disable=unused-argument
        """
        Handle a GET to /user/courses.

        The request should use bearer auth with a token given on user creation.

        Returns the following JSON on success:
        {
            "courses": [], // A list of course IDs as strings
                           // Corresponds to documents in the course collection of the shared db
                           // null if credentials have not been configured, or pending is true
            "pending": false, // Whether the courses are pending (still being processed)
                              // Only true when credentials are present, but courses are still being processed
        }

        Returns the following JSON on failure:
        {
            "error": "...", // Reason for error, e.g. "Bad token", etc.
        }

        Possible error response codes:
        - 401: Invalid token
        """
        data = await self.db.get_user(token)
        # No credentials
        if not ("password" in data and "login" in data):
            print("User credentials not present")
            return web.json_response({"courses": None, "pending": False})
        # Credentials present, but courses are not
        if data.get("courses") is None:
            print("User courses pending")
            return web.json_response({"courses": None, "pending": True})
        # Both present
        return web.json_response({"courses": data["courses"], "pending": False})
    
    @_handle_db_errors
    @_extract_token
    async def _post_user_courses_update(self, request: web.Request, token: str): # pylint: disable=unused-argument
        """
        Handle a POST to /user/courses/update.

        The request should use bearer auth with a token given on user creation.

        204 on success.

        Returns the following JSON on failure:
        {
            "error": "...", // Reason for error, e.g. "Bad token", etc.
        }

        Possible error response codes:
        - 401: Invalid token
        - 409: Cannot update courses due to missing credentials
        - 500: Failed to decrypt user password
        """
        await self.db.update_user_courses(token)
        return web.Response(status=204)
    
    @_handle_db_errors
    @_json_payload
    @_extract_token
    async def _post_form_geometry(self, request: web.Request, token: str, payload: dict): # pylint: disable=unused-argument
        """
        Handle a POST to /form_geometry.

        The request should use bearer auth with a token given on user creation.

        JSON payload should have the following format:
        {
            "url": "...",             // The URL of the form to process
            "override_limit": false,  // Optional, whether to ignore the one request per user at a time limit, default false
            "grab_screenshot": false, // Optional, whether or not to take a screenshot and put it in the database
        }

        Returns the following JSON on success:
        {
            "geometry": [   // A list of form geometry entries
                            // null if pending is true
                {
                    "index": 0,     // The index of this entry in the form
                    "title": "...", // The title of this entry
                    "kind": "text"  // The type of this entry
                },
            ],
            "auth_required": false, // True if the form prompted for authentication 
                                    // null if pending is true
            "screenshot_id": "...", // File ID of taken screenshot in GridFS.
            "pending": false, // Whether the geometry is pending (still being processed)
            "error": "...", // Optional, the error message (if one exists)
        }

        Returns the following JSON on failure:
        {
            "error": "...", // Reason for error, e.g. "Bad token", etc.
        }

        Possible error response codes:
        - 400: Invalid field, invalid form
        - 401: Invalid token
        - 403: Form auth error
        - 429: Concurrent request limit exceeded
        - 409: Cannot sign into form due to missing credentials
        """
        if "url" not in payload:
            return web.json_response({"error": "Missing field: 'url'"}, status=400)
        result = await self.db.get_form_geometry(token, payload["url"], payload.get("override_limit", False), payload.get("grab_screenshot", False))
        result["pending"] = result["geometry"] is None
        if "status" in result:
            status = result.pop("status")
            print(f"Form geometry error {status}: {result['error']}")
            return web.json_response(result, status=status)
        else:
            return web.json_response(result, status=200)
    
    async def _get_debug_tasks(self, request: web.Request):
        """
        Handle a GET to /debug/tasks. For debug purposes.

        Returns the following JSON on success:
        {
            "tasks": [ // A list of tasks
                {
                    "kind": "check-day", // The type of the task, see TaskType enum in documents.py
                    "owner": null, // Reference to the lockbox user that owns this task
                    "next_run_at": "1970-01-01T00:00:00.00", // ISO datetime string of the next time this task should run
                    "is_running": false, // Whether the task is already running
                    "retry_count": 0, // How many times the task has failed
                }
            ]
        }
        """
        tasks = await self.db.get_tasks()
        for task in tasks:
            task.pop("id", None)
        return web.json_response({"tasks": tasks}, status=200)
