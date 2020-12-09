import base64
import bson
import os
import secrets
import typing
from cryptography.fernet import Fernet
from marshmallow import fields as ma_fields
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from umongo import Document, EmbeddedDocument, fields, validate, ValidationError
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


class LockboxFailure(EmbeddedDocument): # pylint: disable=abstract-method
    """
    A document used to report lockbox failures to fenetre.
    """
    _id = fields.ObjectIdField(required=True)
    time_logged = fields.DateTimeField(required=True)
    kind = fields.StrField(required=True, marshmallow_default="unknown")
    message = fields.StrField(required=False, default="")


class User(Document): # pylint: disable=abstract-method
    """
    A user in the private database.
    """
    token = fields.StrField(required=True, unique=True, validate=validate.Length(equal=64))

    # Could be unconfigured
    login = fields.StrField(required=False, unique=True, validate=validate.Regexp(r"\d+"))
    password = BinaryField(required=False)

    active = fields.BoolField(default=True)
    errors = fields.ListField(fields.EmbeddedField(LockboxFailure), default=[])


class LockboxDBError(Exception):
    """
    Raised to indicate an error when performing a lockbox db operation.
    """

    OTHER = 0
    BAD_TOKEN = 1
    INVALID_FIELD = 2

    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


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

        self.LockboxFailureImpl = self._private_instance.register(LockboxFailure)
        self.UserImpl = self._private_instance.register(User)
        
    async def init(self):
        """
        Initialize the databases.
        """
        await self.UserImpl.ensure_indexes()
    
    def private_db(self) -> AsyncIOMotorDatabase:
        return self._private_db
    
    def shared_db(self) -> AsyncIOMotorDatabase:
        return self._shared_db
    
    async def create_user(self) -> str:
        """
        Create a new user.

        Returns token on success.
        """
        token = secrets.token_hex(32)
        await self.UserImpl(token=token).commit()
        return token

    async def modify_user(self, token: str, login: str = None, password: str = None, # pylint: disable=unused-argument
                          active: bool = None, **kwargs) -> None:
        """
        Modify user data.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        try:
            if login is not None:
                user.login = login
            if password is not None:
                user.password = self.fernet.encrypt(password.encode("utf-8"))
            if active is not None:
                user.active = active
            await user.commit()
        except ValidationError as e:
            raise LockboxDBError(f"Invalid field: {e}", LockboxDBError.INVALID_FIELD) from e
    
    async def get_user(self, token: str) -> typing.Dict[str, typing.Any]:
        """
        Get user data as a formatted dict.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        return user.dump()
    
    async def delete_user(self, token: str) -> None:
        """
        Delete a user by token.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        await user.remove()
    
    async def delete_user_error(self, token: str, eid: str) -> None:
        """
        Delete an error by id for a user.
        """
        try:
            result = await self.UserImpl.collection.update_one({"token": token},
                {"$pull": {"errors": {"_id": bson.ObjectId(eid)}}})
        except bson.errors.InvalidId as e:
            raise LockboxDBError("Bad error id") from e
        if result.matched_count == 0:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        if result.modified_count == 0:
            raise LockboxDBError("Bad error id")
