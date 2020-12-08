from quart import Blueprint, request, flash
from quart.exceptions import HTTPException
from fenetre.auth import admin_required, eula_required
from fenetre import auth, lockbox
from quart_auth import login_required, current_user, logout_user
import quart_auth
from fenetre.db import User, SignupProvider, Course
import bson
import marshmallow as ma
import marshmallow.fields as ma_fields
import marshmallow.validate as ma_validate
import binascii
import json
import random
import time
import asyncio

blueprint = Blueprint("api", __name__, url_prefix="/api/v1")

# todo: use global error handler to make this work for 404/405
@blueprint.errorhandler(HTTPException)
async def handle_exception(e: HTTPException):
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.set_data(json.dumps({
        "error": e.name,
        "extra": e.description,
    }))
    response.content_type = "application/json"
    return response

@blueprint.errorhandler(ma.ValidationError)
async def invalid_data(e: ma.ValidationError):
    return {
        "error": "invalid request",
        "extra": e.normalized_messages()
    }, 400

@blueprint.route("/me")
@login_required
async def userinfo():
    userdata = await current_user.user
    lockbox_status = await lockbox.get_lockbox_status_for(userdata)

    return {
        "username": userdata.username,
        "admin": userdata.admin,
        "has_discord_integration": userdata.discord_id is not None,
        "has_lockbox_integration": userdata.lockbox_token is not None,
        "lockbox_error": lockbox_status is not None and lockbox_status.has_errors,                              
        "signed_eula": userdata.signed_eula,
        "lockbox_credentials_present": lockbox_status is not None and lockbox_status.has_credentials,
        "lockbox_form_active": lockbox_status is not None and lockbox_status.active
    }

class LockboxFailureDump(ma.Schema):
    time_logged = ma_fields.DateTime(required=True)
    id = ma_fields.String(required=True) # this comes from an external api and is therefore not an objectid
    kind = ma_fields.String(missing="unknown")
    message = ma_fields.String(required=False, default="")

lockbox_failure_dump = LockboxFailureDump()

@blueprint.route("/me/lockbox_errors")
@eula_required
async def lockbox_errors():
    userdata = await current_user.user
    
    result = [] 

    async for x in lockbox.get_errors_for(userdata):
        result.append(lockbox_failure_dump.dump(x))

    return {
        "lockbox_errors": result
    }

@blueprint.route("/me/lockbox_errors/<idx>", methods=["DELETE"])
@eula_required
async def lockbox_error_del(idx):
    userdata = await current_user.user

    await lockbox.clear_error(userdata, idx)
    return '', 204

class UpdateUserInfoSchema(ma.Schema):
    current_password = ma_fields.String(required=False)
    password = ma_fields.String(required=False, validate=ma_validate.Length(min=8))
    username = ma_fields.String(required=False, validate=ma_validate.Length(min=6))

    @ma.validates_schema
    def validate_mutinc(self, data, **kwargs):
        if 'password' in data and 'current_password' not in data or 'password' not in data and 'current_password' in data:
            raise ma.ValidationError("current_password and password are mutually inclusive")

update_user_info_schema_user = UpdateUserInfoSchema()

@blueprint.route("/me", methods=["PATCH"])
@login_required
async def update_userinfo():
    msg = await request.json
    payload = update_user_info_schema_user.load(msg)

    if "password" in payload:
        if not asyncio.get_event_loop().run_in_executor(None, auth.verify_password_for_user, await current_user.user, payload["current_password"]):
            return {"error": "incorrect current password"}, 401
        await auth.change_password(await current_user.user, payload["password"])

    if "username" in payload:
        u = await current_user.user
        u.username = payload["username"]
        await u.commit()

    return '', 204

@blueprint.route("/me/sign_eula", methods=["POST"])
@login_required
async def sign_eula():
    user = await current_user.user
    if user.signed_eula and user.lockbox_token:
        return {"error": "you have already signed the eula"}, 403

    await auth.sign_eula(user)

    return '', 204

@blueprint.route("/me", methods=["DELETE"])
@login_required
async def delete_self():
    user = await current_user.user

    await auth.delete_user(user)
    logout_user()

    await flash("Your account was deleted")

    return '', 204

class LockboxUpdateSchema(ma.Schema):
    login    = ma_fields.String(validate=ma_validate.Regexp("\d{5,9}"), data_key="username")
    password = ma_fields.String()
    active   = ma_fields.Bool()

lockbox_update_schema = LockboxUpdateSchema()

@blueprint.route("/me/lockbox", methods=["PATCH"])
@eula_required
async def update_self_lockbox():
    user = await current_user.user
    msg = await request.json

    payload = lockbox_update_schema.load(msg)
    await lockbox.update_lockbox_identity(user, payload)

    return '', 204

class UserCourseEnrollmentDump(Course.schema.as_marshmallow_schema()):
    @ma.post_dump(pass_original=True)
    def cleanup_uce(self, data, orig, **kwargs):
        cfg_present = orig.form_config is not None
        data["form_config"] = cfg_present
        return data

    class Meta:
        exclude = ("form_config")

class SignupSchema(ma.Schema):
    token = ma_fields.String(required=True, validate=ma_validate.Regexp("[0-9a-f]{9}"))

    password = ma_fields.String(required=True, validate=ma_validate.Length(min=8))
    username = ma_fields.String(required=True, validate=ma_validate.Length(min=6))

signup_schema = SignupSchema()

# this route is handled separately since it'll sign in the user too
@blueprint.route("/signup", methods=["POST"])
async def do_signup():
    if await current_user.is_authenticated:
        return {"error": "Can't signup while still logged in."}, 403

    msg = await request.json
    payload = signup_schema.load(msg)

    if not await auth.verify_signup_code(payload["token"]):
        return {"error": "Invalid signup code."}, 401

    # create a new user TODO: proper error checking and nicer response
    new_user = await auth.add_blank_user(payload["username"], payload["password"])

    # login user (so subsequent api calls will still work)
    quart_auth.login_user(auth.UserProxy.from_db(new_user))
    
    return '', 201

class SignupProviderDump(SignupProvider.schema.as_marshmallow_schema()):
    class Meta:
        fields = ("id", "name")

signup_provider_dump = SignupProviderDump()

@blueprint.route("/signup_provider")
@admin_required
async def enumerate_signups():
    result = [] 

    async for x in SignupProvider.find({}):
        result.append(signup_provider_dump.dump(x))

    return {
        "signup_providers": result
    }

class NewSignupProviderSchema(ma.Schema):
    name = ma_fields.String(required=True)

new_signup_provider_schema = NewSignupProviderSchema()

@blueprint.route("/signup_provider", methods=["POST"])
@admin_required 
async def new_signup_provider():
    msg = await request.json
    payload = new_signup_provider_schema.load(msg)

    new_provider = await auth.create_signup_provider(payload["name"])

    return {
        "id": str(new_provider.id),
        "name": new_provider.name,
        "secret_key": binascii.hexlify(new_provider.hmac_secret).decode('ascii')
    }, 201

@blueprint.route("/signup_provider/<idx>")
@admin_required
async def get_signup_provider(idx):
    requested = await SignupProvider.find_one({"id": bson.ObjectId(idx)})

    if requested is None:
        return {"error": "no such provider exists"}, 404

    return signup_provider_dump.dump(requested)

@blueprint.route("/signup_provider/<idx>", methods=["DELETE"])
@admin_required
async def delete_signup_provider(idx):
    requested = await SignupProvider.find_one({"id": bson.ObjectId(idx)})

    if requested is None:
        return {"error": "no such provider exists"}, 404

    await requested.remove()
    return '', 204

@blueprint.route("/signup_provider/<idx>/generate")
@admin_required
async def generate_code_for_provider(idx):
    requested = await SignupProvider.find_one({"id": bson.ObjectId(idx)})

    if requested is None:
        return {"error": "no such provider exists"}, 404

    return {
        "token": random.choice(requested.identify_tokens) + auth.generate_signup_code(requested.hmac_secret, int(time.time()))
    }

class UserDump(User.schema.as_marshmallow_schema()):
    class Meta:
        fields = ["username", "id", "admin", "signed_eula"]

user_dump = UserDump()

@blueprint.route("/user")
@admin_required
async def list_users():
    # TODO: should this paginate the responses? I can't be arsed to implement it
    # right now
    
    return {"users": [user_dump.dump(x) async for x in User.find({})]}

class UpdateUserInfoAdminSchema(ma.Schema):
    password = ma_fields.String(required=False, validate=ma_validate.Length(min=8))
    username = ma_fields.String(required=False, validate=ma_validate.Length(min=6))
    admin    = ma_fields.Bool(required=False)

update_user_info_schema_admin = UpdateUserInfoAdminSchema()

@blueprint.route("/user/<idx>")
@admin_required
async def show_user(idx):
    usr = await User.find_one({"id": bson.ObjectId(idx)})

    if usr is None:
        return {"error": "no such user"}, 404

    return user_dump.dump(usr)

@blueprint.route("/user/<idx>", methods=["PATCH"])
@admin_required
async def update_user(idx):
    u = await User.find_one({"id": bson.ObjectId(idx)})

    if u is None:
        return {"error": "no such user"}, 404

    msg = await request.json
    payload = update_user_info_schema_admin.load(msg)

    if "password" in payload:
        await auth.change_password(u, payload["password"])

    if "username" in payload:
        u.username = payload["username"]

    if "admin" in payload:
        u.admin = payload["admin"]

    await u.commit()

    return '', 204

@blueprint.route("/user/<idx>", methods=["DELETE"])
@admin_required
async def delete_user(idx):
    u = await User.find_one({"id": bson.ObjectId(idx)})

    if u is None:
        return {"error": "no such user"}, 404

    await auth.delete_user(u)

    return '', 204
