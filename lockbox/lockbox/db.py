import base64
import bson
import os
import secrets
from cryptography.fernet import Fernet
from marshmallow import fields as ma_fields
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from umongo import Document, fields, validate, ValidationError
from umongo.frameworks import MotorAsyncIOInstance

class BinaryField(fields.BaseField, ma_fields.Field):
    """
    A field storing binary data in a document.

    Shamelessly ripped from fenetre/db.py.
    """

    default_error_messages = {
        'invalid': 'Not a valid byte sequence.'
    }

    def _serialize(self, value, attr, obj, **kwargs):
        return bytes(value)

    def _deserialize(self, value, attr, data, **kwargs):
        if not isinstance(value, bytes):
            self.fail('invalid')
        return value

    def _serialize_to_mongo(self, obj):
        return bson.binary.Binary(obj)

    def _deserialize_from_mongo(self, value):
        return bytes(value)

class User(Document): # pylint: disable=abstract-method
    """
    A user in the private database.
    """
    token = fields.StrField(required=True, unique=True, validate=validate.Length(equal=64))
    login = fields.StrField(required=True, unique=True, validate=validate.Regexp(r"\d+"))
    password = BinaryField(required=True)

    active = fields.BoolField(default=True)

class LockboxFailure(Document): # pylint: disable=abstract-method
    """
    A document used to report lockbox failures to fenetre.

    Copied from fenetre/db.py.
    """
    token = fields.StrField(required=True)
    time_logged = fields.DateTimeField(required=True)
    
    kind = fields.StrField(required=True, marshmallow_default="unknown")
    message = fields.StrField(required=False, default="")

class LockboxDB:
    """
    Holds databases for lockbox.
    """

    def __init__(self, host: str, port: int):
        # Set up fernet
        # Read from base64 encoded key
        if os.environ.get("LOCKBOX_CREDENTIAL_KEY"):
            key = os.environ.get("LOCKBOX_CREDENTIAL_KEY")
        # Read from key file
        elif os.environ.get("LOCKBOX_CREDENTIAL_KEY_FILE"):
            try:
                with open(os.environ.get("LOCKBOX_CREDENTIAL_KEY_FILE"), "rb") as f:
                    key = base64.b64encode(f.read())
            except IOError as e:
                raise ValueError("Cannot read password encryption key file") from e
        else:
            raise ValueError("Encryption key for passwords must be provided! Set LOCKBOX_CREDENTIAL_KEY or LOCKBOX_CREDENTIAL_KEY_FILE.")
        # Should raise ValueError if key is invalid
        self.fernet = Fernet(key)

        self.client = AsyncIOMotorClient(host, port)
        self._private_db = self.client["lockbox"]
        self._shared_db = self.client["shared"]
        self._private_instance = MotorAsyncIOInstance(self._private_db)
        self._shared_instance = MotorAsyncIOInstance(self._shared_db)

        self.UserImpl = self._private_instance.register(User)
        self.LockboxFailureImpl = self._shared_instance.register(LockboxFailure)
        
    async def init(self):
        """
        Initialize the databases.
        """
        await self.LockboxFailureImpl.ensure_indexes()
    
    def private_db(self) -> AsyncIOMotorDatabase:
        return self._private_db
    
    def shared_db(self) -> AsyncIOMotorDatabase:
        return self._shared_db
    
    async def create_user(self, login: str, password: str, active: bool) -> str:
        """
        Create a new user.

        Returns token on success.
        """
        if await self.UserImpl.find_one({"login": login}):
            raise ValueError("user already exists")
        token = secrets.token_hex(32)
        pass_token = self.fernet.encrypt(password.encode("utf-8"))
        try:
            user = self.UserImpl(token=token, login=login, password=pass_token, active=active)
            await user.commit()
        except ValidationError as e:
            raise ValueError(f"validation error: {e}") from e
        return token
