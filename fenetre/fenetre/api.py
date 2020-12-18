from quart import Blueprint, request, flash, current_app
from quart.exceptions import HTTPException
from fenetre.auth import admin_required, eula_required
from fenetre import auth, lockbox
from quart_auth import login_required, current_user, logout_user
import quart_auth
from fenetre.db import User, SignupProvider, Course, Form, gridfs, FormField
from umongo.marshmallow_bonus import ObjectId as ObjectIdField
from gridfs.errors import NoFile
from fenetre.formutil import form_geometry_compatible, create_default_fields_from_geometry
import bson
import marshmallow as ma
import marshmallow.fields as ma_fields
import marshmallow.validate as ma_validate
import binascii
import json
import random
import time
import asyncio
import itsdangerous

blueprint = Blueprint("api", __name__, url_prefix="/api/v1")

def init_app(app):
    @app.before_serving
    async def create_signers():
        current_app.course_cfg_option_signer = itsdangerous.URLSafeTimedSerializer(app.secret_key, salt=b'cfg-options')

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

@blueprint.errorhandler(lockbox.LockboxError)
async def handle_le(e):
    return {
        "error": e.args[0]
    }, e.args[1]

@blueprint.errorhandler(ma.ValidationError)
async def invalid_data(e: ma.ValidationError):
    return {
        "error": "invalid request",
        "extra": e.normalized_messages()
    }, 400

@blueprint.errorhandler(bson.errors.InvalidId)
async def invalid_id(e):
    return {
        "error": "invalid id format"
    }, 400

@blueprint.route("/me")
@login_required
async def userinfo():
    userdata = await current_user.user
    lockbox_status = await lockbox.get_lockbox_status_for(userdata)

    if userdata.signed_eula and userdata.admin:
        unconfigured_courses_present = await Course.count_documents({"configuration_locked": False}) > 0
    else:
        unconfigured_courses_present = None

    return {
        "username": userdata.username,
        "admin": userdata.admin,
        "has_discord_integration": userdata.discord_id is not None,
        "has_lockbox_integration": userdata.lockbox_token is not None,
        "lockbox_error": lockbox_status is not None and lockbox_status.has_errors,                              
        "signed_eula": userdata.signed_eula,
        "lockbox_credentials_present": lockbox_status is not None and lockbox_status.has_credentials,
        "lockbox_form_active": lockbox_status is not None and lockbox_status.active,
        "unconfigured_courses_present": unconfigured_courses_present
    }

class LockboxFailureDump(ma.Schema):
    time_logged = ma_fields.DateTime(required=True)
    id = ma_fields.String(required=True) # this comes from an external api and is therefore not an objectid
    kind = ma_fields.String(missing="unknown")
    message = ma_fields.String(required=False, default="")

lockbox_failure_dump = LockboxFailureDump()

@blueprint.route("/me/lockbox/errors")
@eula_required
async def lockbox_errors():
    userdata = await current_user.user
    
    result = [] 

    async for x in lockbox.get_errors_for(userdata):
        result.append(lockbox_failure_dump.dump(x))

    return {
        "lockbox_errors": result
    }

@blueprint.route("/me/lockbox/errors/<idx>", methods=["DELETE"])
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
        exclude = ("form_config",)

user_course_enrollment_dump = UserCourseEnrollmentDump()

@blueprint.route("/me/lockbox/courses")
@eula_required
async def get_lockbox_courses():
    user = await current_user.user

    current_courses = await lockbox.query_lockbox_enrolled_courses(user)
    if current_courses is None:
        return {"status": "pending", "courses": []}, 200
    else:
        return {
            "status": "ok",
            "courses": [user_course_enrollment_dump.dump(x) for x in current_courses]
        }, 200

@blueprint.route("/me/lockbox/courses/update", methods=["POST"])
@eula_required
async def refresh_lockbox_courses():
    user = await current_user.user

    await lockbox.update_lockbox_enrolled_courses(user)

    return '', 204

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

@blueprint.route("/course")
@admin_required
async def list_all_courses():
    courses = Course.find({})

    results = []

    async for course in courses:
        dump = user_course_enrollment_dump.dump(course)
        if course.form_config is not None:
            dump["form_config_id"] = str(course.form_config.pk)
        else:
            dump["form_config_id"] = None
        results.append(dump)

    return {"courses": results}

@blueprint.route("/course/<idx>")
@eula_required  # specifically not admin so that users can _view_ courses if they have the id
async def course_info(idx):
    obj = await Course.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    dump = user_course_enrollment_dump.dump(obj)

    usr = await current_user.user
    if usr.admin:
        if obj.form_config is not None:
            dump["form_config_id"] = str(obj.form_config.pk)
        else:
            dump["form_config_id"] = None

    return {"course": dump}, 200

class UserFormDump(Form.schema.as_marshmallow_schema()):
    @ma.post_dump(pass_original=True)
    def add_thumb_present(self, data, orig, **kwargs):
        data["has_thumbnail"] = orig.representative_thumbnail is not None
        return data

    class Meta:
        fields = ('name', 'is_default')

user_form_dump = UserFormDump()

# specifically for users on user pages (admins get the form ID in course_info and use /form)
@blueprint.route("/course/<idx>/form")
@eula_required
async def course_form_info(idx):
    obj = await Course.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    if obj.form_config is None:
        return {"error": "form config not present"}, 404

    form_obj = await obj.form_config.fetch()

    if form_obj is None:
        return {"error": "course has no form setup"}, 404

    return {"form": user_form_dump.dump(form_obj)}

@blueprint.route("/course/<idx>/form/thumb.png")
@eula_required
async def course_form_thumbnail_img(idx):
    obj = await Course.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    if obj.form_config is None:
        return {"error": "form config not present"}, 404

    form_obj = await obj.form_config.fetch()

    if form_obj is None:
        return {"error": "course has no form setup"}, 404

    if form_obj.representative_thumbnail is None:
        return {"error": "form has no thumbnail yet"}, 404

    try:
        stream = await gridfs().open_download_stream(form_obj.representative_thumbnail)
    except NoFile:
        return {"error": "form not in db"}, 404

    return (await stream.read()), 200, {"Content-Type": "image/png"}


class CourseConfigOptionDumpInner(ma.Schema):
    # why is this a valid option
    reason = ma_fields.String(required=True, validate=ma_validate.OneOf(["default-form", "matches-url"]))
    # the course this option is for
    for_course = ObjectIdField(required=True)
    # the form ID this is referring to
    form_config_id = ObjectIdField(required=True)
    # the name of the form this is referring to
    form_title = ma_fields.String(required=True)

course_config_option_dump_inner = CourseConfigOptionDumpInner()

class CourseConfigOptionDump(ma.Schema):
    # why is this a valid option
    reason = ma_fields.String(required=True, validate=ma_validate.OneOf(["default-form", "matches-url"]))
    # the name of the form this is referring to
    form_title = ma_fields.String(required=True)
    # has thumbnail (not signed for reasons)
    has_thumbnail = ma_fields.Bool(missing=False)
    
    @ma.post_dump(pass_original=True)
    def add_token(self, data, orig, **kwargs):
        data["token"] = current_app.course_cfg_option_signer.dumps(course_config_option_dump_inner.dump(orig))
        return data

course_config_option_dump = CourseConfigOptionDump()

GOOGLE_FORM_URL_REGEX = r"^https://docs.google.com/forms/d/e/([A-Za-z0-9-_]+)/viewform$"

class RequestCourseConfigOptions(ma.Schema):
    form_url = ma_fields.URL(required=True, validate=ma_validate.Regexp(GOOGLE_FORM_URL_REGEX))

request_course_config_options = RequestCourseConfigOptions()

@blueprint.route("/course/<idx>/config_options", methods=["POST"])
@eula_required
async def generate_valid_configs(idx):
    # there is still some TODO here: this should really _not_ be blindly giving the suggestions it does and instead verify that they at least make some sense
    # with lockbox first.
    user = await current_user.user
    
    # make sure the course exists first
    obj = await Course.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    if obj.configuration_locked and not (await current_user.user).admin:
        return {"error": "config locked"}, 403

    msg = await request.json
    payload = request_course_config_options.load(msg)

    valid_options = []

    # get the geometry from lockbox
    try:
        requested_geom = await lockbox.get_form_geometry(user, payload["form_url"])
    except lockbox.LockboxError as e:
        if e.args[1] == 429:
            return {"status": "pending", "options": []}, 202
        else:
            return {"error": e.args[0]}, e.args[1]

    if requested_geom is None:
        return {"status": "pending", "options": []}, 202

    # try to add the default one
    async for default_option in Form.find({"is_default": True}):
        if default_option is not None and form_geometry_compatible(requested_geom, default_option):
            valid_options.append(
                course_config_option_dump.dump({
                    "reason": "default-form",
                    "form_title": default_option.name,
                    "for_course": obj.pk,
                    "form_config_id": default_option.pk,
                    "has_thumbnail": default_option.representative_thumbnail is not None
                })
            )

    # find any courses with the same url
    already_processed = set()
    async for potential in Course.find({"form_url": payload["form_url"]}):
        if potential.form_config is not None and potential.form_config.pk not in already_processed:
            already_processed.add(potential.form_config.pk)
            option = await potential.form_config.fetch()
            if option is None or option.is_default or not form_geometry_compatible(requested_geom, option):
                continue
            valid_options.insert(0,   # add to start of list so it shows up first
                course_config_option_dump.dump({
                    "reason": "matches-url",
                    "form_title": option.name,
                    "for_course": obj.pk,
                    "form_config_id": option.pk,
                    "has_thumbnail": option.representative_thumbnail is not None
                })
            )

    return {"options": valid_options, "status": "ok"}


@blueprint.route("/course/<idx>/config_options/<signed_option>/thumb.png")
@eula_required
async def potential_course_form_thumbnail_img(idx, signed_option):
    obj = await Course.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    if obj.configuration_locked and not (await current_user.user).admin:
        return {"error": "config locked"}, 403

    try:
        config_option = course_config_option_dump_inner.load(current_app.course_cfg_option_signer.loads(signed_option, max_age=60*60*24))
    except itsdangerous.exc.BadData:
        return {"error": "invalid option str"}, 400

    # verify this is the right one
    if config_option["for_course"] != obj.pk:
        return {"error": "option str for wrong course"}, 403

    # try to load the form
    referred_form = await Form.find_one({"id": bson.ObjectId(config_option["form_config_id"])})

    if referred_form is None:
        return {"error": "form not found"}, 404

    if referred_form.representative_thumbnail is None:
        return {"error": "form has no thumbnail yet"}, 404

    try:
        stream = await gridfs().open_download_stream(referred_form.representative_thumbnail)
    except NoFile:
        return {"error": "form not in db"}, 404

    return (await stream.read()), 200, {"Content-Type": "image/png"}

class UserConfigureCourseSchema(ma.Schema):
    has_form_url = ma_fields.Bool(required=True)
    form_url = ma_fields.URL()
    config_token = ma_fields.Str()

    @ma.post_load
    def enforce(self, data, **kwargs):
        if data["has_form_url"] and "form_url" not in data:
            raise ma.ValidationError("has_form_url==true and form_url are mutually inclusive")
        if ("form_url" in data or "config_token" in data) and not data["has_form_url"]:
            raise ma.ValidationError("has_form_url==false is mutually exclusive with oter options")
        return data

user_configure_course_schema = UserConfigureCourseSchema()

@blueprint.route("/course/<idx>/config", methods=["PUT"])
@eula_required
async def configure_course_user(idx):
    obj = await Course.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    if obj.configuration_locked and not (await current_user.user).admin:
        return {"error": "config locked"}, 403

    msg = await request.json
    payload = user_configure_course_schema.load(msg)

    if "config_token" in payload:
        try:
            config_option = course_config_option_dump_inner.load(current_app.course_cfg_option_signer.loads(payload["config_token"], max_age=60*60*24))
        except itsdangerous.exc.BadData:
            return {"error": "invalid option str"}, 400

        # verify this is the right one
        if config_option["for_course"] != obj.pk:
            return {"error": "option str for wrong course"}, 403

        # try to load the form
        if not await Form.count_documents({"id": bson.ObjectId(config_option["form_config_id"])}):
            return {"error": "missing form data"}, 404
        
        obj.form_config = config_option["form_config_id"]
    else:
        pass
        # should be
        # obj.form_config = None

    if "form_url" in payload:
        obj.form_url = payload["form_url"]

    obj.has_attendance_form = payload["has_form_url"]
    await obj.commit()

    # major hack due to umongo issue #326
    if "config_token" not in payload:
        await Course.collection.update_one({"_id": obj.pk}, {"$unset": {"form_config": None}})

    return '', 204

class CondensedFormDump(Form.schema.as_marshmallow_schema()):
    class Meta:
        exclude = ['sub_fields']

condensed_form_dump = CondensedFormDump()

@blueprint.route("/form")
@admin_required 
async def list_all_forms():
    forms = Form.find({})

    use_counts = {}

    # use some pure mongo to count form uses
    async for result in Course.collection.aggregate([
        {
            "$match": { "has_attendance_form": True, "form_config": { "$ne": None } }
        },
        {
            "$group": {
                "_id": "$form_config",
                "use_count": { "$sum": 1 }
            }
        }
    ]):
        use_counts[result["_id"]] = result["use_count"]

    results = []
    
    async for i in forms:
        obj = condensed_form_dump.dump(i)
        obj['used_by'] = use_counts.get(i.pk, 0)
        results.append(obj)
    
    return {"forms": results}

class NewFormArgs(ma.Schema):
    name = ma_fields.Str(required=True)

    initialize_from = ma_fields.URL(validate=ma_validate.Regexp(GOOGLE_FORM_URL_REGEX), missing=None)
    use_fields_from_url = ma_fields.Bool(missing=True)

new_form_args = NewFormArgs()

@blueprint.route("/form", methods=["POST"])
@admin_required 
async def create_blank_form():
    msg = await request.json
    payload = new_form_args.load(msg)

    new_form = Form(name=payload["name"])

    # try to load geometry
    if payload["initialize_from"]:
        geometry = await lockbox.get_form_geometry(await current_user.user, payload["initialize_from"], needs_screenshot=True)
        if geometry is None:
            return {
                "form": None,
                "status": "pending"
            }, 202
        
        new_form.representative_thumbnail = geometry.screenshot_id
        if payload["use_fields_from_url"]:
            create_default_fields_from_geometry(geometry, new_form)

    await new_form.commit()

    return {
        "form": condensed_form_dump.dump(new_form),
        "status": "ok"
    }, 201

class UpdateFormThumb(ma.Schema):
    initialize_from = ma_fields.URL(validate=ma_validate.Regexp(GOOGLE_FORM_URL_REGEX), required=True)

update_form_thumb_schema = UpdateFormThumb()

@blueprint.route("/form/<idx>", methods=["PUT"])
@admin_required 
async def update_form_thumb(idx):
    msg = await request.json
    payload = update_form_thumb_schema.load(msg)

    form = await Form.find_one({"id": bson.ObjectId(idx)})
    if form is None:
        return {"error": "no such form"}, 404

    geometry = await lockbox.get_form_geometry(await current_user.user, payload["initialize_from"], needs_screenshot=True)
    if geometry is None:
        return {
            "form": None,
            "status": "pending"
        }, 202

    # Make sure any thumbnails are deleted
    if form.representative_thumbnail is not None:
        if await Form.count_documents({"representative_thumbnail": form.representative_thumbnail}) <= 1:
            try:
                await gridfs().delete(form.representative_thumbnail)
            except NoFile:
                pass

    form.representative_thumbnail = geometry.screenshot_id
    await form.commit()

    return {
        "form": condensed_form_dump.dump(form),
        "status": "ok"
    }, 201

@blueprint.route("/form/<idx>")
@admin_required 
async def get_form_specific(idx):
    obj = await Form.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such form"}, 404

    data = obj.dump()
    data["used_by"] = await Course.count_documents({"form_config": obj.pk})
    return data

@blueprint.route("/form/<idx>", methods=["DELETE"])
@admin_required 
async def delete_form_specific(idx):
    obj = await Form.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such form"}, 404
    
    # Make sure any courses using this form have their config cleared
    await Course.collection.update_many({
        "form_config": obj.pk
    }, {"$set": {"configuration_locked": False}, "$unset": {"form_config": None}})

    # Make sure any thumbnails are deleted
    if obj.representative_thumbnail is not None:
        if await Form.count_documents({"representative_thumbnail": obj.representative_thumbnail}) <= 1:
            try:
                await gridfs().delete(obj.representative_thumbnail)
            except NoFile:
                pass

    await obj.remove()

    return '', 204

@blueprint.route("/form/<idx>/thumb.png")
@admin_required
async def generic_form_thumbnail_img(idx):
    obj = await Form.find_one({"id": bson.ObjectId(idx)})

    if obj is None:
        return {"error": "no such course"}, 404

    if obj.representative_thumbnail is None:
        return {"error": "form has no thumbnail yet"}, 404

    try:
        stream = await gridfs().open_download_stream(obj.representative_thumbnail)
    except NoFile:
        return {"error": "thumbnail not in db"}, 404

    return (await stream.read()), 200, {"Content-Type": "image/png"}

class FormUpdateLoad(ma.Schema):
    sub_fields = ma_fields.List(ma_fields.Nested(FormField.schema.as_marshmallow_schema()), required=False)
    name = ma_fields.String(required=False)
    is_default = ma_fields.Bool(required=False)

form_update_load_schema = FormUpdateLoad()


@blueprint.route("/form/<idx>", methods=["PATCH"])
@admin_required 
async def update_patch_form(idx):
    msg = await request.json
    payload = form_update_load_schema.load(msg)

    form = await Form.find_one({"id": bson.ObjectId(idx)})
    if form is None:
        return {"error": "no such form"}, 404

    if "sub_fields" in payload:
        form.sub_fields = payload["sub_fields"]

    if "name" in payload:
        form.name = payload["name"]

    if "is_default" in payload:
        form.is_default = payload["is_default"]

    await form.commit()
    return '', 204
