from quart_auth import login_user, logout_user, current_user, AuthUser, AuthManager, Unauthorized, login_required
from fenetre.db import User, init_db_in_cli_context, SignupProvider
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
import binascii
import time

auth_manager = AuthManager()

class UserProxy(AuthUser):
    def __init__(self, auth_id):
        super().__init__(auth_id)
        self._resolved = auth_id is None
        self._object = None

    @staticmethod
    def from_db(dbu: User):
        return UserProxy(str(dbu.pk))

    @property
    async def is_authenticated(self):
        return self._auth_id is not None and (not self._resolved or self._object is not None)

    async def _resolve(self):
        if not self._resolved:
            self._object = await User.find_one({"_id": bson.ObjectId(self.auth_id)})
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
    @login_required
    async def wrapper(*args, **kwargs):
        if (await current_user.user).admin:
            return await func(*args, **kwargs)
        else:
            raise Unauthorized()

    return wrapper

def eula_required(func):
    """
    Makes a function throw unauthorized is the logged in user has not signed the eula
    """

    @wraps(func)
    @login_required
    async def wrapper(*args, **kwargs):
        if (await current_user.user).signed_eula:
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

async def change_password(user: User, password: str):
    """
    Update the password of the given user
    """

    # pick a random salt
    salt = os.urandom(32)

    # generate the passhash
    passhash = compute_passhash(password, salt)

    user.passhash = passhash
    user.passsalt = salt

    await user.commit()

def generate_signup_code(hmac_secret: bytes, unix_time: int):
    """
    Generate the HOTP part of the signup code

    :param unix_time: should be in UTC
    """

    unix_minutes = unix_time // 60

    data = unix_minutes.to_bytes(8, byteorder='big', signed=False)
    mac  = hmac.new(hmac_secret, data, 'sha256').digest()
    i    = mac[-1] % 16
    trun = int.from_bytes(mac[i:i+4], byteorder='big', signed=False) % 2**31
    hexa = trun % 16**6
    return format(hexa, "06x")

async def verify_signup_code(signup_code: str):
    """
    Verify a sign up code.

    Format:

    XXXYYYYYY
    |//|///// 
    ---+- generator id
       |
       -- actual HOTP (in hexadecimal to 6 digits)

    All hexadecimal letters are lowercase only.
    """

    identifier, token = signup_code[0:3], signup_code[3:]

    # try to find a signup provider that matches the identifier
    potential_providers = SignupProvider.find({"identify_tokens": identifier})

    # try 2 minutes in the past to 6 minutes in the future
    current_time = int(time.time())

    async for potential_provider in potential_providers:
        for offset in range(-2, 7):
            if token == generate_signup_code(potential_provider.hmac_secret, current_time + offset*60):
                return True
    return False

async def create_signup_provider(name: str):
    """
    Create a new signup provider, returning the created database object.

    This may fail if the randomly generated code is in the database; but it's fairly unlikely for this to occur.
    TODO: this shouldn't be failing and should retry
    """

    attempt = 0
    while True:
        # create a new random key
        secret_key = os.urandom(32)

        # generate the subkeys
        digested = hashlib.sha256(secret_key).hexdigest()

        identifiers = [
            digested[i:i+3] for i in range(0, len(digested), 16)
        ]

        if await SignupProvider.count_documents({"$or": [
            {"hmac_secret": secret_key},
            {"identify_tokens": {"$in": identifiers}}
        ]}):
            attempt += 1
            if attempt > 10:
                raise RuntimeError("couldn't create new provider")
        else:
            break

    new_provider = SignupProvider(
        name=name,
        hmac_secret=secret_key,
        identify_tokens=identifiers
    )

    await new_provider.commit()

    return new_provider

async def init_auth_cli(user, password):
    usr = await add_blank_user(user, password)
    # don't have them sign the EULA but _do_ mark them admin
    usr.admin = True
    await usr.commit()

    click.echo("done!")

async def init_signup_source_cli(name):
    new_provider = await create_signup_provider(name)

    secret_key = binascii.hexlify(new_provider.hmac_secret).decode('ascii')
    click.echo("new signup source:")
    click.echo(f" name: {name}")
    click.echo(f" key: {secret_key}")
    click.echo(f" identifiers: {new_provider.identify_tokens}")

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

    @app.cli.command()
    @click.option("-n", "--name", type=str, default="CLI-generated signup source")
    def init_signup_source(name: str):
        """
        Create a random signup provider
        """

        init_db_in_cli_context()
        asyncio.get_event_loop().run_until_complete(init_signup_source_cli(name))
