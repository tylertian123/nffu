from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from quart import Quart, current_app
from umongo.frameworks import MotorAsyncIOInstance
from marshmallow import fields as ma_fields, missing as missing_
from umongo import Document, fields, validate, EmbeddedDocument
import asyncio
import enum
import bson

def private_db() -> AsyncIOMotorDatabase:
    return current_app.priv_db

def shared_db() -> AsyncIOMotorDatabase:
    return current_app.shared_db

def gridfs() -> AsyncIOMotorGridFSBucket:
    return current_app.gridfs_shared

_shared_instance = MotorAsyncIOInstance()
_private_instance = MotorAsyncIOInstance()


class BinaryField(fields.BaseField, ma_fields.Field):
    default_error_messages = {
        'invalid': 'Not a valid byte sequence.'
    }

    def _serialize(self, value, attr, data, **kwargs):
        return bytes(value)

    def _deserialize(self, value, attr, data, **kwargs):
        if not isinstance(value, bytes):
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
    shared_db = client['shared']
    _private_instance.set_db(priv_db)
    _shared_instance.set_db(shared_db)

def init_app(app: Quart):
    @app.before_serving
    async def load_database():
        current_app.client = AsyncIOMotorClient("db", 27017)
        current_app.priv_db = current_app.client['fenetre']
        current_app.shared_db = current_app.client['shared']
        current_app.gridfs_shared = AsyncIOMotorGridFSBucket(current_app.shared_db)

        _shared_instance.set_db(shared_db())
        _private_instance.set_db(private_db())

    @app.cli.command()
    def build_indexes():
        init_db_in_cli_context()

        async def inner():
            await User.ensure_indexes()
            await SignupProvider.ensure_indexes()

            await Course.ensure_indexes()
            await Form.ensure_indexes()

        asyncio.get_event_loop().run_until_complete(inner())

        print("ok")

    @app.cli.command()
    def add_test_data():
        init_db_in_cli_context()

        async def inner():
            new_course = Course(course_code="SCH4UP-1C")
            await new_course.commit()

            print("added course: " + str(new_course.pk))

        asyncio.get_event_loop().run_until_complete(inner())

@_private_instance.register
class User(Document):
    username = fields.StrField(required=True, unique=True, validate=validate.Length(min=6), error_messages={"unique": "Username already taken"})
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

@_private_instance.register
class SignupProvider(Document):
    name = fields.StrField(required=True)

    hmac_secret = BinaryField(required=True, unique=True, validate=validate.Length(equal=32))  # sha-256 secret key
    identify_tokens = fields.ListField(fields.StringField(validate=validate.Length(equal=3)), validate=validate.Length(min=2), unique=True)


class FormFieldType(enum.Enum):
    TEXT = "text"
    DATE = "date"
    MULTIPLE_CHOICE = "multiple-choice"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"


@_shared_instance.register
class FormField(EmbeddedDocument):
    # This should be a substring of the nearest label text to the control we're filling in.
    # Optional _not automatically set_
    expected_label_segment = fields.StrField(required=False, default=None)

    # Index on page (includes headings)
    index_on_page = fields.IntField(required=True, validate=validate.Range(min=0))

    # Value to fill in.
    # The grammar for this field is in fieldexpr.py in lockbox.
    target_value = fields.StrField(required=True)

    # Type of field
    kind = fields.StrField(required=True, validate=validate.OneOf([x.value for x in FormFieldType]))

@_shared_instance.register
class Form(Document):
    sub_fields = fields.ListField(fields.EmbeddedField(FormField))

    # id of file in gridfs, should be a png
    representative_thumbnail = fields.ObjectIdField(default=None)

    # Friendly title for this form configuration
    name = fields.StrField()

    # is this form the default? if there are multiple of these, uh panic
    # TODO: use io_validate to check that
    is_default = fields.BoolField(default=False)

@_shared_instance.register
class Course(Document):
    # Course code including cohort str
    course_code = fields.StrField(required=True, unique=True)

    # Is this course's form setup locked by an admin?
    configuration_locked = fields.BoolField(default=False)

    # FORM config:

    # does this course use an attendance form (to deal with people who have COOP courses or something)
    has_attendance_form = fields.BoolField(default=True)

    # form URL
    form_url = fields.URLField(default=None)
    
    # form configuration
    form_config = fields.ReferenceField(Form, default=None)

    # Slots we know this course occurs on (f"{day}-{period}" so for example "2-1a" is day 2 in the morning asynchronous
    known_slots = fields.ListField(fields.StrField(), default=[])
