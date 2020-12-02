import quart.flask_patch

from flask_static_digest import FlaskStaticDigest
from quart import Quart, render_template, url_for, redirect, request, flash
from quart_auth import login_required, Unauthorized, current_user, logout_user

from fenetre.db import init_app as db_init_app
from fenetre.auth import init_app as auth_init_app, try_login_user, AuthenticationError
from fenetre.static import setup_digest

import secrets

# blueprints

# plugins
static_digest = FlaskStaticDigest()

def create_app():
    app = Quart(__name__)
    app.secret_key = secrets.token_urlsafe()

    static_digest.init_app(app)

    db_init_app(app)
    auth_init_app(app)

    # static page routes (frontend)
    @app.route("/app", defaults={"path": ""})
    @app.route("/app/", defaults={"path": ""})
    @app.route("/app/<path:path>")
    @login_required
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
        return redirect(url_for("login"))

    # setup static digest commands
    setup_digest(app)

    return app
