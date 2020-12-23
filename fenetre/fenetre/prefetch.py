from werkzeug.routing import Rule, Map, NotFound, RequestRedirect
from quart import request
from quart_auth import current_user, Unauthorized
from .db import Course, Form
import bson

_prefetchers = Map([
    Rule("/", endpoint=("me",)),
    Rule("/authcfg/users", endpoint=("userlist",)),
    Rule("/authcfg/signup_provider", endpoint=("signuplist",)),
    Rule("/lockbox/cfg", endpoint=("me", "usercourses",)),
    Rule("/lockbox/cfg/<idx>", endpoint=("me", "speccourse_withthumb")),
    # we don't do the option for setup since it shouldn't be accessed by url anyways
    Rule("/forms/form/<idx>", endpoint=("specform",)),
    Rule("/forms/form", endpoint=("formlist",)),
    Rule("/forms/course", endpoint=("courselist",)),
    Rule("/forms/course/<idx>", endpoint=("speccourse",))
], redirect_defaults=False).bind("", "/")

# preloaders
async def _me(params):
    yield ("/api/v1/me", "fetch")

async def _userlist(params):
    usr = await current_user.user
    if not usr or not usr.admin:
        raise Unauthorized()
    yield ("/api/v1/user", "fetch")

async def _signuplist(params):
    usr = await current_user.user
    if not usr or not usr.admin:
        raise Unauthorized()
    yield ("/api/v1/signup_provider", "fetch")

async def _usercourses(params):
    usr = await current_user.user
    if usr.lockbox_token:
        yield ("/api/v1/me/lockbox/courses", "fetch")

async def _speccourse_withthumb(params):
    yield ("/api/v1/course/" + params["idx"], "fetch")
    try:
        course = await Course.find_one({"id": bson.ObjectId(params["idx"])})
        if course is None:
            return
        if course.form_config:
            yield ("/api/v1/course/" + params["idx"] + "/form", "fetch")
            # we don't verify this but it's almost guaranteed
            yield ("/api/v1/course/" + params["idx"] + "/form/thumb.png", "image")
    except bson.errors.InvalidId:
        return

async def _speccourse(params):
    yield ("/api/v1/course/" + params["idx"], "fetch")

async def _specform(params):
    usr = await current_user.user
    if not usr or not usr.admin:
        raise Unauthorized()
    yield ("/api/v1/form/" + params["idx"], "fetch")
    try:
        form = await Form.find_one({"id": bson.ObjectId(params["idx"])})
        if form is None:
            return
        if form.representative_thumbnail:
            yield ("/api/v1/form/" + params["idx"] + "/thumb.png", "image")
    except bson.errors.InvalidId:
        return

async def _formlist(params):
    usr = await current_user.user
    if not usr or not usr.admin:
        raise Unauthorized()
    yield ("/api/v1/form", "fetch")

async def _courselist(params):
    usr = await current_user.user
    if not usr or not usr.admin:
        raise Unauthorized()
    yield ("/api/v1/course", "fetch")

async def resolve_preloads_for(path):
    try:
        if path in ("", "/"):
            matched_eps, params = ("me",), {}
        else:
            matched_eps, params = _prefetchers.match(path)
    except NotFound:
        return ()
    except RequestRedirect:
        return ()

    results = []
    for ep in matched_eps:
        async for pl in globals()["_" + ep](params):
            results.append(pl)
    return results
