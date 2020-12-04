import bson
from marshmallow import fields as ma_fields
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from umongo import Document, fields, validate
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
    credentials = BinaryField(required=True)

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
