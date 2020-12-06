"""
Handles talking to lockbox
"""

from .db import User
import collections

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

LockboxUserStatus = collections.namedtuple("LockboxUserStatus", "has_credentials active")

async def get_lockbox_status_for(user: User) -> LockboxUserStatus:
    """
    Get status for the given user in lockbox.

    Return None if the user doesn't have a lockbox identity
    """

    return LockboxUserStatus(  # todo
            False,
            False
    )
