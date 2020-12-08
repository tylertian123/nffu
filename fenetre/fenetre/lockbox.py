"""
Handles talking to lockbox
"""

from .db import User
import collections
import typing
import aiohttp
from quart import Quart, current_app

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
            raise RuntimeError("failed to create lockbox identity")

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
            raise RuntimeError("failed to delete: " + resp.reason)

    user.lockbox_token = None
    await user.commit()

LockboxUserStatus = collections.namedtuple("LockboxUserStatus", "has_credentials has_errors active")

async def get_lockbox_status_for(user: User) -> LockboxUserStatus:
    """
    Get status for the given user in lockbox.

    Return None if the user doesn't have a lockbox identity
    """

    if user.lockbox_token is None:
        return None

    async with _lockbox_sess().get("http://lockbox/user", headers=_headers_for_user(user)) as resp:
        if not resp.ok:
            raise RuntimeError("failed to get: " + resp.reason)

        data = await resp.json()

        return LockboxUserStatus(  # todo
                data["credentials_set"],
                len(data["errors"]) > 0,
                data["active"]
        )

LockboxFailure = collections.namedtuple("LockboxFailure", "id kind message time_logged")

async def get_errors_for(user: User) -> typing.AsyncIterable[LockboxFailure]:
    """
    Retrieve all lockbox errors for a specific user.
    """

    responses = []  # TODO

    for i in responses:
        yield i

async def clear_error(for_: User, error_id: str):
    """
    Clear an error from a specific user
    """

    pass

async def update_lockbox_identity(user: User, payload: dict):
    """
    Update the lockbox data for the user

    (payload is passed directly)
    """

    if user.lockbox_token is None:
        raise ValueError("missing token")

    async with _lockbox_sess().patch("http://lockbox/user", headers=_headers_for_user(user), json=payload) as resp:
        if not resp.ok:
            raise RuntimeError("failed to patch: " + resp.reason)

async def query_lockbox_enrolled_courses(user: User):
    """
    Get the current set of courses we've detected for the user.

    Raises an error if the user does not have a lockbox identity, returns None if processing is still occuring and
    a list of Course objects if succesfull
    """

    if user.lockbox_token is None:
        raise ValueError("missing token")

    # TODO
    return None
