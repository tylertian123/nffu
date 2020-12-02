from quart import Blueprint, request
from quart.exceptions import HTTPException
from fenetre.auth import admin_required, eula_required
from fenetre import auth
from quart_auth import login_required, current_user
from fenetre.db import User, LockboxFailure
import bson
import marshmallow as ma
import marshmallow.fields as ma_fields
import marshmallow.validate as ma_validate
import json

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

    return {
        "username": userdata.username,
        "admin": userdata.admin,
        "has_discord_integration": userdata.discord_id is not None,
        "has_lockbox_integreation": userdata.lockbox_token is not None,
        "lockbox_error": await LockboxFailure.count_documents({"token": userdata.lockbox_token}) > 0,                              
        # is something up with lockbox config?
    }

class LockboxFailureDump(LockboxFailure.schema.as_marshmallow_schema()):
    class Meta:
        fields = ("time_logged", "kind", "message", "id")

@blueprint.route("/me/lockbox_errors")
@login_required
@eula_required
async def lockbox_errors():
    userdata = await current_user.user
    
    result = [] 

    async for x in LockboxFailure.find({"token": userdata.lockbox_token}):
        result.append(LockboxFailureDump.dump(x))

    return {
        "lockbox_errors": result
    }

@blueprint.route("/me/lockbox_errors/<idx>", methods=["DELETE"])
@login_required
@eula_required
async def lockbox_error_del(idx):
    result = await LockboxFailure.find({"id": bson.ObjectId(idx)})
    userdata = await current_user.user

    if result is None:
        return {
            "error": "no such error alert"
        }, 404
    
    if result.token != userdata.lockbox_token:
        return {
            "error": "not your error"
        }, 403

    else:
        await result.remove()
        return '', 204

class UpdateUserInfoSchema(ma.Schema):
    password = ma_fields.String(required=False, validate=ma_validate.Length(min=8))
    username = ma_fields.String(required=False, validate=ma_validate.Length(min=6))

update_user_info_schema = UpdateUserInfoSchema()

@blueprint.route("/me", methods=["PUT"])
@login_required
async def update_userinfo():
    msg = await request.json
    payload = update_user_info_schema.load(msg)

    if "password" in payload:
        await auth.change_password(await current_user.user, payload["password"])

    if "username" in payload:
        u = await current_user.user
        u.username = payload["username"]
        await u.commit()

    return '', 204

@blueprint.route("/me/sign_eula", methods=["POST"])
@login_required
async def sign_eula():
    await auth.sign_eula(await current_user.user)

    return '', 204

