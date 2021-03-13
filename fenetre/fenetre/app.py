from quart import Quart, render_template, url_for, redirect, request, flash, session
from quart_auth import login_required, Unauthorized, current_user, logout_user
from datetime import timedelta

from .db import init_app as db_init_app
from .auth import init_app as auth_init_app, try_login_user, AuthenticationError, verify_signup_code, eula_required, EulaRequired
from .static import init_app as static_init_app, static_url_for
from .lockbox import init_app as lockbox_init_app
from .prefetch import resolve_preloads_for

import secrets
import os

# blueprints
from .api import blueprint as api_blueprint, init_app as api_init_app

SHOW_SIGNUP_PAGE = os.environ.get("FENETRE_SHOW_SIGNUP_PAGE", "1") == "1"

def create_app():
    app = Quart(__name__)
    app.config["QUART_AUTH_COOKIE_SECURE"] = False
    app.secret_key = secrets.token_urlsafe()
    if app.debug:
        app.secret_key = "thisisverysecret"
    else:
        app.send_file_max_age_default = timedelta(weeks=52)


    db_init_app(app)
    auth_init_app(app)
    lockbox_init_app(app)
    api_init_app(app)
    static_init_app(app)
    app.register_blueprint(api_blueprint)

    # static page routes (frontend)
    @app.route("/app", defaults={"path": ""})
    @app.route("/app/", defaults={"path": ""})
    @app.route("/app/<path:path>")
    @eula_required
    async def main(path):
        pres = await resolve_preloads_for(path)
        if "next_url" in session:
            del session["next_url"]
        return await render_template("app.html", calculated_fetches=pres)

    @app.route("/")
    async def root():
        return redirect(url_for("main"))

    @app.route("/login", methods=["GET", "POST"])
    async def login():
        if request.method == 'POST':
            form = await request.form
            try:
                await try_login_user(form['username'], form['password'], "remember_me" in form and form["remember_me"] == "on")
            except AuthenticationError as e:
                await flash(str(e), "auth-error")
            else:
                if "next_url" in session:
                    return redirect(session["next_url"])
                return redirect(url_for("main"))
        elif await current_user.is_authenticated:
            return redirect(url_for("main"))
        return await render_template("login.html", show_signup_page=SHOW_SIGNUP_PAGE)

    @app.route("/logout")
    @login_required
    async def logout():
        logout_user()
        await flash("You have been logged out")
        return redirect(url_for("login"))

    @app.errorhandler(Unauthorized)
    async def unauthorized(_):
        await flash("You are not authorized to access that page")
        if "next_url" in session and session["next_url"] == request.path:
            del session["next_url"]
        else:
            session["next_url"] = request.path
        return redirect(url_for("login"))

    @app.route("/signup", defaults={"code": None})
    @app.route("/signup/with/<code>")
    async def signup(code):
        # make sure the user isn't signed in
        if await current_user.is_authenticated:
            return redirect(url_for("main"))

        # if the code was provided, verify it
        if code is not None:
            if not await verify_signup_code(code):
                await flash("Invalid signup code in URL; please enter a fresh one")
                return redirect(url_for("signup", code=None))
            # the code is actually parsed through the react-router in the signup page

        # render the signup page
        return await render_template("signup.html")

    @app.route("/signup/eula")
    @login_required
    async def eula_confirmation():
        # if the eula is already signed don't present this page
        acct = (await current_user.user)
        if acct.signed_eula and acct.lockbox_token:
            return redirect(url_for("main"))

        # the signup page still handles eula signing
        return await render_template("signup.html")

    @app.errorhandler(EulaRequired)
    async def handle_eula(*_: EulaRequired):
        return redirect(url_for("eula_confirmation"))

    @app.route("/favicon.ico")
    async def forward_favicon():
        return redirect(static_url_for("static", filename="favicon.ico"))

    return app
