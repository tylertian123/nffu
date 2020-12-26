"""
Handles talking to lockbox
"""

from .db import User, Course, FormFieldType
import collections
import typing
import aiohttp
import bson
from quart import Quart, current_app
from marshmallow import Schema, fields as ma_fields
from umongo.marshmallow_bonus import ObjectId as ObjectIdField

class LockboxError(Exception):
    pass

def init_app(app: Quart):
    @app.before_serving
    async def setup_context():
        current_app.lockbox_sess = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())

    @app.after_serving
    async def teardown_context():
        await _lockbox_sess().close()

# stubs for rn
def _lockbox_sess():
    return current_app.lockbox_sess

async def create_new_lockbox_identity(user: User):
    """
    Make a new lockbox identity and associated token and associate it to this user in the database
    """

    # if there's already a lockbox identity in the user, return now
    if user.lockbox_token is not None:
        return

    # ask lockbox for a new user
    async with _lockbox_sess().post("http://lockbox/user") as resp:
        if not resp.ok:
            raise LockboxError("failed to create lockbox identity", resp.status)

        data = await resp.json()
        user.lockbox_token = data["token"]

    # commit the user
    await user.commit()

    # yay

def _headers_for_user(user: User):
    if user.lockbox_token is None:
        raise ValueError("missing lockbox token")

    return {"Authorization": "Bearer " + user.lockbox_token}

async def destroy_lockbox_identity(user: User):
    """
    Delete all information in lockbox for this user

    If this fails the entire delete fails.
    """

    if user.lockbox_token is None:
        return

    async with _lockbox_sess().delete("http://lockbox/user", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise LockboxError("failed to delete: " + resp.reason, resp.status)

    user.lockbox_token = None
    await user.commit()

LockboxUserStatus = collections.namedtuple("LockboxUserStatus", "has_credentials has_errors active grade")

async def get_lockbox_status_for(user: User) -> LockboxUserStatus:
    """
    Get status for the given user in lockbox.

    Return None if the user doesn't have a lockbox identity
    """

    if user.lockbox_token is None:
        return None

    async with _lockbox_sess().get("http://lockbox/user", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise LockboxError("failed to get: " + resp.reason, resp.status)

        data = await resp.json()

        return LockboxUserStatus(  # todo
                data["credentials_set"],
                len(data["errors"]) > 0,
                data["active"],
                data["grade"]
        )

LockboxFillResult = collections.namedtuple("LockboxFillResult", "result time_logged course form_sid confirm_sid")

class LastFillFormResultSchema(Schema):
    result = ma_fields.Str(required=True)
    time_logged = ma_fields.DateTime()
    course = ObjectIdField(missing=None, allow_none=True)
    form_screenshot_id = ObjectIdField(missing=None)
    confirmation_screenshot_id = ObjectIdField(missing=None)

last_fill_form_result_schema = LastFillFormResultSchema()

async def get_form_fill_result(user: User) -> LockboxUserStatus:
    """
    Get status for the given user in lockbox.

    Return None if the user doesn't have a lockbox identity
    """

    if user.lockbox_token is None:
        return None

    async with _lockbox_sess().get("http://lockbox/user", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise LockboxError("failed to get: " + resp.reason, resp.status)

        data = await resp.json()

        if not data["last_fill_form_result"]:
            return None

        data = last_fill_form_result_schema.load(data["last_fill_form_result"])

        return LockboxFillResult(  # todo
            data["result"],
            data["time_logged"],
            data["course"],
            data["form_screenshot_id"],
            data["confirmation_screenshot_id"]
        )

LockboxFailure = collections.namedtuple("LockboxFailure", "id kind message time_logged")

class LockboxFailureSchema(Schema):
    _id = ObjectIdField(required=True)
    time_logged = ma_fields.DateTime(required=True)
    kind = ma_fields.Str(required=True)
    message = ma_fields.Str(missing="")

lockbox_failure_schema = LockboxFailureSchema()

async def get_errors_for(user: User) -> typing.AsyncIterable[LockboxFailure]:
    """
    Retrieve all lockbox errors for a specific user.

    No results if the user doesn't have a lockbox identity
    """

    if user.lockbox_token is None:
        return

    async with _lockbox_sess().get("http://lockbox/user", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise LockboxError("failed to get: " + resp.reason, resp.status)

        data = lockbox_failure_schema.load((await resp.json())["errors"], many=True)

    for failure in data:
        yield LockboxFailure(failure["_id"], failure["kind"], failure["message"], failure["time_logged"])

async def clear_error(for_: User, error_id: str):
    """
    Clear an error from a specific user

    Raises ValueError if the user has no lockbox token or the error id is invalid.
    """

    if for_.lockbox_token is None:
        raise ValueError("No lockbox token")

    async with _lockbox_sess().delete(f"http://lockbox/user/error/{error_id}", headers=_headers_for_user(for_)) as resp:
        if resp.status == 400:
            raise ValueError("Bad error id")
        if not resp.ok:
            raise LockboxError("failed to delete: " + resp.reason, resp.status)

async def update_lockbox_identity(user: User, payload: dict):
    """
    Update the lockbox data for the user

    (payload is passed directly)
    """

    if user.lockbox_token is None:
        raise ValueError("missing token")

    async with _lockbox_sess().patch("http://lockbox/user", headers=_headers_for_user(user), json=payload) as resp:
        try:
            error_data = await resp.json()
        except:
            if resp.ok:
                return
            raise

        if not resp.ok:
            raise LockboxError(error_data["error"], resp.status)

async def query_lockbox_enrolled_courses(user: User):
    """
    Get the current set of courses we've detected for the user.

    Raises an error if the user does not have a lockbox identity, returns None if processing is still occuring and
    a list of Course objects if succesfull
    """

    if user.lockbox_token is None:
        raise ValueError("missing token")

    async with _lockbox_sess().get("http://lockbox/user/courses", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise LockboxError("failed to get courses", resp.status)

        data = await resp.json()

        if data["pending"]:
            return None
        elif data["courses"] is None:
            raise ValueError("missing auth")
        else:
            return [await Course.find_one({"id": bson.ObjectId(x)}) for x in data["courses"]]

async def update_lockbox_enrolled_courses(user: User):
    """
    Force a refresh of the enrolled course list
    """

    if user.lockbox_token is None:
        raise ValueError("missing token")

    async with _lockbox_sess().post("http://lockbox/user/courses/update", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise LockboxError("failed to update courses", resp.status)

FormGeometry = collections.namedtuple("FormGeometry", "needs_auth fields screenshot_id")
FormGeometryEntry = collections.namedtuple("FormGeometryEntry", "index title kind")

async def get_form_geometry(user: User, form_url: str, needs_screenshot: bool=False) -> FormGeometry:
    """
    Grab the form geometry.

    Returns None for pending
    """

    if user.lockbox_token is None:
        raise ValueError("missing token")

    async with _lockbox_sess().post("http://lockbox/form_geometry", headers=_headers_for_user(user), json={
        "url": form_url,
        "override_limit": user.admin,
        "grab_screenshot": needs_screenshot
    }) as resp:
        payload = await resp.json()

        if not resp.ok:
            raise LockboxError(payload.get("error", ""), resp.status)
        
        if payload["pending"]:
            return None

        # otherwise, deserialize
        entries = [
            FormGeometryEntry(x["index"], x["title"], FormFieldType(x["kind"]))
            for x in payload["geometry"]
        ]

        sid = None
        if needs_screenshot:
            sid = bson.ObjectId(payload["screenshot_id"])
        
        return FormGeometry(payload["auth_required"], entries, sid)
