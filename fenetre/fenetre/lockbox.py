"""
Handles talking to lockbox
"""

from .db import User

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
