from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from quart import Quart, g
from umongo.frameworks import MotorAsyncIOInstance
from marshmallow import compat as ma_compat, fields as ma_fields
from umongo import Document, fields, validate
import bson

def private_db() -> AsyncIOMotorDatabase:
    return g.priv_db

def shared_db() -> AsyncIOMotorDatabase:
    return g.shared_db

_shared_instance = MotorAsyncIOInstance()
_private_instance = MotorAsyncIOInstance()


class BinaryField(fields.BaseField, ma_fields.Field):
    default_error_messages = {
        'invalid': 'Not a valid byte sequence.'
    }

    def _serialize(self, value, attr, data):
        return ma_compat.binary_type(value)

    def _deserialize(self, value, attr, data):
        if not isinstance(value, ma_compat.binary_type):
            self.fail('invalid')
        return value

    def _serialize_to_mongo(self, obj):
        return bson.binary.Binary(obj)

    def _deserialize_from_mongo(self, value):
        return bytes(value)

def init_db_in_cli_context():
    # connect to the database
    client = AsyncIOMotorClient("db", 27017)
    priv_db = client['fenetre']
    _private_instance.init(priv_db)

def init_app(app: Quart):
    @app.before_serving
    async def load_database():
        g.client = AsyncIOMotorClient("db", 27017)
        g.priv_db = g.client['fenetre']
        g.shared_db = g.client['shared']

        _shared_instance.init(shared_db())
        _private_instance.init(private_db())

@_private_instance.register
class User(Document):
    username = fields.StrField(required=True, unique=True, validate=validate.Length(min=6))
    passhash = BinaryField(required=True)
    passsalt = BinaryField(required=True)

    admin = fields.BoolField(default=False)
    signed_eula = fields.BoolField(default=False)

    # support for oauth via discord
    discord_id = fields.StrField(default=None)
    # potential other oauth?
    # might do github here.
    # we still force a password to exist on the account though.

    lockbox_token = fields.StrField(default=None) # not always present if not setup


