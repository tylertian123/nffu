import quart.flask_patch

from flask_static_digest import FlaskStaticDigest
from quart import Quart, render_template, url_for, redirect, request, flash
from quart_auth import login_required, Unauthorized, current_user, logout_user

from fenetre.db import init_app as db_init_app
from fenetre.auth import init_app as auth_init_app, try_login_user, AuthenticationError, verify_signup_code, eula_required, EulaRequired
from fenetre.static import setup_digest

import secrets

# blueprints
from fenetre.api import blueprint as api_blueprint

# plugins
static_digest = FlaskStaticDigest()

def create_app():
    app = Quart(__name__)
    app.config["QUART_AUTH_COOKIE_SECURE"] = False
    app.secret_key = secrets.token_urlsafe()
    if app.debug:
        app.secret_key = "thisisverysecret"

    static_digest.init_app(app)

    db_init_app(app)
    auth_init_app(app)
    app.register_blueprint(api_blueprint)

    # static page routes (frontend)
    @app.route("/app", defaults={"path": ""})
    @app.route("/app/", defaults={"path": ""})
    @app.route("/app/<path:path>")
    @eula_required
    async def main(path):
        return await render_template("app.html")

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
                return redirect(url_for("main"))
        elif await current_user.is_authenticated:
            return redirect(url_for("main"))
        return await render_template("login.html")

    @app.route("/logout")
    @login_required
    async def logout():
        logout_user()
        await flash("You have been logged out")
        return redirect(url_for("login"))

    @app.errorhandler(Unauthorized)
    async def unauthorized(_):
        await flash("You are not authorized to access that page")
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

    # setup static digest commands
    setup_digest(app)

    return app
