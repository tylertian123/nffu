"""
Handles talking to lockbox
"""

from .db import User
import collections
import typing

# stubs for rn

async def create_new_lockbox_identity(user: User):
    """
    Make a new lockbox identity and associated token and associate it to this user in the database
    """

    # currently does nothing TODO
    pass

async def destroy_lockbox_identity(user: User):
    """
    Delete all information in lockbox for this user

    If this fails the entire delete fails.
    """

    pass

# TODO: should lockbox_failures get moved from shared_db into lockbox and accessed through an api call here?

LockboxUserStatus = collections.namedtuple("LockboxUserStatus", "has_credentials has_errors active")

async def get_lockbox_status_for(user: User) -> LockboxUserStatus:
    """
    Get status for the given user in lockbox.

    Return None if the user doesn't have a lockbox identity
    """

    return LockboxUserStatus(  # todo
            False,
            False,
            False
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
