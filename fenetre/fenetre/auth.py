from quart_auth import login_user, logout_user, current_user, AuthUser, AuthManager, Unauthorized
from fenetre.db import User, init_db_in_cli_context
from fenetre.lockbox import create_new_lockbox_identity
from motor.motor_asyncio import AsyncIOMotorCollection
from functools import wraps
import enum
import hashlib
import hmac
import bson
import os
import click
import asyncio

auth_manager = AuthManager()

class UserProxy(AuthUser):
    def __init__(self, auth_id):
        super().__init__(auth_id)
        self._resolved = auth_id is None
        self._object = None
        print(auth_id)

    @staticmethod
    def from_db(dbu: User):
        return UserProxy(str(dbu.pk))

    @property
    async def is_authenticated(self):
        return self._auth_id is not None and (not self._resolved or self._object is not None)

    async def _resolve(self):
        if not self._resolved:
            self._object = await User.find_one({"_id": bson.ObjectId(self.auth_id)})
            print("o", self._object)
            self._resolved = True

    @property
    async def user(self) -> User:
        await self._resolve()
        return self._object

auth_manager.user_class = UserProxy

class EulaRequired(Unauthorized):
    pass

def admin_required(func):
    """
    Makes a function throw unauthorized is the logged in user is not an admin
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        if (await current_user.user()).admin:
            return await func(*args, **kwargs)
        else:
            raise Unauthorized()

    return wrapper

def eula_required(func):
    """
    Makes a function throw unauthorized is the logged in user has not signed the eula
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        if (await current_user.user()).signed_eula:
            return await func(*args, **kwargs)
        else:
            raise EulaRequired()

    return wrapper

def compute_passhash(password: str, salt: bytes):
    """
    Compute the passhash for a plaintext password
    """

    return hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 130000)

class AuthenticationError(RuntimeError):
    pass

async def try_login_user(username: str, password: str, remember_me: bool):
    """
    Try to login a user
    """

    # find the user
    check_user = await User.find_one({"username": username})
    if check_user is None:
        raise AuthenticationError("Wrong username")

    if not hmac.compare_digest(compute_passhash(password, check_user.passsalt), check_user.passhash):
        raise AuthenticationError("Wrong password")

    login_user(UserProxy.from_db(check_user), remember_me)

async def add_blank_user(username: str, password: str, *, discord_id: str=None) -> User:
    """
    Create a new blank user (optionally with an Ouath secondardy authentication method).

    This initializes the user with no eula signed and no permissions. Since the eula is not
    signed, the lockbox integration is not setup either. Calling sign_eula will setup the
    user in lockbox.
    """

    # pick a random salt
    salt = os.urandom(32)

    # generate the passhash
    passhash = compute_passhash(password, salt)

    # create the new user
    new_user = User(username=username, passhash=passhash, passsalt=salt, discord_id=discord_id)
    await new_user.commit()

    return new_user

async def sign_eula(user: User):
    """
    Mark the user as having signed the eula and give them access to lockbox
    """

    try:
        await create_new_lockbox_identity(user)
    except:
        user.signed_eula = False
        raise
    else:
        user.signed_eula = True
    finally:
        await user.commit()

async def init_auth_cli(user, password):
    usr = await add_blank_user(user, password)
    # don't have them sign the EULA but _do_ mark them admin
    usr.admin = True
    await usr.commit()

    click.echo("done!")

def init_app(app):
    auth_manager.init_app(app)

    @app.cli.command()
    @click.option("-u", "--username", type=str, prompt=True)
    @click.password_option()
    def init_auth(username: str, password: str):
        """
        Setup an admin user with the given credentials
        """

        init_db_in_cli_context()
        asyncio.get_event_loop().run_until_complete(init_auth_cli(username, password))

